from __future__ import annotations

from fastapi.responses import HTMLResponse

from . import main


GUIDE_DROPDOWN_CSS = r"""
<style id="alarmhub-guide-dropdowns">
.platform-guide {
  background: var(--surface) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: var(--radius) !important;
  padding: 0 !important;
  margin: 0 0 14px !important;
  overflow: hidden;
}
.platform-guide > summary {
  list-style: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  cursor: pointer;
  font-size: 1.04rem;
  font-weight: 720;
  color: var(--text);
  user-select: none;
}
.platform-guide > summary::-webkit-details-marker { display: none; }
.platform-guide > summary::after {
  content: "⌄";
  margin-left: auto;
  color: var(--muted);
  font-size: 1.15rem;
  transition: transform .16s ease;
}
.platform-guide[open] > summary::after { transform: rotate(180deg); }
.platform-guide[open] > summary {
  border-bottom: 1px solid var(--border-soft);
  background: var(--surface-soft);
}
.platform-guide-content { padding: 18px 20px 22px; }
.platform-guide-content > section {
  background: transparent !important;
  border: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
}
.platform-guide-content > section > h2 { display: none; }
.platform-guide-hint {
  margin: 0 0 16px;
  color: var(--muted);
  font-size: .93rem;
}
@media (max-width: 720px) {
  .platform-guide > summary { padding: 15px 16px; }
  .platform-guide-content { padding: 15px 16px 18px; }
}
</style>
"""


def _wrap_platform_guides(html: str) -> str:
    ios_marker = "<section id='ios'>"
    android_marker = "<section id='android'>"
    troubleshooting_marker = "<section>\n  <h2>Fehlersuche</h2>"

    if "alarmhub-guide-dropdowns" in html:
        return html
    if ios_marker not in html or android_marker not in html or troubleshooting_marker not in html:
        return html

    before_ios, rest = html.split(ios_marker, 1)
    ios_body, rest = rest.split(android_marker, 1)
    android_body, after_android = rest.split(troubleshooting_marker, 1)

    ios_section = ios_marker + ios_body
    android_section = android_marker + android_body

    chooser = (
        "<section>"
        "<h2>Smartphone-Anleitung auswählen</h2>"
        "<p class='platform-guide-hint'>Wähle dein Betriebssystem. Die Anleitung öffnet sich erst beim Anklicken, damit die Seite kompakt bleibt.</p>"
        "<details class='platform-guide'>"
        "<summary>🍎 iOS / iPhone</summary>"
        f"<div class='platform-guide-content'>{ios_section}</div>"
        "</details>"
        "<details class='platform-guide'>"
        "<summary>🤖 Android / MacroDroid</summary>"
        f"<div class='platform-guide-content'>{android_section}</div>"
        "</details>"
        "</section>"
    )

    html = before_ios + chooser + troubleshooting_marker + after_android
    return html.replace("</head>", GUIDE_DROPDOWN_CSS + "</head>")


for route in main.app.routes:
    if getattr(route, "path", None) != "/guides":
        continue
    methods = getattr(route, "methods", set()) or set()
    if "GET" not in methods:
        continue

    original = route.endpoint

    def guides_dropdown(request, user, _original=original):
        response = _original(request=request, user=user)
        body = response.body.decode("utf-8")
        return HTMLResponse(
            content=_wrap_platform_guides(body),
            status_code=response.status_code,
        )

    route.endpoint = guides_dropdown
    if getattr(route, "dependant", None) is not None:
        route.dependant.call = guides_dropdown
    break
