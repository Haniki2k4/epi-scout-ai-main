from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

# --- Articles ---

def get_articles(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.ArticleIdentity).order_by(models.ArticleIdentity.published_date.desc()).offset(skip).limit(limit).all()

def get_article_by_link(db: Session, link: str):
    return db.query(models.ArticleIdentity).filter(models.ArticleIdentity.link == link).first()

def create_article(db: Session, article: schemas.ArticleCreate):
    # 1. Create Identity
    db_identity = models.ArticleIdentity(
        title=article.title,
        link=article.link,
        published_date=article.published_date
    )
    db.add(db_identity)
    db.commit()
    db.refresh(db_identity)

    # 2. Create Details
    db_details = models.ArticleDetails(
        article_id=db_identity.id,
        summary=article.summary,
        source=article.source,
        keywords_matched=article.keywords_matched,
        tags=article.tags,
        is_whitelisted=article.is_whitelisted
    )
    db.add(db_details)
    db.commit()
    
    return db_identity

# --- Disease Cases ---

def create_disease_case(db: Session, case: models.DiseaseCase):
    db.add(case)
    db.commit()
    db.refresh(case)
    return case

# --- Whitelist ---

def get_whitelisted_domains(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.WhitelistDomain).order_by(models.WhitelistDomain.id).offset(skip).limit(limit).all()

def create_whitelist_domain(db: Session, domain: schemas.WhitelistCreate):
    db_domain = models.WhitelistDomain(domain=domain.domain, is_active=domain.is_active)
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)
    return db_domain

def get_whitelist_by_name(db: Session, domain: str):
    return db.query(models.WhitelistDomain).filter(models.WhitelistDomain.domain == domain).first()

# --- Keywords ---

def get_keywords(db: Session, skip: int = 0, limit: int = 100):
    # Sort by ID descending to show newest first (Recent)
    return db.query(models.Keyword).order_by(models.Keyword.id.desc()).offset(skip).limit(limit).all()

def create_keyword(db: Session, keyword: schemas.KeywordCreate):
    db_keyword = models.Keyword(text=keyword.text)
    db.add(db_keyword)
    db.commit()
    db.refresh(db_keyword)
    return db_keyword

def delete_keyword(db: Session, keyword_id: int):
    db_keyword = db.query(models.Keyword).filter(models.Keyword.id == keyword_id).first()
    if db_keyword:
        db.delete(db_keyword)
        db.commit()
        return True
    return False

def get_keyword_by_text(db: Session, text: str):
    return db.query(models.Keyword).filter(models.Keyword.text == text).first()
    
def add_keyword(db: Session, text: str):
    existing = get_keyword_by_text(db, text)
    if not existing:
        create_keyword(db, schemas.KeywordCreate(text=text))
