"""Day 7: save, explicit duplicate decisions, search and portable exports."""
import csv
import hashlib
import io
import json
import unicodedata
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update, or_, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import (Contact, ContactEmail, ContactPhone, ContactProfile, Organization,
                        Scan, IdempotencyKey, norm_key, new_id)
from app.services import erasure
from app.services.drafts import DraftFields, apply_edit, current_draft
from app.services.normalize import FIELDS, digits
from app.services.dedupe import duplicate_candidates
from app.services.contacts import (require_contact, choose_organization, project_contact,
                                   contact_result, claim_version)

router = APIRouter(prefix="/api")


class OrganizationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["new", "link"] = "new"
    id: str | None = None

    @model_validator(mode="after")
    def valid_choice(self):
        if (self.mode == "link") != bool(self.id):
            raise ValueError("Chọn đúng doanh nghiệp cần liên kết.")
        return self


class SaveContact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scan_id: str = Field(min_length=1, max_length=36)
    revision: int = Field(ge=0)
    organization: OrganizationChoice = Field(default_factory=OrganizationChoice)
    duplicate_action: Literal["check", "new", "update"] = "check"
    target_contact_id: str | None = None
    target_version: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def valid_target(self):
        if self.duplicate_action == "update":
            if not self.target_contact_id or self.target_version is None:
                raise ValueError("Cần chọn hồ sơ và phiên bản để cập nhật.")
        elif self.target_contact_id is not None or self.target_version is not None:
            raise ValueError("Chỉ chọn hồ sơ đích khi cập nhật.")
        return self


class EditContact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    fields: DraftFields
    organization: OrganizationChoice
    note: str = Field(default="", max_length=10000)


@contextmanager
def transaction_errors(db):
    try:
        yield
    except ApiError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError("CONTACT_SAVE_FAILED", "Chưa lưu được hồ sơ. Dữ liệu cũ được giữ; hãy thử lại.", 500, True) from exc


def replay(db, key, fingerprint):
    previous = db.get(IdempotencyKey, key)
    if previous:
        if previous.endpoint != fingerprint:
            raise ApiError("IDEMPOTENCY_CONFLICT", "Khóa lưu đã được dùng cho nội dung khác.", 409)
        return {"id": previous.response_id}
    return None


@router.post("/contacts", status_code=201)
def save_contact(body: SaveContact, db: Session = Depends(get_db),
                 idempotency_key: str = Header(min_length=1, max_length=128)):
    fingerprint = hashlib.sha256(("POST /contacts\n" + json.dumps(
        body.model_dump(), sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
    previous = replay(db, idempotency_key, fingerprint)
    if previous:
        return previous
    contact_id = body.target_contact_id or new_id()
    with transaction_errors(db):
        # Reserve the key before reading mutable state. SQLite serializes writers.
        db.add(IdempotencyKey(key=idempotency_key, endpoint=fingerprint, response_id=contact_id))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            previous = replay(db, idempotency_key, fingerprint)
            if previous:
                return previous
            raise
        scan = db.get(Scan, body.scan_id)
        if scan is None:
            raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
        if scan.status == "committed":
            raise ApiError("SCAN_COMMITTED", "Bản quét đã có hồ sơ. Mở hồ sơ để sửa tiếp.", 409)
        grounding = scan.grounding_json or {}
        draft = current_draft(grounding)
        if scan.status != "ocr_done" or draft is None or body.revision != grounding.get("draft_revision", 0):
            raise ApiError("DRAFT_CONFLICT", "Lưu hoặc tải lại bản nháp trước khi tạo hồ sơ.", 409)
        if not any(draft["fields"][field] for field in FIELDS):
            raise ApiError("EMPTY_CONTACT", "Bản nháp chưa có thông tin để lưu.", 422)
        candidates = duplicate_candidates(db, draft, scan.image_ref, body.organization.id)
        strong = [x for x in candidates if x["score"] >= 60]
        if strong and body.duplicate_action == "check":
            raise ApiError("DUPLICATE_REVIEW_REQUIRED", "Có hồ sơ có thể trùng. Chọn cập nhật hoặc tạo mới.", 409)
        if body.duplicate_action == "update":
            if contact_id not in {x["id"] for x in strong}:
                raise ApiError("DUPLICATE_TARGET_INVALID", "Hồ sơ đích không còn là ứng viên trùng. Kiểm tra lại.", 409)
            contact, profile = require_contact(db, contact_id)
            claim_version(db, contact_id, body.target_version)
        else:
            contact = Contact(id=contact_id, full_name_original="", name_norm="")
            profile = ContactProfile(contact_id=contact_id, draft={}, names_norm="", companies_norm="")
            db.add(contact)
            db.flush()
            db.add(profile)
        organization = choose_organization(db, draft, body.organization, scan)
        project_contact(db, contact, profile, draft, organization, body.note)
        changed = db.execute(update(Scan).where(Scan.id == scan.id, Scan.status == "ocr_done",
                            Scan.grounding_json == grounding).values(status="committed", contact_id=contact_id)
                            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise ApiError("DRAFT_CONFLICT", "Bản quét vừa thay đổi. Tải lại trước khi lưu.", 409)
        db.commit()
    return {"id": contact_id}


@router.get("/scans/{scan_id}/duplicates")
def scan_duplicates(scan_id: str, organization_id: str | None = None, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
    draft = current_draft(scan.grounding_json or {})
    return {"items": duplicate_candidates(db, draft, scan.image_ref, organization_id, scan.contact_id) if draft else []}


@router.get("/contacts")
def search_contacts(q: str = Query(default="", max_length=500), page: int = Query(default=1, ge=1),
                    size: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    query = select(Contact).outerjoin(ContactProfile, ContactProfile.contact_id == Contact.id).outerjoin(Organization)
    if normalized := norm_key(q):
        conditions = [Contact.name_norm.contains(normalized, autoescape=True),
                      ContactProfile.names_norm.contains(normalized, autoescape=True),
                      ContactProfile.companies_norm.contains(normalized, autoescape=True),
                      Organization.name_norm.contains(normalized, autoescape=True),
                      Contact.emails.any(ContactEmail.value_norm.contains(normalized, autoescape=True))]
        if phone := digits(q):
            # Do not turn an email/name containing a digit into a broad phone query.
            if all(c in "0123456789+().- " for c in unicodedata.normalize("NFKC", q)):
                conditions.append(Contact.phones.any(ContactPhone.value_digits.contains(phone, autoescape=True)))
        query = query.where(or_(*conditions))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    contacts = db.scalars(query.order_by(Contact.created_at.desc(), Contact.id).offset((page-1)*size).limit(size)).all()
    return {"items": [{"id": c.id, "name": c.full_name_original,
                       "company": c.organization.name_original if c.organization else "",
                       "emails": [x.value_raw for x in c.emails], "phones": [x.value_raw for x in c.phones],
                       "updated_at": c.updated_at} for c in contacts], "total": total, "page": page, "size": size}


@router.get("/contacts/{contact_id}")
def get_contact(contact_id: str, db: Session = Depends(get_db)):
    return contact_result(db, contact_id)


@router.delete("/contacts/{contact_id}")
def delete_contact_route(contact_id: str, db: Session = Depends(get_db),
                         config: Settings = Depends(get_settings)):
    """Xoa han mot ho so: ban ghi, cac ban quet cua no, va anh goc.

    Quyen xoa cua Nghi dinh 13/2023 va GDPR - xem `services/erasure.py`. Xoa
    han, khong danh dau an: mot ban ghi "da xoa" van la du lieu ca nhan dang
    luu, va cau tra loi cho "cac anh xoa du lieu cua toi chua" phai la co.

    KHONG dung `require_contact`: ham do doi ho so co `ContactProfile`, nhung
    mot ho so cu thieu profile thi cang phai xoa duoc.
    """
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise ApiError("CONTACT_NOT_FOUND", "Không tìm thấy hồ sơ.", 404)
    with transaction_errors(db):
        return erasure.delete_contact(db, contact, config.image_path)


@router.get("/contacts/{contact_id}/duplicates")
def contact_duplicates(contact_id: str, db: Session = Depends(get_db)):
    contact, profile = require_contact(db, contact_id)
    candidates = duplicate_candidates(db, profile.draft, organization_id=contact.organization_id, exclude=contact_id)
    for image_ref in db.scalars(select(Scan.image_ref).where(Scan.contact_id == contact_id)):
        candidates += duplicate_candidates(db, profile.draft, image_ref, contact.organization_id, contact_id)
    best = {}
    for row in candidates:
        if row["id"] not in best or row["score"] > best[row["id"]]["score"]:
            best[row["id"]] = row
    return {"items": sorted(best.values(), key=lambda x: (-x["score"], x["id"]))}


@router.patch("/contacts/{contact_id}")
def edit_contact(contact_id: str, body: EditContact, db: Session = Depends(get_db)):
    with transaction_errors(db):
        # Acquire the write/version claim before reading the profile.
        claim_version(db, contact_id, body.version)
        contact, profile = require_contact(db, contact_id)
        try:
            draft = apply_edit(profile.draft, body.fields)
        except ValueError as exc:
            raise ApiError("INVALID_PROFILE", str(exc), 422) from exc
        if not any(draft["fields"][field] for field in FIELDS):
            raise ApiError("EMPTY_CONTACT", "Không thể xóa hết dữ liệu hồ sơ.", 422)
        organization = choose_organization(db, draft, body.organization)
        project_contact(db, contact, profile, draft, organization, body.note)
        db.commit()
    db.expire_all()
    return contact_result(db, contact_id)


@router.get("/organizations")
def organization_choices(db: Session = Depends(get_db)):
    # The demo dataset is small; include IDs so equal names stay distinguishable.
    return {"items": [{"id": o.id, "name": o.name_original, "website": o.website}
                      for o in db.scalars(select(Organization).order_by(Organization.name_norm, Organization.id))]}


def csv_cell(value):
    text = str(value or "")
    # Keep phone numbers as text; neutralize formulas from untrusted card text.
    stripped = text.lstrip()
    if stripped.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


@router.get("/export")
def export_contacts(format: Literal["json", "csv", "vcf"] = "json",
                    db: Session = Depends(get_db)):
    rows = [contact_result(db, cid) for cid in db.scalars(select(Contact.id).order_by(Contact.created_at, Contact.id))]
    if format == "json":
        content = json.dumps({"schema_version": 1, "contacts": rows}, ensure_ascii=False, indent=2).encode("utf-8")
        media_type = "application/json"
    elif format == "vcf":
        # vCard 3.0: mo file tren dien thoai la danh ba tu nhan, khong can
        # buoc map cot nhu CSV.
        from app.services import vcard
        content = vcard.build(rows)
        media_type = "text/vcard; charset=utf-8"
    else:
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["contact_id", *FIELDS, "note", "accepted_enrichments"])
        for row in rows:
            accepted = [claim for job in row["research"] if job["is_current_organization"]
                        for claim in job.get("enrichments", [])
                        if claim.get("decision") == "accepted"]
            # Arrays of strings retain boundaries and keep leading zeros in Excel.
            # Full provenance/metadata lives in the lossless JSON export.
            writer.writerow([row["id"], *[json.dumps([
                x["value"] + (" ext. " + x["extension"] if x.get("extension") else "")
                for x in row["draft"]["fields"][field]], ensure_ascii=False)
                for field in FIELDS], csv_cell(row["note"]),
                             json.dumps(accepted, ensure_ascii=False)])
        content = output.getvalue().encode("utf-8-sig")
        media_type = "text/csv; charset=utf-8"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="contacts.{format}"',
                             "Cache-Control": "no-store"})
