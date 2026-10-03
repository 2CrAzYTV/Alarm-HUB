"""Administration: overview of all accounts, editing, locking/unlocking, registration settings.

Access is limited to the addresses in ADMIN_EMAILS. Every value that a user typed
is escaped here, because the admin sees data entered by other people.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import direct_webcomm as dw
from . import main
from . import webcomm_management as wm

ADMIN_CSS = (
    "<style>.badge{display:inline-block;font-size:.8em;padding:2px 8px;border-radius:999px;margin-left:6px;border:1px solid #30363d}"
    ".badge.ok{color:#2fbf71}.badge.off{color:#d95454;border-color:#d95454}.badge.admin{color:#5da8ff}"
    ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}"
    ".stat{background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:10px}.stat b{display:block;font-size:1.4em}"
    "form.inline{display:inline}dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0}dt{color:#8b949e}dd{margin:0;word-break:break-word}</style>"
)


def require_admin(user: main.User = Depends(main.current_user)) -> main.User:
    if not main.is_admin(user):
        raise HTTPException(404, "Nicht gefunden.")
    return user


def _fmt(value: datetime | None) -> str:
    if not value:
        return "–"
    return value.astimezone(ZoneInfo(main.DEFAULT_TZ)).strftime("%d.%m.%Y %H:%M")


def _e(value) -> str:
    return escape(str(value)) if value is not None else "–"


def _page(title: str, body: str, user: main.User) -> HTMLResponse:
    return HTMLResponse(main._layout(title, ADMIN_CSS + body, user))


def _post_button(action: str, label: str, csrf: str, danger: bool = False, confirm: str | None = None) -> str:
    onsubmit = f" onsubmit=\"return confirm({escape(json.dumps(confirm))})\"" if confirm else ""
    cls = " class='danger'" if danger else ""
    return f"<form class='inline' method='post' action='{action}'{onsubmit}><input type='hidden' name='csrf' value='{csrf}'><button{cls}>{label}</button></form>"


def _target(db: Session, user_id: int) -> main.User:
    target = db.get(main.User, user_id)
    if not target:
        raise HTTPException(404, "Benutzer nicht gefunden.")
    return target


def _not_self(admin: main.User, target: main.User, what: str) -> None:
    if admin.id == target.id:
        raise HTTPException(400, f"Du kannst dein eigenes Konto nicht {what}.")


@main.app.get("/admin", response_class=HTMLResponse)
def admin_overview(request: Request, admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    csrf = main._csrf(request)
    users = db.scalars(select(main.User).order_by(main.User.id)).all()

    def counts(model, column=None):
        col = column or model.user_id
        return dict(db.execute(select(col, func.count()).group_by(col)).all())

    alarm_counts = counts(main.Alarm)
    device_counts = counts(main.DeviceToken)
    shift_counts = counts(main.WebCommShift)
    device_last = dict(db.execute(select(main.DeviceToken.user_id, func.max(main.DeviceToken.last_used_at)).group_by(main.DeviceToken.user_id)).all())
    creds = {c.user_id: c for c in db.scalars(select(dw.DirectWebCommCredential)).all()}

    active = sum(1 for u in users if not u.disabled_at)
    stats = (
        "<div class='grid'>"
        f"<div class='stat'><b>{len(users)}</b>Konten</div>"
        f"<div class='stat'><b>{active}</b>aktiv</div>"
        f"<div class='stat'><b>{len(users) - active}</b>gesperrt</div>"
        f"<div class='stat'><b>{sum(alarm_counts.values())}</b>Wecker</div>"
        f"<div class='stat'><b>{sum(device_counts.values())}</b>Geräte-Tokens</div>"
        "</div>"
    )

    rows = []
    for u in users:
        badges = "<span class='badge off'>gesperrt</span>" if u.disabled_at else "<span class='badge ok'>aktiv</span>"
        if main.is_admin(u):
            badges += "<span class='badge admin'>Admin</span>"
        cred = creds.get(u.id)
        if not cred:
            webcomm = "WebComm direkt: –"
        elif cred.last_error:
            webcomm = "WebComm direkt: <span class='badge off'>Fehler</span>"
        else:
            webcomm = f"WebComm direkt: ok ({_fmt(cred.last_sync_at)})"
        toggle = ""
        if u.id != admin.id:
            toggle = (_post_button(f"/admin/users/{u.id}/enable", "Entsperren", csrf) if u.disabled_at
                      else _post_button(f"/admin/users/{u.id}/disable", "Sperren", csrf, danger=True, confirm=f"{u.email} sperren?"))
        rows.append(
            f"<div class='alarm'><div><b><a href='/admin/users/{u.id}'>{_e(u.email)}</a></b>{badges}<br>"
            f"<span class='muted'>seit {_fmt(u.created_at)} · letzter Login {_fmt(u.last_login_at)} · "
            f"{alarm_counts.get(u.id, 0)} Wecker · {shift_counts.get(u.id, 0)} Schichten · "
            f"{device_counts.get(u.id, 0)} Geräte (zuletzt {_fmt(device_last.get(u.id))}) · {webcomm}</span></div>"
            f"<div class='row'><a href='/admin/users/{u.id}'>Details</a>{toggle}</div></div>"
        )

    mode = main.registration_mode()
    options = "".join(
        f"<option value='{v}'{' selected' if v == mode else ''}>{label}</option>"
        for v, label in (("invite", "Nur mit Einladungscode"), ("open", "Offen für alle"), ("closed", "Geschlossen"))
    )
    registration = (
        "<section><h2>Registrierung</h2>"
        f"<form method='post' action='/admin/registration'><input type='hidden' name='csrf' value='{csrf}'>"
        f"<label>Modus<select name='mode'>{options}</select></label>"
        f"<label>Einladungscode<input name='invite_code' value='{_e(main.registration_invite_code())}' autocomplete='off'></label>"
        "<div class='row'><button>Speichern</button></div></form>"
        f"<p>{_post_button('/admin/registration/new-code', 'Neuen Code erzeugen', csrf, confirm='Neuen Einladungscode erzeugen? Der alte gilt dann nicht mehr.')}</p>"
        "<p class='muted'>Bestehende Konten sind davon nicht betroffen. Der Code gilt nur für neue Registrierungen.</p></section>"
    )

    lockouts = {**main._ip_limiter.active(), **main._account_limiter.active()}
    lock_rows = "".join(
        f"<div class='alarm'><div><b>{_e(key.split(':', 1)[1])}</b><br><span class='muted'>"
        f"{'IP-Adresse' if key.startswith(('login-ip', 'reg-ip')) else 'Konto'} · {n} Fehlversuche · läuft ab in {max(1, int(left // 60))} Min.</span></div>"
        f"<form class='inline' method='post' action='/admin/lockouts/clear'><input type='hidden' name='csrf' value='{csrf}'>"
        f"<input type='hidden' name='key' value='{_e(key)}'><button>Aufheben</button></form></div>"
        for key, (n, left) in sorted(lockouts.items())
    ) or "<p class='muted'>Keine Fehlversuche in den letzten Minuten.</p>"

    body = (
        f"<section><h2>Übersicht</h2>{stats}</section>"
        f"<section><h2>Benutzer</h2>{''.join(rows)}</section>"
        f"{registration}"
        f"<section><h2>Fehlgeschlagene Logins</h2><p class='muted'>Ab {main.LOGIN_MAX_FAILURES} Fehlversuchen pro IP bzw. {main.LOGIN_MAX_FAILURES * 2} pro Konto ist der Login {main.LOGIN_LOCKOUT_SECONDS // 60} Minuten gesperrt.</p>{lock_rows}</section>"
    )
    return _page("Administration", body, admin)


@main.app.get("/admin/users/{user_id}", response_class=HTMLResponse)
def admin_user(user_id: int, request: Request, admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    csrf = main._csrf(request)
    u = _target(db, user_id)
    base = f"/admin/users/{u.id}"
    is_self = u.id == admin.id

    status = "<span class='badge off'>gesperrt seit " + _fmt(u.disabled_at) + "</span>" if u.disabled_at else "<span class='badge ok'>aktiv</span>"
    lock = ""
    if not is_self:
        lock = (_post_button(f"{base}/enable", "Konto entsperren", csrf) if u.disabled_at
                else _post_button(f"{base}/disable", "Konto sperren", csrf, danger=True, confirm=f"{u.email} sperren? Alle Logins und Tokens werden sofort abgewiesen."))
    account = (
        f"<section><h2>Konto {status}</h2><dl>"
        f"<dt>ID</dt><dd>{u.id}</dd><dt>Erstellt</dt><dd>{_fmt(u.created_at)}</dd><dt>Letzter Login</dt><dd>{_fmt(u.last_login_at)}</dd>"
        f"<dt>Rolle</dt><dd>{'Admin' if main.is_admin(u) else 'Benutzer'}</dd></dl>"
        f"<form method='post' action='{base}/profile'><input type='hidden' name='csrf' value='{csrf}'>"
        f"<label>E-Mail<input type='email' name='email' value='{_e(u.email)}' required></label>"
        f"<label>Zeitzone<input name='timezone_name' value='{_e(u.timezone)}' required></label><button>Speichern</button></form>"
        f"<form method='post' action='{base}/password'><input type='hidden' name='csrf' value='{csrf}'>"
        "<label>Neues Passwort (min. 10 Zeichen)<input type='password' name='password' minlength='10' autocomplete='new-password' required></label><button>Passwort setzen</button></form>"
        f"<div class='row'>{lock}</div></section>"
    )

    alarms = db.scalars(select(main.Alarm).where(main.Alarm.user_id == u.id).order_by(main.Alarm.hour, main.Alarm.minute)).all()
    alarm_rows = "".join(
        f"<div class='alarm'><div><b>{a.hour:02d}:{a.minute:02d} · {_e(a.name)}</b><br><span class='muted'>"
        f"{'einmalig ' + str(a.one_time_date) if a.one_time_date else 'Wochentage ' + _e(a.weekdays)} · {'aktiv' if a.enabled else 'inaktiv'}</span></div>"
        f"<div class='row'>{_post_button(f'{base}/alarms/{a.id}/toggle', 'Deaktivieren' if a.enabled else 'Aktivieren', csrf)}"
        f"{_post_button(f'{base}/alarms/{a.id}/delete', 'Löschen', csrf, danger=True, confirm='Wecker löschen?')}</div></div>"
        for a in alarms
    ) or "<p class='muted'>Keine eigenen Wecker.</p>"

    upcoming = main._upcoming(u, db, 10)
    upcoming_rows = "".join(
        f"<div class='alarm'><div><b>{_e(x['date'])} · {_e(x['time'])}</b> · {_e(x['name'])}<br><span class='muted'>{_e(x['source'])}</span></div></div>"
        for x in upcoming
    ) or "<p class='muted'>Keine kommenden Wecker.</p>"

    devices = db.scalars(select(main.DeviceToken).where(main.DeviceToken.user_id == u.id).order_by(main.DeviceToken.created_at)).all()
    device_rows = "".join(
        f"<div class='alarm'><div><b>{_e(d.name)}</b><br><span class='muted'>erstellt {_fmt(d.created_at)} · zuletzt benutzt {_fmt(d.last_used_at)}</span></div>"
        f"{_post_button(f'{base}/devices/{d.id}/delete', 'Widerrufen', csrf, danger=True, confirm='Token widerrufen? Kurzbefehle mit diesem Token funktionieren dann nicht mehr.')}</div>"
        for d in devices
    ) or "<p class='muted'>Keine Geräte-Tokens.</p>"

    integration = db.scalar(select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == u.id))
    cred = db.scalar(select(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == u.id))
    schedule = db.scalar(select(wm.DirectWebCommSchedule).where(wm.DirectWebCommSchedule.user_id == u.id))
    shift_count = db.scalar(select(func.count()).select_from(main.WebCommShift).where(main.WebCommShift.user_id == u.id)) or 0
    next_shifts = db.scalars(
        select(main.WebCommShift).where(main.WebCommShift.user_id == u.id, main.WebCommShift.start > datetime.now(timezone.utc)).order_by(main.WebCommShift.start).limit(5)
    ).all()
    shift_rows = "".join(f"<li>{_fmt(s.start)} · {_e(s.title)}{' · ' + _e(s.start_location) if s.start_location else ''}</li>" for s in next_shifts)

    webcomm = "<section><h2>WebComm</h2><dl>"
    webcomm += f"<dt>Sync-Token</dt><dd>{'vorhanden' if integration and integration.token_hash else '–'}</dd>"
    if cred:
        webcomm += (
            f"<dt>WebComm direkt</dt><dd>{_e(cred.url)}</dd><dt>Benutzerkennung</dt><dd>{_e(cred.username)}</dd>"
            f"<dt>Letzter Import</dt><dd>{_fmt(cred.last_sync_at)}</dd>"
            f"<dt>Letzter Fehler</dt><dd>{_e(cred.last_error) if cred.last_error else '–'}</dd>"
        )
    else:
        webcomm += "<dt>WebComm direkt</dt><dd>nicht eingerichtet</dd>"
    if schedule:
        webcomm += f"<dt>Automatischer Import</dt><dd>{'an' if schedule.enabled else 'aus'} · alle {schedule.interval_minutes} Min. · {_e(schedule.window_start)}–{_e(schedule.window_end)}</dd>"
    webcomm += f"<dt>Schichten</dt><dd>{shift_count}</dd></dl>"
    if shift_rows:
        webcomm += f"<p class='muted'>Nächste Schichten:</p><ul>{shift_rows}</ul>"
    buttons = ""
    if integration and integration.token_hash:
        buttons += _post_button(f"{base}/webcomm/token/delete", "Sync-Token widerrufen", csrf, danger=True, confirm="Sync-Token widerrufen?")
    if cred:
        buttons += _post_button(f"{base}/webcomm/direct/delete", "WebComm-Zugangsdaten löschen", csrf, danger=True, confirm="Gespeicherte WebComm-Zugangsdaten löschen?")
    webcomm += f"<div class='row'>{buttons}</div></section>"

    danger = ""
    if not is_self:
        danger = (
            "<section><h2>Konto löschen</h2><p class='muted'>Löscht das Konto mit allen Weckern, Tokens, Schichten und WebComm-Daten endgültig.</p>"
            f"<form method='post' action='{base}/delete'><input type='hidden' name='csrf' value='{csrf}'>"
            "<label>Zur Bestätigung die E-Mail-Adresse eingeben<input name='confirm_email' autocomplete='off' required></label>"
            "<button class='danger'>Endgültig löschen</button></form></section>"
        )

    body = (
        "<p><a href='/admin'>← Zurück zur Übersicht</a></p>"
        f"{account}"
        f"<section><h2>Kommende Wecker</h2>{upcoming_rows}</section>"
        f"<section><h2>Eigene Wecker</h2>{alarm_rows}</section>"
        f"<section><h2>Geräte / API</h2>{device_rows}</section>"
        f"{webcomm}{danger}"
    )
    return _page(_e(u.email), body, admin)


def _back(user_id: int | None = None) -> RedirectResponse:
    return RedirectResponse(f"/admin/users/{user_id}" if user_id else "/admin", 303)


@main.app.post("/admin/registration")
def admin_registration(request: Request, mode: str = Form(...), invite_code: str = Form(""), csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    if mode not in {"open", "invite", "closed"}:
        raise HTTPException(400, "Unbekannter Modus.")
    invite_code = invite_code.strip()
    if mode == "invite" and len(invite_code) < 6:
        raise HTTPException(400, "Der Einladungscode muss mindestens 6 Zeichen haben.")
    main.save_setting(db, "registration_mode", mode)
    main.save_setting(db, "registration_invite_code", invite_code)
    return _back()


@main.app.post("/admin/registration/new-code")
def admin_new_code(request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    main.save_setting(db, "registration_invite_code", "".join(secrets.choice(alphabet) for _ in range(10)))
    return _back()


@main.app.post("/admin/lockouts/clear")
def admin_clear_lockout(request: Request, key: str = Form(...), csrf: str = Form(...), admin: main.User = Depends(require_admin)):
    main._check_csrf(request, csrf)
    main._ip_limiter.reset(key)
    main._account_limiter.reset(key)
    return _back()


@main.app.post("/admin/users/{user_id}/disable")
def admin_disable(user_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    target = _target(db, user_id)
    _not_self(admin, target, "sperren")
    if not target.disabled_at:
        target.disabled_at = datetime.now(timezone.utc)
        db.commit()
    return _back(target.id if f"/admin/users/{target.id}" in request.headers.get("referer", "") else None)


@main.app.post("/admin/users/{user_id}/enable")
def admin_enable(user_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    target = _target(db, user_id)
    target.disabled_at = None
    db.commit()
    main._account_limiter.reset("login-account:" + target.email)
    return _back(target.id if f"/admin/users/{target.id}" in request.headers.get("referer", "") else None)


@main.app.post("/admin/users/{user_id}/profile")
def admin_profile(user_id: int, request: Request, email: str = Form(...), timezone_name: str = Form(...), csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    target = _target(db, user_id)
    email = email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Ungültige E-Mail-Adresse.")
    try:
        ZoneInfo(timezone_name)
    except Exception:
        raise HTTPException(400, "Unbekannte Zeitzone.")
    other = db.scalar(select(main.User).where(main.User.email == email, main.User.id != target.id))
    if other:
        raise HTTPException(409, "Diese E-Mail-Adresse wird schon verwendet.")
    if target.id == admin.id and email not in main.ADMIN_EMAILS:
        raise HTTPException(400, "Damit würdest du dir selbst die Admin-Rechte entziehen (ADMIN_EMAILS).")
    target.email = email
    target.timezone = timezone_name
    db.commit()
    return _back(target.id)


@main.app.post("/admin/users/{user_id}/password")
def admin_password(user_id: int, request: Request, password: str = Form(...), csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    target = _target(db, user_id)
    if len(password) < 10:
        raise HTTPException(400, "Passwort muss mindestens 10 Zeichen lang sein.")
    target.password_hash = main.pwd.hash(password)
    db.commit()
    main._account_limiter.reset("login-account:" + target.email)
    return _back(target.id)


@main.app.post("/admin/users/{user_id}/alarms/{alarm_id}/toggle")
def admin_alarm_toggle(user_id: int, alarm_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    alarm = db.scalar(select(main.Alarm).where(main.Alarm.id == alarm_id, main.Alarm.user_id == user_id))
    if not alarm:
        raise HTTPException(404, "Wecker nicht gefunden.")
    alarm.enabled = not alarm.enabled
    db.commit()
    return _back(user_id)


@main.app.post("/admin/users/{user_id}/alarms/{alarm_id}/delete")
def admin_alarm_delete(user_id: int, alarm_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    db.execute(delete(main.Alarm).where(main.Alarm.id == alarm_id, main.Alarm.user_id == user_id))
    db.commit()
    return _back(user_id)


@main.app.post("/admin/users/{user_id}/devices/{device_id}/delete")
def admin_device_delete(user_id: int, device_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    db.execute(delete(main.DeviceToken).where(main.DeviceToken.id == device_id, main.DeviceToken.user_id == user_id))
    db.commit()
    return _back(user_id)


@main.app.post("/admin/users/{user_id}/webcomm/token/delete")
def admin_webcomm_token_delete(user_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    integration = db.scalar(select(main.WebCommIntegration).where(main.WebCommIntegration.user_id == user_id))
    if integration:
        integration.token_hash = None
        db.commit()
    return _back(user_id)


@main.app.post("/admin/users/{user_id}/webcomm/direct/delete")
def admin_webcomm_direct_delete(user_id: int, request: Request, csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    db.execute(delete(dw.DirectWebCommCredential).where(dw.DirectWebCommCredential.user_id == user_id))
    db.commit()
    return _back(user_id)


@main.app.post("/admin/users/{user_id}/delete")
def admin_user_delete(user_id: int, request: Request, confirm_email: str = Form(...), csrf: str = Form(...), admin: main.User = Depends(require_admin), db: Session = Depends(main.db_session)):
    main._check_csrf(request, csrf)
    target = _target(db, user_id)
    _not_self(admin, target, "löschen")
    if confirm_email.strip().lower() != target.email:
        raise HTTPException(400, "Die E-Mail-Adresse stimmt nicht überein.")
    db.delete(target)
    db.commit()
    return _back()
