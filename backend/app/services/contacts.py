"""Transactional contact projections and lossless reviewed profile storage."""
from copy import deepcopy

from sqlalchemy import delete, select, update

from app.errors import ApiError
from app.models import (Contact, ContactProfile, ContactEmail, ContactPhone, Address,
                        Organization, Scan, EnrichmentJob, norm_key, utcnow)
from app.services.enrich.worker import job_result


def require_contact(db, contact_id):
    contact = db.get(Contact, contact_id)
    profile = db.get(ContactProfile, contact_id)
    if contact is None:
        raise ApiError("CONTACT_NOT_FOUND", "Không tìm thấy hồ sơ.", 404)
    if profile is None:
        raise ApiError("PROFILE_NOT_READY", "Hồ sơ cũ chưa có dữ liệu đa giá trị để sửa.", 409)
    return contact, profile


def choose_organization(db, draft, choice, scan=None):
    if choice.mode == "link":
        organization = db.get(Organization, choice.id)
        if organization is None:
            raise ApiError("ORGANIZATION_NOT_FOUND", "Không tìm thấy doanh nghiệp đã chọn.", 404)
        return organization
    if scan:
        job = db.scalar(select(EnrichmentJob).where(
            EnrichmentJob.scan_id == scan.id,
            EnrichmentJob.draft_revision == (scan.grounding_json or {}).get("draft_revision", 0)))
        if job:
            # This organization was created for precisely this draft revision.
            return db.get(Organization, job.organization_id)
    fields = draft["fields"]
    names, websites = fields["company_names"], fields["websites"]
    if not names and not websites:
        return None
    organization = Organization(name_original=names[0]["value"] if names else "",
                                name_norm=norm_key(names[0]["value"] if names else ""),
                                website=websites[0]["value"] if websites else None,
                                website_domain=websites[0].get("website_domain") if websites else None)
    db.add(organization)
    db.flush()
    return organization


def project_contact(db, contact, profile, draft, organization, note):
    """Caller owns the transaction. Never edits the original Scan evidence."""
    fields = draft["fields"]
    contact.full_name_original = fields["full_names"][0]["value"] if fields["full_names"] else ""
    contact.name_norm = norm_key(contact.full_name_original)
    contact.organization_id = organization.id if organization else None
    contact.job_titles = [x["value"] for x in fields["job_titles"]]
    contact.departments = [x["value"] for x in fields["departments"]]
    contact.note = note
    contact.review_status, contact.reviewed_at, contact.updated_at = "reviewed", utcnow(), utcnow()
    profile.draft = deepcopy(draft)
    profile.names_norm = "\n".join(norm_key(x["value"]) for x in fields["full_names"])
    profile.companies_norm = "\n".join(norm_key(x["value"]) for x in fields["company_names"])
    for model in (ContactEmail, ContactPhone, Address):
        db.execute(delete(model).where(model.contact_id == contact.id))
    for x in fields["emails"]:
        db.add(ContactEmail(contact_id=contact.id, value_raw=x["value"],
                            value_norm=norm_key(x["value"]), source=x["source"]))
    for x in fields["phones"]:
        db.add(ContactPhone(contact_id=contact.id, value_raw=x["value"], value_digits=x["value_digits"],
                            label=x.get("label") or None, extension=x.get("extension") or None, source=x["source"]))
    for x in fields["addresses"]:
        db.add(Address(contact_id=contact.id, value_raw=x["value"], source=x["source"]))


def contact_result(db, contact_id):
    contact, profile = require_contact(db, contact_id)
    scans = db.scalars(select(Scan).where(Scan.contact_id == contact_id).order_by(Scan.created_at, Scan.id)).all()
    research = []
    for scan in scans:
        job = db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == scan.id,
                        EnrichmentJob.draft_revision == (scan.grounding_json or {}).get("draft_revision", 0)))
        if job:
            research.append({"is_current_organization": job.organization_id == contact.organization_id,
                             **job_result(db, job)})
    org = db.get(Organization, contact.organization_id) if contact.organization_id else None
    return {"id": contact.id, "version": profile.version, "draft": profile.draft,
            "full_name_original": contact.full_name_original,
            "organization": {"id": org.id, "name_original": org.name_original,
                             "website": org.website} if org else None,
            "note": contact.note, "review_status": contact.review_status,
            "reviewed_at": contact.reviewed_at, "created_at": contact.created_at,
            "updated_at": contact.updated_at,
            "scans": [{"id": s.id, "image_ref": s.image_ref, "raw_text": s.raw_text,
                       "is_mock": bool(s.ocr_provider and s.ocr_provider.startswith("mock"))} for s in scans],
            "research": research}


def claim_version(db, contact_id, version):
    changed = db.execute(update(ContactProfile).where(
        ContactProfile.contact_id == contact_id, ContactProfile.version == version)
        .values(version=ContactProfile.version + 1).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise ApiError("CONTACT_CONFLICT", "Hồ sơ đã thay đổi. Tải lại trước khi cập nhật.", 409)
