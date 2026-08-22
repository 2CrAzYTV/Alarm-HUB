from __future__ import annotations

from urllib.parse import urlparse

from . import direct_webcomm as dw


async def _verify_webcomm_start_page(page):
    """Recognize compatible WebComm login pages without relying on one vendor's branding text."""
    await page.wait_for_timeout(350)
    final = urlparse(page.url)
    if final.scheme != "https" or not final.hostname:
        raise RuntimeError("Die WebComm-Startseite hat auf eine ungültige oder unverschlüsselte Adresse weitergeleitet.")
    dw._assert_public_host(final.hostname)

    body_text = (await page.locator("body").inner_text(timeout=10000)).casefold()
    title = (await page.title()).casefold()
    path = (final.path or "").casefold()

    user_input = await dw._visible([
        page.locator('input[name*="user" i]'),
        page.locator('input[id*="user" i]'),
        page.locator('input[name*="login" i]'),
        page.locator('input[id*="login" i]'),
        page.locator('input[type="text"]'),
    ])
    pass_input = await dw._visible([
        page.locator('input[type="password"]'),
        page.locator('input[name*="pass" i]'),
        page.locator('input[id*="pass" i]'),
    ])
    login = await dw._visible([
        page.get_by_role("button", name="Anmelden"),
        page.get_by_role("button", name="Login"),
        page.locator('input[type="submit"]'),
        page.locator('button[type="submit"]'),
        page.locator('input[value*="Anmelden" i]'),
        page.locator('input[value*="Login" i]'),
    ])

    username_marker = any(x in body_text for x in ("benutzerkennung", "benutzername", "username", "user name"))
    password_marker = any(x in body_text for x in ("kennwort", "passwort", "password"))
    login_marker = any(x in body_text for x in ("anmelden", "login", "einloggen"))

    # Some deployments render the WebComm heading as an image. In that case the
    # visible text/title contains no "WebComm", while the canonical application
    # path still does. Accept either branding text or a /WebComm/ application path.
    webcomm_marker = "webcomm" in body_text or "webcomm" in title or "/webcomm/" in path or path.endswith("/webcomm")

    # Form structure is the strongest compatibility signal. Require the three
    # visible login controls plus at least two semantic labels and a WebComm path/brand.
    semantic_markers = sum((username_marker, password_marker, login_marker))
    if not (user_input and pass_input and login and webcomm_marker and semantic_markers >= 2):
        raise RuntimeError(
            "Die angegebene Startseite wurde nicht als kompatible WebComm-Anmeldung erkannt. "
            "Erwartet werden ein Benutzerfeld, ein Passwortfeld, ein Anmeldebutton und eine WebComm-URL bzw. WebComm-Kennung."
        )
    return user_input, pass_input, login


# direct_webcomm._check_start_page() and _fetch_pdf() resolve this global at runtime,
# therefore one assignment updates both validation and the actual import flow.
dw._verify_webcomm_start_page = _verify_webcomm_start_page
