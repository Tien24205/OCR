"""Test cho so lieu tong quan cua trang Bang dieu khien."""

from __future__ import annotations

import json

from app.models import Contact, Enrichment, Organization, Scan, norm_key, utcnow
from app.services.stats import collect


def test_kho_du_lieu_rong_khong_no(db):
    """Truong hop hay bi bo quen nhat: chua co gi ma van phai tra loi duoc."""
    data = collect(db)
    assert data["totals"] == {"scans": 0, "contacts": 0, "organizations": 0,
                              "enrichments": 0}
    assert data["confidence"]["average"] is None
    assert data["languages"] == {}
    assert len(data["contacts_per_day"]) == 14      # van du 14 ngay, toan so 0


def _scan(**kwargs) -> Scan:
    base = dict(image_ref="a" * 64, image_mime="image/jpeg", image_bytes=10,
                status="ocr_done")
    base.update(kwargs)
    return Scan(**base)


def test_gop_ngon_ngu_confidence_va_quyet_dinh_agent(db):
    db.add(_scan(
        extraction_json={"card_language": "ja"},
        grounding_json={
            "confidence": {"overall_score": 0.9, "missing_critical": []},
            "agent_decisions": [{"action": "proceed"}, {"action": "retry"}],
        },
    ))
    db.add(_scan(
        extraction_json={"card_language": "en"},
        grounding_json={
            "confidence": {"overall_score": 0.3,
                           "missing_critical": ["missing_name"]},
            "agent_decisions": [{"action": "escalate"}],
        },
    ))
    db.commit()

    data = collect(db)
    assert data["languages"] == {"ja": 1, "en": 1}
    assert data["confidence"]["measured_scans"] == 2
    assert data["confidence"]["average"] == 0.6
    assert data["confidence"]["below_half"] == 1
    assert data["missing_critical"] == {"missing_name": 1}
    assert data["agent_actions"]["retry"] == 1
    assert data["agent_actions"]["escalate"] == 1


def test_cot_json_luu_duoi_dang_chuoi_van_doc_duoc(db):
    """SQLite co the tra ve cot JSON duoi dang chuoi tuy cach ghi."""
    scan = _scan()
    db.add(scan)
    db.commit()
    db.execute(
        Scan.__table__.update()
        .where(Scan.id == scan.id)
        .values(grounding_json=json.dumps({"confidence": {"overall_score": 0.8}}))
    )
    db.commit()

    assert collect(db)["confidence"]["average"] == 0.8


def test_ngon_ngu_lay_tu_detected_langs_khi_extraction_khong_co(db):
    db.add(_scan(detected_langs=["ja"], extraction_json={}))
    db.commit()
    assert collect(db)["languages"] == {"ja": 1}


def test_doanh_nghiep_nhieu_lien_he_nhat_duoc_xep_hang(db):
    big = Organization(name_original="株式会社大", name_norm=norm_key("株式会社大"))
    small = Organization(name_original="小さな会社", name_norm=norm_key("小さな会社"))
    db.add_all([big, small])
    db.flush()
    for i in range(3):
        db.add(Contact(organization_id=big.id, full_name_original=f"A{i}",
                       name_norm=f"a{i}", review_status="reviewed"))
    db.add(Contact(organization_id=small.id, full_name_original="B",
                   name_norm="b", review_status="draft"))
    db.commit()

    top = collect(db)["top_organizations"]
    assert [r["organization"] for r in top] == ["株式会社大", "小さな会社"]
    assert top[0]["contacts"] == 3
    assert collect(db)["contacts_by_review"] == {"reviewed": 3, "draft": 1}


def test_ho_so_tao_hom_nay_duoc_dem_vao_ngay_cuoi(db):
    db.add(Contact(full_name_original="X", name_norm="x", review_status="draft",
                   created_at=utcnow()))
    db.commit()
    per_day = collect(db)["contacts_per_day"]
    assert per_day[-1]["contacts"] == 1


def test_trang_thai_tra_cuu_duoc_gop(db):
    org = Organization(name_original="Acme", name_norm="acme")
    db.add(org)
    db.flush()
    for status in ("verified", "verified", "not_found"):
        db.add(Enrichment(organization_id=org.id, attribute="industry",
                          value="x", status=status))
    db.commit()

    assert collect(db)["enrichments_by_status"] == {"verified": 2, "not_found": 1}
