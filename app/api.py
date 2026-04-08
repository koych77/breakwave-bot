from fastapi import FastAPI, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, func, desc
from contextlib import asynccontextmanager
from app.database import async_session, init_db
from app.models import Season, Participant, Event, Result, Subscriber
from app.config import WEBAPP_DIR, DATA_DIR
import os


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


# --- Serve webapp ---

app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


@app.get("/")
async def root():
    return FileResponse(str(WEBAPP_DIR / "index.html"))
