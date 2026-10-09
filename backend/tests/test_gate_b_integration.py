"""Gate B integration tests use an isolated SQLite database, never the crawler DB."""
import os
os.environ["DATABASE_URL"] = "mysql+pymysql://root@127.0.0.1:1/unused"  # Import-time engine is never connected.

from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.modules.auth.models import User
from backend.app.modules.evaluation.models import ArticleEvaluation
from backend.app.modules.evaluation.crud import update_human_label
from backend.app.modules.news import models
from backend.app.modules.news import router_context_signals as api
from backend.app.modules.news import router_quality as quality
from backend.app.modules.news import crawler


class GateBIntegrationTests(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.analyst = User(username="analyst", hashed_password="x", role="analyst", is_active=True)
        self.db.add(self.analyst)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def article(self, route="context"):
        article = models.ArticleIdentity(
            title="Chùm ca bất thường tại Hà Nội",
            link=f"https://example.org/{uuid4()}",
            published_date=datetime.utcnow(),
            is_excluded=True,
        )
        self.db.add(article)
        self.db.flush()
        self.db.add(models.ArticleDetails(
            article_id=article.id, summary="Nhiều người nhập viện",
            source="example.org", keywords_matched="",
            stage1_route=route, context_signal_type="unexplained_cluster",
            context_matched_phrases='["chùm ca"]',
            context_evidence_text="Chùm ca bất thường tại Hà Nội",
            review_version=0,
        ))
        self.db.add(ArticleEvaluation(article_id=article.id, llm_label="relevant"))
        self.db.commit()
        return article

    def body(self, decision="dismissed", version=0, request_id=None, **kwargs):
        values = dict(
            request_id=request_id or uuid4(),
            expected_review_version=version,
            decision=decision,
            reason="Đã kiểm tra bài gốc",
        )
        values.update(kwargs)
        return api.ContextReviewRequest(**values)

    def review(self, article, body):
        return api.review_context_signal(article.id, body, self.db, self.analyst)

    def test_resolver_accepts_confirmed_disease_without_keyword(self):
        event, _, _, _ = crawler.resolve_event_for_article(
            db=self.db, title="Chùm ca tại Hà Nội", normalized_title="Chùm ca tại Hà Nội",
            summary="CDC xác nhận", matched_keywords="", pub_date=datetime.utcnow(),
            location="Hà Nội", cumulative_cases=0, new_cases=0, severity=None,
            override_disease_name="Sởi",
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.disease_name, "Sởi")

    def test_pending_queue_only_contains_hidden_unreviewed_context(self):
        context = self.article()
        self.article(route="keyword")
        rows = api.list_context_signals("pending", 50, self.db, self.analyst)
        self.assertEqual([row["article_id"] for row in rows], [context.id])
        self.assertTrue(self.db.get(models.ArticleIdentity, context.id).is_excluded)

    def test_dismissed_stays_hidden_without_event(self):
        article = self.article()
        self.review(article, self.body())
        self.db.refresh(article)
        self.assertTrue(article.is_excluded)
        self.assertIsNone(article.event_id)
        self.assertEqual(self.db.query(ArticleEvaluation).filter_by(article_id=article.id).one().human_label, "irrelevant")

    def test_monitoring_stays_hidden_and_in_monitoring_queue(self):
        article = self.article()
        self.review(article, self.body("monitoring_unknown", signal_evidence="Đang điều tra"))
        rows = api.list_context_signals("monitoring", 50, self.db, self.analyst)
        self.assertEqual([row["article_id"] for row in rows], [article.id])
        self.assertTrue(self.db.get(models.ArticleIdentity, article.id).is_excluded)

    def test_disease_decision_publishes_in_one_transaction(self):
        article = self.article()
        def fake_resolve(**kwargs):
            event = models.NewsEvent(
                canonical_title=kwargs["title"], disease_name=kwargs["override_disease_name"],
                event_date=datetime.utcnow(), fingerprint=str(uuid4()),
            )
            kwargs["db"].add(event)
            kwargs["db"].flush()
            return event, 0.9, "confirmed_by_analyst", 0
        with patch.object(api, "resolve_event_for_article", side_effect=fake_resolve):
            review = self.review(article, self.body(
                "disease_identified", signal_evidence="Báo cáo CDC",
                disease_name="Sởi", disease_source="CDC Hà Nội",
            ))
        self.db.refresh(article)
        self.assertFalse(article.is_excluded)
        self.assertEqual(article.event_id, review["event_id"])
        self.assertEqual(self.db.query(ArticleEvaluation).filter_by(article_id=article.id).one().human_label, "relevant")

    def _fake_event(self, kwargs):
        event = models.NewsEvent(canonical_title=kwargs["title"], disease_name=kwargs["override_disease_name"], event_date=datetime.utcnow(), fingerprint=str(uuid4()))
        kwargs["db"].add(event)
        kwargs["db"].flush()
        return event, 0.9, "matched", 0

    def test_monitoring_can_upgrade_to_disease(self):
        article = self.article()
        self.review(article, self.body("monitoring_unknown", signal_evidence="Chùm ca"))
        with patch.object(api, "resolve_event_for_article", side_effect=lambda **kwargs: self._fake_event(kwargs)):
            self.review(article, self.body(
                "disease_identified", version=1, signal_evidence="CDC xác nhận",
                disease_name="Tả", disease_source="CDC",
            ))
        reviews = self.db.query(models.ContextSignalReview).filter_by(article_id=article.id).order_by(models.ContextSignalReview.version).all()
        self.assertEqual([row.is_superseded for row in reviews], [True, False])
        self.assertEqual(reviews[-1].version, 2)

    def test_same_request_id_and_payload_is_idempotent(self):
        article = self.article()
        body = self.body()
        first = self.review(article, body)
        second = self.review(article, body)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.db.query(models.ContextSignalReview).count(), 1)

    def test_request_id_reuse_with_different_payload_conflicts(self):
        article = self.article()
        request_id = uuid4()
        self.review(article, self.body(request_id=request_id))
        with self.assertRaises(HTTPException) as result:
            self.review(article, self.body(request_id=request_id, reason="Lý do khác"))
        self.assertEqual(result.exception.status_code, 409)

    def test_request_id_reuse_for_another_article_conflicts(self):
        first = self.article()
        second = self.article()
        request_id = uuid4()
        self.review(first, self.body(request_id=request_id))
        with self.assertRaises(HTTPException) as result:
            self.review(second, self.body(request_id=request_id))
        self.assertEqual(result.exception.status_code, 409)

    def test_stale_review_version_conflicts(self):
        article = self.article()
        self.review(article, self.body("monitoring_unknown", signal_evidence="Chùm ca"))
        with self.assertRaises(HTTPException) as result:
            self.review(article, self.body("dismissed", version=0))
        self.assertEqual(result.exception.status_code, 409)

    def test_final_decision_cannot_be_reopened(self):
        article = self.article()
        self.review(article, self.body())
        with self.assertRaises(HTTPException) as result:
            self.review(article, self.body("monitoring_unknown", version=1, signal_evidence="Mới"))
        self.assertEqual(result.exception.status_code, 422)

    def test_generic_relevant_label_cannot_publish_context_article(self):
        article = self.article()
        with self.assertRaises(ValueError):
            update_human_label(self.db, article.id, "relevant", self.analyst.id)
        self.db.refresh(article)
        self.assertTrue(article.is_excluded)
        self.assertIsNone(article.event_id)

    def test_quality_rejects_conflicting_gate_b_labels(self):
        sample = models.RssEntrySample(
            link="https://example.org/sample", title="Chùm ca", summary="",
            sampled_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=1),
            passed_stage1=False, stage1_route="context", gate_b_evaluated=True,
            detector_matched=True,
        )
        self.db.add(sample)
        self.db.commit()
        with self.assertRaises(HTTPException) as result:
            quality.label_sample(sample.id, quality.SampleLabel(human_relevant=False, human_signal_label="early_signal"), self.db, self.analyst)
        self.assertEqual(result.exception.status_code, 422)

    def test_scan_cannot_complete_with_missing_feed_rows(self):
        with patch("backend.app.core.database.SessionLocal", self.session_factory):
            crawler._create_scan_run("test-scan")
            with self.assertRaises(RuntimeError):
                crawler._finalize_scan_run("test-scan", "completed", 1)
        scan = self.db.get(models.ScanRun, "test-scan")
        self.assertEqual(scan.status, "running")
        self.assertIsNone(scan.completed_at)

    def test_shadow_and_active_samples_for_same_url_are_separate(self):
        with patch("backend.app.core.database.SessionLocal", self.session_factory):
            crawler._create_scan_run("sample-scan")
            for mode in ("shadow", "active"):
                sample = dict(
                    link="https://example.org/signal", title="Chùm ca",
                    sampled_at=datetime.utcnow(), expires_at=datetime.utcnow() + timedelta(days=1),
                    passed_stage1=mode == "active", stage1_route="context",
                    gate_b_mode=mode, gate_b_evaluated=True, detector_matched=True, detector_version=crawler.DETECTOR_VERSION,
                )
                crawler._persist_crawl_run(
                    "https://example.org/feed", None, datetime.utcnow(), 1, 0, 0, 0, None,
                    [sample], "sample-scan", 1,
                    {"unexplained_cluster": 1, "animal_signal": 0, "environment_signal": 0, "field_response": 0},
                    int(mode == "active"),
                )
        self.assertEqual(self.db.query(models.RssEntrySample).count(), 2)

