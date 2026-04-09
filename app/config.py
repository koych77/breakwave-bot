import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEBAPP_DIR = BASE_DIR / "webapp"
DATA_DIR.mkdir(exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "88pirafu")

DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'breakwave.db'}"
DATABASE_SYNC_URL = f"sqlite:///{DATA_DIR / 'breakwave.db'}"

WEBAPP_URL = os.getenv("WEBAPP_URL", "")

# Scoring system
PLACE_POINTS = {1: 30, 2: 20, 3: 10}
PARTICIPATION_POINTS = 1
