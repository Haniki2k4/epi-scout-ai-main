"""Keep reader advice out of events without suppressing independent outbreak reports."""
import os

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://root@127.0.0.1:1/unused")

import pytest

from backend.app.modules.news import crawler
from backend.app.modules.news.stage1_context import is_advisory_without_outbreak_evidence


QUESTION = "Canh giá đỗ, huyết heo có giúp nhanh khỏi cúm?"
SUMMARY = (
    "Tôi mắc cúm A, vợ khuyên mua giá đỗ và huyết heo nấu canh để bệnh nhanh khỏi. "
    "Cách này có hiệu quả không? (Huy Minh, 45 tuổi, Thanh Hóa)"
)


@pytest.mark.parametrize("title", [QUESTION, QUESTION.rstrip("?"), "Nấu canh gì khi mắc cúm A"])
def test_reader_advice_is_rejected_without_counting_age_or_address(title):
    assert is_advisory_without_outbreak_evidence(title, SUMMARY)
    assert crawler.matches_keywords(title, SUMMARY, ["cúm A"]) is None


@pytest.mark.parametrize("is_context", [False, True])
def test_rechecks_and_gate_b_skip_llm_for_reader_advice(monkeypatch, is_context):
    def forbidden(*args):
        pytest.fail("Reader advice must be rejected before calling the provider")
    monkeypatch.setattr(crawler, "_call_llm_api", forbidden)
    label, keywords, _, meta = crawler.llm_recheck_article(
        QUESTION, SUMMARY, [] if is_context else ["cúm A"], is_context=is_context,
    )
    assert label == "noise" and keywords == []
    assert meta["diseases"] == [] and meta["location"] == "unknown"
    assert meta["new_cases"] == meta["cumulative_cases"] == 0


@pytest.mark.parametrize("title", ["Thanh Hóa ghi nhận thêm 15 ca mắc cúm A phải nhập viện", QUESTION])
def test_independent_cdc_cluster_evidence_is_kept(title):
    summary = "CDC tỉnh Thanh Hóa báo cáo chùm ca gồm 15 ca mắc cúm A tại trường mầm non."
    assert not is_advisory_without_outbreak_evidence(title, summary)
    assert crawler.matches_keywords(title, summary, ["cúm A"]) == "cúm A"


@pytest.mark.parametrize("label", ["noise", "irrelevant"])
def test_rejected_llm_labels_cannot_leak_case_data(monkeypatch, label):
    monkeypatch.setattr(crawler, "LLM_RECHECK_ENABLED", True)
    monkeypatch.setattr(crawler, "get_llm_preflight_status", lambda: {"ok": True})
    monkeypatch.setattr(crawler, "_get_llm_cooldown_status", lambda: (False, ""))
    monkeypatch.setattr(crawler, "_llm_session_is_fallback", False)
    monkeypatch.setattr(crawler, "_llm_circuit_state", "CLOSED")
    monkeypatch.setattr(crawler, "_call_llm_api", lambda *args: {
        "label": label, "matched_keywords": ["cúm A"], "location": "Thanh Hóa",
        "normalized_title": "Một ca cúm", "new_cases": 1, "severity": "medium",
        "diseases": [{"disease_name": "cúm A", "new_cases": 1}],
        "event_start_date": "2026-11-03",
    })
    actual, keywords, _, meta = crawler.llm_recheck_article("Dinh dưỡng khi mắc cúm A", "Bác sĩ tư vấn", ["cúm A"])
    assert actual == label and keywords == []
    assert meta["diseases"] == [] and meta["location"] == "unknown"
    assert meta["normalized_title"] == "" and meta["severity"] is None
    assert meta["new_cases"] == meta["cumulative_cases"] == 0
    assert meta["event_start_date"] is None
