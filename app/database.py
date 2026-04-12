from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        # Create tables via raw SQL with IF NOT EXISTS
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                is_current BOOLEAN DEFAULT 1,
                created_at DATETIME
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                nickname VARCHAR(100),
                nomination VARCHAR(100) NOT NULL,
                season_id INTEGER NOT NULL REFERENCES seasons(id),
                telegram_id BIGINT,
                phone VARCHAR(50),
                age INTEGER
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                emoji VARCHAR(10) DEFAULT '🏆',
                event_type VARCHAR(20) NOT NULL,
                season_id INTEGER REFERENCES seasons(id),
                date VARCHAR(50),
                time VARCHAR(20),
                location VARCHAR(300),
                description TEXT,
                contact VARCHAR(200),
                fee VARCHAR(100),
                photo_path VARCHAR(500),
                status VARCHAR(20) DEFAULT 'upcoming',
                multiplier INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY,
                participant_id INTEGER NOT NULL REFERENCES participants(id),
                event_id INTEGER NOT NULL REFERENCES events(id),
                main_place FLOAT,
                extra_nom1 FLOAT,
                extra_nom2 FLOAT,
                extra_nom3 FLOAT,
                points INTEGER DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                first_name VARCHAR(200),
                username VARCHAR(200),
                role VARCHAR(20) DEFAULT 'guest',
                linked_participant_id INTEGER,
                subscribed_at DATETIME,
                is_active BOOLEAN DEFAULT 1
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                first_name VARCHAR(200),
                username VARCHAR(200),
                created_at DATETIME
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS nominations (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_registrations (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id),
                telegram_id BIGINT NOT NULL,
                participant_id INTEGER REFERENCES participants(id),
                first_name VARCHAR(200),
                username VARCHAR(200),
                created_at DATETIME
            )
        """))

        # Add new columns to existing tables if missing
        await _add_column_if_not_exists(conn, "participants", "telegram_id", "BIGINT")
        await _add_column_if_not_exists(conn, "participants", "nickname", "VARCHAR(100)")
        await _add_column_if_not_exists(conn, "participants", "phone", "VARCHAR(50)")
        await _add_column_if_not_exists(conn, "participants", "age", "INTEGER")
        await _add_column_if_not_exists(conn, "subscribers", "role", "VARCHAR(20) DEFAULT 'guest'")
        await _add_column_if_not_exists(conn, "subscribers", "linked_participant_id", "INTEGER")

        # One-time rename of legacy nomination names
        await conn.execute(text(
            "UPDATE participants SET nomination = 'до 3х лет опытом' WHERE nomination = 'до 3 лет опыта'"
        ))
        await conn.execute(text(
            "UPDATE participants SET nomination = 'Bgirls' WHERE nomination = 'Bgirl'"
        ))
        await conn.execute(text(
            "UPDATE nominations SET name = 'до 3х лет опытом' WHERE name = 'до 3 лет опыта'"
        ))
        # Bgirls might collide if both rows exist; delete old then rename
        await conn.execute(text(
            "DELETE FROM nominations WHERE name = 'Bgirl' AND EXISTS (SELECT 1 FROM nominations WHERE name = 'Bgirls')"
        ))
        await conn.execute(text(
            "UPDATE nominations SET name = 'Bgirls' WHERE name = 'Bgirl'"
        ))


async def _add_column_if_not_exists(conn, table, column, col_type):
    try:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception:
        pass  # Column already exists


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
