from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Unicode, UnicodeText
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class ArticleIdentity(Base):
    __tablename__ = "article_identity"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Unicode(500), nullable=True) # NVARCHAR
    link = Column(String(500), unique=True, index=True) # Link is usually ASCII, but String is fine
    published_date = Column(DateTime, default=datetime.utcnow)

    # Relationship 1-1 with details
    details = relationship("ArticleDetails", back_populates="identity", uselist=False, cascade="all, delete-orphan")
    
    # Relationship 1-n with disease cases
    cases = relationship("DiseaseCase", back_populates="article", cascade="all, delete-orphan")

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

class WhitelistDomain(Base):
    __tablename__ = "whitelist_domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, index=True)
    is_active = Column(Boolean, default=True)

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Unicode(255), unique=True, index=True) # Support Vietnamese keywords
    created_at = Column(DateTime, default=datetime.utcnow)
