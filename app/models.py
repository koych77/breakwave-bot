from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    participants = relationship("Participant", back_populates="season", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="season", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    nomination = Column(String(100), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=True)

    season = relationship("Season", back_populates="participants")
    results = relationship("Result", back_populates="participant", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    emoji = Column(String(10), default="🏆")
    event_type = Column(String(20), nullable=False)  # 'school' or 'external'
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=True)
    date = Column(String(50), nullable=True)
    time = Column(String(20), nullable=True)
    location = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    contact = Column(String(200), nullable=True)
    fee = Column(String(100), nullable=True)
    photo_path = Column(String(500), nullable=True)
    status = Column(String(20), default="upcoming")  # upcoming, completed, locked
    multiplier = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    season = relationship("Season", back_populates="events")
    results = relationship("Result", back_populates="event", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    main_place = Column(Float, nullable=True)
    extra_nom1 = Column(Float, nullable=True)
    extra_nom2 = Column(Float, nullable=True)
    extra_nom3 = Column(Float, nullable=True)
    points = Column(Integer, default=0)

    participant = relationship("Participant", back_populates="results")
    event = relationship("Event", back_populates="results")


class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String(200), nullable=True)
    username = Column(String(200), nullable=True)
    role = Column(String(20), default="guest")  # 'guest' or 'participant'
    linked_participant_id = Column(Integer, ForeignKey("participants.id"), nullable=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String(200), nullable=True)
    username = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Nomination(Base):
    __tablename__ = "nominations"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
