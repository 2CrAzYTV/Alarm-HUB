from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import main


CALENDAR_FILE_ROOT = Path(os.getenv("CALENDAR_FILE_DIR", "/config/calendar-files"))
MAX_CALENDAR_FILE_BYTES = int(os.getenv("CALENDAR_FILE_MAX_BYTES", str(20 * 1024 * 1024)))
_ALLOWED_KINDS = {"pdf", "screenshot"}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class CalendarFile(main.Base):
    __tablename__ = "calendar_files"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "kind", name="uq_calendar_file_user_period_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str] = mapped_column(String(7), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    public_token: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    stored_path: Mapped[str] = mapped_column(String(1024))
    content_sha256: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def _safe_original_name(value: str | None, suffix: str, period: str, kind: str) -> str:
    name = Path(value or "").name.strip()
    if not name:
        name = f"webcomm-{period}-{kind}{suffix}"
    return name[:255]


def _validate_period(period: str) -> str:
    value = period.strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise HTTPException(400, "Ungültiger Zeitraum. Erwartet wird YYYY-MM.")
    return value


def _public_path(token: str) -> str:
    return f"/public/calendar-files/{token}"


@main.app.post("/api/v1/integrations/webcomm/calendar-files")
async def upload_calendar_file(
    file: UploadFile = File(...),
    period: str = Form(...),
    kind: str = Form(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(main.db_session),
):
    user = main._token_user(authorization, db, main.WebCommIntegration)
    normalized_period = _validate_period(period)
    normalized_kind = kind.strip().lower()
    if normalized_kind not in _ALLOWED_KINDS:
        raise HTTPException(400, "Nicht unterstützter Dateityp.")

    media_type = (file.content_type or "application/octet-stream").lower()
    suffix = _ALLOWED_CONTENT_TYPES.get(media_type)
    if not suffix:
        raise HTTPException(415, "Nur PDF, JPEG, PNG oder WebP werden unterstützt.")
    if normalized_kind == "pdf" and media_type != "application/pdf":
        raise HTTPException(415, "Für kind=pdf ist eine PDF-Datei erforderlich.")
    if normalized_kind == "screenshot" and not media_type.startswith("image/"):
        raise HTTPException(415, "Für kind=screenshot ist eine Bilddatei erforderlich.")

    content = await file.read(MAX_CALENDAR_FILE_BYTES + 1)
    if len(content) > MAX_CALENDAR_FILE_BYTES:
        raise HTTPException(413, "Datei ist zu groß.")
    if not content:
        raise HTTPException(400, "Leere Datei.")

    digest = hashlib.sha256(content).hexdigest()
    record = db.scalar(
        select(CalendarFile).where(
            CalendarFile.user_id == user.id,
            CalendarFile.period == normalized_period,
            CalendarFile.kind == normalized_kind,
        )
    )

    if not record:
        record = CalendarFile(
            user_id=user.id,
            period=normalized_period,
            kind=normalized_kind,
            public_token=secrets.token_urlsafe(40),
            original_name="",
            media_type=media_type,
            stored_path="",
            content_sha256="",
        )
        db.add(record)

    user_dir = CALENDAR_FILE_ROOT / f"user-{user.id}" / normalized_period
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"{normalized_kind}{suffix}"

    changed = record.content_sha256 != digest or Path(record.stored_path or "") != destination
    if changed:
        destination.write_bytes(content)

    old_path = Path(record.stored_path) if record.stored_path else None
    if old_path and old_path != destination and old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            pass

    record.original_name = _safe_original_name(file.filename, suffix, normalized_period, normalized_kind)
    record.media_type = media_type
    record.stored_path = str(destination)
    record.content_sha256 = digest
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    return {
        "ok": True,
        "period": record.period,
        "kind": record.kind,
        "changed": changed,
        "content_sha256": record.content_sha256,
        "public_path": _public_path(record.public_token),
    }


@main.app.get("/public/calendar-files/{token}")
def public_calendar_file(token: str, db: Session = Depends(main.db_session)):
    if len(token) < 32:
        raise HTTPException(404, "Datei nicht gefunden.")

    record = db.scalar(select(CalendarFile).where(CalendarFile.public_token == token))
    if not record:
        raise HTTPException(404, "Datei nicht gefunden.")

    path = Path(record.stored_path)
    expected_root = (CALENDAR_FILE_ROOT / f"user-{record.user_id}").resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(expected_root)
    except (OSError, ValueError):
        raise HTTPException(404, "Datei nicht gefunden.")

    if not resolved.is_file():
        raise HTTPException(404, "Datei nicht gefunden.")

    headers = {
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(
        resolved,
        media_type=record.media_type,
        filename=record.original_name,
        content_disposition_type="inline",
        headers=headers,
    )
