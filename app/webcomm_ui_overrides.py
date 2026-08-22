from __future__ import annotations

from fastapi.responses import HTMLResponse

from . import direct_webcomm as dw
from . import main


# Remove the vendor-specific default URL from the WebComm-direct form.
# Existing saved URLs are still shown; only a fresh/reset configuration starts empty.
for route in main.app.routes:
    if getattr(route, "path", None) != "/webcomm-direct":
        continue
    methods = getattr(route, "methods", set()) or set()
    if "GET" not in methods:
        continue

    original = route.endpoint

    def direct_page_without_default(request, user, db, _original=original):
        response = _original(request=request, user=user, db=db)
        cred = db.scalar(
            dw.select(dw.DirectWebCommCredential).where(
                dw.DirectWebCommCredential.user_id == user.id
            )
        )
        if cred is not None:
            return response

        old = "https://webcomm.goevb.de/WebComm/default.aspx?TestingCookie=1"
        body = response.body.decode("utf-8").replace(old, "")
        return HTMLResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    route.endpoint = direct_page_without_default
    if getattr(route, "dependant", None) is not None:
        route.dependant.call = direct_page_without_default
    break
