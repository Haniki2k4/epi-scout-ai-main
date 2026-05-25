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
    llm_normalized_title: Optional[str] = None
    is_whitelisted: bool = False
    outbreak_relevance_score: float = 0.0
    is_suspected_false_positive: bool = False
    event_id: Optional[int] = None
    event_match_score: Optional[float] = None
    dedupe_reason: Optional[str] = None

# --- API Models ---
class ArticleCreate(ArticleBase):
    pass

class ArticleDTO(ArticleBase):
    id: int
    cases: List["DiseaseCaseDTO"] = []
    llm_label: Optional[str] = None
    human_label: Optional[str] = None
    class Config:
        from_attributes = True

class PaginatedArticles(BaseModel):
    items: List[ArticleDTO]
    total: int
    skip: int
    limit: int

class DiseaseCaseDTO(BaseModel):
    disease_name: str
    case_count: int
    location: Optional[str] = None
    class Config:
        from_attributes = True

# Update forward references if needed, but strings work fine in Pydantic v2
class KeywordBase(BaseModel):
    text: str
    is_active: bool = True

class KeywordCreate(KeywordBase):
    pass

class KeywordDTO(KeywordBase):
    id: int
    class Config:
        from_attributes = True

class ScanRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    keywords_to_scan: Optional[List[str]] = None  # None = dùng hết từ DB, [] = quét hết, ["x","y"] = lọc

class ScanResult(BaseModel):
    saved_trusted_count: int
    execution_time: Optional[float] = None
    disease_counts: Optional[dict] = None  # {"sốt xuất huyết": 3, "tay chân miệng": 1}
    total_checked: int = 0                 # Tổng số bài đã xử lý
    noise_count: int = 0                   # Số bài LLM gắn nhãn noise
    irrelevant_count: int = 0              # Số bài LLM gắn nhãn irrelevant
    unsure_count: int = 0                  # Số bài LLM gắn nhãn unsure
    started_at: Optional[datetime] = None  # Thời điểm bắt đầu quét


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
    source_count: int = 0
    sources_preview: List[str] = []

    class Config:
        from_attributes = True


class NewsEventDetailDTO(NewsEventBase):
    id: int
    article_count: int = 0
    source_count: int = 0
    sources_preview: List[str] = []
    articles: List[ArticleDTO] = []

    class Config:
        from_attributes = True


class RssSourceCreate(BaseModel):
    url: str
    label: Optional[str] = None
    category: Optional[str] = None
    source_type: Optional[str] = "DOMESTIC"
    is_active: bool = True

class RssSourceDTO(RssSourceCreate):
    id: int
    class Config:
        from_attributes = True

class RssSourceToggleRequest(BaseModel):
    is_active: bool

class RssSourceUpdate(BaseModel):
    url: Optional[str] = None
    label: Optional[str] = None
    category: Optional[str] = None
    source_type: Optional[str] = None
    is_active: Optional[bool] = None
