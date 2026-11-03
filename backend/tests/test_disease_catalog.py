"""Preservation, cause-specific analytics and union totals against isolated SQLite."""
import os
os.environ.setdefault("DATABASE_URL", "mysql+pymysql://root@127.0.0.1:1/unused")

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.modules.auth.models import User  # Register FK target.
from backend.app.modules.news import crud, models, stats
from backend.app.modules.news.disease_catalog import (
    ADDITIONAL_KEYWORDS, LEGACY_KEYWORDS, canonical_disease, disease_names,
    matches_disease_filter, normalize_disease_entries,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def article(db, keywords, cases=(), excluded=False):
    row = models.ArticleIdentity(title="Tín hiệu dịch tễ", link=f"https://example.org/{uuid4()}",
                                 published_date=datetime.utcnow(), is_excluded=excluded)
    row.details = models.ArticleDetails(keywords_matched=keywords)
    row.cases = [models.DiseaseCase(disease_name=name, reported_value=10) for name in cases]
    db.add(row)
    db.commit()
    return row


def test_seed_is_additive_idempotent_and_keeps_disabled_keywords(db):
    old = [models.Keyword(text="virus", is_active=True), models.Keyword(text="sốt", is_active=False),
           models.Keyword(text="WhItMoRe", is_active=False), models.Keyword(text="từ khóa riêng", is_active=True)]
    db.add_all(old)
    db.commit()
    snapshot = [(r.id, r.text, r.is_active, r.created_at) for r in old]
    crud.seed_default_keywords(db)
    first_count = db.query(models.Keyword).count()
    crud.seed_default_keywords(db)
    assert db.query(models.Keyword).count() == first_count
    assert [(r.id, r.text, r.is_active, r.created_at) for r in old] == snapshot
    names = {canonical_disease(r.text) for r in db.query(models.Keyword).all()}
    assert {canonical_disease(k) for k in ADDITIONAL_KEYWORDS + LEGACY_KEYWORDS} <= names
    assert len([r for r in db.query(models.Keyword).all() if canonical_disease(r.text) == "whitmore"]) == 1


def test_aliases_collapse_but_flu_subtypes_stay_separate():
    assert disease_names(["Whitmore", "melioidosis", "Burkholderia pseudomallei"]) == {"whitmore"}
    assert disease_names(["virus", "cúm", "cúm A", "H5N1", "H9N2"]) == {"cúm a/h5n1", "cúm a/h9n2"}
    assert canonical_disease("vi khuẩn ăn thịt người") != "whitmore"
    assert canonical_disease("Rickettsia") != canonical_disease("sốt mò")


def test_unresolved_broad_signals_are_retained_without_inventing_causes():
    assert disease_names(["virus", "sốt"]) == {"virus chưa xác định", "sốt chưa rõ nguyên nhân"}
    assert disease_names(["virus", "sốt", "sốt xuất huyết"]) == {"sốt xuất huyết"}
    assert disease_names(["sốt", "sốt rét"]) == {"sốt rét"}
    assert disease_names(["sốt", "sốt siêu vi", "virus"]) == {"sốt do virus chưa xác định"}
    assert disease_names(["virus chưa xác định", "Ebola"]) == {"virus chưa xác định", "ebola"}
    assert disease_names(["sốt chưa rõ nguyên nhân", "sốt rét"]) == {"sốt chưa rõ nguyên nhân", "sốt rét"}
    assert matches_disease_filter({"ebola"}, "virus")
    assert not matches_disease_filter({"bệnh than"}, "virus")
    assert not matches_disease_filter({"virus chưa xác định"}, "Ebola")


def test_statistics_use_detail_and_count_one_article_once(db):
    old = article(db, "virus, sốt, dengue, sốt xuất huyết", ["sốt xuất huyết", "sốt xuất huyết"])
    article(db, "virus, sốt, cúm, H5N1, cúm A/H9N2")
    article(db, "virus, sốt")
    article(db, "Whitmore, melioidosis")
    article(db, "Ebola", excluded=True)
    counts = {r["disease_name"]: r["article_count"] for r in stats.disease_mention_counts(db)}
    assert counts["sốt xuất huyết"] == 1
    assert counts["cúm a/h5n1"] == counts["cúm a/h9n2"] == 1
    assert counts["virus chưa xác định"] == 1
    assert counts["whitmore"] == 1
    assert "ebola" not in counts
    group = stats.get_disease_breakdown(db, "virus")
    assert group["total_articles"] == 3
    assert sum(d["article_count"] for d in group["diseases"]) == 4
    assert stats.get_zscore_spikes(db, "virus", days=3, window=2)[-1]["count"] == 3
    assert stats.get_zscore_spikes(db, "H5N1", days=3, window=2)[-1]["count"] == 1
    assert stats.get_zscore_spikes(db, "Ebola", days=3, window=2)[-1]["count"] == 0
    assert stats.get_zscore_spikes(db, days=3, window=2)[-1]["date"] == datetime.utcnow().strftime("%Y-%m-%d")
    assert stats.get_prophet_forecast(db, "virus")["historical"][-1]["y"] == 3
    assert "dengue" not in {r["disease"] for r in stats.get_heatmap_data(db)}
    assert "virus" not in stats.get_interest_trends(db)["diseases"]
    assert old.details.keywords_matched == "virus, sốt, dengue, sốt xuất huyết"
    assert [c.reported_value for c in old.cases] == [10, 10]


def test_legacy_generic_keyword_can_use_existing_source_disease_without_rewrite(db):
    old = article(db, "virus", ["Ebola", "Ebola"])
    assert stats.disease_mention_counts(db) == [{"disease_name": "ebola", "article_count": 1}]
    assert old.details.keywords_matched == "virus"
    assert old.cases[0].disease_name == "Ebola"


def test_disease_catalog_shows_all_active_canonical_names(db):
    db.add_all([models.Keyword(text="H5N1", is_active=True),
                models.Keyword(text="cúm A/H5N1", is_active=True)])
    db.commit()
    names = [r["disease_name"] for r in stats.get_disease_catalog(db)]
    assert names.count("cúm a/h5n1") == 1
    assert "virus chưa xác định" in names


def test_event_lookup_matches_legacy_alias_without_changing_it(db):
    event = models.NewsEvent(canonical_title="Ổ dịch Whitmore", disease_name="Melioidosis",
                             location="Hà Nội", event_date=datetime.utcnow(), fingerprint="old")
    db.add(event)
    db.commit()
    found = crud.get_recent_events(db, "whitmore", "Hà Nội", datetime.utcnow()-timedelta(days=1),
                                   datetime.utcnow()+timedelta(days=1))
    assert found == [event]
    assert event.disease_name == "Melioidosis"


def test_llm_names_are_validated_and_alias_duplicates_do_not_duplicate_numbers():
    entries = [{"disease_name": "melioidosis", "new_cases": 3},
               {"disease_name": "Whitmore", "new_cases": 3},
               {"disease_name": "Ebola", "new_cases": 99}, {"new_cases": 4}]
    assert normalize_disease_entries(entries, ["Whitmore"]) == [{"disease_name": "whitmore", "new_cases": 3}]


def test_stage1_accepts_scientific_alias_and_keeps_advice_filter(monkeypatch):
    from backend.app.modules.news import crawler
    monkeypatch.setattr(crawler, "LLM_RECHECK_ENABLED", True)
    assert crawler.matches_keywords("Hà Nội ghi nhận 3 ca mắc melioidosis, một ca tử vong",
                                    "Ổ dịch đang được điều tra", ["Whitmore"]) == "Whitmore"
    assert crawler.matches_keywords("Bệnh Whitmore là gì?", "Bác sĩ tư vấn cách phòng bệnh", ["Whitmore"]) is None


def test_llm_pipeline_accepts_alias_and_rejects_unlisted_cause(monkeypatch):
    from backend.app.modules.news import crawler
    monkeypatch.setattr(crawler, "LLM_RECHECK_ENABLED", True)
    monkeypatch.setattr(crawler, "get_llm_preflight_status", lambda: {"ok": True})
    monkeypatch.setattr(crawler, "_get_llm_cooldown_status", lambda: (False, ""))
    monkeypatch.setattr(crawler, "_llm_session_is_fallback", False)
    monkeypatch.setattr(crawler, "_llm_circuit_state", "CLOSED")
    monkeypatch.setattr(crawler, "_call_llm_api", lambda *args: {
        "label": "relevant", "matched_keywords": ["melioidosis"], "reason": "3 ca được nguồn nêu rõ",
        "diseases": [{"disease_name": "melioidosis", "new_cases": 3},
                     {"disease_name": "Ebola", "new_cases": 99}],
    })
    label, matched, reason, meta = crawler.llm_recheck_article(
        "3 ca Whitmore", "Các ca đang được điều trị", ["Whitmore"])
    assert label == "relevant" and matched == ["Whitmore"]
    assert meta["diseases"] == [{"disease_name": "whitmore", "new_cases": 3}]
    assert reason == "3 ca được nguồn nêu rõ"


def test_breakdown_api_validates_category_and_range(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.core.database import get_db
    from backend.app.modules.news.router_stats import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    # Empty database: validation-only requests never access the SQLite session.
    with TestClient(app) as client:
        assert client.get("/api/stats/disease-breakdown?category=unknown").status_code == 422
        assert client.get("/api/stats/disease-breakdown?days=0").status_code == 422


def keyword_client(db, admin=True):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.core.database import get_db
    from backend.app.modules.auth.security import require_admin_role
    from backend.app.modules.news.router_resources import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    if admin:
        app.dependency_overrides[require_admin_role] = lambda: User(username="admin", role="admin")
    return TestClient(app)


def test_product_import_does_not_reenable_disabled_alias(db):
    old = models.Keyword(text="Whitmore", is_active=False)
    db.add(old)
    db.commit()
    with keyword_client(db) as client:
        suggestions = client.get("/api/keywords/suggestions").json()
        assert all(item["canonical_name"] != "whitmore" for item in suggestions)
        response = client.post("/api/keywords/import-suggestions", json={"keywords": ["melioidosis", "Marburg"]})
        assert response.status_code == 200
        assert response.json()["added_count"] == 1
        assert response.json()["skipped_count"] == 1
        again = client.post("/api/keywords/import-suggestions", json={"keywords": ["Marburg"]})
        assert again.json()["added_count"] == 0
    db.refresh(old)
    assert old.text == "Whitmore" and old.is_active is False


def test_product_add_edit_toggle_remove_preserves_article_history(db):
    stored = article(db, "tác nhân thử nghiệm", ["tác nhân thử nghiệm"])
    with keyword_client(db) as client:
        created = client.post("/api/keywords", json={"text": "tác nhân thử nghiệm, virus thử nghiệm"})
        assert created.status_code == 200
        first, second = created.json()
        assert client.put(f'/api/keywords/{first["id"]}', json={"text": second["text"]}).status_code == 409
        renamed = client.put(f'/api/keywords/{first["id"]}', json={"text": "tác nhân thử nghiệm mới"})
        assert renamed.json()["text"] == "tác nhân thử nghiệm mới"
        toggled = client.patch(f'/api/keywords/{first["id"]}/toggle', json={"is_active": False})
        assert toggled.json()["is_active"] is False
        assert client.delete(f'/api/keywords/{first["id"]}').status_code == 200
        assert client.delete(f'/api/keywords/{first["id"]}').status_code == 404
    db.refresh(stored)
    assert stored.details.keywords_matched == "tác nhân thử nghiệm"
    assert stored.cases[0].disease_name == "tác nhân thử nghiệm"


def test_keyword_changes_require_admin_and_reject_invalid_imports(db):
    with keyword_client(db, admin=False) as client:
        assert client.get("/api/keywords/suggestions").status_code == 401
        assert client.post("/api/keywords/import-suggestions", json={"keywords": ["Marburg"]}).status_code == 401
        assert client.post("/api/keywords", json={"text": "Marburg"}).status_code == 401
    with keyword_client(db) as client:
        assert client.post("/api/keywords/import-suggestions", json={"keywords": []}).status_code == 422
        assert client.post("/api/keywords/import-suggestions", json={"keywords": ["not approved"]}).status_code == 400
        assert client.post("/api/keywords", json={"text": "a" * 256}).status_code == 400
