"""Repair HTML entities in headlines already stored in the database.

Run from backend: python -m scripts.repair_html_titles [--apply]
"""
import argparse

from app.core.database import SessionLocal
from app.modules.auth import models as auth_models  # Register users for news event foreign keys
from app.modules.news.html_utils import decode_html_entities
from app.modules.news.models import ArticleDetails, ArticleIdentity, NewsEvent, RssEntrySample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit changes; default is dry run")
    args = parser.parse_args()
    fields = (
        (ArticleIdentity, "title"),
        (ArticleDetails, "llm_normalized_title"),
        (NewsEvent, "canonical_title"),
        (RssEntrySample, "title"),
    )
    db = SessionLocal()
    try:
        for model, field_name in fields:
            column = getattr(model, field_name)
            count = 0
            for row in db.query(model).filter(column.like("%&%")).yield_per(100):
                original = getattr(row, field_name)
                decoded = decode_html_entities(original)
                if decoded != original:
                    count += 1
                    if args.apply:
                        setattr(row, field_name, decoded)
            print(f"{model.__tablename__}.{field_name}: {count}")
        if args.apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
