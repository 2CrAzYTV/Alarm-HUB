from __future__ import annotations

from urllib.parse import urlparse

from . import direct_webcomm as direct


async def _visible_in_frame(frame, selectors: list[str]):
    for selector in selectors:
        try:
            loc = frame.locator(selector)
            if await loc.count() and await loc.first.is_visible():
                return loc.first
        except Exception:
            pass
    return None


async def _verify_webcomm_start_page(page):
    """Robust WebComm login-page detection for different operator installations.

    Some installations render labels differently or place the login form in a frame.
    We therefore identify WebComm primarily by the /WebComm/ URL path plus the actual
    presence of username, password and submit controls. Text markers are only a
    secondary signal.
    """
    await page.wait_for_timeout(500)

    final = urlparse(page.url)
    if final.scheme != "https" or not final.hostname:
        raise RuntimeError(
            "Die WebComm-Startseite hat auf eine ungültige oder unverschlüsselte Adresse weitergeleitet."
        )
    direct._assert_public_host(final.hostname)

    frames = list(page.frames)
    texts: list[str] = []
    for frame in frames:
        try:
            text = await frame.locator("body").inner_text(timeout=5000)
            if text:
                texts.append(text.casefold())
        except Exception:
            pass

    body_text = "\n".join(texts)
    try:
        title = (await page.title()).casefold()
    except Exception:
        title = ""

    path_marker = "/webcomm/" in (final.path or "").casefold()
    text_marker = "webcomm" in body_text or "webcomm" in title

    user_input = None
    pass_input = None
    login = None

    user_selectors = [
        'input[name*="user" i]',
        'input[id*="user" i]',
        'input[name*="login" i]',
        'input[id*="login" i]',
        'input[name*="kennung" i]',
        'input[id*="kennung" i]',
        'input[autocomplete="username"]',
        'input[type="text"]',
        'input[type="email"]',
    ]
    pass_selectors = [
        'input[type="password"]',
        'input[autocomplete="current-password"]',
    ]
    login_selectors = [
        'input[type="submit"]',
        'button[type="submit"]',
        'button',
        'input[type="button"]',
    ]

    for frame in frames:
        if user_input is None:
            user_input = await _visible_in_frame(frame, user_selectors)
        if pass_input is None:
            pass_input = await _visible_in_frame(frame, pass_selectors)
        if login is None:
            login = await _visible_in_frame(frame, login_selectors)
        if user_input is not None and pass_input is not None and login is not None:
            break

    # Prefer a button whose visible label/value actually looks like a login action.
    for frame in frames:
        try:
            labelled = await direct._visible([
                frame.get_by_role("button", name="Anmelden"),
                frame.get_by_role("button", name="Login"),
                frame.locator('input[type="submit"][value*="Anmeld" i]'),
                frame.locator('input[type="submit"][value*="Login" i]'),
                frame.locator('input[type="button"][value*="Anmeld" i]'),
                frame.locator('input[type="button"][value*="Login" i]'),
            ])
            if labelled is not None:
                login = labelled
                break
        except Exception:
            pass

    if not (user_input is not None and pass_input is not None and login is not None):
        raise RuntimeError(
            "Die WebComm-Anmeldemaske wurde nicht gefunden. Erwartet werden ein Benutzerfeld, ein Passwortfeld und ein Anmeldebutton."
        )

    if not (path_marker or text_marker):
        raise RuntimeError(
            "Die Seite enthält eine Anmeldemaske, wurde aber nicht als WebComm erkannt. Die URL sollte normalerweise /WebComm/ enthalten."
        )

    return user_input, pass_input, login


direct._verify_webcomm_start_page = _verify_webcomm_start_page
