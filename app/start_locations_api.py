from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import integrations_ui
from . import main


@main.app.get("/api/v1/integrations/webcomm/start-locations")
def webcomm_start_locations_api(
    authorization: str | None = Header(default=None),
    db: Session = Depends(main.db_session),
):
    user = main._token_user(authorization, db, main.WebCommIntegration)
    mappings = db.scalars(
        select(integrations_ui.StartLocationMapping).where(
            integrations_ui.StartLocationMapping.user_id == user.id
        )
    ).all()
    locations = {
        mapping.source_location: mapping.route_address
        for mapping in mappings
        if mapping.source_location.strip() and mapping.route_address.strip()
    }
    return {"ok": True, "locations": locations}
