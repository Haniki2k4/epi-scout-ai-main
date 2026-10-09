"""
Script to restore the database from backup.sql using credentials from .env.
Usage: python backend/scripts/restore_backup.py [path_to_sql]
"""
import sys
from pathlib import Path
import pymysql
import pymysql.constants.CLIENT

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from backend.app.core import database

# Tables created by migrations newer than backup.sql (revision e7b4c1d2f903)
# These must be dropped prior to restoring backup.sql so that alembic upgrade head
# does not collide with existing tables.
NEWER_TABLES = [
    "event_review_log",
    "crawl_runs",
    "rss_entry_samples",
    "event_pair_labels",
]

def restore_backup(sql_file: str = "backup.sql"):
    file_path = ROOT_DIR / sql_file
    if not file_path.exists():
        print(f"Error: {file_path} not found.")
        return False

    print(f"Restoring {file_path} into {database.DATABASE_NAME} on {database.SERVER_NAME}...")
    conn = pymysql.connect(
        host=database.SERVER_NAME,
        port=int(database.DB_PORT),
        user=database.DB_USER,
        password=database.DB_PASSWORD,
        database=database.DATABASE_NAME,
        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS,
        charset="utf8mb4",
    )

    with conn.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in NEWER_TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    with open(file_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cursor:
        cursor.execute(sql)
        while conn.next_result():
            pass
    conn.commit()
    conn.close()
    print("Database restored successfully!")
    return True

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "backup.sql"
    restore_backup(target)
