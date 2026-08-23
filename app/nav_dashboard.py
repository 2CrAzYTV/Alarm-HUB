from __future__ import annotations

from . import main


_original_layout = main._layout


def _layout_with_dashboard(title: str, body: str, user: main.User | None = None) -> str:
    html = _original_layout(title, body, user)
    if not user:
        return html

    nav_start = html.find("<nav>")
    nav_end = html.find("</nav>", nav_start)
    if nav_start == -1 or nav_end == -1:
        return html

    nav_html = html[nav_start:nav_end]
    if "href='/'>Dashboard</a>" in nav_html:
        return html

    nav_html = nav_html.replace(
        "<a href='/alarms'>Meine Wecker</a>",
        "<a href='/'>Dashboard</a><a href='/alarms'>Meine Wecker</a>",
        1,
    )
    return html[:nav_start] + nav_html + html[nav_end:]


main._layout = _layout_with_dashboard
