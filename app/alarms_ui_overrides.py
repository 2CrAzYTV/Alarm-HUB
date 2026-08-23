from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import main


def alarms_page_simple(
    request: Request,
    user: main.User = Depends(main.current_user),
    db: Session = Depends(main.db_session),
):
    token = main._csrf(request)

    body = f"""
    <section>
      <h2>Wecker hinzufügen</h2>
      <p class='muted'>Hier kannst du einen manuellen Wecker anlegen. Die Übersicht aller kommenden manuellen und WebComm-Wecker findest du im <a href='/'>Dashboard</a>.</p>
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
