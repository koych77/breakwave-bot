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
        
        # Initialize CRM tables
        await init_crm_tables(conn)


async def _add_column_if_not_exists(conn, table, column, col_type):
    try:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception:
        pass  # Column already exists


async def init_crm_tables(conn):
    """Create CRM tables if not exist."""
    # Coaches table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS coaches (
            id INTEGER PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            first_name VARCHAR(200),
            username VARCHAR(200),
            phone VARCHAR(50),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME
        )
    """))
    
    # Locations table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY,
            coach_id INTEGER NOT NULL REFERENCES coaches(id),
            name VARCHAR(200) NOT NULL,
            address VARCHAR(500),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME
        )
    """))
    
    # Students table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            coach_id INTEGER NOT NULL REFERENCES coaches(id),
            name VARCHAR(200) NOT NULL,
            phone VARCHAR(50),
            telegram_id BIGINT,
            age INTEGER,
            subscription_start DATE,
            subscription_end DATE,
            lessons_count INTEGER DEFAULT 8,
            lessons_remaining INTEGER DEFAULT 8,
            lesson_duration INTEGER DEFAULT 90,
            amount FLOAT DEFAULT 0.0,
            currency VARCHAR(10) DEFAULT 'BYN',
            is_paid BOOLEAN DEFAULT 0,
            is_unlimited BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME
        )
    """))
    
    # StudentLocations table (many-to-many with schedule)
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS student_locations (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            location_id INTEGER NOT NULL REFERENCES locations(id),
            lesson_days VARCHAR(100) DEFAULT '1,3',
            lesson_times TEXT DEFAULT '{"default": "18:00"}',
            is_primary BOOLEAN DEFAULT 0,
            created_at DATETIME
        )
    """))
    
    # Attendance table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            location_id INTEGER REFERENCES locations(id),
            attendance_date DATE NOT NULL,
            attendance_time VARCHAR(10),
            is_extra BOOLEAN DEFAULT 0,
            lesson_counted BOOLEAN DEFAULT 1,
            notes TEXT,
            created_at DATETIME
        )
    """))
    
    # Payments table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES students(id),
            amount FLOAT NOT NULL,
            currency VARCHAR(10) DEFAULT 'BYN',
            payment_type VARCHAR(50) DEFAULT 'subscription',
            description VARCHAR(500),
            paid_at DATETIME
        )
    """))
    
    # Coach settings table
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS coach_settings (
            id INTEGER PRIMARY KEY,
            coach_id INTEGER NOT NULL REFERENCES coaches(id),
            notify_daily_summary BOOLEAN DEFAULT 1,
            notify_low_lessons BOOLEAN DEFAULT 1,
            notify_payment_due BOOLEAN DEFAULT 1,
            default_lessons_count INTEGER DEFAULT 8,
            default_lesson_duration INTEGER DEFAULT 90,
            default_currency VARCHAR(10) DEFAULT 'BYN',
            created_at DATETIME,
            updated_at DATETIME
        )
    """))
    
    # Run CRM migrations
    await _migrate_crm_tables(conn)


async def _migrate_crm_tables(conn):
    """Migrate CRM tables for schema updates."""
    # Add is_unlimited to students
    await _add_column_if_not_exists(conn, "students", "is_unlimited", "BOOLEAN DEFAULT 0")
    
    # Ensure updated_at column exists
    await _add_column_if_not_exists(conn, "students", "updated_at", "DATETIME")
    
    # Ensure student_locations table has all columns
    await _add_column_if_not_exists(conn, "student_locations", "is_primary", "BOOLEAN DEFAULT 0")
    await _add_column_if_not_exists(conn, "student_locations", "lesson_times", "TEXT")
    
    # Ensure attendance table has all columns
    await _add_column_if_not_exists(conn, "attendance", "lesson_counted", "BOOLEAN DEFAULT 1")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
