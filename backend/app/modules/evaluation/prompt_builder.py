import hashlib
import json
import os
from typing import Any

PROMPT_VERSION = os.getenv("LLM_PROMPT_VERSION", "v1.0").strip()
SCHEMA_VERSION = "stage2-v1"

SYSTEM_PROMPT = "Bạn là chuyên gia dịch tễ. Chỉ trả JSON hợp lệ, không thêm văn bản ngoài JSON."
CRITERIA = {
    "keyword": "Phân loại relevant, noise, irrelevant hoặc unsure. Relevant cần sự kiện dịch tễ thực; bài tư vấn hoặc dùng sai nghĩa là noise.",
    "context": "Phát hiện chùm ca bất thường, tín hiệu động vật/môi trường hoặc phản ứng thực địa. Không suy đoán tên bệnh.",
}
OUTPUT_SCHEMA = '{"label":"relevant|noise|irrelevant|unsure","reason":"...","matched_keywords":[],"location":null,"diseases":[]}'


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def calculate_prompt_template_hash(route: str) -> str:
    return hashlib.sha256(
        (SYSTEM_PROMPT + CRITERIA.get(route, CRITERIA["keyword"]) + OUTPUT_SCHEMA).encode("utf-8")
    ).hexdigest()


def calculate_few_shot_dataset_hash(examples: list[dict] | None) -> str | None:
    return sha256_json(examples) if examples else None


def compute_canonical_input_checksum(
    *, title: str, summary: str, keywords: list[str] | None, stage1_route: str,
    signal_type: str | None, prompt_template_hash: str | None,
    few_shot_dataset_hash: str | None, schema_version: str,
) -> str:
    return sha256_json({
        "title": title.strip(), "summary": summary.strip(),
        "keywords": sorted(keywords or []), "stage1_route": stage1_route.strip(),
        "signal_type": (signal_type or "").strip(),
        "prompt_template_hash": prompt_template_hash or "",
        "few_shot_dataset_hash": few_shot_dataset_hash or "",
        "schema_version": schema_version.strip(),
    })


def build_prompt(
    *, title: str, summary: str, keywords: list[str], route: str,
    signal_type: str | None = None, examples: list[dict] | None = None,
) -> str:
    sections = [
        CRITERIA.get(route, CRITERIA["keyword"]),
        OUTPUT_SCHEMA,
        f"Tiêu đề: {title}",
        f"Tóm tắt: {summary}",
        f"Từ khóa ứng viên: {canonical_json(keywords)}",
    ]
    if signal_type:
        sections.append(f"Loại tín hiệu ngữ cảnh: {signal_type}")
    if examples:
        sections.append(f"Ví dụ đã duyệt: {canonical_json(examples)}")
    return "\n\n".join(sections)
