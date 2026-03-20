from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- Shared Properties ---
class ArticleBase(BaseModel):
    title: str
    link: str
    summary: Optional[str] = None
    source: Optional[str] = None
    published_date: Optional[datetime] = None
    keywords_matched: Optional[str] = None
    tags: Optional[str] = None
    is_whitelisted: bool = False
    event_id: Optional[int] = None
    event_match_score: Optional[float] = None
    dedupe_reason: Optional[str] = None

# --- API Models ---
class ArticleCreate(ArticleBase):
    pass

class ArticleDTO(ArticleBase):
    id: int
    class Config:
        from_attributes = True

class WhitelistBase(BaseModel):
    domain: str
    is_active: bool = True

class WhitelistCreate(WhitelistBase):
    pass

class WhitelistDTO(WhitelistBase):
    id: int
    class Config:
        from_attributes = True

class KeywordBase(BaseModel):
    text: str

class KeywordCreate(KeywordBase):
    pass

class KeywordDTO(KeywordBase):
    id: int
    class Config:
        from_attributes = True

class ScanRequest(BaseModel):
    fetch_unknown: bool = False # If true, also returns unknown articles

class ScanResult(BaseModel):
    saved_trusted_count: int
    unknown_articles: List[ArticleBase]


class NewsEventBase(BaseModel):
    canonical_title: str
    disease_name: str
    location: Optional[str] = None
    event_date: Optional[datetime] = None
    case_count: int = 0
    severity: Optional[str] = None
    status: Optional[str] = None
    fingerprint: str


class NewsEventDTO(NewsEventBase):
    id: int
    article_count: int = 0

    class Config:
        from_attributes = True


class NewsEventDetailDTO(NewsEventBase):
    id: int
    articles: List[ArticleDTO] = []

    class Config:
        from_attributes = True
