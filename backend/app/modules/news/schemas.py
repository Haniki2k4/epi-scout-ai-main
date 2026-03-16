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
