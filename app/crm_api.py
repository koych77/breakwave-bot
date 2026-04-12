"""CRM API endpoints for coach management."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, desc, func, delete, and_
from datetime import datetime, date, timedelta
from typing import Optional
import json
import logging

from app.database import async_session
from app.crm_models import Coach, Student, Location, StudentLocation, Attendance, Payment, CoachSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


# --- Auth helpers ---

async def get_current_coach(init_data: str):
    """Get coach from Telegram init data."""
    if not init_data:
        return None
    try:
        import urllib.parse
        parsed = dict(urllib.parse.parse_qsl(init_data))
        user = json.loads(parsed.get("user", "{}"))
        telegram_id = user.get("id")
        if not telegram_id:
            return None
        
        async with async_session() as s:
            result = await s.execute(
                select(Coach).where(Coach.telegram_id == telegram_id, Coach.is_active == True)
            )
            coach = result.scalar_one_or_none()
            
            # Auto-create coach if not exists
            if not coach:
                coach = Coach(
                    telegram_id=telegram_id,
                    first_name=user.get("first_name"),
                    username=user.get("username"),
                    is_active=True
                )
                s.add(coach)
                await s.commit()
                await s.refresh(coach)
                
                # Create default settings
                settings = CoachSettings(coach_id=coach.id)
                s.add(settings)
                await s.commit()
            
            return coach
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return None


# --- Coach endpoints ---

@router.post("/coach/me")
async def get_coach_profile(request: Request):
    """Get current coach profile."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    return {
        "id": coach.id,
        "first_name": coach.first_name,
        "username": coach.username,
        "phone": coach.phone,
    }


@router.post("/coach/settings")
async def get_coach_settings(request: Request):
    """Get coach settings."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(CoachSettings).where(CoachSettings.coach_id == coach.id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = CoachSettings(coach_id=coach.id)
            s.add(settings)
            await s.commit()
        
        return {
            "notify_daily_summary": settings.notify_daily_summary,
            "notify_low_lessons": settings.notify_low_lessons,
            "notify_payment_due": settings.notify_payment_due,
            "default_lessons_count": settings.default_lessons_count,
            "default_lesson_duration": settings.default_lesson_duration,
            "default_currency": settings.default_currency,
        }


@router.post("/coach/settings/update")
async def update_coach_settings(request: Request):
    """Update coach settings."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(CoachSettings).where(CoachSettings.coach_id == coach.id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = CoachSettings(coach_id=coach.id)
            s.add(settings)
        
        for field in ["notify_daily_summary", "notify_low_lessons", "notify_payment_due",
                      "default_lessons_count", "default_lesson_duration", "default_currency"]:
            if field in body:
                setattr(settings, field, body[field])
        
        await s.commit()
        return {"success": True}


# --- Locations endpoints ---

@router.post("/locations")
async def list_locations(request: Request):
    """Get all coach locations."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Location).where(
                Location.coach_id == coach.id,
                Location.is_active == True
            ).order_by(Location.name)
        )
        locations = result.scalars().all()
        
        return [{
            "id": loc.id,
            "name": loc.name,
            "address": loc.address,
        } for loc in locations]


@router.post("/locations/create")
async def create_location(request: Request):
    """Create new location."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, 400)
    
    async with async_session() as s:
        loc = Location(
            coach_id=coach.id,
            name=name,
            address=body.get("address", ""),
            is_active=True
        )
        s.add(loc)
        await s.commit()
        
        return {"success": True, "id": loc.id, "name": loc.name}


@router.post("/locations/{location_id}/update")
async def update_location(location_id: int, request: Request):
    """Update location."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Location).where(
                Location.id == location_id,
                Location.coach_id == coach.id
            )
        )
        loc = result.scalar_one_or_none()
        if not loc:
            return JSONResponse({"error": "not found"}, 404)
        
        if "name" in body:
            loc.name = body["name"].strip()
        if "address" in body:
            loc.address = body.get("address", "")
        
        await s.commit()
        return {"success": True}


@router.post("/locations/{location_id}/delete")
async def delete_location(location_id: int, request: Request):
    """Soft delete location."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Location).where(
                Location.id == location_id,
                Location.coach_id == coach.id
            )
        )
        loc = result.scalar_one_or_none()
        if not loc:
            return JSONResponse({"error": "not found"}, 404)
        
        loc.is_active = False
        await s.commit()
        return {"success": True}


# --- Students endpoints ---

@router.post("/students")
async def list_students(request: Request):
    """Get all coach students."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    active_only = body.get("active_only", True)
    
    async with async_session() as s:
        q = select(Student).where(Student.coach_id == coach.id)
        if active_only:
            q = q.where(Student.is_active == True)
        q = q.order_by(Student.name)
        
        result = await s.execute(q)
        students = result.scalars().all()
        
        result_list = []
        for st in students:
            # Get locations for student
            loc_result = await s.execute(
                select(StudentLocation, Location).join(
                    Location, StudentLocation.location_id == Location.id
                ).where(StudentLocation.student_id == st.id)
            )
            locations = []
            for sl, loc in loc_result.all():
                locations.append({
                    "id": loc.id,
                    "name": loc.name,
                    "lesson_days": sl.lesson_days,
                    "lesson_times": sl.lesson_times,
                    "is_primary": sl.is_primary,
                })
            
            result_list.append({
                "id": st.id,
                "name": st.name,
                "phone": st.phone,
                "age": st.age,
                "subscription_start": st.subscription_start.isoformat() if st.subscription_start else None,
                "subscription_end": st.subscription_end.isoformat() if st.subscription_end else None,
                "lessons_count": st.lessons_count,
                "lessons_remaining": st.lessons_remaining,
                "lesson_duration": st.lesson_duration,
                "amount": st.amount,
                "currency": st.currency,
                "is_paid": st.is_paid,
                "is_unlimited": st.is_unlimited,
                "is_active": st.is_active,
                "locations": locations,
            })
        
        return result_list


@router.post("/students/create")
async def create_student(request: Request):
    """Create new student."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, 400)
    
    async with async_session() as s:
        # Get default settings
        settings_result = await s.execute(
            select(CoachSettings).where(CoachSettings.coach_id == coach.id)
        )
        settings = settings_result.scalar_one_or_none()
        
        default_lessons = settings.default_lessons_count if settings else 8
        default_duration = settings.default_lesson_duration if settings else 90
        default_currency = settings.default_currency if settings else "BYN"
        
        # Parse subscription dates
        sub_start = None
        sub_end = None
        if body.get("subscription_start"):
            try:
                sub_start = datetime.fromisoformat(body["subscription_start"]).date()
            except:
                pass
        if body.get("subscription_end"):
            try:
                sub_end = datetime.fromisoformat(body["subscription_end"]).date()
            except:
                pass
        
        # Create student
        student = Student(
            coach_id=coach.id,
            name=name,
            phone=body.get("phone"),
            age=body.get("age"),
            subscription_start=sub_start,
            subscription_end=sub_end,
            lessons_count=body.get("lessons_count", default_lessons),
            lessons_remaining=body.get("lessons_count", default_lessons),
            lesson_duration=body.get("lesson_duration", default_duration),
            amount=body.get("amount", 0.0),
            currency=body.get("currency", default_currency),
            is_paid=body.get("is_paid", False),
            is_unlimited=body.get("is_unlimited", False),
            is_active=True,
        )
        s.add(student)
        await s.flush()
        
        # Add location associations
        locations_data = body.get("locations", [])
        for loc_data in locations_data:
            sl = StudentLocation(
                student_id=student.id,
                location_id=loc_data["location_id"],
                lesson_days=loc_data.get("lesson_days", "1,3"),
                lesson_times=json.dumps(loc_data.get("lesson_times", {"default": "18:00"})),
                is_primary=loc_data.get("is_primary", False),
            )
            s.add(sl)
        
        await s.commit()
        return {"success": True, "id": student.id}


@router.post("/students/{student_id}")
async def get_student(student_id: int, request: Request):
    """Get student details."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Student).where(
                Student.id == student_id,
                Student.coach_id == coach.id
            )
        )
        st = result.scalar_one_or_none()
        if not st:
            return JSONResponse({"error": "not found"}, 404)
        
        # Get locations
        loc_result = await s.execute(
            select(StudentLocation, Location).join(
                Location, StudentLocation.location_id == Location.id
            ).where(StudentLocation.student_id == st.id)
        )
        locations = []
        for sl, loc in loc_result.all():
            locations.append({
                "id": loc.id,
                "name": loc.name,
                "lesson_days": sl.lesson_days,
                "lesson_times": json.loads(sl.lesson_times) if sl.lesson_times else {"default": "18:00"},
                "is_primary": sl.is_primary,
            })
        
        # Get attendance history
        att_result = await s.execute(
            select(Attendance, Location).outerjoin(
                Location, Attendance.location_id == Location.id
            ).where(
                Attendance.student_id == st.id
            ).order_by(desc(Attendance.attendance_date))
        )
        attendance = []
        for att, loc in att_result.all():
            attendance.append({
                "id": att.id,
                "date": att.attendance_date.isoformat(),
                "time": att.attendance_time,
                "location": loc.name if loc else None,
                "is_extra": att.is_extra,
                "lesson_counted": att.lesson_counted,
            })
        
        return {
            "id": st.id,
            "name": st.name,
            "phone": st.phone,
            "age": st.age,
            "subscription_start": st.subscription_start.isoformat() if st.subscription_start else None,
            "subscription_end": st.subscription_end.isoformat() if st.subscription_end else None,
            "lessons_count": st.lessons_count,
            "lessons_remaining": st.lessons_remaining,
            "lesson_duration": st.lesson_duration,
            "amount": st.amount,
            "currency": st.currency,
            "is_paid": st.is_paid,
            "is_unlimited": st.is_unlimited,
            "is_active": st.is_active,
            "locations": locations,
            "attendance": attendance,
        }


@router.post("/students/{student_id}/update")
async def update_student(student_id: int, request: Request):
    """Update student."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Student).where(
                Student.id == student_id,
                Student.coach_id == coach.id
            )
        )
        st = result.scalar_one_or_none()
        if not st:
            return JSONResponse({"error": "not found"}, 404)
        
        # Update basic fields
        for field in ["name", "phone", "age", "is_paid", "is_unlimited", "is_active"]:
            if field in body:
                setattr(st, field, body[field])
        
        if "lessons_count" in body:
            st.lessons_count = body["lessons_count"]
        if "lessons_remaining" in body:
            st.lessons_remaining = body["lessons_remaining"]
        if "lesson_duration" in body:
            st.lesson_duration = body["lesson_duration"]
        if "amount" in body:
            st.amount = body["amount"]
        
        # Update dates
        if "subscription_start" in body:
            try:
                st.subscription_start = datetime.fromisoformat(body["subscription_start"]).date()
            except:
                st.subscription_start = None
        if "subscription_end" in body:
            try:
                st.subscription_end = datetime.fromisoformat(body["subscription_end"]).date()
            except:
                st.subscription_end = None
        
        # Update locations
        if "locations" in body:
            # Remove existing
            await s.execute(
                delete(StudentLocation).where(StudentLocation.student_id == st.id)
            )
            # Add new
            for loc_data in body["locations"]:
                sl = StudentLocation(
                    student_id=st.id,
                    location_id=loc_data["location_id"],
                    lesson_days=loc_data.get("lesson_days", "1,3"),
                    lesson_times=json.dumps(loc_data.get("lesson_times", {"default": "18:00"})),
                    is_primary=loc_data.get("is_primary", False),
                )
                s.add(sl)
        
        await s.commit()
        return {"success": True}


@router.post("/students/{student_id}/delete")
async def delete_student(student_id: int, request: Request):
    """Soft delete student."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    async with async_session() as s:
        result = await s.execute(
            select(Student).where(
                Student.id == student_id,
                Student.coach_id == coach.id
            )
        )
        st = result.scalar_one_or_none()
        if not st:
            return JSONResponse({"error": "not found"}, 404)
        
        st.is_active = False
        await s.commit()
        return {"success": True}


# --- Attendance endpoints ---

@router.post("/attendance/mark")
async def mark_attendance(request: Request):
    """Mark student attendance."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    student_id = body.get("student_id")
    location_id = body.get("location_id")
    attendance_date = body.get("date")
    attendance_time = body.get("time")
    
    if not student_id:
        return JSONResponse({"error": "student_id required"}, 400)
    
    async with async_session() as s:
        # Verify student belongs to coach
        result = await s.execute(
            select(Student).where(
                Student.id == student_id,
                Student.coach_id == coach.id
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            return JSONResponse({"error": "student not found"}, 404)
        
        # Parse date
        if attendance_date:
            try:
                att_date = datetime.fromisoformat(attendance_date).date()
            except:
                att_date = date.today()
        else:
            att_date = date.today()
        
        # Check if already marked
        existing = await s.execute(
            select(Attendance).where(
                Attendance.student_id == student_id,
                Attendance.attendance_date == att_date
            )
        )
        if existing.scalar_one_or_none():
            return JSONResponse({"error": "already marked for this date"}, 400)
        
        # Decrement lessons remaining (if not unlimited and not extra)
        lesson_counted = False
        if not student.is_unlimited and not body.get("is_extra", False):
            if student.lessons_remaining > 0:
                student.lessons_remaining -= 1
                lesson_counted = True
        
        # Create attendance record
        att = Attendance(
            student_id=student_id,
            location_id=location_id,
            attendance_date=att_date,
            attendance_time=attendance_time,
            is_extra=body.get("is_extra", False),
            lesson_counted=lesson_counted,
            notes=body.get("notes"),
        )
        s.add(att)
        await s.commit()
        
        return {
            "success": True,
            "attendance_id": att.id,
            "lessons_remaining": student.lessons_remaining,
            "lesson_counted": lesson_counted,
        }


@router.post("/attendance/unmark")
async def unmark_attendance(request: Request):
    """Remove attendance mark."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    attendance_id = body.get("attendance_id")
    if not attendance_id:
        return JSONResponse({"error": "attendance_id required"}, 400)
    
    async with async_session() as s:
        result = await s.execute(
            select(Attendance, Student).join(
                Student, Attendance.student_id == Student.id
            ).where(
                Attendance.id == attendance_id,
                Student.coach_id == coach.id
            )
        )
        row = result.one_or_none()
        if not row:
            return JSONResponse({"error": "not found"}, 404)
        
        att, student = row
        
        # Restore lesson count if it was counted
        if att.lesson_counted and not student.is_unlimited:
            student.lessons_remaining += 1
        
        await s.delete(att)
        await s.commit()
        
        return {"success": True, "lessons_remaining": student.lessons_remaining}


@router.post("/attendance/today")
async def get_today_attendance(request: Request):
    """Get today's attendance."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    target_date = body.get("date")
    if target_date:
        try:
            target = datetime.fromisoformat(target_date).date()
        except:
            target = date.today()
    else:
        target = date.today()
    
    async with async_session() as s:
        result = await s.execute(
            select(Attendance, Student, Location).join(
                Student, Attendance.student_id == Student.id
            ).outerjoin(
                Location, Attendance.location_id == Location.id
            ).where(
                Student.coach_id == coach.id,
                Attendance.attendance_date == target
            ).order_by(Attendance.attendance_time)
        )
        
        attendance = []
        for att, student, loc in result.all():
            attendance.append({
                "id": att.id,
                "student_id": student.id,
                "student_name": student.name,
                "location_id": loc.id if loc else None,
                "location_name": loc.name if loc else None,
                "time": att.attendance_time,
                "is_extra": att.is_extra,
            })
        
        return {"date": target.isoformat(), "attendance": attendance}


# --- Dashboard/Summary endpoints ---

@router.post("/dashboard")
async def get_dashboard(request: Request):
    """Get CRM dashboard data."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    today = date.today()
    weekday = today.weekday()
    
    async with async_session() as s:
        # Get all active students with their locations
        result = await s.execute(
            select(Student).where(
                Student.coach_id == coach.id,
                Student.is_active == True
            )
        )
        students = result.scalars().all()
        
        total_students = len(students)
        unlimited_count = sum(1 for s in students if s.is_unlimited)
        low_lessons = []
        payments_due = []
        today_lessons = []
        
        for student in students:
            # Check low lessons
            remaining = student.lessons_remaining or 0
            if not student.is_unlimited and remaining <= 2:
                low_lessons.append({
                    "id": student.id,
                    "name": student.name,
                    "lessons_remaining": remaining,
                })
            
            # Check payment due
            if student.subscription_end:
                days_left = (student.subscription_end - today).days
                if days_left <= 3:
                    payments_due.append({
                        "id": student.id,
                        "name": student.name,
                        "days_left": days_left,
                        "expired": days_left < 0,
                    })
            
            # Get today's lessons
            student_locations = await s.execute(
                select(StudentLocation, Location).join(
                    Location, StudentLocation.location_id == Location.id
                ).where(StudentLocation.student_id == student.id)
            )
            
            for sl, loc in student_locations.all():
                if not sl.lesson_days:
                    continue
                days = [d.strip() for d in sl.lesson_days.split(",")]
                if str(weekday) in days:
                    # Parse lesson time for this day
                    try:
                        times = json.loads(sl.lesson_times or '{}')
                        lesson_time = times.get(str(weekday), times.get('default', '18:00'))
                    except:
                        lesson_time = '18:00'
                    
                    today_lessons.append({
                        "student_id": student.id,
                        "student_name": student.name,
                        "location_id": loc.id,
                        "location_name": loc.name,
                        "time": lesson_time,
                        "lessons_remaining": student.lessons_remaining if not student.is_unlimited else None,
                        "is_unlimited": student.is_unlimited,
                    })
        
        # Sort by time
        today_lessons.sort(key=lambda x: x["time"])
        
        return {
            "total_students": total_students,
            "unlimited_count": unlimited_count,
            "low_lessons": low_lessons,
            "payments_due": payments_due,
            "today_lessons": today_lessons,
            "today_date": today.isoformat(),
        }


@router.post("/search")
async def search_students(request: Request):
    """Search students by name or phone."""
    body = await request.json()
    coach = await get_current_coach(body.get("initData", ""))
    if not coach:
        return JSONResponse({"error": "unauthorized"}, 403)
    
    query = body.get("q", "").strip().lower()
    if not query:
        return []
    
    async with async_session() as s:
        result = await s.execute(
            select(Student).where(
                Student.coach_id == coach.id,
                Student.is_active == True,
                func.lower(Student.name).contains(query) |
                func.lower(Student.phone).contains(query)
            ).order_by(Student.name)
        )
        students = result.scalars().all()
        
        return [{
            "id": st.id,
            "name": st.name,
            "phone": st.phone,
            "lessons_remaining": st.lessons_remaining,
            "is_unlimited": st.is_unlimited,
        } for st in students]
