"""So lieu tong quan cho trang Bang dieu khien.

VI SAO TACH KHOI main.py: truy van va gop du lieu la logic nghiep vu, viet
test duoc doc lap. `main.py` chi con lam viec cua no la dinh tuyen HTTP.

Mot phan so lieu nam trong cot JSON (`grounding_json` chua confidence va
agent_decisions), nen phai doc ra roi gop bang Python. Phan con lai gop bang
SQL de khong keo ca bang len bo nho.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Contact, Enrichment, Organization, Scan

RECENT_DAYS = 14
TOP_ORGS = 8


def _loads(value) -> dict:
    """Cot JSON co the la dict (SQLAlchemy tu giai ma) hoac chuoi."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return {}


def _day(timestamp: str | None) -> str:
    return (timestamp or "")[:10]


def collect(db: Session) -> dict:
    totals = {
        "scans": db.scalar(select(func.count(Scan.id))) or 0,
        "contacts": db.scalar(select(func.count(Contact.id))) or 0,
        "organizations": db.scalar(select(func.count(Organization.id))) or 0,
        "enrichments": db.scalar(select(func.count(Enrichment.id))) or 0,
    }

    by_status = dict(
        db.execute(select(Scan.status, func.count(Scan.id)).group_by(Scan.status)).all()
    )

    by_review = dict(
        db.execute(
            select(Contact.review_status, func.count(Contact.id))
            .group_by(Contact.review_status)
        ).all()
    )

    enrichment_status = dict(
        db.execute(
            select(Enrichment.status, func.count(Enrichment.id))
            .group_by(Enrichment.status)
        ).all()
    )

    # --- Phan nam trong cot JSON: phai doc ra roi gop ---
    languages: Counter[str] = Counter()
    agent_actions: Counter[str] = Counter()
    scores: list[float] = []
    missing_critical: Counter[str] = Counter()

    rows = db.execute(
        select(Scan.detected_langs, Scan.grounding_json, Scan.extraction_json)
    ).all()
    for detected, grounding, extraction in rows:
        grounding = _loads(grounding)

        lang = (_loads(extraction).get("card_language") or "").strip()
        if not lang:
            detected = detected if isinstance(detected, list) else _loads(detected)
            if isinstance(detected, list) and detected:
                lang = detected[0]
        languages[lang or "khong ro"] += 1

        confidence = grounding.get("confidence") or {}
        if isinstance(confidence.get("overall_score"), (int, float)):
            scores.append(float(confidence["overall_score"]))
        for item in confidence.get("missing_critical") or []:
            missing_critical[str(item)] += 1

        for decision in grounding.get("agent_decisions") or []:
            action = str(decision.get("action") or "?")
            agent_actions[action] += 1

    # --- Ho so tao moi theo ngay, 14 ngay gan nhat ---
    today = date.today()
    window = [(today - timedelta(days=i)).isoformat() for i in range(RECENT_DAYS - 1, -1, -1)]
    created = Counter(
        _day(value) for (value,) in db.execute(select(Contact.created_at)).all()
    )
    per_day = [{"date": day, "contacts": created.get(day, 0)} for day in window]

    # --- Doanh nghiep co nhieu nguoi lien he nhat ---
    top_orgs = [
        {"organization": name, "contacts": count}
        for name, count in db.execute(
            select(Organization.name_original, func.count(Contact.id))
            .join(Contact, Contact.organization_id == Organization.id)
            .group_by(Organization.id)
            .order_by(func.count(Contact.id).desc())
            .limit(TOP_ORGS)
        ).all()
    ]

    return {
        "totals": totals,
        "scans_by_status": by_status,
        "contacts_by_review": by_review,
        "enrichments_by_status": enrichment_status,
        "languages": dict(languages.most_common()),
        "agent_actions": dict(agent_actions.most_common()),
        "missing_critical": dict(missing_critical.most_common()),
        "confidence": {
            "measured_scans": len(scores),
            "average": round(sum(scores) / len(scores), 3) if scores else None,
            "below_half": sum(1 for s in scores if s < 0.5),
        },
        "contacts_per_day": per_day,
        "top_organizations": top_orgs,
    }
