"""CRM models for coach management."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, BigInteger, Date, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base
import json


class Coach(Base):
    __tablename__ = "coaches"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String(200))
    username = Column(String(200))
    phone = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    students = relationship("Student", back_populates="coach", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="coach", cascade="all, delete-orphan")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    name = Column(String(200), nullable=False)  # Название зала (вводится тренером)
    address = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    coach = relationship("Coach", back_populates="locations")
    student_locations = relationship("StudentLocation", back_populates="location", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="location")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    
    # Basic info
    name = Column(String(200), nullable=False)
    phone = Column(String(50))
    telegram_id = Column(BigInteger)
    age = Column(Integer)
    
    # Subscription info
    subscription_start = Column(Date)
    subscription_end = Column(Date)
    lessons_count = Column(Integer, default=8)  # Всего занятий в абонементе
    lessons_remaining = Column(Integer, default=8)  # Осталось занятий
    lesson_duration = Column(Integer, default=90)  # Минут
    
    # Billing
    amount = Column(Float, default=0.0)  # Сумма абонемента
    currency = Column(String(10), default="BYN")
    is_paid = Column(Boolean, default=False)
    
    # Unlimited option
    is_unlimited = Column(Boolean, default=False)  # Безлимит на месяц
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    coach = relationship("Coach", back_populates="students")
    student_locations = relationship("StudentLocation", back_populates="student", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")

    def get_lesson_time_for_day(self, day_of_week, location_id=None):
        """Get lesson time for specific day and location."""
        for sl in self.student_locations:
            if location_id and sl.location_id != location_id:
                continue
            try:
                times = json.loads(sl.lesson_times or '{}')
                time = times.get(str(day_of_week), times.get('default', '18:00'))
                return time
            except:
                return '18:00'
        return '18:00'

    def get_locations_for_day(self, day_of_week):
        """Get all locations where student has lessons on this day."""
        result = []
        for sl in self.student_locations:
            if not sl.lesson_days:
                continue
            days = [d.strip() for d in sl.lesson_days.split(',')]
            if str(day_of_week) in days:
                result.append(sl)
        return result


class StudentLocation(Base):
    """Association table between Student and Location with schedule info."""
    __tablename__ = "student_locations"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    
    # Schedule for this location (e.g., "1,3" for Mon/Wed)
    lesson_days = Column(String(100), default="1,3")
    
    # JSON format for multi-time: {"1": "18:00", "3": "19:00", "default": "18:00"}
    lesson_times = Column(Text, default='{"default": "18:00"}')
    
    is_primary = Column(Boolean, default=False)  # Основной зал
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="student_locations")
    location = relationship("Location", back_populates="student_locations")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    
    attendance_date = Column(Date, nullable=False, default=date.today)
    attendance_time = Column(String(10))
    
    # Was this an extra lesson (not part of subscription)?
    is_extra = Column(Boolean, default=False)
    
    # Lesson counter was decremented
    lesson_counted = Column(Boolean, default=True)
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="attendances")
    location = relationship("Location", back_populates="attendances")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="BYN")
    payment_type = Column(String(50), default="subscription")  # subscription, single, etc.
    description = Column(String(500))
    paid_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    student = relationship("Student", back_populates="payments")


class CoachSettings(Base):
    """Coach preferences/settings."""
    __tablename__ = "coach_settings"

    id = Column(Integer, primary_key=True)
    coach_id = Column(Integer, ForeignKey("coaches.id"), nullable=False)
    
    # Notification settings
    notify_daily_summary = Column(Boolean, default=True)
    notify_low_lessons = Column(Boolean, default=True)
    notify_payment_due = Column(Boolean, default=True)
    
    # Default values for new students
    default_lessons_count = Column(Integer, default=8)
    default_lesson_duration = Column(Integer, default=90)
    default_currency = Column(String(10), default="BYN")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
