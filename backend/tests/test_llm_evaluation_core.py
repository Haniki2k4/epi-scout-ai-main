import unittest

from app.modules.evaluation import models
from app.modules.evaluation.prompt_builder import (
    SCHEMA_VERSION, calculate_prompt_template_hash,
    compute_canonical_input_checksum,
)
from app.modules.evaluation.writer import identity_for, normalize_url


class PromptChecksumTests(unittest.TestCase):
    def checksum(self, keywords, route="keyword"):
        return compute_canonical_input_checksum(
            title="Ca bệnh tại Hà Nội", summary="Ghi nhận 3 ca.",
            keywords=keywords, stage1_route=route, signal_type=None,
            prompt_template_hash=calculate_prompt_template_hash(route),
            few_shot_dataset_hash=None, schema_version=SCHEMA_VERSION,
        )

    def test_keyword_order_is_canonical(self):
        self.assertEqual(self.checksum(["sởi", "cúm"]), self.checksum(["cúm", "sởi"]))

    def test_route_changes_checksum(self):
        self.assertNotEqual(self.checksum(["sởi"]), self.checksum(["sởi"], "context"))

    def test_url_normalization_removes_tracking(self):
        url = normalize_url("HTTPS://Example.com/news/?utm_source=x&id=2#top")
        self.assertEqual(url, "https://example.com/news?id=2")

    def test_identity_is_stable(self):
        first = identity_for("https://example.com/a?utm_source=x", "A", "B")
        second = identity_for("https://example.com/a", "A", "B")
        self.assertEqual(first[0], second[0])


class SchemaContractTests(unittest.TestCase):
    def test_attempt_uniqueness_is_per_chain(self):
        names = {constraint.name for constraint in models.LlmInferenceRun.__table__.constraints}
        self.assertIn("uq_llm_run_chain_attempt", names)

    def test_dataset_has_extraction_snapshots(self):
        columns = models.LlmDatasetVersionItem.__table__.columns
        for name in (
            "human_diseases_snapshot", "human_location_snapshot",
            "human_event_date_snapshot", "human_case_observations_snapshot",
        ):
            self.assertIn(name, columns)


if __name__ == "__main__":
    unittest.main()
