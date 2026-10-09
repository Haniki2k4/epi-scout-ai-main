from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Unicode, UnicodeText, JSON, Float, UniqueConstraint, Index, inspect, text
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
    case_count = Column(Integer, nullable=True)
    severity = Column(Unicode(50), nullable=True)
    status = Column(Unicode(50), default="pending_review")
    analyst_reviewed_at = Column(DateTime, nullable=True)
    analyst_reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Unicode(500), nullable=True)
    verification_notes = Column(UnicodeText, nullable=True)
    verification_source = Column(Unicode(500), nullable=True)
    verified_case_source_id = Column(Integer, ForeignKey("disease_cases.id"), nullable=True)
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

class EventReviewLog(Base):
    __tablename__ = "event_review_log"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("news_events.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    reason = Column(Unicode(500), nullable=True)
    notes = Column(UnicodeText, nullable=True)
    verification_source = Column(Unicode(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    stage1_route = Column(String(20), nullable=True)
    context_signal_type = Column(String(50), nullable=True)
    context_matched_phrases = Column(Unicode(1000), nullable=True)
    context_evidence_text = Column(UnicodeText, nullable=True)
    llm_reason = Column(Unicode(500), nullable=True)
    review_version = Column(Integer, nullable=False, default=0)

    identity = relationship("ArticleIdentity", back_populates="details")

class DiseaseCase(Base):
    __tablename__ = "disease_cases"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("article_identity.id"))
    disease_name = Column(Unicode(255), index=True)
    case_count = Column(Integer, nullable=True)  # legacy; never aggregate
    location = Column(Unicode(255), nullable=True)
    report_date = Column(DateTime, default=datetime.utcnow)
    reported_value = Column(Integer, nullable=True)
    case_type = Column(String(30), nullable=True)
    count_scope = Column(String(20), nullable=True)
    report_period_start = Column(DateTime, nullable=True)
    report_period_end = Column(DateTime, nullable=True)
    evidence_quote = Column(Unicode(400), nullable=True)
    time_allocation = Column(String(20), nullable=True)
    location_allocation = Column(String(20), nullable=True)
    data_quality = Column(String(20), nullable=True)

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


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("rss_sources.id"), nullable=True)
    feed_url = Column(String(767), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    entries_fetched = Column(Integer, default=0)
    entries_passed_stage1 = Column(Integer, default=0)
    entries_saved = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_sample = Column(Unicode(500), nullable=True)
    scan_run_id = Column(String(36), ForeignKey("scan_runs.scan_run_id"), nullable=True)
    eligible_entries_total = Column(Integer, nullable=True)
    gate_b_candidates_total = Column(Integer, nullable=True)
    gate_b_active_total = Column(Integer, nullable=True)
    gate_b_unexplained_cluster = Column(Integer, nullable=True)
    gate_b_animal_signal = Column(Integer, nullable=True)
    gate_b_environment_signal = Column(Integer, nullable=True)
    gate_b_field_response = Column(Integer, nullable=True)


class ScanRun(Base):
    __tablename__ = "scan_runs"
    __table_args__ = (Index("ix_scan_runs_status_completed", "status", "completed_at"),)

    scan_run_id = Column(String(36), primary_key=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")
    feed_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)


class RssEntrySample(Base):
    __tablename__ = "rss_entry_samples"

    id = Column(Integer, primary_key=True)
    sample_uuid = Column(String(36), nullable=True, unique=True)
    source_id = Column(Integer, ForeignKey("rss_sources.id"), nullable=True)
    link = Column(String(767), nullable=False)
    title = Column(Unicode(500), nullable=False)
    summary = Column(UnicodeText, nullable=True)
    published_date = Column(DateTime, nullable=True)
    sampled_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    passed_stage1 = Column(Boolean, nullable=False)
    llm_label = Column(String(20), nullable=True)
    predicted_disease = Column(Unicode(500), nullable=True)
    predicted_location = Column(Unicode(255), nullable=True)
    predicted_event_date = Column(DateTime, nullable=True)
    predicted_case_values = Column(UnicodeText, nullable=True)
    article_id = Column(Integer, ForeignKey("article_identity.id", ondelete="SET NULL"), nullable=True)
    human_relevant = Column(Boolean, nullable=True)
    labeled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    labeled_at = Column(DateTime, nullable=True)
    human_disease = Column(Unicode(255), nullable=True)
    human_diseases = Column(JSON, nullable=True)
    human_location = Column(Unicode(255), nullable=True)
    human_event_date = Column(DateTime, nullable=True)
    human_case_value = Column(Integer, nullable=True)
    stage1_route = Column(String(20), nullable=True)
    gate_b_mode = Column(String(10), nullable=True)
    gate_b_evaluated = Column(Boolean, nullable=True)
    detector_matched = Column(Boolean, nullable=True)
    detector_version = Column(String(30), nullable=True)
    context_signal_type = Column(String(50), nullable=True)
    human_signal_label = Column(String(30), nullable=True)
    llm_reason = Column(Unicode(500), nullable=True)


class ContextSignalReview(Base):
    __tablename__ = "context_signal_reviews"
    __table_args__ = (Index("ix_context_signal_reviews_article_current", "article_id", "is_superseded"),)

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("article_identity.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_at = Column(DateTime, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    request_id = Column(String(36), unique=True, nullable=True)
    decision = Column(String(30), nullable=False)
    is_superseded = Column(Boolean, nullable=False, default=False)
    signal_evidence = Column(UnicodeText, nullable=True)
    reason = Column(Unicode(500), nullable=False)
    disease_name = Column(Unicode(255), nullable=True)
    disease_source = Column(Unicode(500), nullable=True)
    location = Column(Unicode(255), nullable=True)
    event_id = Column(Integer, ForeignKey("news_events.id", ondelete="SET NULL"), nullable=True)


class EventPairLabel(Base):
    __tablename__ = "event_pair_labels"
    __table_args__ = (UniqueConstraint("article_a_id", "article_b_id", name="uq_event_pair_articles"),)

    id = Column(Integer, primary_key=True)
    article_a_id = Column(Integer, ForeignKey("article_identity.id"), nullable=False)
    article_b_id = Column(Integer, ForeignKey("article_identity.id"), nullable=False)
    same_event = Column(Boolean, nullable=False)
    predicted_same_event = Column(Boolean, nullable=False)
    labeled_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    labeled_at = Column(DateTime, nullable=False)

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
