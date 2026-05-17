from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArticleEvaluationUpdate(BaseModel):
    human_label: Optional[str] = None
    keyword_is_correct: Optional[bool] = None
    corrected_keyword: Optional[str] = None
    update_article_keyword: Optional[bool] = False

class ArticleEvaluationDTO(BaseModel):
    id: int
    article_id: int
    llm_label: Optional[str]
    human_label: Optional[str]
    keyword_is_correct: Optional[bool]
    corrected_keyword: Optional[str]
    is_verified: bool
    verified_at: Optional[datetime]

    class Config:
        from_attributes = True
