from __future__ import annotations

import base64
import hashlib
import html
import re
import shlex
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import pdfplumber
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from playwright.async_api import async_playwright
from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import main


class DirectWebCommCredential(main.Base):
    __tablename__ = "direct_webcomm_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(500))
    username: Mapped[str] = mapped_column(String(320))
    password_encrypted: Mapped[str] = mapped_column(String(2048))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}
HEADER_RE = re.compile(r"Dienstplan\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})", re.I)
DAY_ROW_RE = re.compile(r"^(\d{1,2})\.\s+[A-Za-zÄÖÜäöü]{2,3}\.\s+(.+?)\s*$")
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _fernet() -> Fernet:
    digest = hashlib.sha256(main.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Gespeichertes WebComm-Passwort kann nicht entschlüsselt werden. SECRET_KEY wurde möglicherweise geändert.") from exc


def _validate_url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(400, "WebComm-URL muss eine vollständige HTTPS-Adresse sein.")
    # Alarm-HUB may become internet-facing. Restrict direct browser access to the known WebComm host
    # instead of allowing arbitrary user-controlled URLs into the server's internal network.
    if parsed.hostname.casefold() != "webcomm.goevb.de":
        raise HTTPException(400, "Direkter Import ist derzeit aus Sicherheitsgründen auf webcomm.goevb.de beschränkt.")
    return value


def _service_title(service_number: int) -> str | None:
    if 100 <= service_number <= 199:
        return "Früh"
    if 200 <= service_number <= 299:
        return "Spät"
    if 300 <= service_number <= 349:
        return "Tagesdienst"
    if 350 <= service_number <= 399:
        return "Halbspät"
    if 400 <= service_number <= 499 or 700 <= service_number <= 799:
        return "Geteilt"
    if 600 <= service_number <= 699:
        return "Lehrgang"
    if 1000 <= service_number <= 7999:
        return "Sonderdienst"
    return None


def _parse_time(value: str):
    match = TIME_RE.match(value)
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_duty_pdf(pdf_path: Path, tz_name: str) -> list[dict]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join((page.extract_text(x_tolerance=2, y_tolerance=3) or "") for page in pdf.pages)

    header = HEADER_RE.search(text)
    if not header:
        raise RuntimeError("WebComm-Monat/Jahr im PDF-Kopf nicht gefunden.")
    month = MONTHS.get(header.group(1).lower())
    if not month:
        raise RuntimeError(f"Unbekannter WebComm-Monat: {header.group(1)}")
    year = int(header.group(2))
    tz = ZoneInfo(tz_name or main.DEFAULT_TZ)
    result: list[dict] = []

    for raw in text.splitlines():
        line = raw.strip()
        match = DAY_ROW_RE.match(line)
        if not match:
            continue
        fields = match.group(2).split()
        if len(fields) < 6 or not fields[1].isdigit():
            continue
        service = fields[1]
        title = _service_title(int(service))
        start_parts = _parse_time(fields[2])
        end_parts = _parse_time(fields[4])
        if not title or not start_parts or not end_parts:
            continue
        try:
            day = date(year, month, int(match.group(1)))
        except ValueError:
            continue
        start = datetime(day.year, day.month, day.day, start_parts[0], start_parts[1], tzinfo=tz)
        end = datetime(day.year, day.month, day.day, end_parts[0], end_parts[1], tzinfo=tz)
        if end <= start:
            end += timedelta(days=1)
        result.append({
            "uid": f"webcomm-direct-{day.isoformat()}-{service}",
            "title": title,
            "service_number": service,
            "start": start,
            "end": end,
            "start_location": fields[3],
            "end_location": fields[5],
        })
    return result


async def _visible(items):
    for item in items:
        try:
            if await item.count() and await item.first.is_visible():
                return item.first
        except Exception:
            pass
    return None


async def _click(page, purpose: str):
    choices = {
        "duty_plan": [
            page.locator("#ctl00_ctl00_lnk_1"),
            page.get_by_role("link", name="Dienstplan"),
            page.get_by_role("button", name="Dienstplan"),
            page.get_by_text("Dienstplan", exact=True),
        ],
        "menu": [
            page.locator("#Navbar"), page.locator('a[title="Menü"]'),
            page.locator('[aria-label*="Menü" i]'), page.locator('[title*="Menü" i]'),
            page.get_by_text("Menü", exact=True),
        ],
        "next": [
            page.locator("#ctl00_ctl00_navilink1"), page.locator('a[title="Nächster"]'),
            page.locator("a.link1-click"),
        ],
        "print": [
            page.locator("#ctl00_ctl00_navilink4"), page.locator('a[title="Drucken"]'),
            page.locator('a[href^="rosprint.aspx?"]'), page.locator('[title*="Druck" i]'),
        ],
    }[purpose]
    found = await _visible(choices)
    if not found:
        raise RuntimeError(f"WebComm-Element '{purpose}' wurde nicht gefunden.")
    await found.click(timeout=15000)


async def _fetch_pdf(url: str, username: str, password: str, output: Path, month_offset: int) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=shlex.split("--no-sandbox --disable-dev-shm-usage"))
        try:
            context = await browser.new_context(accept_downloads=True, viewport={"width": 1920, "height": 1080})
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            user_input = await _visible([
                page.locator('input[name*="user" i]'), page.locator('input[id*="user" i]'),
                page.locator('input[type="text"]'),
            ])
            pass_input = await _visible([page.locator('input[type="password"]')])
            if not user_input or not pass_input:
                raise RuntimeError("WebComm-Loginfelder wurden nicht gefunden.")
            await user_input.fill(username)
            await pass_input.fill(password)
            login = await _visible([
                page.get_by_role("button", name="Anmelden"), page.get_by_role("button", name="Login"),
                page.locator('input[type="submit"]'), page.locator('button[type="submit"]'),
            ])
            if not login:
                raise RuntimeError("WebComm-Anmeldebutton wurde nicht gefunden.")
            await login.click()
            await page.wait_for_load_state("domcontentloaded")
            await _click(page, "duty_plan")
            await page.wait_for_timeout(1000)

            for _ in range(max(0, int(month_offset))):
                try:
                    await _click(page, "next")
                except RuntimeError:
                    await _click(page, "menu")
                    await page.wait_for_timeout(300)
                    await _click(page, "next")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(700)

            print_link = await _visible([
                page.locator("#ctl00_ctl00_navilink4"), page.locator('a[title="Drucken"]'),
                page.locator('a[href^="rosprint.aspx?"]'),
            ])
            if not print_link:
                try:
                    await _click(page, "menu")
                    await page.wait_for_timeout(300)
                except RuntimeError:
                    pass
                print_link = await _visible([
                    page.locator("#ctl00_ctl00_navilink4"), page.locator('a[title="Drucken"]'),
                    page.locator('a[href^="rosprint.aspx?"]'),
                ])
            if not print_link:
                raise RuntimeError("WebComm-Druckansicht wurde nicht gefunden.")
            href = await print_link.get_attribute("href")
            if not href:
                raise RuntimeError("WebComm-Drucklink enthält keine URL.")
            print_url = urljoin(page.url, href)
            response = await context.request.get(print_url, timeout=45000)
            if not response.ok:
                raise RuntimeError(f"WebComm-Druckansicht antwortet mit HTTP {response.status}.")
            body = await response.body()
            content_type = (response.headers.get("content-type") or "").lower()
            output.parent.mkdir(parents=True, exist_ok=True)
            if "application/pdf" in content_type or body.startswith(b"%PDF-"):
                output.write_bytes(body)
            else:
                try:
                    page_html = body.decode("utf-8")
                except UnicodeDecodeError:
                    page_html = body.decode("latin-1", errors="replace")
                print_page = await context.new_page()
                await print_page.set_content(f'<base href="{html.escape(print_url, quote=True)}">' + page_html, wait_until="networkidle", timeout=45000)
                await print_page.emulate_media(media="print")
                await print_page.pdf(path=str(output), format="A4", print_background=True, prefer_css_page_size=True)
                await print_page.close()
            if not output.exists() or output.stat().st_size < 100:
                raise RuntimeError("WebComm-Druckansicht hat keine gültige PDF erzeugt.")
        finally:
            await browser.close()


async def import_direct(user: main.User, credential: DirectWebCommCredential, db: Session) -> int:
    password = _decrypt(credential.password_encrypted)
    all_shifts: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="alarmhub-webcomm-") as tmp:
        base = Path(tmp)
        for offset in (0, 1):
            pdf_path = base / f"month-{offset}.pdf"
            await _fetch_pdf(credential.url, credential.username, password, pdf_path, offset)
            for item in parse_duty_pdf(pdf_path, user.timezone or main.DEFAULT_TZ):
                all_shifts[item["uid"]] = item

    integration = db.scalar(select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user.id))
    if not integration:
        integration = main.WebCommIntegration(user_id=user.id, enabled=True, offsets="120,90")
        db.add(integration)
        db.flush()
    integration.enabled = True

    db.query(main.WebCommShift).filter(main.WebCommShift.user_id == user.id).delete()
    for item in sorted(all_shifts.values(), key=lambda x: x["start"]):
        db.add(main.WebCommShift(
            user_id=user.id,
            external_uid=item["uid"][:255],
            title=item["title"][:160],
            service_number=item["service_number"][:64],
            start=item["start"].astimezone(timezone.utc),
            end=item["end"].astimezone(timezone.utc),
            start_location=item["start_location"][:160] if item["start_location"] else None,
            end_location=item["end_location"][:160] if item["end_location"] else None,
        ))
    now = datetime.now(timezone.utc)
    integration.updated_at = now
    credential.last_sync_at = now
    credential.last_error = None
    db.commit()
    return len(all_shifts)


def _patch_navigation() -> None:
    original = main._layout

    def wrapped(title: str, body: str, user: main.User | None = None) -> str:
        page = original(title, body, user)
        if user and "href='/webcomm-direct'" not in page:
            page = page.replace("<a href='/devices'>Geräte / API</a>", "<a href='/webcomm-direct'>WebComm direkt</a><a href='/devices'>Geräte / API</a>")
        return page

    main._layout = wrapped


_patch_navigation()


@main.app.get("/webcomm-direct", response_class=HTMLResponse)
def direct_page(request: Request, user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    token = main._csrf(request)
    cred = db.scalar(select(DirectWebCommCredential).where(DirectWebCommCredential.user_id == user.id))
    url = html.escape(cred.url if cred else "https://webcomm.goevb.de/WebComm/default.aspx?TestingCookie=1", quote=True)
    username = html.escape(cred.username if cred else "", quote=True)
    tz = ZoneInfo(user.timezone or main.DEFAULT_TZ)
    last_sync = cred.last_sync_at.astimezone(tz).strftime("%d.%m.%Y %H:%M:%S") if cred and cred.last_sync_at else "noch nie"
    error = f"<p class='muted'><b>Letzter Fehler:</b> {html.escape(cred.last_error)}</p>" if cred and cred.last_error else ""
    saved = "✓ Zugangsdaten gespeichert" if cred else "noch nicht eingerichtet"
    body = f"""
    <section>
      <h2>Direkter WebComm-Import</h2>
      <p>Diese Variante ist für Benutzer gedacht, die <b>WebComm Calendar Sync nicht verwenden</b>. Alarm-HUB meldet sich selbst bei WebComm an und importiert den aktuellen und den folgenden Monat.</p>
      <p class='muted'>Das Passwort wird verschlüsselt in PostgreSQL gespeichert und nie wieder im Klartext angezeigt. Der direkte Browserzugriff ist aus Sicherheitsgründen auf webcomm.goevb.de beschränkt.</p>
      <p><b>Status:</b> {saved} · <b>Letzter Import:</b> {last_sync}</p>{error}
      <form method='post' action='/webcomm-direct/save'>
        <input type='hidden' name='csrf' value='{token}'>
        <label>WebComm URL<input name='url' value='{url}' required></label>
        <label>WebComm Benutzername<input name='username' value='{username}' autocomplete='username' required></label>
        <label>WebComm Passwort<input type='password' name='password' autocomplete='current-password' placeholder='{'gespeichert – leer lassen zum Beibehalten' if cred else 'Passwort'}'></label>
        <button>Zugangsdaten speichern</button>
      </form>
    </section>
    <section>
      <h2>Import</h2>
      <p>Importiert den aktuellen und den Folgemonat direkt aus WebComm und ersetzt die bisher für diesen Benutzer gespeicherten WebComm-Schichten.</p>
      <form method='post' action='/webcomm-direct/sync'><input type='hidden' name='csrf' value='{token}'><button {'disabled' if not cred else ''}>Jetzt aus WebComm importieren</button></form>
      <p class='muted'>Die Vorlaufzeiten für die Wecker stellst du weiterhin unter „Integrationen“ ein.</p>
    </section>
    """
    return HTMLResponse(main._layout("WebComm direkt", body, user))


@main.app.post("/webcomm-direct/save")
def direct_save(request: Request, url: str = Form(...), username: str = Form(...), password: str = Form(""), csrf: str = Form(...), user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    url = _validate_url(url)
    username = username.strip()
    if not username:
        raise HTTPException(400, "WebComm-Benutzername fehlt.")
    cred = db.scalar(select(DirectWebCommCredential).where(DirectWebCommCredential.user_id == user.id))
    if not cred:
        if not password:
            raise HTTPException(400, "Beim ersten Speichern ist das WebComm-Passwort erforderlich.")
        cred = DirectWebCommCredential(user_id=user.id, url=url, username=username, password_encrypted=_encrypt(password))
        db.add(cred)
    else:
        cred.url = url
        cred.username = username
        if password:
            cred.password_encrypted = _encrypt(password)
    db.commit()
    return RedirectResponse("/webcomm-direct", 303)


@main.app.post("/webcomm-direct/sync", response_class=HTMLResponse)
async def direct_sync(request: Request, csrf: str = Form(...), user: main.User = Depends(main.current_user), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    cred = db.scalar(select(DirectWebCommCredential).where(DirectWebCommCredential.user_id == user.id))
    if not cred:
        raise HTTPException(400, "Bitte zuerst WebComm-Zugangsdaten speichern.")
    try:
        imported = await import_direct(user, cred, db)
    except Exception as exc:
        db.rollback()
        cred = db.scalar(select(DirectWebCommCredential).where(DirectWebCommCredential.user_id == user.id))
        if cred:
            cred.last_error = str(exc)[:1000]
            db.commit()
        body = f"<section><h2>Import fehlgeschlagen</h2><p>{html.escape(str(exc))}</p><p><a href='/webcomm-direct'>Zurück</a></p></section>"
        return HTMLResponse(main._layout("WebComm direkt", body, user), status_code=502)
    body = f"<section><h2>Import erfolgreich</h2><p><b>{imported}</b> Schichten aus aktuellem und folgendem Monat wurden importiert.</p><p>Die daraus berechneten Wecker erscheinen sofort im Dashboard und in der Geräte-API.</p><p><a href='/webcomm-direct'>Zurück</a> · <a href='/'>Dashboard</a></p></section>"
    return HTMLResponse(main._layout("WebComm direkt", body, user))
