import sys
from pathlib import Path

# Ensure root directory is on sys.path so 'app' can be imported in Vercel Serverless environment
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app  # noqa: E402

__all__ = ["app"]
