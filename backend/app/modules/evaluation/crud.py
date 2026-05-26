from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from . import models, schemas
from ..news.models import ArticleIdentity, SchedulerConfig

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
    evals = db.query(models.ArticleEvaluation).join(ArticleIdentity).filter(models.ArticleEvaluation.is_verified == True).all()
    if not evals:
        return {
            "accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0,
            "total_verified": 0, "agreement_rate": 0, "confusion_matrix": {},
            "disease_accuracy": 0, "latest_session": None
        }

    # Labels available: relevant, noise, irrelevant, unsure
    labels = ["relevant", "noise", "irrelevant", "unsure"]

    # Build confusion matrix
    confusion = {l1: {l2: 0 for l2 in labels} for l1 in labels}

    # Disease name accuracy calculation
    disease_correct = 0
    disease_total = 0

    correct = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    total = len(evals)

    for e in evals:
        # Classification metrics
        if e.llm_label == e.human_label:
            correct += 1

        if e.llm_label in labels and e.human_label in labels:
            confusion[e.llm_label][e.human_label] += 1

        if e.llm_label == "relevant" and e.human_label == "relevant":
            true_positives += 1
        elif e.llm_label == "relevant" and e.human_label != "relevant":
            false_positives += 1
        elif e.llm_label != "relevant" and e.human_label == "relevant":
            false_negatives += 1

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
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    # Disease accuracy
    disease_accuracy = (disease_correct / disease_total * 100) if disease_total > 0 else 0

    # Latest scan session from SchedulerConfig (phiên quét gần nhất, không phải phiên gán nhãn)
    latest_session = None
    latest_scan = db.query(SchedulerConfig).filter(SchedulerConfig.id == 1).first()
    if latest_scan and latest_scan.last_run_at:
        # Tính tỷ lệ label đúng/sai cho bài báo trong phiên quét đó
        scan_day_start = latest_scan.last_run_at.replace(hour=0, minute=0, second=0, microsecond=0)
        scan_day_end = scan_day_start + timedelta(days=1)
        session_articles = db.query(ArticleIdentity).filter(
            ArticleIdentity.published_date >= scan_day_start,
            ArticleIdentity.published_date < scan_day_end,
        ).all()
        session_article_ids = [a.id for a in session_articles]
        session_evals = db.query(models.ArticleEvaluation).filter(
            models.ArticleEvaluation.article_id.in_(session_article_ids),
            models.ArticleEvaluation.human_label.isnot(None),
        ).all()
        session_correct = sum(1 for e in session_evals if e.llm_label == e.human_label)
        session_total = len(session_evals)

        scan_duration = latest_scan.last_scan_duration_seconds or 0
        total_checked = latest_scan.last_scan_total_checked or 0
        avg_time = round(scan_duration / total_checked, 2) if total_checked > 0 else 0

        latest_session = {
            "date": latest_scan.last_run_at.strftime("%Y-%m-%d %H:%M"),
            "total": latest_scan.last_run_saved_count or 0,
            "correct": session_correct,
            "verified_count": session_total,
            "total_checked": latest_scan.last_scan_total_checked or 0,
            "noise_count": latest_scan.last_scan_noise_count or 0,
            "irrelevant_count": latest_scan.last_scan_irrelevant_count or 0,
            "unsure_count": latest_scan.last_scan_unsure_count or 0,
            "duration_seconds": scan_duration,
            "avg_time_per_article": avg_time,
        }

    return {
        "accuracy": round(accuracy * 100, 2),
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "total_verified": total,
        "agreement_rate": round(accuracy * 100, 2),
        "confusion_matrix": confusion,
        "disease_accuracy": round(disease_accuracy, 2),
        "latest_session": latest_session
    }
