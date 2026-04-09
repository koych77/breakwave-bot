from fastapi import FastAPI, UploadFile, File, Query, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, func, desc, delete
from contextlib import asynccontextmanager
from app.database import async_session, init_db
from app.models import Season, Participant, Event, Result, Subscriber
from app.config import WEBAPP_DIR, DATA_DIR, BOT_TOKEN
from app.excel_parser import import_excel_to_db
import hmac
import hashlib
import json
import os
import logging
import urllib.parse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)


# --- Seasons ---

@app.get("/api/seasons")
async def get_seasons():
    async with async_session() as s:
        result = await s.execute(select(Season).order_by(desc(Season.created_at)))
        seasons = result.scalars().all()
        return [{"id": se.id, "name": se.name, "is_current": se.is_current} for se in seasons]


@app.get("/api/seasons/current")
async def get_current_season():
    async with async_session() as s:
        result = await s.execute(select(Season).where(Season.is_current == True))
        season = result.scalar_one_or_none()
        if not season:
            return {"id": None, "name": None}
        return {"id": season.id, "name": season.name}


# --- Ranking ---

@app.get("/api/ranking")
async def get_ranking(season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        participants = await s.execute(
            select(Participant).where(Participant.season_id == season_id)
        )
        participants = participants.scalars().all()

        ranking = []
        for p in participants:
            results = await s.execute(select(Result).where(Result.participant_id == p.id))
            total = sum(r.points for r in results.scalars().all())
            if total > 0:
                ranking.append({
                    "id": p.id,
                    "name": p.name,
                    "nomination": p.nomination,
                    "total_points": total,
                })

        ranking.sort(key=lambda x: x["total_points"], reverse=True)

        # Assign ranks (same rank for same points)
        current_rank = 1
        for i, item in enumerate(ranking):
            if i > 0 and ranking[i]["total_points"] < ranking[i - 1]["total_points"]:
                current_rank = i + 1
            item["rank"] = current_rank

        return ranking


@app.get("/api/ranking/nomination/{nomination}")
async def get_ranking_by_nomination(nomination: str, season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        participants = await s.execute(
            select(Participant).where(
                Participant.season_id == season_id,
                Participant.nomination == nomination
            )
        )
        participants = participants.scalars().all()

        ranking = []
        for p in participants:
            results = await s.execute(select(Result).where(Result.participant_id == p.id))
            total = sum(r.points for r in results.scalars().all())
            ranking.append({
                "id": p.id,
                "name": p.name,
                "nomination": p.nomination,
                "total_points": total,
            })

        ranking.sort(key=lambda x: x["total_points"], reverse=True)

        current_rank = 1
        for i, item in enumerate(ranking):
            if i > 0 and ranking[i]["total_points"] < ranking[i - 1]["total_points"]:
                current_rank = i + 1
            item["rank"] = current_rank

        return ranking


# --- Nominations ---

@app.get("/api/nominations")
async def get_nominations(season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        result = await s.execute(
            select(Participant.nomination, func.count(Participant.id))
            .where(Participant.season_id == season_id)
            .group_by(Participant.nomination)
        )
        rows = result.all()
        return [{"name": r[0], "count": r[1]} for r in rows]


# --- Events ---

@app.get("/api/events")
async def get_events(season_id: int = None, event_type: str = None):
    async with async_session() as s:
        q = select(Event)
        if event_type:
            q = q.where(Event.event_type == event_type)
        if season_id:
            if event_type == "external":
                q = q.where((Event.season_id == season_id) | (Event.season_id == None))
            else:
                q = q.where(Event.season_id == season_id)
        else:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if season and event_type != "external":
                q = q.where((Event.season_id == season.id) | (Event.season_id == None))

        q = q.order_by(Event.sort_order, Event.created_at)
        result = await s.execute(q)
        events = result.scalars().all()

        return [{
            "id": e.id,
            "name": e.name,
            "emoji": e.emoji,
            "event_type": e.event_type,
            "date": e.date,
            "time": e.time,
            "location": e.location,
            "description": e.description,
            "contact": e.contact,
            "fee": e.fee,
            "photo_path": e.photo_path,
            "status": e.status,
            "multiplier": e.multiplier,
        } for e in events]


@app.get("/api/events/{event_id}")
async def get_event(event_id: int):
    async with async_session() as s:
        result = await s.execute(select(Event).where(Event.id == event_id))
        e = result.scalar_one_or_none()
        if not e:
            return JSONResponse({"error": "not found"}, 404)
        return {
            "id": e.id,
            "name": e.name,
            "emoji": e.emoji,
            "event_type": e.event_type,
            "date": e.date,
            "time": e.time,
            "location": e.location,
            "description": e.description,
            "contact": e.contact,
            "fee": e.fee,
            "photo_path": e.photo_path,
            "status": e.status,
            "multiplier": e.multiplier,
        }


@app.get("/api/events/{event_id}/results")
async def get_event_results(event_id: int):
    async with async_session() as s:
        result = await s.execute(
            select(Result, Participant)
            .join(Participant, Result.participant_id == Participant.id)
            .where(Result.event_id == event_id)
            .order_by(desc(Result.points))
        )
        rows = result.all()
        items = []
        current_rank = 1
        for i, (r, p) in enumerate(rows):
            if i > 0 and r.points < rows[i - 1][0].points:
                current_rank = i + 1
            items.append({
                "participant_id": p.id,
                "name": p.name,
                "nomination": p.nomination,
                "main_place": r.main_place,
                "points": r.points,
                "rank": current_rank,
            })
        return items


# --- Participants ---

@app.get("/api/participants")
async def get_participants(season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        result = await s.execute(
            select(Participant).where(Participant.season_id == season_id).order_by(Participant.name)
        )
        return [{"id": p.id, "name": p.name, "nomination": p.nomination} for p in result.scalars().all()]


@app.get("/api/participants/search")
async def search_participants(q: str = "", season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        result = await s.execute(
            select(Participant).where(
                Participant.season_id == season_id,
                Participant.name.ilike(f"%{q}%")
            ).order_by(Participant.name)
        )
        return [{"id": p.id, "name": p.name, "nomination": p.nomination} for p in result.scalars().all()]


@app.get("/api/participants/{participant_id}")
async def get_participant(participant_id: int):
    async with async_session() as s:
        result = await s.execute(select(Participant).where(Participant.id == participant_id))
        p = result.scalar_one_or_none()
        if not p:
            return JSONResponse({"error": "not found"}, 404)

        # Get all results with event info
        res = await s.execute(
            select(Result, Event)
            .join(Event, Result.event_id == Event.id)
            .where(Result.participant_id == p.id)
            .order_by(Event.sort_order)
        )
        rows = res.all()
        total = sum(r.points for r, e in rows)

        # Get overall rank
        all_participants = await s.execute(
            select(Participant).where(Participant.season_id == p.season_id)
        )
        ranking_data = []
        for ap in all_participants.scalars().all():
            ap_res = await s.execute(select(Result).where(Result.participant_id == ap.id))
            ap_total = sum(r.points for r in ap_res.scalars().all())
            ranking_data.append({"id": ap.id, "total": ap_total})

        ranking_data.sort(key=lambda x: x["total"], reverse=True)
        overall_rank = 1
        for i, rd in enumerate(ranking_data):
            if i > 0 and rd["total"] < ranking_data[i - 1]["total"]:
                overall_rank = i + 1
            if rd["id"] == p.id:
                break

        # Nomination rank
        nom_participants = [rd for rd in ranking_data if True]
        nom_res = await s.execute(
            select(Participant).where(
                Participant.season_id == p.season_id,
                Participant.nomination == p.nomination
            )
        )
        nom_ranking = []
        for np in nom_res.scalars().all():
            np_res = await s.execute(select(Result).where(Result.participant_id == np.id))
            np_total = sum(r.points for r in np_res.scalars().all())
            nom_ranking.append({"id": np.id, "total": np_total})
        nom_ranking.sort(key=lambda x: x["total"], reverse=True)
        nom_rank = 1
        for i, rd in enumerate(nom_ranking):
            if i > 0 and rd["total"] < nom_ranking[i - 1]["total"]:
                nom_rank = i + 1
            if rd["id"] == p.id:
                break

        return {
            "id": p.id,
            "name": p.name,
            "nomination": p.nomination,
            "total_points": total,
            "overall_rank": overall_rank,
            "nomination_rank": nom_rank,
            "events": [{
                "event_id": e.id,
                "event_name": e.name,
                "emoji": e.emoji,
                "multiplier": e.multiplier,
                "status": e.status,
                "points": r.points,
                "main_place": r.main_place,
            } for r, e in rows],
        }


# --- Dashboard ---

@app.get("/api/dashboard")
async def get_dashboard(season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return []
            season_id = season.id

        noms_res = await s.execute(
            select(Participant.nomination).where(Participant.season_id == season_id).distinct()
        )
        nominations = [r[0] for r in noms_res.all()]

        dashboard = []
        for nom in nominations:
            parts = await s.execute(
                select(Participant).where(
                    Participant.season_id == season_id,
                    Participant.nomination == nom
                )
            )
            ranking = []
            for p in parts.scalars().all():
                res = await s.execute(select(Result).where(Result.participant_id == p.id))
                total = sum(r.points for r in res.scalars().all())
                if total > 0:
                    ranking.append({"id": p.id, "name": p.name, "total_points": total})

            ranking.sort(key=lambda x: x["total_points"], reverse=True)

            top3 = []
            current_rank = 1
            for i, item in enumerate(ranking):
                if i > 0 and item["total_points"] < ranking[i - 1]["total_points"]:
                    current_rank = i + 1
                if current_rank > 3:
                    break
                item["rank"] = current_rank
                top3.append(item)

            dashboard.append({"nomination": nom, "top3": top3})

        return dashboard


# --- Stats ---

@app.get("/api/stats")
async def get_stats(season_id: int = None):
    async with async_session() as s:
        if not season_id:
            res = await s.execute(select(Season).where(Season.is_current == True))
            season = res.scalar_one_or_none()
            if not season:
                return {}
            season_id = season.id

        parts = await s.execute(select(Participant).where(Participant.season_id == season_id))
        participants = parts.scalars().all()

        total_points = 0
        max_points = 0
        points_list = []
        for p in participants:
            res = await s.execute(select(Result).where(Result.participant_id == p.id))
            t = sum(r.points for r in res.scalars().all())
            total_points += t
            points_list.append(t)
            if t > max_points:
                max_points = t

        noms = await s.execute(
            select(Participant.nomination).where(Participant.season_id == season_id).distinct()
        )

        avg_points = round(sum(points_list) / len(points_list), 1) if points_list else 0

        subs = await s.execute(select(func.count(Subscriber.id)).where(Subscriber.is_active == True))
        sub_count = subs.scalar() or 0

        return {
            "total_participants": len(participants),
            "total_nominations": len(noms.all()),
            "max_points": max_points,
            "avg_points": avg_points,
            "total_points": total_points,
            "subscribers": sub_count,
        }


# --- Admin helpers ---

def verify_telegram_init_data(init_data: str) -> dict | None:
    """Verify Telegram WebApp initData and extract user info."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        check_hash = parsed.pop("hash", "")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash == check_hash:
            user = json.loads(parsed.get("user", "{}"))
            return user
    except Exception as e:
        logger.warning(f"initData verification failed: {e}")
    return None


def check_admin(init_data: str) -> dict | None:
    """Check if the user from initData is an admin."""
    user = verify_telegram_init_data(init_data)
    if not user:
        return None
    from app.config import ADMIN_IDS
    from app.bot import _dynamic_admins
    user_id = user.get("id")
    if ADMIN_IDS and user_id in ADMIN_IDS:
        return user
    if user_id in _dynamic_admins:
        return user
    return None


# --- Admin API ---

@app.post("/api/admin/check")
async def admin_check(request: Request):
    body = await request.json()
    init_data = body.get("initData", "")
    user = check_admin(init_data)
    if user:
        return {"is_admin": True, "user": user}
    return {"is_admin": False}


@app.post("/api/admin/upload-excel")
async def admin_upload_excel(file: UploadFile = File(...), initData: str = Form("")):
    user = check_admin(initData)
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    if not file.filename.endswith((".xlsx", ".xls")):
        return JSONResponse({"error": "invalid file type"}, 400)

    file_path = DATA_DIR / "upload.xlsx"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        async with async_session() as s:
            result = await import_excel_to_db(s, str(file_path))
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Excel import error: {e}")
        return JSONResponse({"error": str(e)}, 500)


@app.post("/api/admin/events")
async def admin_create_event(request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    async with async_session() as s:
        res = await s.execute(select(Season).where(Season.is_current == True))
        season = res.scalar_one_or_none()

        event = Event(
            name=body["name"],
            emoji=body.get("emoji", "🏆"),
            event_type=body.get("event_type", "external"),
            season_id=season.id if season else None,
            date=body.get("date"),
            time=body.get("time"),
            location=body.get("location"),
            description=body.get("description"),
            fee=body.get("fee"),
            contact=body.get("contact"),
            status="upcoming",
            multiplier=int(body.get("multiplier", 1)),
            sort_order=100,
        )
        s.add(event)
        await s.commit()
        return {"success": True, "id": event.id}


@app.put("/api/admin/events/{event_id}")
async def admin_update_event(event_id: int, request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    async with async_session() as s:
        result = await s.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            return JSONResponse({"error": "not found"}, 404)

        for field in ["name", "emoji", "event_type", "date", "time", "location", "description", "fee", "contact", "status"]:
            if field in body:
                setattr(event, field, body[field])
        if "multiplier" in body:
            event.multiplier = int(body["multiplier"])
        await s.commit()
        return {"success": True}


@app.delete("/api/admin/events/{event_id}")
async def admin_delete_event(event_id: int, request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    async with async_session() as s:
        await s.execute(delete(Result).where(Result.event_id == event_id))
        await s.execute(delete(Event).where(Event.id == event_id))
        await s.commit()
    return {"success": True}


@app.post("/api/admin/participants")
async def admin_create_participant(request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    async with async_session() as s:
        res = await s.execute(select(Season).where(Season.is_current == True))
        season = res.scalar_one_or_none()
        if not season:
            return JSONResponse({"error": "no active season"}, 400)

        p = Participant(name=body["name"], nomination=body["nomination"], season_id=season.id)
        s.add(p)
        await s.flush()

        # Create empty results for all school events
        events = await s.execute(
            select(Event).where(Event.season_id == season.id, Event.event_type == "school")
        )
        for e in events.scalars().all():
            s.add(Result(participant_id=p.id, event_id=e.id, points=0))

        await s.commit()
        return {"success": True, "id": p.id}


@app.delete("/api/admin/participants/{participant_id}")
async def admin_delete_participant(participant_id: int, request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    async with async_session() as s:
        await s.execute(delete(Result).where(Result.participant_id == participant_id))
        await s.execute(delete(Participant).where(Participant.id == participant_id))
        await s.commit()
    return {"success": True}


@app.post("/api/admin/notify")
async def admin_notify(request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    text = body.get("text", "")
    if not text:
        return JSONResponse({"error": "empty text"}, 400)

    from app.bot import send_notification_to_all
    from app.config import WEBAPP_URL
    webapp_url = WEBAPP_URL or "https://web-production-7b91a.up.railway.app"
    count = await send_notification_to_all(text, webapp_url)
    return {"success": True, "sent": count}


@app.get("/api/admin/stats")
async def admin_stats():
    async with async_session() as s:
        subs_total = await s.execute(select(func.count(Subscriber.id)))
        subs_active = await s.execute(select(func.count(Subscriber.id)).where(Subscriber.is_active == True))

        res = await s.execute(select(Season).where(Season.is_current == True))
        season = res.scalar_one_or_none()

        parts_count = 0
        events_count = 0
        if season:
            pc = await s.execute(select(func.count(Participant.id)).where(Participant.season_id == season.id))
            parts_count = pc.scalar() or 0
            ec = await s.execute(select(func.count(Event.id)).where(Event.season_id == season.id))
            events_count = ec.scalar() or 0

        return {
            "subscribers_total": subs_total.scalar() or 0,
            "subscribers_active": subs_active.scalar() or 0,
            "participants": parts_count,
            "events": events_count,
        }


@app.post("/api/admin/season-new")
async def admin_new_season(request: Request):
    body = await request.json()
    user = check_admin(body.get("initData", ""))
    if not user:
        return JSONResponse({"error": "unauthorized"}, 403)

    name = body.get("name", "Новый сезон")
    async with async_session() as s:
        await s.execute(Season.__table__.update().where(Season.is_current == True).values(is_current=False))
        new_season = Season(name=name, is_current=True)
        s.add(new_season)
        await s.commit()
    return {"success": True}


# --- Serve webapp ---

app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


@app.get("/")
async def root():
    return FileResponse(str(WEBAPP_DIR / "index.html"))
