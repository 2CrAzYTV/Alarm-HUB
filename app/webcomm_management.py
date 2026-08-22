from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Boolean, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import direct_webcomm as dw
from . import main


class DirectWebCommSchedule(main.Base):
    __tablename__ = "direct_webcomm_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    window_start: Mapped[str] = mapped_column(String(5), default="07:00")
    window_end: Mapped[str] = mapped_column(String(5), default="18:00")


scheduler = AsyncIOScheduler()


def _minutes(value: str) -> int:
    try:
        h, m = [int(x) for x in value.split(":", 1)]
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except Exception:
        pass
    raise ValueError("Ungültige Uhrzeit")


def _window_open(schedule: DirectWebCommSchedule, tz_name: str) -> bool:
    now = datetime.now(ZoneInfo(tz_name or main.DEFAULT_TZ))
    cur = now.hour * 60 + now.minute
    start = _minutes(schedule.window_start)
    end = _minutes(schedule.window_end)
    return start <= cur <= end if start <= end else cur >= start or cur <= end


async def _run_scheduled_imports() -> None:
    db = main.SessionLocal()
    try:
        schedules = db.scalars(select(DirectWebCommSchedule).where(DirectWebCommSchedule.enabled.is_(True))).all()
        now = datetime.now(timezone.utc)
        for schedule in schedules:
            user = db.get(main.User, schedule.user_id)
            cred = db.scalar(select(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == schedule.user_id))
            if not user or not cred or not _window_open(schedule, user.timezone):
                continue
            if cred.last_sync_at and (now - cred.last_sync_at.astimezone(timezone.utc)).total_seconds() < max(5, schedule.interval_minutes) * 60:
                continue
            try:
                await dw.import_direct(user, cred, db)
            except Exception as exc:
                db.rollback()
                cred = db.scalar(select(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == schedule.user_id))
                if cred:
                    cred.last_error = str(exc)[:1000]
                    db.commit()
    finally:
        db.close()


# Extend the existing FastAPI lifespan so the scheduler starts with Alarm-HUB.
_original_lifespan = main.app.router.lifespan_context


@asynccontextmanager
async def _lifespan(app):
    main.Base.metadata.create_all(main.engine)
    scheduler.add_job(_run_scheduled_imports, "interval", minutes=1, id="direct-webcomm-sync", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    try:
        async with _original_lifespan(app):
            yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


main.app.router.lifespan_context = _lifespan


# Add a dedicated management entry for both API and direct-import users.
_original_layout = main._layout


def _layout(title: str, body: str, user: main.User | None = None) -> str:
    page = _original_layout(title, body, user)
    if user and "href='/webcomm-data'" not in page:
        page = page.replace("<a href='/devices'>Geräte / API</a>", "<a href='/webcomm-data'>WebComm-Daten</a><a href='/devices'>Geräte / API</a>")
    return page


main._layout = _layout


@main.app.get("/webcomm-data", response_class=HTMLResponse)
def webcomm_data_page(request: Request, user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    token = main._csrf(request)
    integration = db.scalar(select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user.id))
    cred = db.scalar(select(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == user.id))
    schedule = db.scalar(select(DirectWebCommSchedule).where(DirectWebCommSchedule.user_id == user.id))
    shifts = db.scalars(select(main.WebCommShift).where(main.WebCommShift.user_id == user.id)).all()
    direct_count = sum(1 for x in shifts if (x.external_uid or "").startswith("webcomm-direct-"))
    api_count = len(shifts) - direct_count
    source = "keine Daten"
    if direct_count and api_count:
        source = "gemischt"
    elif direct_count:
        source = "Direktimport"
    elif api_count:
        source = "API / WebComm-Calendar-Sync"
    enabled = schedule.enabled if schedule else False
    interval = schedule.interval_minutes if schedule else 30
    start = schedule.window_start if schedule else "07:00"
    end = schedule.window_end if schedule else "18:00"
    body = f"""
    <section><h2>Status</h2>
      <p><b>Aktuelle Quelle:</b> {source}</p>
      <p><b>Gespeicherte WebComm-Schichten:</b> {len(shifts)} · API: {api_count} · Direkt: {direct_count}</p>
      <p><b>Integration/API:</b> {'aktiviert' if integration and integration.enabled else 'nicht aktiviert'} · <b>Direkt-Zugangsdaten:</b> {'vorhanden' if cred else 'nicht vorhanden'}</p>
    </section>
    <section><h2>Automatischer Direktimport</h2>
      <p class='muted'>Nur für Benutzer ohne WebComm-Calendar-Sync gedacht. Der Direktimport prüft im gewählten Zeitfenster regelmäßig WebComm.</p>
      <form method='post' action='/webcomm-data/schedule'><input type='hidden' name='csrf' value='{token}'>
        <label><input type='checkbox' name='enabled' {'checked' if enabled else ''}> Automatischen Direktimport aktivieren</label>
        <label>Intervall in Minuten<input type='number' min='5' max='1440' name='interval_minutes' value='{interval}'></label>
        <label>Start Zeitfenster<input type='time' name='window_start' value='{start}' required></label>
        <label>Ende Zeitfenster<input type='time' name='window_end' value='{end}' required></label>
        <button>Automatik speichern</button>
      </form>
    </section>
    <section><h2>WebComm-Daten zurücksetzen</h2>
      <p>Löscht ausschließlich die importierten WebComm-Schichten und damit die daraus erzeugten Wecker. Integrationstoken, Direkt-Zugangsdaten und manuelle Wecker bleiben erhalten.</p>
      <form method='post' action='/webcomm-data/reset'><input type='hidden' name='csrf' value='{token}'><button class='danger'>WebComm-Daten löschen / resetten</button></form>
    </section>
    """
    return HTMLResponse(main._layout("WebComm-Daten", body, user))


@main.app.post("/webcomm-data/schedule")
def save_schedule(request: Request, enabled: str | None = Form(None), interval_minutes: int = Form(30), window_start: str = Form("07:00"), window_end: str = Form("18:00"), csrf: str = Form(...), user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    try:
        _minutes(window_start); _minutes(window_end)
    except ValueError:
        raise HTTPException(400, "Ungültiges Zeitfenster.")
    interval = max(5, min(1440, int(interval_minutes)))
    if enabled and not db.scalar(select(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == user.id)):
        raise HTTPException(400, "Für die Automatik müssen zuerst unter 'WebComm direkt' Zugangsdaten gespeichert werden.")
    schedule = db.scalar(select(DirectWebCommSchedule).where(DirectWebCommSchedule.user_id == user.id))
    if not schedule:
        schedule = DirectWebCommSchedule(user_id=user.id); db.add(schedule)
    schedule.enabled = enabled is not None
    schedule.interval_minutes = interval
    schedule.window_start = window_start
    schedule.window_end = window_end
    db.commit()
    return RedirectResponse("/webcomm-data", 303)


@main.app.post("/webcomm-data/reset")
def reset_webcomm_data(request: Request, csrf: str = Form(...), user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    deleted = db.query(main.WebCommShift).filter(main.WebCommShift.user_id == user.id).delete()
    db.commit()
    return RedirectResponse(f"/webcomm-data?reset={deleted}", 303)
