"""Explainable candidates; scores are strongest signal, never automatic merging."""
from sqlalchemy import select

from app.models import Contact, ContactProfile, Scan, norm_key


def values(draft, field):
    return draft.get("fields", {}).get(field, [])


def duplicate_candidates(db, draft, image_ref=None, organization_id=None, exclude=None):
    names = {norm_key(x["value"]) for x in values(draft, "full_names") if x["value"]}
    emails = {norm_key(x["value"]) for x in values(draft, "emails") if x["value"]}
    mobiles = {x["value_digits"][-9:] for x in values(draft, "phones")
               if x.get("label") == "mobile" and len(x.get("value_digits", "")) >= 9}
    domains = {x["website_domain"].removeprefix("www.") for x in values(draft, "websites")
               if x.get("website_domain")}
    same_images = set(db.scalars(select(Scan.contact_id).where(
        Scan.image_ref == image_ref, Scan.contact_id.is_not(None)))) if image_ref else set()
    results = []
    for contact in db.scalars(select(Contact).order_by(Contact.id)):
        if contact.id == exclude:
            continue
        profile = db.get(ContactProfile, contact.id)
        other_names = {norm_key(x["value"]) for x in values(profile.draft, "full_names")} if profile else {contact.name_norm}
        other_domains = {x["website_domain"].removeprefix("www.") for x in values(profile.draft, "websites")
                         if x.get("website_domain")} if profile else set()
        if contact.organization and contact.organization.website_domain:
            other_domains.add(contact.organization.website_domain.removeprefix("www."))
        signals = []
        if emails.intersection(x.value_norm for x in contact.emails):
            signals.append((100, "Trùng email"))
        if contact.id in same_images:
            signals.append((100, "Quét lại cùng ảnh"))
        if mobiles.intersection(x.value_digits[-9:] for x in contact.phones
                                if x.label == "mobile" and len(x.value_digits) >= 9):
            signals.append((80, "Trùng 9 chữ số cuối của số di động"))
        if names.intersection(other_names):
            signals.append((25, "Trùng tên"))
            if organization_id and contact.organization_id == organization_id:
                signals.append((70, "Cùng tên và doanh nghiệp đã liên kết"))
            if domains.intersection(other_domains):
                signals.append((60, "Cùng tên và domain website"))
        if signals:
            results.append({"id": contact.id, "name": contact.full_name_original,
                            "company": contact.organization.name_original if contact.organization else "",
                            "version": profile.version if profile else None,
                            "score": max(s[0] for s in signals), "reasons": [s[1] for s in signals]})
    return sorted(results, key=lambda x: (-x["score"], x["id"]))
