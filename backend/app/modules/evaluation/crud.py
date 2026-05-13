from sqlalchemy.orm import Session
from datetime import datetime
from . import models, schemas
from ..news.models import ArticleIdentity

def get_evaluations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.ArticleEvaluation).offset(skip).limit(limit).all()

def get_evaluation_by_article(db: Session, article_id: int):
    return db.query(models.ArticleEvaluation).filter(models.ArticleEvaluation.article_id == article_id).first()

def update_human_label(db: Session, article_id: int, human_label: str, user_id: int, llm_label: str | None = None):
    eval_record = get_evaluation_by_article(db, article_id)
    if not eval_record:
        eval_record = models.ArticleEvaluation(article_id=article_id)
        db.add(eval_record)
        db.commit()
        db.refresh(eval_record)

    if llm_label:
        eval_record.llm_label = llm_label
    elif not eval_record.llm_label:
        article = db.query(ArticleIdentity).filter(ArticleIdentity.id == article_id).first()
        if article:
            eval_record.llm_label = "relevant" if article.event_id else "irrelevant"

    eval_record.human_label = human_label
    eval_record.is_verified = True
    eval_record.verified_at = datetime.utcnow()
    eval_record.verified_by = user_id

    db.commit()
    db.refresh(eval_record)
    return eval_record

def get_metrics(db: Session):
    evals = db.query(models.ArticleEvaluation).filter(models.ArticleEvaluation.is_verified == True).all()
    if not evals:
        return {"accuracy": 0, "precision": 0, "total_verified": 0, "agreement_rate": 0}

    correct = 0
    true_positives = 0
    false_positives = 0
    total = len(evals)

    for e in evals:
        if e.llm_label == e.human_label:
            correct += 1
        
        if e.llm_label == "relevant" and e.human_label == "relevant":
            true_positives += 1
        elif e.llm_label == "relevant" and e.human_label != "relevant":
            false_positives += 1

    accuracy = correct / total
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0

    return {
        "accuracy": round(accuracy * 100, 2),
        "precision": round(precision * 100, 2),
        "total_verified": total,
        "agreement_rate": round(accuracy * 100, 2)
    }
