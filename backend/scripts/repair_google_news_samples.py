"""Repair unresolved Google News URLs in RSS quality samples.

Dry-run by default. Use --apply after reviewing the output.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
spec = importlib.util.spec_from_file_location(
    "google_news_resolver", ROOT / "backend/app/modules/news/google_news.py"
)
resolver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = resolver
spec.loader.exec_module(resolver)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-id", type=int)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    connection = pymysql.connect(
        host=os.getenv("DB_SERVER", "localhost"),
        port=int(os.getenv("DB_PORT") or "3306"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "EpiScoutDB"),
        connect_timeout=5,
        read_timeout=20,
        write_timeout=20,
    )
    resolved_count = linked_count = 0
    try:
        with connection.cursor() as cursor:
            where = "id = %s" if args.sample_id else "link LIKE 'https://news.google.com/%'"
            params = (args.sample_id,) if args.sample_id else ()
            cursor.execute(
                f"SELECT id, link FROM rss_entry_samples WHERE {where} ORDER BY id LIMIT %s",
                (*params, max(1, min(args.limit, 2000))),
            )
            rows = cursor.fetchall()
            for sample_id, old_link in rows:
                new_link = resolver.resolve_google_news_url(old_link)
                if new_link == old_link:
                    print(f"id={sample_id} unresolved")
                    continue
                resolved_count += 1
                cursor.execute("SELECT id FROM article_identity WHERE link = %s LIMIT 1", (new_link,))
                article = cursor.fetchone()
                article_id = article[0] if article else None
                linked_count += int(article_id is not None)
                print(f"id={sample_id} source={new_link} article_id={article_id or 'none'}")
                if args.apply:
                    cursor.execute(
                        "UPDATE rss_entry_samples SET link = %s, article_id = COALESCE(article_id, %s) WHERE id = %s",
                        (new_link[:767], article_id, sample_id),
                    )
        if args.apply:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    mode = "updated" if args.apply else "dry-run"
    print(f"{mode}: resolved={resolved_count}, linked_existing_article={linked_count}")


if __name__ == "__main__":
    main()

