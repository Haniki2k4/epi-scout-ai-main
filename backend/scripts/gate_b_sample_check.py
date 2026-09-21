from collections import Counter
from pathlib import Path
import importlib.util
import os
import re

import pymysql
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[2]
load_dotenv(root / ".env")
spec = importlib.util.spec_from_file_location("signal_detector", root / "backend/app/modules/news/signal_detector.py")
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

config = {
    "host": os.getenv("DB_SERVER", "localhost"),
    "port": int(os.getenv("DB_PORT") or "3306"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "EpiScoutDB"),
    "connect_timeout": 5,
    "read_timeout": 10,
}
connection = pymysql.connect(**config)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT title, summary FROM rss_entry_samples WHERE passed_stage1 = 0 ORDER BY sampled_at DESC LIMIT 1000")
        rows = cursor.fetchall()
finally:
    connection.close()

counts = Counter()
evaluated = 0
for title, summary in rows:
    if re.search(r"^\s*(\[video\]|\(video\)|video\s*:|video\s*-|\[clip\]|\(clip\))", title or "", re.IGNORECASE):
        continue
    evaluated += 1
    match = module.detect_context_signal(title or "", summary or "")
    if match:
        counts[match.signal_type] += 1
print(f"rss_samples={len(rows)} evaluated_nonvideo={evaluated} detector_matches={sum(counts.values())}")
for signal_type in ("unexplained_cluster", "animal_signal", "environment_signal", "field_response"):
    print(f"{signal_type}={counts[signal_type]}")

