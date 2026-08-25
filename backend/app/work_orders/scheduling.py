"""Assign a technician and a concrete slot to a work order.

A technician is free when the factory's roster says they are on shift, minus
their standing busy blocks, minus every slot another work order already holds.
That last part is what makes the promise true: a proposal becomes a booking the
moment the work order exists, so the next work order cannot be given the same
hour.

Maintenance is kept out of production hours when a slot exists before the
priority deadline, and booked inside them — flagged as downtime — when none
does. A critical job that cannot wait for the line to stop is still a job.

ponytail: shift times are treated as UTC, matching how readings are stored.
Give the factory a timezone when one runs outside UTC.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from ..assets.models import BusinessContext
from .models import WorkOrder

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# How long a job of each priority may wait for a slot before we stop looking.
DEADLINE_DAYS = {"critical": 2, "high": 5, "medium": 14, "low": 30}
DEFAULT_DURATION_H = 2.0
# Candidate start times are tried on this grid. Half an hour is fine enough for
# a maintenance window and keeps the scan cheap.
STEP = timedelta(minutes=30)

# A work order in one of these states no longer holds its slot.
RELEASED = {"cancelled", "rejected", "completed"}


def _parse(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _day_intervals(week: dict | None, day: str) -> list[tuple[time, time]]:
    """Read one weekday out of a work_time/occupied_time map.

    work_time holds one interval per day, occupied_time a list — accept both so
    the same reader serves shifts, busy blocks and the production schedule.
    """
    raw = (week or {}).get(day)
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start, end = _parse(item.get("start")), _parse(item.get("end"))
        if start and end and end > start:
            out.append((start, end))
    return out


def _at(day: datetime, moment: time) -> datetime:
    return datetime.combine(day.date(), moment, tzinfo=timezone.utc)


def _overlaps(start: datetime, end: datetime, blocks: list[tuple[datetime, datetime]]) -> bool:
    return any(start < other_end and other_start < end for other_start, other_end in blocks)


def bookings(db, factory_id: str, exclude_order_id: str | None = None) -> dict[str, list[tuple[datetime, datetime]]]:
    """Slots already held, per technician."""
    query = select(WorkOrder).where(
        WorkOrder.factory_id == factory_id,
        WorkOrder.assigned_technician.is_not(None),
        WorkOrder.scheduled_start.is_not(None),
        WorkOrder.status.not_in(RELEASED),
    )
    held: dict[str, list[tuple[datetime, datetime]]] = {}
    for order in db.scalars(query):
        if exclude_order_id and order.id == exclude_order_id:
            continue
        start, end = _as_utc(order.scheduled_start), _as_utc(order.scheduled_end)
        if start and end:
            held.setdefault(order.assigned_technician, []).append((start, end))
    return held


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite hands back naive datetimes even from timezone=True columns.
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def conflicting_order(db, factory_id, technician, start, end, exclude_order_id=None) -> WorkOrder | None:
    """The work order already holding this technician over [start, end), if any."""
    for order in db.scalars(select(WorkOrder).where(
        WorkOrder.factory_id == factory_id,
        WorkOrder.assigned_technician == technician,
        WorkOrder.scheduled_start.is_not(None),
        WorkOrder.status.not_in(RELEASED),
    )):
        if exclude_order_id and order.id == exclude_order_id:
            continue
        other_start, other_end = _as_utc(order.scheduled_start), _as_utc(order.scheduled_end)
        if other_start and other_end and start < other_end and other_start < end:
            return order
    return None


def _first_slot(technician, duration, held, production, horizon_start, horizon_end, avoid_production):
    """Earliest slot for one technician, or None."""
    work_time = technician.get("work_time") or {}
    occupied = technician.get("occupied_time") or {}
    day = horizon_start
    while day <= horizon_end:
        name = DAYS[day.weekday()]
        busy = [(_at(day, s), _at(day, e)) for s, e in _day_intervals(occupied, name)]
        busy += held
        running = [(_at(day, s), _at(day, e)) for s, e in _day_intervals(production, name)]
        for shift_start, shift_end in _day_intervals(work_time, name):
            candidate = max(_at(day, shift_start), horizon_start)
            last = _at(day, shift_end)
            while candidate + duration <= last:
                finish = candidate + duration
                if not _overlaps(candidate, finish, busy) and not (
                    avoid_production and _overlaps(candidate, finish, running)
                ):
                    return candidate, finish, _overlaps(candidate, finish, running)
                candidate += STEP
        day = (day + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return None


def _matches_skills(technician: dict, skills: list[str]) -> bool:
    haystack = f"{technician.get('role', '')} {technician.get('specialty') or ''}".lower()
    return any(skill.lower() in haystack for skill in skills if skill)


def propose(db, factory_id: str, details: dict, priority: str, now: datetime | None = None,
            exclude_order_id: str | None = None) -> dict:
    """Pick a technician and a slot. Always returns a verdict, never raises.

    `technician` is None when nothing fits — the work order is still created,
    and a coordinator schedules it by hand.
    """
    now = now or datetime.now(timezone.utc)
    context = db.get(BusinessContext, factory_id)
    roster = list((context.technicians_json if context else None) or [])
    if not roster:
        return {"technician": None, "reason": "no_technicians"}

    production = (context.production_schedule or {}).get("work_time") if context else None
    duration = timedelta(hours=float(details.get("est_duration_h") or DEFAULT_DURATION_H))
    skills = details.get("required_skills") or []
    horizon_end = now + timedelta(days=DEADLINE_DAYS.get(priority, 14))
    held = bookings(db, factory_id, exclude_order_id)

    skilled = [t for t in roster if _matches_skills(t, skills)]
    # Skill first: a matched technician later in the week beats an unmatched one
    # tomorrow. Only when no matched technician fits at all does anyone do.
    for pool in ([skilled, roster] if skilled else [roster]):
        for avoid_production in (True, False):
            best = None
            for technician in pool:
                name = technician.get("name")
                if not name:
                    continue
                found = _first_slot(technician, duration, held.get(name, []), production,
                                    now, horizon_end, avoid_production)
                if found and (best is None or found[0] < best[1]):
                    best = (technician, *found)
            if best:
                technician, start, end, during_production = best
                return {
                    "technician": technician["name"],
                    "start": start,
                    "end": end,
                    "during_production": during_production,
                    "skill_matched": _matches_skills(technician, skills),
                }
    return {"technician": None, "reason": "no_slot_before_deadline"}
