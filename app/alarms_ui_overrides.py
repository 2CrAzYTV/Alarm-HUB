from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import main


def alarms_page_with_webcomm(
    request: Request,
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    token = main._csrf(request)

    manual_alarms = db.scalars(
        select(main.Alarm)
        .where(main.Alarm.user_id == user.id)
        .order_by(main.Alarm.hour, main.Alarm.minute)
    ).all()

    manual_rows = "".join(
        f"<div class='alarm'><div><b>{alarm.hour:02d}:{alarm.minute:02d} · {alarm.name}</b>"
        f"<br><span class='muted'>{'einmalig ' + str(alarm.one_time_date) if alarm.one_time_date else 'Wochentage ' + alarm.weekdays}"
        f" · {'aktiv' if alarm.enabled else 'inaktiv'}</span></div>"
        f"<form method='post' action='/alarms/{alarm.id}/delete'>"
        f"<input type='hidden' name='csrf' value='{token}'>"
        f"<button class='danger'>Löschen</button></form></div>"
        for alarm in manual_alarms
    ) or "<p class='muted'>Noch keine manuellen Wecker.</p>"

    webcomm_alarms = [
        item for item in main._upcoming(user, db, 200)
        if item.get("source") == "webcomm"
    ]

    webcomm_rows = "".join(
        f"<div class='alarm'><div>"
        f"<b>{item['date']} · {item['time']} · {item['name']}</b>"
        f"<br><span class='muted'>Automatisch aus WebComm"
        f"{' · Dienst ' + str(item.get('service_number')) if item.get('service_number') else ''}"
        f"</span></div></div>"
        for item in webcomm_alarms
    ) or "<p class='muted'>Aktuell keine kommenden WebComm-Wecker.</p>"

    form = f"""
    <section>
      <h2>Wecker hinzufügen</h2>
      <form method='post' action='/alarms'>
        <input type='hidden' name='csrf' value='{token}'>
        <label>Name<input name='name' required placeholder='z. B. Frühschicht'></label>
        <label>Uhrzeit<input type='time' name='alarm_time' required></label>
        <label>Wochentage (0=Mo … 6=So)<input name='weekdays' value='0,1,2,3,4,5,6'></label>
        <label>Einmaliges Datum (optional)<input type='date' name='one_time_date'></label>
        <button>Wecker speichern</button>
      </form>
    </section>
    """

    body = (
        form
        + f"<section><h2>Manuelle Wecker</h2>{manual_rows}</section>"
        + "<section><h2>WebComm-Wecker</h2>"
          "<p class='muted'>Diese Wecker werden automatisch aus den synchronisierten WebComm-Schichten und deinen eingestellten Vorlaufzeiten erzeugt. Sie können hier nicht einzeln gelöscht werden.</p>"
        + webcomm_rows
        + "</section>"
    )

    return HTMLResponse(main._layout("Meine Wecker", body, user))


def _install_override() -> None:
    for route in main.app.routes:
        if getattr(route, "path", None) != "/alarms":
            continue
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods:
            continue
        route.endpoint = alarms_page_with_webcomm
        if getattr(route, "dependant", None) is not None:
            route.dependant.call = alarms_page_with_webcomm
        break


_install_override()
