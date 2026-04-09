from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, inspect
from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        # Create all tables with IF NOT EXISTS (checkfirst=True)
        def _create_all(sync_conn):
            Base.metadata.create_all(sync_conn, checkfirst=True)

        await conn.run_sync(_create_all)

        # Add new columns to existing tables if missing
        await _add_column_if_not_exists(conn, "participants", "telegram_id", "BIGINT")
        await _add_column_if_not_exists(conn, "participants", "nickname", "VARCHAR(100)")
        await _add_column_if_not_exists(conn, "participants", "phone", "VARCHAR(50)")
        await _add_column_if_not_exists(conn, "participants", "age", "INTEGER")
        await _add_column_if_not_exists(conn, "subscribers", "role", "VARCHAR(20) DEFAULT 'guest'")
        await _add_column_if_not_exists(conn, "subscribers", "linked_participant_id", "INTEGER")


async def _add_column_if_not_exists(conn, table, column, col_type):
    try:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception:
        pass  # Column already exists


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
