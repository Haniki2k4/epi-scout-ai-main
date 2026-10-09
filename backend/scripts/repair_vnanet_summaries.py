"""Repair VNA summaries polluted by concatenated related headlines.

Dry run by default. Pass ``--apply`` to create a JSON backup and commit changes.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.modules.news.html_utils import trim_feed_related_titles
from backend.app.modules.news.models import ArticleDetails, RssEntrySample, RssSource

VNA_FEED_URL = "https://vnanet.vn/vi/rss/suc-khoe-7.rss"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", default="backups")
    args = parser.parse_args()

    changes: list[dict] = []
    db = SessionLocal()
    try:
        details = db.scalars(
            select(ArticleDetails).where(ArticleDetails.source == "vnanet.vn")
        ).all()
        for row in details:
            cleaned = trim_feed_related_titles(row.summary or "", VNA_FEED_URL)
            if cleaned != (row.summary or ""):
                changes.append({
                    "table": "article_details",
                    "id": row.id,
                    "old_summary": row.summary,
                    "new_summary": cleaned,
                })
                row.summary = cleaned

        source_ids = db.scalars(
            select(RssSource.id).where(RssSource.url == VNA_FEED_URL)
        ).all()
        if source_ids:
            samples = db.scalars(
                select(RssEntrySample).where(RssEntrySample.source_id.in_(source_ids))
            ).all()
            for row in samples:
                cleaned = trim_feed_related_titles(row.summary or "", VNA_FEED_URL)
                if cleaned != (row.summary or ""):
                    changes.append({
                        "table": "rss_entry_samples",
                        "id": row.id,
                        "old_summary": row.summary,
                        "new_summary": cleaned,
                    })
                    row.summary = cleaned

        print(f"Detected {len(changes)} contaminated summaries")
        if not args.apply or not changes:
            db.rollback()
            return

        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"vnanet-summary-repair-{stamp}.json"
        backup_path.write_text(
            json.dumps(changes, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        db.commit()
        print(f"Updated {len(changes)} summaries; backup: {backup_path}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
