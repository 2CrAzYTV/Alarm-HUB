from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import main


def alarms_page_simple(
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
      {manual_rows}
    </section>
    """

    html = main._layout("Meine Wecker", body, user)

    # /alarms is provided through a route override. Ensure the navigation is
    # identical to the rest of Alarm-HUB even if layout wrappers are loaded in
    # a different order.
    if "href='/'>Dashboard</a>" not in html:
        html = html.replace(
            "<a href='/alarms'>Meine Wecker</a>",
            "<a href='/'>Dashboard</a><a href='/alarms'>Meine Wecker</a>",
            1,
        )

    return HTMLResponse(html)


def _install_override() -> None:
    for route in main.app.routes:
        if getattr(route, "path", None) != "/alarms":
            continue
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods:
            continue
        route.endpoint = alarms_page_simple
        if getattr(route, "dependant", None) is not None:
            route.dependant.call = alarms_page_simple
        break


_install_override()
