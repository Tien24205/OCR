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

from app.access import NguoiGoi, loc_theo_chu
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


def collect(db: Session, nguoi: NguoiGoi | None = None) -> dict:
    """So lieu cho trang Bang dieu khien, trong pham vi cua `nguoi`.

    VI SAO PHAI LOC O DAY NUA: trang nay khong nhan ma ban ghi nao, nen no
    la duong DE QUEN NHAT khi them phan quyen - va cai quen o day khong lo
    ra nhu mot loi. No lo ra duoi dang nhung con so: nguoi dung thay "50 ho
    so" trong khi minh chi co hai, va thay ten cong ty cua nguoi khac trong
    bang "doanh nghiep nhieu dau moi nhat". Ten cong ty la quan he lam an,
    va do la thu khong duoc lan giua cac tai khoan.
    """
    nguoi = nguoi or NguoiGoi()

    def cua_toi(stmt, cot):
        return loc_theo_chu(stmt, cot, nguoi)

    # Doanh nghiep va tra cuu la du lieu DUNG CHUNG - chung khong co
    # `owner_id`. Khi nguoi goi la mot NGUOI cu the thi chi dem nhung doanh
    # nghiep co lien he cua ho; khong thi con so tu no da noi ra ca he thong
    # co bao nhieu doi tac.
    #
    # Khi nguoi goi thay tat ca (quan tri, he thong tich hop, hoac che do mo)
    # thi KHONG rang buoc gi: rang buoc o do se am tham bo di nhung doanh
    # nghiep chua co lien he nao, va do la mot thay doi khac han - khong lien
    # quan gi den phan quyen.
    gioi_han_theo_lien_he = not nguoi.thay_tat_ca
    ma_ho_so = cua_toi(select(Contact.id), Contact.owner_id)
    ma_doanh_nghiep = select(Contact.organization_id).where(
        Contact.id.in_(ma_ho_so), Contact.organization_id.is_not(None))

    def trong_pham_vi(stmt, cot):
        """Rang buoc theo doanh nghiep, chi khi nguoi goi bi gioi han."""
        return stmt.where(cot.in_(ma_doanh_nghiep)) if gioi_han_theo_lien_he else stmt

    totals = {
        "scans": db.scalar(cua_toi(select(func.count(Scan.id)), Scan.owner_id)) or 0,
        "contacts": db.scalar(
            cua_toi(select(func.count(Contact.id)), Contact.owner_id)) or 0,
        "organizations": db.scalar(trong_pham_vi(
            select(func.count(func.distinct(Organization.id))),
            Organization.id)) or 0,
        "enrichments": db.scalar(trong_pham_vi(
            select(func.count(Enrichment.id)),
            Enrichment.organization_id)) or 0,
    }

    by_status = dict(
        db.execute(cua_toi(select(Scan.status, func.count(Scan.id)), Scan.owner_id)
                   .group_by(Scan.status)).all()
    )

    by_review = dict(
        db.execute(
            cua_toi(select(Contact.review_status, func.count(Contact.id)),
                    Contact.owner_id)
            .group_by(Contact.review_status)
        ).all()
    )

    enrichment_status = dict(
        db.execute(
            trong_pham_vi(select(Enrichment.status, func.count(Enrichment.id)),
                          Enrichment.organization_id)
            .group_by(Enrichment.status)
        ).all()
    )

    # --- Phan nam trong cot JSON: phai doc ra roi gop ---
    languages: Counter[str] = Counter()
    agent_actions: Counter[str] = Counter()
    scores: list[float] = []
    missing_critical: Counter[str] = Counter()

    rows = db.execute(cua_toi(
        select(Scan.detected_langs, Scan.grounding_json, Scan.extraction_json),
        Scan.owner_id)).all()
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
        _day(value) for (value,) in
        db.execute(cua_toi(select(Contact.created_at), Contact.owner_id)).all()
    )
    per_day = [{"date": day, "contacts": created.get(day, 0)} for day in window]

    # --- Doanh nghiep co nhieu nguoi lien he nhat ---
    top_orgs = [
        {"organization": name, "contacts": count}
        for name, count in db.execute(
            select(Organization.name_original, func.count(Contact.id))
            .join(Contact, Contact.organization_id == Organization.id)
            .where(Contact.id.in_(ma_ho_so))
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
