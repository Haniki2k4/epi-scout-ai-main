from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArticleEvaluationUpdate(BaseModel):
    human_label: str

class ArticleEvaluationDTO(BaseModel):
    id: int
    article_id: int
    llm_label: Optional[str]
    human_label: Optional[str]
    is_verified: bool
    verified_at: Optional[datetime]

    class Config:
        from_attributes = True
