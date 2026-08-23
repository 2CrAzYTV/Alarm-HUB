from __future__ import annotations

import os
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import main


class CommuteSettings(main.Base):
    __tablename__ = "commute_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    home_address: Mapped[str] = mapped_column(String(320), default="")
    transport_mode: Mapped[str] = mapped_column(String(32), default="car")


class StartLocationMapping(main.Base):
    __tablename__ = "start_location_mappings"
    __table_args__ = (
        UniqueConstraint("user_id", "source_location", name="uq_start_location_mapping_user_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_location: Mapped[str] = mapped_column(String(160))
    route_address: Mapped[str] = mapped_column(String(320), default="")


TRANSPORT_MODES = {
    "car": "Auto",
    "transit": "Bus/Bahn",
    "bicycle": "Fahrrad",
}


def _transport_options(selected: str) -> str:
    return "".join(
        f"<option value='{value}'{' selected' if value == selected else ''}>{label}</option>"
        for value, label in TRANSPORT_MODES.items()
    )


def _location_rows(user: main.User, db: Session, shifts: list[main.WebCommShift], token: str) -> str:
    discovered = sorted(
        {
            (shift.start_location or "").strip()
            for shift in shifts
            if (shift.start_location or "").strip()
        },
        key=str.casefold,
    )
    mappings = {
        mapping.source_location: mapping
        for mapping in db.scalars(
            select(StartLocationMapping).where(StartLocationMapping.user_id == user.id)
        ).all()
    }

    if not discovered:
        return "<p class='muted'>Noch keine Startorte aus WebComm erkannt.</p>"

    rows: list[str] = []
    for source in discovered:
        mapping = mappings.get(source)
        address = mapping.route_address if mapping else ""
        status = "✓ zugeordnet" if address.strip() else "⚠ Adresse fehlt – Wegezeit wird nicht verwendet"
        rows.append(
            "<div class='card'>"
            f"<p><b>WebComm-Startort:</b> <code>{escape(source)}</code><br>"
            f"<span class='muted'>{status}</span></p>"
            "<form method='post' action='/integrations/commute/location'>"
            f"<input type='hidden' name='csrf' value='{token}'>"
            f"<input type='hidden' name='source_location' value='{escape(source, quote=True)}'>"
            "<label>Echte Adresse für die Routenberechnung"
            f"<input name='route_address' value='{escape(address, quote=True)}' "
            "placeholder='Straße Hausnummer, PLZ Ort'></label>"
            "<button type='submit'>Startort-Zuordnung speichern</button>"
            "</form></div>"
        )
    return "".join(rows)


def integrations_page_fixed(
    request: Request,
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    token = main._csrf(request)
    integration = db.scalar(
        select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user.id)
    )
    offsets = integration.offsets if integration else "120,90"
    state = "aktiviert" if integration and integration.enabled else "nicht aktiviert"
    tz = ZoneInfo(user.timezone or main.DEFAULT_TZ)
    now_utc = datetime.now(timezone.utc)
    shifts = db.scalars(
        select(main.WebCommShift)
        .where(main.WebCommShift.user_id == user.id)
        .order_by(main.WebCommShift.start)
    ).all()
    future_shifts = [shift for shift in shifts if shift.start > now_utc]
    next_shift = future_shifts[0] if future_shifts else None
    next_shift_text = "keine zukünftige Schicht importiert"
    if next_shift:
        local_start = next_shift.start.astimezone(tz)
        next_shift_text = f"{local_start.strftime('%d.%m.%Y %H:%M')} · {next_shift.title}"

    upcoming_webcomm = [
        item for item in main._upcoming(user, db, 200)
        if item.get("source") == "webcomm"
    ]
    last_sync_text = "noch kein erfolgreicher Sync"
    if integration and shifts:
        last_sync_text = integration.updated_at.astimezone(tz).strftime("%d.%m.%Y %H:%M:%S")

    saved_note = ""
    if request.query_params.get("saved") == "1":
        saved_value = request.query_params.get("offsets") or offsets
        saved_note = f"<p><b>✓ Vorlaufzeiten gespeichert: {escape(saved_value)} Minuten.</b></p>"

    commute = db.scalar(
        select(CommuteSettings).where(CommuteSettings.user_id == user.id)
    )
    commute_enabled = bool(commute and commute.enabled)
    home_address = commute.home_address if commute else ""
    transport_mode = commute.transport_mode if commute else "car"
    if transport_mode not in TRANSPORT_MODES:
        transport_mode = "car"

    commute_note = ""
    if request.query_params.get("commute_saved") == "1":
        commute_note = "<p><b>✓ Wegezeit-Einstellungen gespeichert.</b></p>"
    if request.query_params.get("location_saved") == "1":
        commute_note += "<p><b>✓ Startort-Zuordnung gespeichert.</b></p>"

    ors_ready = bool(os.getenv("OPENROUTESERVICE_API_KEY", "").strip())
    ors_status = "bereit" if ors_ready else "API-Key fehlt"
    transitous_status = "bereit" if ors_ready else "OpenRouteService-Key für Adressauflösung fehlt"
    location_rows = _location_rows(user, db, shifts, token)

    status_box = (
        "<div class='card'><h3>WebComm-Syncstatus</h3>"
        f"<p><b>Letzter Sync:</b> {last_sync_text}</p>"
        f"<p><b>Importierte Schichten:</b> {len(shifts)}</p>"
        f"<p><b>Nächste Schicht:</b> {next_shift_text}</p>"
        f"<p><b>Erzeugte kommende Wecker:</b> {len(upcoming_webcomm)}</p></div>"
    )

    body = f"""
    <section>
      <h2>WebComm (optional)</h2>
      <p>WebComm ist nur eine zusätzliche automatische Alarmquelle. Deine manuellen Wecker funktionieren unabhängig davon.</p>
      <p>Status: <b>{state}</b></p>
      {status_box}

      <div class='card'>
        <h3>Vorlaufzeiten</h3>
        {saved_note}
        <p class='muted'>Diese Werte bestimmen, wie viele Minuten vor Abfahrt bzw. vor dem Fahrtbeginn geweckt wird. Ohne aktive Wegezeit gelten sie direkt vor dem Schichtbeginn.</p>
        <p><b>Aktuell gespeichert:</b> {offsets} Minuten</p>
        <form method='post' action='/integrations/webcomm/offsets'>
          <input type='hidden' name='csrf' value='{token}'>
          <label>Vorlaufzeiten in Minuten
            <input name='offsets' value='{offsets}' placeholder='120,90,45' required>
          </label>
          <button type='submit'>Vorlaufzeiten speichern</button>
        </form>
      </div>

      <div class='card'>
        <h3>Wegezeit zum Schichtbeginn</h3>
        {commute_note}
        <p class='muted'>Alarm-HUB verwendet deine Heimatadresse und eine von dir bestätigte Adresse für den jeweiligen WebComm-Startort. Neue Startort-Kürzel werden automatisch erkannt. Solange ein Startort nicht zugeordnet ist, wird für diese Schicht aus Sicherheitsgründen keine Wegezeit abgezogen und nur die normale Vorlaufzeit verwendet.</p>
        <p><b>Auto/Fahrrad:</b> OpenRouteService · {ors_status}<br><b>Bus/Bahn:</b> Transitous · {transitous_status}</p>
        <p class='muted'>Bus/Bahn wird über den freien Open-Source-Routingdienst <a href='https://transitous.org/' target='_blank' rel='noopener noreferrer'>Transitous</a> berechnet. Verwendete ÖPNV-Datenquellen und OpenStreetMap-Hinweise: <a href='https://transitous.org/sources/' target='_blank' rel='noopener noreferrer'>Transitous Sources</a>.</p>
        <form method='post' action='/integrations/commute'>
          <input type='hidden' name='csrf' value='{token}'>
          <label class='row'>
            <input type='checkbox' name='enabled' value='1'{' checked' if commute_enabled else ''}>
            Wegezeit bei WebComm-Weckern berücksichtigen
          </label>
          <label>Heimatadresse
            <input name='home_address' value='{escape(home_address, quote=True)}' placeholder='Straße Hausnummer, PLZ Ort'>
          </label>
          <label>Verkehrsmittel
            <select name='transport_mode'>
              {_transport_options(transport_mode)}
            </select>
          </label>
          <button type='submit'>Wegezeit-Einstellungen speichern</button>
        </form>
      </div>

      <div class='card'>
        <h3>WebComm-Startorte zuordnen</h3>
        <p class='muted'>Jeder neue Wert aus dem Dienstplan erscheint hier automatisch, z. B. <code>BHOF</code> oder <code>BHOF-Siegen</code>. Hinterlege einmalig die echte Adresse. Die Zuordnung gilt anschließend automatisch für alle Schichten mit exakt diesem Startort.</p>
        {location_rows}
      </div>

      <div class='card'>
        <h3>WebComm-Calendar-Sync Token</h3>
        <p class='muted'>Nur verwenden, wenn du die Integration neu einrichtest oder bewusst ein neues Token erzeugen möchtest. Ein neues Token ersetzt das bisherige.</p>
        <form method='post' action='/integrations/webcomm'>
          <input type='hidden' name='csrf' value='{token}'>
          <input type='hidden' name='offsets' value='{offsets}'>
          <button type='submit'>Token neu erzeugen</button>
        </form>
        <p class='muted'>Das neue Token wird nur einmal nach dem Erzeugen angezeigt.</p>
      </div>
    </section>
    """
    return HTMLResponse(main._layout("Integrationen", body, user))


@main.app.post("/integrations/webcomm/offsets")
def save_webcomm_offsets(
    request: Request,
    offsets: str = Form(...),
    csrf: str = Form(...),
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    main._check_csrf(request, csrf)
    parsed = main._offsets(offsets)
    if not parsed:
        raise HTTPException(400, "Mindestens eine gültige Vorlaufzeit erforderlich.")

    normalized = ",".join(str(value) for value in parsed)
    integration = db.scalar(
        select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user.id)
    )
    if not integration:
        integration = main.WebCommIntegration(user_id=user.id, enabled=True)
        db.add(integration)

    integration.offsets = normalized
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(integration)

    if integration.offsets != normalized:
        raise HTTPException(500, "Vorlaufzeiten konnten nicht dauerhaft gespeichert werden.")

    return RedirectResponse(
        f"/integrations?saved=1&offsets={quote(normalized)}",
        303,
    )


@main.app.post("/integrations/commute")
def save_commute_settings(
    request: Request,
    home_address: str = Form(""),
    transport_mode: str = Form("car"),
    enabled: str | None = Form(None),
    csrf: str = Form(...),
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    main._check_csrf(request, csrf)

    if transport_mode not in TRANSPORT_MODES:
        raise HTTPException(400, "Ungültiges Verkehrsmittel.")

    normalized_address = home_address.strip()[:320]
    is_enabled = enabled == "1"
    if is_enabled and not normalized_address:
        raise HTTPException(400, "Für die Wegezeit ist eine Heimatadresse erforderlich.")

    settings = db.scalar(
        select(CommuteSettings).where(CommuteSettings.user_id == user.id)
    )
    if not settings:
        settings = CommuteSettings(user_id=user.id)
        db.add(settings)

    settings.enabled = is_enabled
    settings.home_address = normalized_address
    settings.transport_mode = transport_mode
    db.commit()
    db.refresh(settings)

    if (
        settings.enabled != is_enabled
        or settings.home_address != normalized_address
        or settings.transport_mode != transport_mode
    ):
        raise HTTPException(500, "Wegezeit-Einstellungen konnten nicht dauerhaft gespeichert werden.")

    return RedirectResponse("/integrations?commute_saved=1", 303)


@main.app.post("/integrations/commute/location")
def save_start_location_mapping(
    request: Request,
    source_location: str = Form(...),
    route_address: str = Form(""),
    csrf: str = Form(...),
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    main._check_csrf(request, csrf)
    source = source_location.strip()[:160]
    address = route_address.strip()[:320]
    if not source:
        raise HTTPException(400, "WebComm-Startort fehlt.")

    known = db.scalar(
        select(main.WebCommShift.id).where(
            main.WebCommShift.user_id == user.id,
            main.WebCommShift.start_location == source,
        )
    )
    if known is None:
        raise HTTPException(400, "Dieser WebComm-Startort ist nicht in deinen importierten Schichten vorhanden.")

    mapping = db.scalar(
        select(StartLocationMapping).where(
            StartLocationMapping.user_id == user.id,
            StartLocationMapping.source_location == source,
        )
    )
    if not mapping:
        mapping = StartLocationMapping(user_id=user.id, source_location=source)
        db.add(mapping)
    mapping.route_address = address
    db.commit()
    db.refresh(mapping)

    return RedirectResponse("/integrations?location_saved=1", 303)


def _install_override() -> None:
    for route in main.app.routes:
        if getattr(route, "path", None) != "/integrations":
            continue
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods:
            continue
        route.endpoint = integrations_page_fixed
        if getattr(route, "dependant", None) is not None:
            route.dependant.call = integrations_page_fixed
        break


_install_override()
