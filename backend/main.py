import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app.main import app
else:
    from .app.main import app

__all__ = ["app"]
