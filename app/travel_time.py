from __future__ import annotations

import json
import math
import os
import threading
import time as time_module
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import integrations_ui
from . import main


ORS_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

TRANSPORT_LABELS = {
    "car": "Auto",
    "transit": "Bus/Bahn",
    "bicycle": "Fahrrad",
}

_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    now = time_module.monotonic()
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None
        expires, value = item
        if expires <= now:
            _cache.pop(key, None)
            return None
        return value


def _cache_set(key: str, value, ttl_seconds: int) -> None:
    with _cache_lock:
        _cache[key] = (time_module.monotonic() + ttl_seconds, value)


def _json_request(url: str, *, headers: dict[str, str] | None = None, payload: dict | None = None, timeout: float = 7.0) -> dict:
    body = None
    merged_headers = {"Accept": "application/json", "User-Agent": "Alarm-HUB/1.0"}
    if headers:
        merged_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=merged_headers, method="POST" if body is not None else "GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_duration_seconds(value: str | None) -> float:
    raw = (value or "").strip()
    if not raw.endswith("s"):
        return 0.0
    try:
        return max(0.0, float(raw[:-1]))
    except ValueError:
        return 0.0


def _ors_geocode(address: str) -> tuple[float, float] | None:
    if not ORS_API_KEY or not address.strip():
        return None
    key = f"ors-geocode:{address.strip().casefold()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    query = urlencode({"text": address.strip(), "size": 1})
    try:
        data = _json_request(
            f"https://api.openrouteservice.org/geocode/search?{query}",
            headers={"Authorization": ORS_API_KEY},
        )
        coordinates = data["features"][0]["geometry"]["coordinates"]
        result = (float(coordinates[0]), float(coordinates[1]))
    except Exception:
        result = None
    _cache_set(key, result, 24 * 60 * 60)
    return result


def _ors_duration_minutes(origin: str, destination: str, mode: str) -> int | None:
    if mode not in {"car", "bicycle"} or not ORS_API_KEY:
        return None

    key = f"ors-route:{mode}:{origin.strip().casefold()}:{destination.strip().casefold()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    start = _ors_geocode(origin)
    end = _ors_geocode(destination)
    if not start or not end:
        _cache_set(key, None, 15 * 60)
        return None

    profile = "driving-car" if mode == "car" else "cycling-regular"
    try:
        data = _json_request(
            f"https://api.openrouteservice.org/v2/directions/{profile}",
            headers={"Authorization": ORS_API_KEY},
            payload={"coordinates": [[start[0], start[1]], [end[0], end[1]]]},
        )
        seconds = float(data["routes"][0]["summary"]["duration"])
        result = max(1, math.ceil(seconds / 60.0))
    except Exception:
        result = None
    _cache_set(key, result, 12 * 60 * 60 if result is not None else 15 * 60)
    return result


def _google_transit_departure(origin: str, destination: str, arrival_at: datetime) -> tuple[datetime, int] | None:
    if not GOOGLE_MAPS_API_KEY:
        return None

    arrival_utc = arrival_at.astimezone(timezone.utc).replace(microsecond=0)
    cache_key = (
        f"google-transit:{origin.strip().casefold()}:{destination.strip().casefold()}:"
        f"{arrival_utc.strftime('%Y-%m-%dT%H:%M')}"
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    payload = {
        "origin": {"address": origin.strip()},
        "destination": {"address": destination.strip()},
        "travelMode": "TRANSIT",
        "arrivalTime": arrival_utc.isoformat().replace("+00:00", "Z"),
        "languageCode": "de-DE",
        "regionCode": "DE",
    }
    field_mask = (
        "routes.duration,"
        "routes.legs.steps.staticDuration,"
        "routes.legs.steps.transitDetails.stopDetails.departureTime,"
        "routes.legs.steps.transitDetails.stopDetails.arrivalTime"
    )

    try:
        data = _json_request(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            headers={
                "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
                "X-Goog-FieldMask": field_mask,
            },
            payload=payload,
        )
        route = data["routes"][0]
        steps = route.get("legs", [{}])[0].get("steps", [])

        pre_transit_seconds = 0.0
        first_departure: datetime | None = None
        for step in steps:
            details = step.get("transitDetails") or {}
            stop_details = details.get("stopDetails") or {}
            departure_text = stop_details.get("departureTime")
            if departure_text:
                first_departure = datetime.fromisoformat(departure_text.replace("Z", "+00:00"))
                break
            pre_transit_seconds += _parse_duration_seconds(step.get("staticDuration"))

        if first_departure is not None:
            route_start = first_departure - timedelta(seconds=pre_transit_seconds)
            lead_seconds = max(60.0, (arrival_utc - route_start.astimezone(timezone.utc)).total_seconds())
            result = (route_start, max(1, math.ceil(lead_seconds / 60.0)))
        else:
            duration_seconds = _parse_duration_seconds(route.get("duration"))
            if duration_seconds <= 0:
                result = None
            else:
                route_start = arrival_utc - timedelta(seconds=duration_seconds)
                result = (route_start, max(1, math.ceil(duration_seconds / 60.0)))
    except Exception:
        result = None

    _cache_set(cache_key, result, 30 * 60 if result is not None else 10 * 60)
    return result


def _commute_for_shift(settings: integrations_ui.CommuteSettings, shift: main.WebCommShift) -> dict | None:
    destination = (shift.start_location or "").strip()
    origin = (settings.home_address or "").strip()
    if not settings.enabled or not origin or not destination:
        return None

    mode = settings.transport_mode
    if mode in {"car", "bicycle"}:
        minutes = _ors_duration_minutes(origin, destination, mode)
        if minutes is None:
            return None
        return {"minutes": minutes, "departure": None, "mode": mode}

    if mode == "transit":
        result = _google_transit_departure(origin, destination, shift.start)
        if result is None:
            return None
        departure, minutes = result
        return {"minutes": minutes, "departure": departure, "mode": mode}

    return None


def upcoming_with_commute(user: main.User, db: Session, limit: int = 50) -> list[dict]:
    tz = ZoneInfo(user.timezone or main.DEFAULT_TZ)
    now = datetime.now(tz)
    items: list[dict] = []

    for alarm in db.scalars(
        select(main.Alarm).where(main.Alarm.user_id == user.id, main.Alarm.enabled.is_(True))
    ).all():
        at = main._next_manual_occurrence(alarm, user, now)
        if at:
            items.append(
                {
                    "source": "manual",
                    "id": alarm.id,
                    "name": alarm.name,
                    "at": at.isoformat(),
                    "date": at.strftime("%d.%m.%Y"),
                    "time": at.strftime("%H:%M"),
                }
            )

    integration = db.scalar(
        select(main.WebCommIntegration).where(
            main.WebCommIntegration.user_id == user.id,
            main.WebCommIntegration.enabled.is_(True),
        )
    )
    if integration:
        settings = db.scalar(
            select(integrations_ui.CommuteSettings).where(
                integrations_ui.CommuteSettings.user_id == user.id
            )
        )
        shifts = db.scalars(
            select(main.WebCommShift)
            .where(
                main.WebCommShift.user_id == user.id,
                main.WebCommShift.start > now.astimezone(timezone.utc),
            )
            .order_by(main.WebCommShift.start)
            .limit(40)
        ).all()

        for shift in shifts:
            local_start = shift.start.astimezone(tz)
            commute = _commute_for_shift(settings, shift) if settings else None
            for offset in main._offsets(integration.offsets):
                if commute and commute.get("departure") is not None:
                    route_departure = commute["departure"].astimezone(tz)
                    at = route_departure - timedelta(minutes=offset)
                else:
                    commute_minutes = int(commute["minutes"]) if commute else 0
                    at = local_start - timedelta(minutes=offset + commute_minutes)

                if at <= now:
                    continue

                item = {
                    "source": "webcomm",
                    "id": shift.id,
                    "name": f"{shift.title} · {offset} min vorher",
                    "at": at.isoformat(),
                    "date": at.strftime("%d.%m.%Y"),
                    "time": at.strftime("%H:%M"),
                    "shift_start": local_start.isoformat(),
                    "service_number": shift.service_number,
                    "start_location": shift.start_location,
                }
                if commute:
                    item["commute_minutes"] = int(commute["minutes"])
                    item["transport_mode"] = commute["mode"]
                    item["transport_label"] = TRANSPORT_LABELS.get(commute["mode"], commute["mode"])
                elif settings and settings.enabled:
                    item["commute_unavailable"] = True
                items.append(item)

    items.sort(key=lambda value: value["at"])
    return items[:limit]


main._upcoming = upcoming_with_commute
