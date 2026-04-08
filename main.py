import asyncio
import logging
import os
import uvicorn
from threading import Thread
from pathlib import Path

# Load .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())
from aiogram.types import BotCommand
from app.api import app as fastapi_app
from app.bot import bot, dp
from app.database import init_db
from app.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def on_startup():
    await init_db()
    logger.info("Database initialized")

    # Auto-import Excel if present and DB is empty
    excel_path = None
    for f in DATA_DIR.parent.glob("*.xlsx"):
        excel_path = str(f)
        break

    if excel_path:
        from sqlalchemy import select
        from app.database import async_session
        from app.models import Season
        async with async_session() as s:
            result = await s.execute(select(Season))
            if not result.scalar_one_or_none():
                logger.info(f"Auto-importing Excel: {excel_path}")
                from app.excel_parser import import_excel_to_db
                result = await import_excel_to_db(s, excel_path)
                logger.info(f"Imported: {result}")

    # Set bot commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть приложение"),
        BotCommand(command="help", description="Помощь"),
    ])

    # Register first admin
    from app.config import ADMIN_IDS
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS not set. First user to send /start with admin command will be admin.")


def run_api():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8080, log_level="info")


async def run_bot():
    await on_startup()
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


def main():
    # Run FastAPI in a thread
    api_thread = Thread(target=run_api, daemon=True)
    api_thread.start()
    logger.info("API server started on port 8080")

    # Run bot in main asyncio loop
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
