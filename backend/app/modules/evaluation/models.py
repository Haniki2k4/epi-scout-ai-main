from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Unicode
from sqlalchemy.orm import relationship
from datetime import datetime
from ...core.database import Base

class ArticleEvaluation(Base):
    __tablename__ = "article_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("article_identity.id"), unique=True, index=True)
    
    llm_label = Column(String(50), nullable=True)
    human_label = Column(String(50), nullable=True)
    
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    article = relationship("ArticleIdentity", backref="evaluation")
