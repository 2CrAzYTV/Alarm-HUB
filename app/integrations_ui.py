from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import main


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
        saved_note = "<p><b>✓ Vorlaufzeiten gespeichert.</b></p>"

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
        <p class='muted'>Diese Werte bestimmen, wie viele Minuten vor einer WebComm-Schicht ein Wecker erzeugt wird.</p>
        <form method='post' action='/integrations/webcomm/offsets'>
          <input type='hidden' name='csrf' value='{token}'>
          <label>Vorlaufzeiten in Minuten
            <input name='offsets' value='{offsets}' placeholder='120,90,45'>
          </label>
          <button>Vorlaufzeiten speichern</button>
        </form>
      </div>

      <div class='card'>
        <h3>WebComm-Calendar-Sync Token</h3>
        <p class='muted'>Nur verwenden, wenn du die Integration neu einrichtest oder bewusst ein neues Token erzeugen möchtest. Ein neues Token ersetzt das bisherige.</p>
        <form method='post' action='/integrations/webcomm'>
          <input type='hidden' name='csrf' value='{token}'>
          <input type='hidden' name='offsets' value='{offsets}'>
          <button>Token neu erzeugen</button>
        </form>
        <p class='muted'>Das neue Token wird nur einmal nach dem Erzeugen angezeigt.</p>
      </div>
    </section>
    """
    return HTMLResponse(main._layout("Integrationen", body, user))


@main.app.post("/integrations/webcomm/offsets")
def save_webcomm_offsets(
    request: Request,
    offsets: str = Form("120,90"),
    csrf: str = Form(...),
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    main._check_csrf(request, csrf)
    parsed = main._offsets(offsets)
    if not parsed:
        raise HTTPException(400, "Mindestens eine gültige Vorlaufzeit erforderlich.")

    integration = db.scalar(
        select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user.id)
    )
    if not integration:
        integration = main.WebCommIntegration(user_id=user.id, enabled=True)
        db.add(integration)

    integration.offsets = ",".join(str(value) for value in parsed)
    integration.updated_at = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse("/integrations?saved=1", 303)


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
