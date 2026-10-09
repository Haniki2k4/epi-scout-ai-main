from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from . import models

PREDICTIONS = ("relevant", "noise", "irrelevant", "unsure")
TRUTHS = ("relevant", "noise", "irrelevant")


def _safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


class MetricsEngine:
    def calculate(
        self, db: Session, *, model_id: str | None = None,
        prompt_version: str | None = None, benchmark_only: bool = False,
        from_date: datetime | None = None, to_date: datetime | None = None,
    ) -> dict:
        query = db.query(models.LlmInferenceRun, models.LlmEvaluationItem).join(
            models.LlmEvaluationItem,
            models.LlmInferenceRun.evaluation_item_id == models.LlmEvaluationItem.id,
        )
        if model_id:
            query = query.filter(models.LlmInferenceRun.model_id == model_id)
        if prompt_version:
            query = query.filter(models.LlmInferenceRun.prompt_version == prompt_version)
        if benchmark_only:
            query = query.filter(models.LlmInferenceRun.is_benchmark_sample.is_(True))
        if from_date:
            query = query.filter(models.LlmInferenceRun.requested_at >= from_date)
        if to_date:
            query = query.filter(models.LlmInferenceRun.requested_at <= to_date)

        rows = query.all()
        status_counts = Counter(run.inference_status for run, _ in rows)
        reviewed_by_item = {}
        for run, item in rows:
            if not (
                run.inference_status == "success"
                and run.llm_label in PREDICTIONS
                and item.human_label in TRUTHS
            ):
                continue
            source_run = db.get(models.LlmInferenceRun, item.ground_truth_source_run_id) if item.ground_truth_source_run_id else None
            if source_run is not None and source_run.input_checksum != run.input_checksum:
                continue
            previous = reviewed_by_item.get(item.id)
            if previous is None or run.requested_at > previous[0].requested_at:
                reviewed_by_item[item.id] = (run, item)
        reviewed = list(reviewed_by_item.values())
        matrix = {truth: {pred: 0.0 for pred in PREDICTIONS} for truth in TRUTHS}
        raw_matrix = {truth: {pred: 0 for pred in PREDICTIONS} for truth in TRUTHS}
        for run, item in reviewed:
            raw_matrix[item.human_label][run.llm_label] += 1
            weight = 1.0
            if benchmark_only and run.sampling_probability:
                weight = 1.0 / run.sampling_probability
            matrix[item.human_label][run.llm_label] += weight

        tp = matrix["relevant"]["relevant"]
        fp = matrix["noise"]["relevant"] + matrix["irrelevant"]["relevant"]
        fn_selective = matrix["relevant"]["noise"] + matrix["relevant"]["irrelevant"]
        fn_e2e = fn_selective + matrix["relevant"]["unsure"]
        precision = _safe_div(tp, tp + fp)
        selective_recall = _safe_div(tp, tp + fn_selective)
        end_to_end_recall = _safe_div(tp, tp + fn_e2e)
        f1 = _safe_div(2 * precision * end_to_end_recall, precision + end_to_end_recall) if precision is not None and end_to_end_recall is not None else None
        terminal = sum(status_counts.values()) - status_counts.get("pending", 0)
        success = status_counts.get("success", 0)
        decided = sum(1 for run, _ in rows if run.llm_label in {"relevant", "noise", "irrelevant"})

        extraction_counts = {
            "disease": [0, 0], "location": [0, 0],
            "event_date": [0, 0], "case_observations": [0, 0],
        }
        for run, item in reviewed:
            predicted_diseases = {
                str(value.get("disease_name", "")).strip().lower()
                for value in (run.predicted_diseases or []) if isinstance(value, dict)
            }
            human_diseases = {str(value).strip().lower() for value in (item.human_diseases or [])}
            if human_diseases:
                extraction_counts["disease"][1] += 1
                extraction_counts["disease"][0] += int(predicted_diseases == human_diseases)
            if item.human_location:
                extraction_counts["location"][1] += 1
                extraction_counts["location"][0] += int(
                    (run.predicted_location or "").strip().lower() == item.human_location.strip().lower()
                )
            if item.human_event_date:
                extraction_counts["event_date"][1] += 1
                extraction_counts["event_date"][0] += int(
                    run.predicted_event_date is not None
                    and run.predicted_event_date.date() == item.human_event_date.date()
                )
            if item.human_case_observations:
                extraction_counts["case_observations"][1] += 1
                extraction_counts["case_observations"][0] += int(
                    run.predicted_case_observations == item.human_case_observations
                )
        extraction = {
            key: {"correct": value[0], "total": value[1], "accuracy": _safe_div(value[0], value[1])}
            for key, value in extraction_counts.items()
        }

        latencies = sorted(run.latency_ms for run, _ in rows if run.latency_ms is not None)
        percentile = lambda p: latencies[min(int((len(latencies) - 1) * p), len(latencies) - 1)] if latencies else None
        return {
            "reviewed_count": len(reviewed),
            "confusion_matrix": raw_matrix,
            "weighted_confusion_matrix": matrix if benchmark_only else None,
            "precision": precision, "selective_recall": selective_recall,
            "end_to_end_recall": end_to_end_recall, "f1": f1,
            "coverage": _safe_div(decided, success),
            "abstention_rate": _safe_div(sum(1 for run, _ in rows if run.llm_label == "unsure"), success),
            "extraction": extraction,
            "provider": {
                "total": len(rows), "status_counts": dict(status_counts),
                "success_rate": _safe_div(success, terminal),
                "fallback_count": sum(1 for run, _ in rows if run.fallback_from_run_id is not None),
                "fallback_rate": _safe_div(
                    sum(1 for run, _ in rows if run.fallback_from_run_id is not None), terminal
                ),
                "latency_p50_ms": percentile(0.5), "latency_p95_ms": percentile(0.95),
            },
        }
