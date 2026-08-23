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


SERVICE_CARD_ROOT = Path(os.getenv("CALENDAR_FILE_DIR", "/config/calendar-files")) / "service-cards"
MAX_SERVICE_CARD_BYTES = int(os.getenv("CALENDAR_FILE_MAX_BYTES", str(20 * 1024 * 1024)))


class ServiceCardFile(main.Base):
    __tablename__ = "service_card_files"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "document_key",
            "service_number",
            name="uq_service_card_user_document_service",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_key: Mapped[str] = mapped_column(String(255), index=True)
    service_number: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_subject: Mapped[str] = mapped_column(String(320), default="")
    valid_from: Mapped[str] = mapped_column(String(10), default="")
    access_token: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    stored_path: Mapped[str] = mapped_column(String(1024))
    content_sha256: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def _clean_service_number(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", value.strip())
    if not cleaned:
        raise HTTPException(400, "Dienstnummer fehlt.")
    return cleaned[:64]


def _clean_document_key(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._:-]", "_", value.strip())
    if not cleaned:
        raise HTTPException(400, "Dokumentschlüssel fehlt.")
    return cleaned[:255]


def _calendar_path(token: str) -> str:
    return f"/calendar-service-cards/{token}"


@main.app.post("/api/v1/integrations/webcomm/service-cards")
async def upload_service_card(
    file: UploadFile = File(...),
    service_number: str = Form(...),
    document_key: str = Form(...),
    source_name: str = Form(""),
    source_subject: str = Form(""),
    valid_from: str = Form(""),
    authorization: str | None = Header(default=None),
    db: Session = Depends(main.db_session),
):
    user = main._token_user(authorization, db, main.WebCommIntegration)
    service = _clean_service_number(service_number)
    doc_key = _clean_document_key(document_key)

    media_type = (file.content_type or "application/pdf").lower()
    if media_type != "application/pdf":
        raise HTTPException(415, "Dienstkarten müssen als PDF hochgeladen werden.")

    content = await file.read(MAX_SERVICE_CARD_BYTES + 1)
    if len(content) > MAX_SERVICE_CARD_BYTES:
        raise HTTPException(413, "Dienstkarte ist zu groß.")
    if not content or not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Ungültige oder leere PDF-Datei.")

    digest = hashlib.sha256(content).hexdigest()
    record = db.scalar(
        select(ServiceCardFile).where(
            ServiceCardFile.user_id == user.id,
            ServiceCardFile.document_key == doc_key,
            ServiceCardFile.service_number == service,
        )
    )

    if not record:
        record = ServiceCardFile(
            user_id=user.id,
            document_key=doc_key,
            service_number=service,
            source_name="",
            source_subject="",
            valid_from="",
            access_token=secrets.token_urlsafe(40),
            original_name="",
            media_type="application/pdf",
            stored_path="",
            content_sha256="",
        )
        db.add(record)

    doc_hash = hashlib.sha256(doc_key.encode("utf-8")).hexdigest()[:20]
    user_dir = SERVICE_CARD_ROOT / f"user-{user.id}" / doc_hash
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"dienst-{service}.pdf"

    changed = record.content_sha256 != digest or Path(record.stored_path or "") != destination
    if changed:
        destination.write_bytes(content)

    old_path = Path(record.stored_path) if record.stored_path else None
    if old_path and old_path != destination and old_path.exists():
        try:
            old_path.unlink()
        except OSError:
            pass

    record.source_name = Path(source_name or file.filename or "dienstkarten.pdf").name[:255]
    record.source_subject = (source_subject or "").strip()[:320]
    record.valid_from = (valid_from or "").strip()[:10]
    record.original_name = f"Dienstkarte-{service}.pdf"
    record.media_type = "application/pdf"
    record.stored_path = str(destination)
    record.content_sha256 = digest
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    return {
        "ok": True,
        "service_number": record.service_number,
        "document_key": record.document_key,
        "changed": changed,
        "content_sha256": record.content_sha256,
        "calendar_path": _calendar_path(record.access_token),
    }


@main.app.get("/calendar-service-cards/{token}")
def calendar_service_card(token: str, db: Session = Depends(main.db_session)):
    if len(token) < 32:
        raise HTTPException(404, "Dienstkarte nicht gefunden.")

    record = db.scalar(select(ServiceCardFile).where(ServiceCardFile.access_token == token))
    if not record:
        raise HTTPException(404, "Dienstkarte nicht gefunden.")

    path = Path(record.stored_path)
    expected_root = (SERVICE_CARD_ROOT / f"user-{record.user_id}").resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(expected_root)
    except (OSError, ValueError):
        raise HTTPException(404, "Dienstkarte nicht gefunden.")

    if not resolved.is_file():
        raise HTTPException(404, "Dienstkarte nicht gefunden.")

    return FileResponse(
        resolved,
        media_type="application/pdf",
        filename=record.original_name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
