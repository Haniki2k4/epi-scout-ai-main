"""Quality labels store and score multiple diseases in an isolated SQLite database."""
import os
os.environ["DATABASE_URL"] = "mysql+pymysql://root@127.0.0.1:1/unused"

from datetime import datetime, timedelta
from unittest import TestCase

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.modules.auth.models import User
from backend.app.modules.news import models
from backend.app.modules.news.router_quality import SampleLabel, get_quality_metrics, label_sample, list_samples


class MultipleDiseaseQualityTests(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin = User(username="quality_admin", hashed_password="x", role="admin", is_active=True)
        self.db.add(self.admin)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def sample(self, predicted="Sởi, Thủy đậu"):
        now = datetime.utcnow()
        row = models.RssEntrySample(
            link=f"https://example.org/sample-{now.timestamp()}",
            title="Hai bệnh tại địa phương",
            sampled_at=now, expires_at=now + timedelta(days=7),
            passed_stage1=True, stage1_route="keyword",
            predicted_disease=predicted, predicted_case_values="[]",
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_store_list_and_score_exact_set(self):
        row = self.sample()
        body = SampleLabel(human_relevant=True, human_diseases=[" Sởi ", "Thủy đậu", "sởi"])
        label_sample(row.id, body, self.db, self.admin)
        self.db.refresh(row)
        self.assertEqual(row.human_diseases, ["Sởi", "Thủy đậu"])
        self.assertIsNone(row.human_disease)
        listed = list_samples(False, 50, self.db, self.admin)
        self.assertEqual(listed[0]["human_diseases"], ["Sởi", "Thủy đậu"])
        disease_metric = get_quality_metrics(30, self.db, self.admin)["field_accuracy"]["disease"]
        self.assertEqual(disease_metric["correct"], 1)
        self.assertEqual(disease_metric["labeled_count"], 1)

    def test_extra_prediction_is_incorrect(self):
        row = self.sample("Sởi, Thủy đậu, Cúm A")
        label_sample(row.id, SampleLabel(human_relevant=True, human_diseases=["Sởi", "Thủy đậu"]), self.db, self.admin)
        disease_metric = get_quality_metrics(30, self.db, self.admin)["field_accuracy"]["disease"]
        self.assertEqual(disease_metric["correct"], 0)

    def test_legacy_single_disease_is_read_as_list(self):
        row = self.sample("Sởi")
        row.human_disease = "Sởi"
        row.human_relevant = True
        self.db.commit()
        listed = list_samples(False, 50, self.db, self.admin)
        self.assertEqual(listed[0]["human_diseases"], ["Sởi"])
        self.assertEqual(get_quality_metrics(30, self.db, self.admin)["field_accuracy"]["disease"]["correct"], 1)

    def test_reject_empty_disease_name(self):
        with self.assertRaises(ValidationError):
            SampleLabel(human_relevant=True, human_diseases=[" "])

