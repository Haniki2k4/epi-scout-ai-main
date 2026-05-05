from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Unicode, UnicodeText, Float, inspect, text
from sqlalchemy.orm import relationship
from datetime import datetime

from ...core.database import Base


class NewsEvent(Base):
    __tablename__ = "news_events"

    id = Column(Integer, primary_key=True, index=True)
    canonical_title = Column(Unicode(500), nullable=False)
    disease_name = Column(Unicode(255), index=True, nullable=False)
    location = Column(Unicode(255), nullable=True)
    event_date = Column(DateTime, default=datetime.utcnow, index=True)
    case_count = Column(Integer, default=0)
    severity = Column(Unicode(50), nullable=True)
    status = Column(Unicode(50), default="active")
    fingerprint = Column(String(255), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    articles = relationship("ArticleIdentity", back_populates="event")

    @property
    def article_count(self):
        return len(self.articles or [])

    @property
    def unique_sources(self):
        return sorted({article.source for article in (self.articles or []) if article.source})

    @property
    def source_count(self):
        return len(self.unique_sources)

    @property
    def sources_preview(self):
        return self.unique_sources[:5]

class ArticleIdentity(Base):
    __tablename__ = "article_identity"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Unicode(500), nullable=True) # NVARCHAR
    link = Column(String(500), unique=True, index=True) # Link is usually ASCII, but String is fine
    published_date = Column(DateTime, default=datetime.utcnow)
    event_id = Column(Integer, ForeignKey("news_events.id"), nullable=True, index=True)
    event_match_score = Column(Float, nullable=True)
    dedupe_reason = Column(Unicode(255), nullable=True)

    # Relationship 1-1 with details
    details = relationship("ArticleDetails", back_populates="identity", uselist=False, cascade="all, delete-orphan")
    
    # Relationship 1-n with disease cases
    cases = relationship("DiseaseCase", back_populates="article", cascade="all, delete-orphan")
    event = relationship("NewsEvent", back_populates="articles")

    @property
    def summary(self):
        return self.details.summary if self.details else None
        
    @property
    def source(self):
        return self.details.source if self.details else None

    @property
    def keywords_matched(self):
        return self.details.keywords_matched if self.details else None

    @property
    def is_whitelisted(self):
        return self.details.is_whitelisted if self.details else False
        
    @property
    def tags(self):
        return self.details.tags if self.details else None

class ArticleDetails(Base):
    __tablename__ = "article_details"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("article_identity.id"), unique=True)
    
    summary = Column(UnicodeText, nullable=True) # NVARCHAR(MAX)
    source = Column(Unicode(255), nullable=True) 
    keywords_matched = Column(Unicode(500), nullable=True)
    tags = Column(Unicode(500), nullable=True) # New column for tags (e.g. "Mới, Cảnh báo")
    is_whitelisted = Column(Boolean, default=False)
    
    identity = relationship("ArticleIdentity", back_populates="details")

class DiseaseCase(Base):
    __tablename__ = "disease_cases"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("article_identity.id"))
    
    disease_name = Column(Unicode(255), index=True) # e.g. "Sốt xuất huyết"
    case_count = Column(Integer, default=0)         # e.g. 5
    location = Column(Unicode(255), nullable=True)  # e.g. "Hà Nội"
    report_date = Column(DateTime, default=datetime.utcnow) # Time associated with the report
    
    article = relationship("ArticleIdentity", back_populates="cases")



class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Unicode(255), unique=True, index=True) # Support Vietnamese keywords
    is_active = Column(Boolean, default=True)             # Admin can disable keywords
    created_at = Column(DateTime, default=datetime.utcnow)


class RssSource(Base):
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(767), unique=True, index=True, nullable=False)
    label = Column(Unicode(255), nullable=True)    # Tên tờ báo / kênh
    category = Column(String(100), nullable=True)  # e.g. suc-khoe, the-gioi, global
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchedulerConfig(Base):
    """Cấu hình Auto Crawler Scheduler - chỉ có 1 bản ghi (id=1)"""
    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, default=1)
    is_enabled = Column(Boolean, default=True)            # Bật/tắt auto-scan
    interval_hours = Column(Integer, default=6)           # Chu kỳ quét (giờ)
    last_run_at = Column(DateTime, nullable=True)         # Thời điểm quét lần cuối
    next_run_at = Column(DateTime, nullable=True)         # Thời điểm quét tiếp theo
    last_run_saved_count = Column(Integer, default=0)     # Số bài lưu lần cuối
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailConfig(Base):
    """Cấu hình gửi email qua Mailtrap API - chỉ có 1 bản ghi (id=1)"""
    __tablename__ = "email_config"

    id = Column(Integer, primary_key=True, default=1)
    mailtrap_api_token = Column(String(255), nullable=True)  # Mailtrap API Token
    mailtrap_inbox_id = Column(String(50), nullable=True)    # Mailtrap Inbox ID (cho Sandbox)
    sender_email = Column(String(255), nullable=True)         # Địa chỉ gửi đi
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
