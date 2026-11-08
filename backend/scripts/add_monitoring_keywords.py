"""Preview/add missing monitoring keywords; never updates or deletes existing rows.

Run from the repository root:
  python -m backend.scripts.add_monitoring_keywords [--apply]
  python -m backend.scripts.add_monitoring_keywords --docker-container epi-scout-mysql --apply
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from backend.app.modules.news import crud, models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--docker-container")
    args = parser.parse_args()
    if args.docker_container:
        # Capture configuration internally. Never print passwords or connection URLs.
        result = subprocess.run(["docker", "inspect", args.docker_container],
                                capture_output=True, text=True, check=True)
        config = json.loads(result.stdout)[0]
        env = dict(value.split("=", 1) for value in config["Config"]["Env"] if "=" in value)
        port = config["NetworkSettings"]["Ports"]["3306/tcp"][0]["HostPort"]
        engine = create_engine(URL.create("mysql+pymysql", username="root",
            password=env["MYSQL_ROOT_PASSWORD"], host="127.0.0.1", port=int(port),
            database=os.getenv("DB_NAME") or env["MYSQL_DATABASE"]), hide_parameters=True)
    else:
        from backend.app.core.database import engine

    try:
        with Session(engine) as db:
            before = [
                {"id": row.id, "text": row.text, "is_active": row.is_active,
                 "created_at": row.created_at.isoformat() if row.created_at else None}
                for row in db.query(models.Keyword).order_by(models.Keyword.id).all()
            ]
            print(f"Existing keywords: {len(before)}")
            if not args.apply:
                missing = crud.missing_default_keywords(db)
                print(json.dumps({"proposed_missing_keywords": missing}, ensure_ascii=False))
                print("Preview only. Use --apply to add missing defaults and monitoring keywords.")
                return
            backup_dir = Path(__file__).resolve().parents[2] / "backups"
            backup_dir.mkdir(exist_ok=True)
            path = backup_dir / f"keywords-before-add-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
            path.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
            crud.seed_default_keywords(db)
            after = {r.id: r for r in db.query(models.Keyword).all()}
            for old in before:
                current = after[old["id"]]
                assert current.text == old["text"] and current.is_active == old["is_active"]
                assert (current.created_at.isoformat() if current.created_at else None) == old["created_at"]
            print(f"Added keywords: {len(after) - len(before)}")
            print(f"Preserved existing rows: {len(before)}")
            print(f"Backup: {path}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
