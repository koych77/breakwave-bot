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
        # Get existing table names
        def _get_tables(sync_conn):
            insp = inspect(sync_conn)
            return insp.get_table_names()

        existing = await conn.run_sync(_get_tables)

        # Create only tables that don't exist yet
        def _create_missing(sync_conn):
            tables_to_create = []
            for table in Base.metadata.sorted_tables:
                if table.name not in existing:
                    tables_to_create.append(table)
            if tables_to_create:
                Base.metadata.create_all(sync_conn, tables=tables_to_create)

        await conn.run_sync(_create_missing)

        # Add new columns to existing tables if missing
        await _add_column_if_not_exists(conn, "participants", "telegram_id", "BIGINT")
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
