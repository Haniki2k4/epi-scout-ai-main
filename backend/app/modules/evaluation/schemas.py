from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


HumanLabel = Literal["relevant", "noise", "irrelevant", "unsure"]
SignalLabel = Literal["confirmed_event", "early_signal"]


class ArticleEvaluationUpdate(BaseModel):
    human_label: str | None = None
    keyword_is_correct: bool | None = None
    corrected_keyword: str | None = None
    update_article_keyword: bool = False


class ArticleEvaluationDTO(BaseModel):
    id: int
    article_id: int
    llm_label: str | None
    human_label: str | None
    keyword_is_correct: bool | None
    corrected_keyword: str | None
    is_verified: bool
    verified_at: datetime | None

    model_config = {"from_attributes": True}


class LabelingPayload(BaseModel):
    expected_revision: int = Field(ge=0)
    reviewed_inference_run_id: int | None = None
    human_label: HumanLabel
    human_signal_label: SignalLabel | None = None
    human_diseases: list[str] = Field(default_factory=list)
    human_location: str | None = Field(default=None, max_length=255)
    human_event_date: datetime | None = None
    human_case_observations: list[dict[str, Any]] = Field(default_factory=list)
    eligible_for_training: bool = False
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_labels(self):
        if self.human_label != "relevant" and self.human_signal_label is not None:
            raise ValueError("human_signal_label chỉ hợp lệ khi human_label là relevant")
        if self.human_label == "unsure" and self.eligible_for_training:
            raise ValueError("Nhãn unsure không được dùng cho training")
        return self


class RetryPayload(BaseModel):
    model_id: str | None = Field(default=None, max_length=150)
    prompt_version: str | None = Field(default=None, max_length=50)


class DatasetCreatePayload(BaseModel):
    version_tag: str = Field(min_length=1, max_length=50)
    split_strategy: Literal["temporal_grouped", "grouped_stratified_fallback"] = "temporal_grouped"
    notes: str | None = None
    split_seed: int = 42


class ItemDTO(BaseModel):
    id: int
    canonical_url: str | None
    title_snapshot: str
    summary_snapshot: str
    source_domain: str | None
    published_date: datetime | None
    human_label: str | None
    human_signal_label: str | None
    human_diseases: list[str] | None
    human_location: str | None
    human_event_date: datetime | None
    human_case_observations: list[dict[str, Any]] | None
    review_status: str
    eligible_for_training: bool
    label_revision: int
    current_inference_run_id: int | None
    current_run: dict[str, Any] | None = None

    model_config = {"from_attributes": True}
