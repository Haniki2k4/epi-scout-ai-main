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
    def valid_articles(self):
        from sqlalchemy.orm.session import object_session
        from ..evaluation.models import ArticleEvaluation
        
        session = object_session(self)
        if not session or not self.articles:
            return [a for a in (self.articles or []) if not getattr(a, "is_excluded", False)]
            
        article_ids = [a.id for a in self.articles]
        evals = session.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
        eval_map = {e.article_id: e for e in evals}
        
        valid = []
        for a in self.articles:
            if getattr(a, "is_excluded", False):
                continue
            e = eval_map.get(a.id)
            label = e.human_label if (e and e.human_label) else (e.llm_label if e else None)
            if label in ["noise", "irrelevant", "unsure"]:
                continue
            valid.append(a)
            
        return valid

    @property
    def article_count(self):
        return len(self.valid_articles)

    @property
    def unique_sources(self):
        return sorted({article.source for article in self.valid_articles if getattr(article, "source", None)})

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
    is_excluded = Column(Boolean, default=False, nullable=True)  # Loại bỏ khỏi hiển thị công khai
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
    def outbreak_relevance_score(self):
        return self.details.outbreak_relevance_score if self.details else 0.0

    @property
    def is_suspected_false_positive(self):
        return self.details.is_suspected_false_positive if self.details else False
        
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
    llm_normalized_title = Column(Unicode(200), nullable=True)  # LLM-generated normalized title for event grouping
    is_whitelisted = Column(Boolean, default=False)
    outbreak_relevance_score = Column(Float, default=0.0)
    is_suspected_false_positive = Column(Boolean, default=False)
    
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
    source_type = Column(String(50), default="DOMESTIC") # Enum: DOMESTIC, INTERNATIONAL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SchedulerConfig(Base):
    """Cấu hình Auto Crawler Scheduler - chỉ có 1 bản ghi (id=1)"""
    __tablename__ = "scheduler_config"

    id = Column(Integer, primary_key=True, default=1)
    is_enabled = Column(Boolean, default=True)            # Bật/tắt auto-scan
    interval_hours = Column(Integer, default=6)           # Chu kỳ quét (giờ)
    last_run_at = Column(DateTime, nullable=True)         # Thời điểm quét lần cuối (kết thúc)
    next_run_at = Column(DateTime, nullable=True)         # Thời điểm quét tiếp theo
    last_run_saved_count = Column(Integer, default=0)     # Số bài lưu lần cuối
    last_scan_total_checked = Column(Integer, default=0)  # Tổng số bài đã kiểm tra
    last_scan_noise_count = Column(Integer, default=0)    # Số bài noise
    last_scan_irrelevant_count = Column(Integer, default=0) # Số bài irrelevant
    last_scan_unsure_count = Column(Integer, default=0)   # Số bài unsure
    last_scan_started_at = Column(DateTime, nullable=True) # Thời điểm bắt đầu quét
    last_scan_duration_seconds = Column(Integer, default=0) # Tổng thời gian quét (giây)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



