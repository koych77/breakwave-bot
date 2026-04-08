import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import Season, Participant, Event, Result

SCHOOL_EVENTS = [
    {"name": "Winter", "emoji": "❄️", "multiplier": 1, "sort_order": 1},
    {"name": "Spring", "emoji": "🌸", "multiplier": 1, "sort_order": 2},
    {"name": "Summer", "emoji": "☀️", "multiplier": 1, "sort_order": 3},
    {"name": "Autumn", "emoji": "🍂", "multiplier": 1, "sort_order": 4},
    {"name": "Final", "emoji": "🔥", "multiplier": 2, "sort_order": 5},
]

SHEET_MAP = {
    "❄️ Winter": "Winter",
    "🌸 Spring": "Spring",
    "☀️ Summer": "Summer",
    "🍂 Autumn": "Autumn",
    "🔥 Final": "Final",
}


def _cell(ws, row, col):
    v = ws.cell(row=row, column=col).value
    return v


def parse_excel(file_path: str) -> dict:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    data = {"participants": [], "events": {}}

    # Parse participants from "👥 Участники" sheet
    part_sheet = None
    for sn in wb.sheetnames:
        if "Участники" in sn:
            part_sheet = wb[sn]
            break

    if part_sheet:
        for row in range(4, part_sheet.max_row + 1):
            num = _cell(part_sheet, row, 2)
            name = _cell(part_sheet, row, 3)
            nomination = _cell(part_sheet, row, 4)
            if not name or not nomination:
                continue
            data["participants"].append({
                "num": int(num) if num else row - 3,
                "name": str(name).strip(),
                "nomination": str(nomination).strip(),
            })

    # Parse event results
    for sheet_name, event_name in SHEET_MAP.items():
        ws = None
        for sn in wb.sheetnames:
            if event_name in sn:
                ws = wb[sn]
                break
        if not ws:
            continue

        results = []
        has_data = False

        # Find the points column by header
        points_col = 9
        for col in range(1, ws.max_column + 1):
            hdr = _cell(ws, 3, col)
            if hdr and "Баллы" in str(hdr):
                points_col = col
                break

        for row in range(4, ws.max_row + 1):
            name = _cell(ws, row, 3)
            if not name:
                continue
            points_val = _cell(ws, row, points_col)
            points = int(points_val) if points_val else 0
            if points > 0:
                has_data = True

            main_place = _cell(ws, row, 5)
            extra1 = _cell(ws, row, 6)
            extra2 = _cell(ws, row, 7)
            extra3 = _cell(ws, row, 8)

            results.append({
                "name": str(name).strip(),
                "main_place": float(main_place) if main_place is not None else None,
                "extra_nom1": float(extra1) if extra1 is not None else None,
                "extra_nom2": float(extra2) if extra2 is not None else None,
                "extra_nom3": float(extra3) if extra3 is not None else None,
                "points": points,
            })

        data["events"][event_name] = {
            "results": results,
            "has_data": has_data,
        }

    wb.close()
    return data


async def import_excel_to_db(session: AsyncSession, file_path: str, season_name: str = None):
    data = parse_excel(file_path)

    # Get or create current season
    result = await session.execute(select(Season).where(Season.is_current == True))
    season = result.scalar_one_or_none()

    if not season:
        season = Season(name=season_name or "Сезон 2025/2026", is_current=True)
        session.add(season)
        await session.flush()

    # Clear old data for this season
    await session.execute(delete(Result).where(
        Result.participant_id.in_(
            select(Participant.id).where(Participant.season_id == season.id)
        )
    ))
    await session.execute(delete(Participant).where(Participant.season_id == season.id))

    old_events = await session.execute(
        select(Event).where(Event.season_id == season.id, Event.event_type == "school")
    )
    for ev in old_events.scalars().all():
        await session.execute(delete(Result).where(Result.event_id == ev.id))
        await session.delete(ev)

    await session.flush()

    # Create participants
    participant_map = {}
    for p in data["participants"]:
        part = Participant(name=p["name"], nomination=p["nomination"], season_id=season.id)
        session.add(part)
        await session.flush()
        participant_map[p["name"]] = part

    # Create events and results
    updated_events = []
    for ev_info in SCHOOL_EVENTS:
        ev_name = ev_info["name"]
        ev_data = data["events"].get(ev_name, {"results": [], "has_data": False})

        status = "completed" if ev_data["has_data"] else "upcoming"

        event = Event(
            name=ev_name,
            emoji=ev_info["emoji"],
            event_type="school",
            season_id=season.id,
            status=status,
            multiplier=ev_info["multiplier"],
            sort_order=ev_info["sort_order"],
        )
        session.add(event)
        await session.flush()

        if ev_data["has_data"]:
            updated_events.append(ev_name)

        for r in ev_data["results"]:
            part = participant_map.get(r["name"])
            if not part:
                continue
            res = Result(
                participant_id=part.id,
                event_id=event.id,
                main_place=r["main_place"],
                extra_nom1=r["extra_nom1"],
                extra_nom2=r["extra_nom2"],
                extra_nom3=r["extra_nom3"],
                points=r["points"],
            )
            session.add(res)

    await session.commit()
    return {"season_id": season.id, "participants": len(participant_map), "updated_events": updated_events}
