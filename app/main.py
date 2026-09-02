from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://alarmhub:alarmhub@alarm-hub-db:5432/alarmhub")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-before-public-deployment")
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "true").lower() in {"1", "true", "yes", "on"}
DEFAULT_TZ = os.getenv("DEFAULT_TIMEZONE", "Europe/Berlin")

pwd = CryptContext(schemes=["argon2"], deprecated="auto")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    timezone: Mapped[str] = mapped_column(String(64), default=DEFAULT_TZ)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Alarm(Base):
    __tablename__ = "alarms"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    hour: Mapped[int] = mapped_column(Integer)
    minute: Mapped[int] = mapped_column(Integer)
    weekdays: Mapped[str] = mapped_column(String(32), default="0,1,2,3,4,5,6")
    one_time_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(back_populates="alarms")


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Gerät")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebCommIntegration(Base):
    __tablename__ = "webcomm_integrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    offsets: Mapped[str] = mapped_column(String(255), default="120,90")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WebCommShift(Base):
    __tablename__ = "webcomm_shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    external_uid: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Schicht")
    service_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    end_location: Mapped[str | None] = mapped_column(String(160), nullable=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Alarm Hub", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, https_only=SESSION_HTTPS_ONLY, same_site="lax", max_age=60 * 60 * 24 * 30)


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def _check_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf") or ""
    if not expected or not hmac.compare_digest(expected, token or ""):
        raise HTTPException(403, "Ungültiges Formular-Token.")


def current_user(request: Request, db: Session = Depends(db_session)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Bitte anmelden.")
    user = db.get(User, int(user_id))
    if not user:
        request.session.clear()
        raise HTTPException(401, "Bitte anmelden.")
    return user


# Merged into the base <style> block below. Kept as its own constant (rather
# than inlined) because it was originally a standalone theme layer.
THEME_CSS = r"""
<style id="alarmhub-ui-refresh">
:root {
  color-scheme: dark;
  --bg: #0b0f14;
  --surface: #111821;
  --surface-soft: #151e28;
  --surface-hover: #1a2632;
  --border: #263241;
  --border-soft: #1d2834;
  --text: #edf3f8;
  --muted: #94a3b3;
  --accent: #5da8ff;
  --accent-soft: rgba(93, 168, 255, .12);
  --success: #2fbf71;
  --danger: #d95454;
  --shadow: 0 18px 48px rgba(0, 0, 0, .20);
  --radius: 16px;
}

* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% -10%, rgba(67, 120, 190, .11), transparent 34rem),
    var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

nav {
  max-width: 1120px !important;
  margin: 0 auto !important;
  padding: 14px 22px !important;
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
  flex-wrap: wrap !important;
  border: 0 !important;
}
nav::before {
  content: "Alarm-HUB";
  margin-right: auto;
  font-size: 1.02rem;
  font-weight: 760;
  letter-spacing: -.02em;
  color: var(--text);
}
nav > a:first-of-type { display: none; }
nav a {
  color: var(--muted) !important;
  padding: 8px 11px;
  border-radius: 10px;
  font-size: .91rem;
  font-weight: 570;
  transition: background .15s ease, color .15s ease;
}
nav a:hover {
  color: var(--text) !important;
  background: var(--surface-hover);
}

body > nav {
  position: sticky;
  top: 0;
  z-index: 20;
  max-width: none !important;
  padding-left: max(22px, calc((100vw - 1120px) / 2)) !important;
  padding-right: max(22px, calc((100vw - 1120px) / 2)) !important;
  background: rgba(11, 15, 20, .88);
  border-bottom: 1px solid rgba(38, 50, 65, .72) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

main {
  max-width: 1040px !important;
  margin: 0 auto !important;
  padding: 38px 22px 70px !important;
}
main > h1 {
  margin: 0 0 26px;
  font-size: clamp(1.8rem, 4vw, 2.45rem);
  line-height: 1.1;
  letter-spacing: -.035em;
}

h2, h3 { letter-spacing: -.02em; }
h2 { margin-top: 0; font-size: 1.22rem; }
h3 { margin-top: 0; font-size: 1.02rem; }
p { margin: .65rem 0; }

section {
  background: var(--surface) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: var(--radius) !important;
  padding: 22px !important;
  margin: 0 0 18px !important;
  box-shadow: none !important;
}
section + section { margin-top: 18px !important; }

.card {
  background: var(--surface-soft) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: 13px !important;
  padding: 16px 17px !important;
  margin: 14px 0 !important;
  box-shadow: none !important;
}
.card:last-child { margin-bottom: 0 !important; }

/* Long beginner guides stay readable instead of looking like dozens of heavy panels. */
#ios .card, #android .card {
  background: transparent !important;
  border: 0 !important;
  border-top: 1px solid var(--border-soft) !important;
  border-radius: 0 !important;
  padding: 18px 0 4px !important;
  margin: 14px 0 0 !important;
}
#ios .card:first-of-type, #android .card:first-of-type {
  border-top: 0 !important;
  padding-top: 4px !important;
}

a {
  color: var(--accent);
  text-decoration: none;
}
a:hover { text-decoration: none; }

.row {
  display: flex !important;
  gap: 10px !important;
  flex-wrap: wrap !important;
  align-items: center !important;
}

input:not([type="checkbox"]):not([type="radio"]), select, textarea {
  width: 100%;
  max-width: 560px;
  background: #0d141c !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 10px 12px !important;
  min-height: 42px;
  outline: none;
  transition: border-color .15s ease, box-shadow .15s ease;
}
input:not([type="checkbox"]):not([type="radio"]):focus, select:focus, textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft);
}
input[type="checkbox"], input[type="radio"] {
  width: 18px !important;
  height: 18px !important;
  min-height: 0 !important;
  max-width: none !important;
  padding: 0 !important;
  margin: 0 8px 0 0 !important;
  accent-color: #2477d4;
  vertical-align: middle;
  cursor: pointer;
}
label {
  display: block !important;
  margin: 13px 0 !important;
  color: #cbd6e1;
  font-size: .92rem;
  font-weight: 560;
}
label input:not([type="checkbox"]):not([type="radio"]), label select, label textarea {
  display: block;
  margin-top: 6px;
}
label:has(> input[type="checkbox"]), label:has(> input[type="radio"]) {
  display: flex !important;
  align-items: center;
  gap: 2px;
  width: fit-content;
  cursor: pointer;
}

button, .button, a.button {
  appearance: none;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  padding: 9px 14px !important;
  min-height: 40px;
  background: #2477d4 !important;
  color: #fff !important;
  font-weight: 650;
  cursor: pointer;
  transition: transform .12s ease, filter .12s ease;
}
button:hover, .button:hover, a.button:hover { filter: brightness(1.08); }
button:active { transform: translateY(1px); }
button.danger {
  background: transparent !important;
  border-color: rgba(217, 84, 84, .42) !important;
  color: #ff9696 !important;
}

.alarm {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  gap: 16px !important;
  padding: 15px 2px !important;
  border-top: 1px solid var(--border-soft) !important;
}
.alarm:first-of-type { border-top: 0 !important; }
.alarm b { font-size: .98rem; }

.muted {
  color: var(--muted) !important;
  font-size: .9rem;
}

code {
  color: #c6dcf5;
  background: #0b1219;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  padding: 2px 6px;
  word-break: break-word !important;
}
pre {
  overflow-x: auto;
  padding: 14px;
  background: #0b1219;
  border: 1px solid var(--border-soft);
  border-radius: 11px;
}
pre code { border: 0; padding: 0; background: transparent; }

ol, ul { padding-left: 1.35rem; }
li { margin: .42rem 0; }
hr { border: 0; border-top: 1px solid var(--border-soft); margin: 22px 0; }

details {
  background: var(--surface-soft);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 13px 15px;
  margin: 14px 0;
}
summary {
  cursor: pointer;
  font-weight: 680;
  color: #dbe7f1;
}
details[open] summary { margin-bottom: 14px; }

@media (max-width: 720px) {
  body > nav {
    position: static;
    padding: 12px 14px !important;
  }
  nav::before { width: 100%; margin-bottom: 4px; }
  nav a { padding: 7px 9px; font-size: .86rem; }
  main { padding: 28px 14px 54px !important; }
  main > h1 { margin-bottom: 20px; }
  section { padding: 17px !important; border-radius: 14px !important; }
  .alarm { align-items: flex-start !important; flex-direction: column; }
  .alarm form, .alarm button { width: 100%; }
}
</style>
"""


def _layout(title: str, body: str, user: User | None = None) -> str:
    nav = "<a href='/'>Alarm Hub</a>"
    if user:
        nav += (
            "<a href='/'>Dashboard</a>"
            "<a href='/alarms'>Meine Wecker</a>"
            "<a href='/integrations'>Integrationen</a>"
            "<a href='/webcomm-direct'>WebComm direkt</a>"
            "<a href='/webcomm-data'>WebComm-Daten</a>"
            "<a href='/devices'>Geräte / API</a>"
            "<a href='/guides'>Anleitungen</a>"
            "<a href='/logout'>Abmelden</a>"
        )
    else:
        nav += "<a href='/login'>Anmelden</a><a href='/register'>Registrieren</a>"
    head = (
        "<style>\n"
        ":root{color-scheme:dark}body{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#e6edf3;margin:0}"
        "main,nav{max-width:980px;margin:auto;padding:20px}nav{display:flex;gap:14px;flex-wrap:wrap;border-bottom:1px solid #30363d}"
        "a{color:#58a6ff;text-decoration:none}section,.card{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:18px;margin:16px 0}"
        "input,select,button{box-sizing:border-box;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:9px;padding:10px}"
        "label{display:block;margin:10px 0}button{background:#238636;cursor:pointer}button.danger{background:#8b2525}"
        ".row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.muted{color:#8b949e}"
        ".alarm{display:flex;justify-content:space-between;gap:12px;align-items:center;border-top:1px solid #30363d;padding:12px 0}"
        "code{word-break:break-all}</style>" + THEME_CSS
    )
    return f"<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title} · Alarm Hub</title>{head}</head><body><nav>{nav}</nav><main><h1>{title}</h1>{body}</main></body></html>"


def _next_manual_occurrence(alarm: Alarm, user: User, now: datetime) -> datetime | None:
    tz = ZoneInfo(user.timezone or DEFAULT_TZ)
    now = now.astimezone(tz)
    if alarm.one_time_date:
        candidate = datetime.combine(alarm.one_time_date, time(alarm.hour, alarm.minute), tzinfo=tz)
        return candidate if candidate > now else None
    weekdays = {int(x) for x in alarm.weekdays.split(",") if x.strip().isdigit() and 0 <= int(x) <= 6}
    for add in range(8):
        d = now.date() + timedelta(days=add)
        if d.weekday() not in weekdays:
            continue
        candidate = datetime.combine(d, time(alarm.hour, alarm.minute), tzinfo=tz)
        if candidate > now:
            return candidate
    return None


def _offsets(raw: str) -> list[int]:
    result = []
    for part in (raw or "").replace(";", ",").split(","):
        try:
            value = int(part.strip())
        except ValueError:
            continue
        if 0 <= value <= 1440 and value not in result:
            result.append(value)
    return result


def _upcoming(user: User, db: Session, limit: int = 50) -> list[dict]:
    tz = ZoneInfo(user.timezone or DEFAULT_TZ)
    now = datetime.now(tz)
    items: list[dict] = []
    for alarm in db.scalars(select(Alarm).where(Alarm.user_id == user.id, Alarm.enabled.is_(True))).all():
        at = _next_manual_occurrence(alarm, user, now)
        if at:
            items.append({"source": "manual", "id": alarm.id, "name": alarm.name, "at": at.isoformat(), "date": at.strftime("%d.%m.%Y"), "time": at.strftime("%H:%M")})
    integration = db.scalar(select(WebCommIntegration).where(WebCommIntegration.user_id == user.id, WebCommIntegration.enabled.is_(True)))
    if integration:
        shifts = db.scalars(select(WebCommShift).where(WebCommShift.user_id == user.id, WebCommShift.start > now.astimezone(timezone.utc)).order_by(WebCommShift.start).limit(40)).all()
        for shift in shifts:
            local_start = shift.start.astimezone(tz)
            for offset in _offsets(integration.offsets):
                at = local_start - timedelta(minutes=offset)
                if at > now:
                    items.append({"source": "webcomm", "id": shift.id, "name": f"{shift.title} · {offset} min vorher", "at": at.isoformat(), "date": at.strftime("%d.%m.%Y"), "time": at.strftime("%H:%M"), "shift_start": local_start.isoformat(), "service_number": shift.service_number})
    items.sort(key=lambda x: x["at"])
    return items[:limit]


def _token_user(authorization: str | None, db: Session, model) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer-Token fehlt.")
    raw = authorization.split(" ", 1)[1].strip()
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(model).where(model.token_hash == digest))
    if not token:
        raise HTTPException(401, "Ungültiges Token.")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(401, "Benutzer nicht gefunden.")
    if isinstance(token, DeviceToken):
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
    return user


@app.get("/health")
def health():
    return {"ok": True, "service": "alarm-hub"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(db_session)):
    user = db.get(User, int(request.session["user_id"])) if request.session.get("user_id") else None
    if not user:
        return HTMLResponse(_layout("Alarm Hub", "<section><h2>Deine Wecker. Deine Integrationen.</h2><p>Erstelle beliebig viele eigene Wecker. WebComm ist optional und kann als zusätzliche automatische Alarmquelle verbunden werden.</p><div class='row'><a href='/register'>Konto erstellen</a><a href='/login'>Anmelden</a></div></section>"))
    upcoming = _upcoming(user, db, 10)
    rows = "".join(f"<div class='alarm'><div><b>{x['date']} · {x['time']}</b> · {x['name']}<br><span class='muted'>{x['source']}</span></div></div>" for x in upcoming) or "<p class='muted'>Keine kommenden Wecker.</p>"
    return HTMLResponse(_layout("Dashboard", f"<section><h2>Nächste Wecker</h2>{rows}</section>", user))


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    token = _csrf(request)
    return HTMLResponse(_layout("Registrieren", f"<section><form method='post'><input type='hidden' name='csrf' value='{token}'><label>E-Mail<input type='email' name='email' required></label><label>Passwort<input type='password' name='password' minlength='10' required></label><label>Zeitzone<input name='timezone_name' value='{DEFAULT_TZ}' required></label><button>Registrieren</button></form></section>"))


@app.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...), timezone_name: str = Form(DEFAULT_TZ), csrf: str = Form(...), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    email = email.strip().lower()
    if len(password) < 10:
        raise HTTPException(400, "Passwort muss mindestens 10 Zeichen lang sein.")
    try:
        ZoneInfo(timezone_name)
    except Exception:
        raise HTTPException(400, "Unbekannte Zeitzone.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-Mail ist bereits registriert.")
    user = User(email=email, password_hash=pwd.hash(password), timezone=timezone_name)
    db.add(user); db.commit(); db.refresh(user)
    request.session.clear(); request.session["user_id"] = user.id
    return RedirectResponse("/", 303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    token = _csrf(request)
    return HTMLResponse(_layout("Anmelden", f"<section><form method='post'><input type='hidden' name='csrf' value='{token}'><label>E-Mail<input type='email' name='email' required></label><label>Passwort<input type='password' name='password' required></label><button>Anmelden</button></form></section>"))


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), csrf: str = Form(...), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not pwd.verify(password, user.password_hash):
        raise HTTPException(401, "Anmeldung fehlgeschlagen.")
    request.session.clear(); request.session["user_id"] = user.id
    return RedirectResponse("/", 303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


@app.get("/alarms", response_class=HTMLResponse)
def alarms_page(request: Request, user: User = Depends(current_user), db: Session = Depends(db_session)):
    token = _csrf(request)
    alarms = db.scalars(select(Alarm).where(Alarm.user_id == user.id).order_by(Alarm.hour, Alarm.minute)).all()
    rows = "".join(
        f"<div class='alarm'><div><b>{a.hour:02d}:{a.minute:02d} · {a.name}</b>"
        f"<br><span class='muted'>{'einmalig ' + str(a.one_time_date) if a.one_time_date else 'Wochentage ' + a.weekdays}"
        f" · {'aktiv' if a.enabled else 'inaktiv'}</span></div>"
        f"<form method='post' action='/alarms/{a.id}/delete'>"
        f"<input type='hidden' name='csrf' value='{token}'>"
        f"<button class='danger'>Löschen</button></form></div>"
        for a in alarms
    ) or "<p class='muted'>Noch keine manuellen Wecker.</p>"

    body = f"""
    <section>
      <h2>Wecker hinzufügen</h2>
      <p class='muted'>Hier kannst du einen manuellen Wecker anlegen. Alle kommenden manuellen und WebComm-Wecker siehst du gesammelt im <a href='/'>Dashboard</a>.</p>
      <form method='post' action='/alarms'>
        <input type='hidden' name='csrf' value='{token}'>
        <label>Name<input name='name' required placeholder='z. B. Frühschicht'></label>
        <label>Uhrzeit<input type='time' name='alarm_time' required></label>
        <label>Wochentage (0=Mo … 6=So)<input name='weekdays' value='0,1,2,3,4,5,6'></label>
        <label>Einmaliges Datum (optional)<input type='date' name='one_time_date'></label>
        <button>Wecker speichern</button>
      </form>
    </section>

    <section>
      <h2>Manuelle Wecker</h2>
      <p class='muted'>Hier verwaltest und löschst du ausschließlich selbst angelegte Wecker. Automatisch erzeugte WebComm-Wecker bleiben im Dashboard.</p>
      {rows}
    </section>
    """
    return HTMLResponse(_layout("Meine Wecker", body, user))


@app.post("/alarms")
def add_alarm(request: Request, name: str = Form(...), alarm_time: str = Form(...), weekdays: str = Form("0,1,2,3,4,5,6"), one_time_date: str = Form(""), csrf: str = Form(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    try:
        hh, mm = [int(x) for x in alarm_time.split(":", 1)]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except Exception:
        raise HTTPException(400, "Ungültige Uhrzeit.")
    try:
        one_date = date.fromisoformat(one_time_date) if one_time_date else None
    except ValueError:
        raise HTTPException(400, "Ungültiges Datum.")
    normalized_days = ",".join(str(x) for x in sorted({int(x) for x in weekdays.replace(";", ",").split(",") if x.strip().isdigit() and 0 <= int(x) <= 6}))
    if not one_date and not normalized_days:
        raise HTTPException(400, "Mindestens ein Wochentag ist erforderlich.")
    db.add(Alarm(user_id=user.id, name=name.strip()[:120], hour=hh, minute=mm, weekdays=normalized_days, one_time_date=one_date, enabled=True)); db.commit()
    return RedirectResponse("/alarms", 303)


@app.post("/alarms/{alarm_id}/delete")
def delete_alarm(alarm_id: int, request: Request, csrf: str = Form(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id, Alarm.user_id == user.id))
    if not alarm:
        raise HTTPException(404, "Wecker nicht gefunden.")
    db.delete(alarm); db.commit()
    return RedirectResponse("/alarms", 303)


@app.post("/integrations/webcomm", response_class=HTMLResponse)
def configure_webcomm(request: Request, offsets: str = Form("120,90"), csrf: str = Form(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    parsed = _offsets(offsets)
    if not parsed:
        raise HTTPException(400, "Mindestens eine gültige Vorlaufzeit erforderlich.")
    raw = secrets.token_urlsafe(40)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    integration = db.scalar(select(WebCommIntegration).where(WebCommIntegration.user_id == user.id))
    if not integration:
        integration = WebCommIntegration(user_id=user.id); db.add(integration)
    integration.enabled = True; integration.offsets = ",".join(str(x) for x in parsed); integration.token_hash = digest; integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    body = f"<section><h2>WebComm verbunden</h2><p>Dieses Sync-Token wird nur jetzt angezeigt:</p><p><code>{raw}</code></p><p>Speichere es im WebComm Calendar Sync. Es werden nur Schichtdaten übertragen, keine WebComm-Zugangsdaten.</p><a href='/integrations'>Zurück</a></section>"
    return HTMLResponse(_layout("WebComm Token", body, user))


@app.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, user: User = Depends(current_user), db: Session = Depends(db_session)):
    token = _csrf(request)
    devices = db.scalars(select(DeviceToken).where(DeviceToken.user_id == user.id).order_by(DeviceToken.created_at.desc())).all()
    rows = "".join(
        f"<div class='alarm'><div><b>{d.name}</b><br><span class='muted'>erstellt {d.created_at.isoformat()}"
        f"{' · zuletzt benutzt '+d.last_used_at.isoformat() if d.last_used_at else ' · noch nie benutzt'}</span></div>"
        f"<form method='post' action='/devices/{d.id}/delete'><input type='hidden' name='csrf' value='{token}'><button class='danger'>Token löschen</button></form></div>"
        for d in devices
    ) or "<p class='muted'>Noch keine Geräte-Tokens.</p>"
    body = f"<section><h2>Geräte-Token erstellen</h2><form method='post' action='/devices'><input type='hidden' name='csrf' value='{token}'><label>Name<input name='name' placeholder='z. B. iPhone' required></label><button>Token erzeugen</button></form><p class='muted'>Das Token wird nur einmal vollständig angezeigt.</p></section><section><h2>Vorhandene Geräte</h2>{rows}</section>"
    return HTMLResponse(_layout("Geräte / API", body, user))


@app.post("/devices", response_class=HTMLResponse)
def create_device(request: Request, name: str = Form(...), csrf: str = Form(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    raw = secrets.token_urlsafe(40)
    db.add(DeviceToken(user_id=user.id, name=name.strip()[:120] or "Gerät", token_hash=hashlib.sha256(raw.encode()).hexdigest()))
    db.commit()
    body = f"<section><h2>Geräte-Token erstellt</h2><p>Dieses Token wird nur jetzt angezeigt:</p><p><code>{raw}</code></p><p>Nutze es als <code>Authorization: Bearer …</code> für <code>/api/v1/me/upcoming</code>.</p><a href='/devices'>Zurück</a></section>"
    return HTMLResponse(_layout("Geräte-Token", body, user))


@app.post("/devices/{device_id}/delete")
def delete_device_token(device_id: int, request: Request, csrf: str = Form(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    _check_csrf(request, csrf)
    device = db.scalar(select(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.user_id == user.id))
    if not device:
        raise HTTPException(404, "Geräte-Token nicht gefunden.")
    db.delete(device)
    db.commit()
    return RedirectResponse("/devices", 303)


@app.get("/api/v1/me/upcoming")
def upcoming_api(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    if authorization:
        user = _token_user(authorization, db, DeviceToken)
    else:
        user = current_user(request, db)
    return {"ok": True, "timezone": user.timezone, "alarms": _upcoming(user, db, 50)}


@app.post("/api/v1/integrations/webcomm/shifts")
async def webcomm_sync(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(db_session)):
    user = _token_user(authorization, db, WebCommIntegration)
    payload = await request.json()
    shifts = payload.get("shifts") if isinstance(payload, dict) else None
    if not isinstance(shifts, list):
        raise HTTPException(400, "shifts muss eine Liste sein.")
    db.query(WebCommShift).filter(WebCommShift.user_id == user.id).delete()
    imported = 0
    for item in shifts[:500]:
        try:
            start = datetime.fromisoformat(str(item.get("start")))
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(user.timezone or DEFAULT_TZ))
            end = datetime.fromisoformat(str(item.get("end"))) if item.get("end") else None
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=ZoneInfo(user.timezone or DEFAULT_TZ))
        except Exception:
            continue
        db.add(WebCommShift(user_id=user.id, external_uid=str(item.get("uid") or f"{item.get('day')}-{item.get('service_number')}-{start.isoformat()}")[:255], title=str(item.get("title") or "Schicht")[:160], service_number=str(item.get("service_number"))[:64] if item.get("service_number") is not None else None, start=start.astimezone(timezone.utc), end=end.astimezone(timezone.utc) if end else None, start_location=str(item.get("start_location"))[:160] if item.get("start_location") else None, end_location=str(item.get("end_location"))[:160] if item.get("end_location") else None))
        imported += 1
    integration = db.scalar(select(WebCommIntegration).where(WebCommIntegration.user_id == user.id))
    if integration:
        integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "imported": imported}
