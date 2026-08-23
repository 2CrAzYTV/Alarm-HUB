from __future__ import annotations

from . import main


_original_layout = main._layout


def _layout_with_dashboard(title: str, body: str, user: main.User | None = None) -> str:
    html = _original_layout(title, body, user)
    if user and "href='/'>Dashboard</a>" not in html:
        html = html.replace(
            "<a href='/alarms'>Meine Wecker</a>",
            "<a href='/'>Dashboard</a><a href='/alarms'>Meine Wecker</a>",
            1,
        )
    return html


main._layout = _layout_with_dashboard
