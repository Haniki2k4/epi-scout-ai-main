from sqlalchemy.orm import Session
from datetime import datetime
from . import models, schemas
from ..news.models import ArticleIdentity

def get_evaluations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.ArticleEvaluation).offset(skip).limit(limit).all()

def get_evaluation_by_article(db: Session, article_id: int):
    return db.query(models.ArticleEvaluation).filter(models.ArticleEvaluation.article_id == article_id).first()

def update_human_label(db: Session, article_id: int, human_label: str | None, user_id: int, llm_label: str | None = None, keyword_is_correct: bool | None = None, corrected_keyword: str | None = None, update_article_keyword: bool = False):
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

    if human_label is not None:
        eval_record.human_label = human_label
    if keyword_is_correct is not None:
        eval_record.keyword_is_correct = keyword_is_correct
    if corrected_keyword is not None:
        eval_record.corrected_keyword = corrected_keyword
        if update_article_keyword:
            from ..news.models import ArticleDetails
            article_details = db.query(ArticleDetails).filter(ArticleDetails.article_id == article_id).first()
            if article_details:
                article_details.keywords_matched = corrected_keyword if corrected_keyword != "NONE" else None

    eval_record.is_verified = True
    eval_record.verified_at = datetime.utcnow()
    eval_record.verified_by = user_id

    db.commit()
    db.refresh(eval_record)
    return eval_record

def get_metrics(db: Session):
    evals = db.query(models.ArticleEvaluation).filter(models.ArticleEvaluation.is_verified == True).all()
    if not evals:
        return {
            "accuracy": 0, "precision": 0, "total_verified": 0, "agreement_rate": 0,
            "cohens_kappa": 0, "confusion_matrix": {}, "disease_accuracy": 0
        }

    # Labels available: relevant, noise, irrelevant, unsure
    labels = ["relevant", "noise", "irrelevant", "unsure"]

    # Build confusion matrix
    confusion = {l1: {l2: 0 for l2 in labels} for l1 in labels}
    label_counts_llm = {l: 0 for l in labels}
    label_counts_human = {l: 0 for l in labels}

    # Disease name accuracy calculation
    disease_correct = 0
    disease_total = 0

    correct = 0
    true_positives = 0
    false_positives = 0
    total = len(evals)

    for e in evals:
        # Classification metrics
        if e.llm_label == e.human_label:
            correct += 1

        if e.llm_label in labels and e.human_label in labels:
            confusion[e.llm_label][e.human_label] += 1
            label_counts_llm[e.llm_label] += 1
            label_counts_human[e.human_label] += 1

        if e.llm_label == "relevant" and e.human_label == "relevant":
            true_positives += 1
        elif e.llm_label == "relevant" and e.human_label != "relevant":
            false_positives += 1

        # Disease name accuracy
        if e.keyword_is_correct is not None:
            disease_total += 1
            if e.keyword_is_correct:
                disease_correct += 1
        elif e.article and e.article.keywords_matched:
            # Fallback for old data
            llm_keywords = set(k.strip().lower() for k in e.article.keywords_matched.split(",") if k.strip())
            if e.human_label == "relevant" and e.article.event_id:
                disease_total += 1
                if llm_keywords:
                    disease_correct += 1

    accuracy = correct / total
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0

    # Calculate Cohen's Kappa
    # κ = (Po - Pe) / (1 - Pe)
    # Po = observed agreement (accuracy)
    # Pe = expected agreement by chance
    po = accuracy
    pe = 0
    for label in labels:
        expected_llm = label_counts_llm[label] / total
        expected_human = label_counts_human[label] / total
        pe += expected_llm * expected_human

    cohens_kappa = (po - pe) / (1 - pe) if (1 - pe) > 0 else 0

    # Disease accuracy
    disease_accuracy = (disease_correct / disease_total * 100) if disease_total > 0 else 0

    return {
        "accuracy": round(accuracy * 100, 2),
        "precision": round(precision * 100, 2),
        "total_verified": total,
        "agreement_rate": round(accuracy * 100, 2),
        "cohens_kappa": round(cohens_kappa, 4),
        "confusion_matrix": confusion,
        "disease_accuracy": round(disease_accuracy, 2)
    }
