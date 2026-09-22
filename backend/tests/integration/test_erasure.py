"""Duong xoa du lieu ca nhan va thoi han luu tru (san-sang-thuong-mai.md, C2).

BAY DUOC KIEM O DAY: anh luu theo SHA-256 cua noi dung, nen quet cung mot tam
the hai lan chi tao MOT tep. Xoa mu la lay mat anh cua ban quet khac - va no
khong hong ngay, chi den luc ai do mo ban quet cu thi anh bao 404.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import (Address, Contact, ContactEmail, ContactPhone, ContactProfile,
                        Organization, Scan)
from app.services import erasure
from test_pipeline_day4 import system, send, providers      # noqa: F401


def ho_so(system, scan_id=None, ten="Jane Doe"):
    """Mot ho so day du: doanh nghiep, email, dien thoai, dia chi, profile."""
    with system.factory() as db:
        org = Organization(name_original="Example Inc.", name_norm="example inc")
        db.add(org)
        db.flush()
        contact = Contact(full_name_original=ten, name_norm=ten.lower(),
                          organization_id=org.id)
        db.add(contact)
        db.flush()
        db.add_all([
            ContactEmail(contact_id=contact.id, value_raw="jane@example.com",
                         value_norm="jane@example.com", source="ocr"),
            ContactPhone(contact_id=contact.id, value_raw="03-1234-5678",
                         value_digits="0312345678", source="ocr"),
            Address(contact_id=contact.id, value_raw="Tokyo", source="ocr"),
            ContactProfile(contact_id=contact.id, draft={"fields": {}}, names_norm=ten.lower(),
                           companies_norm="example inc"),
        ])
        if scan_id:
            db.get(Scan, scan_id).contact_id = contact.id
        db.commit()
        return contact.id, org.id


def dem(system, model, **loc):
    with system.factory() as db:
        q = select(func.count()).select_from(model)
        for cot, gia_tri in loc.items():
            q = q.where(getattr(model, cot) == gia_tri)
        return db.scalar(q)


# --- Xoa ban quet ---------------------------------------------------------

def test_xoa_ban_quet_thi_xoa_ca_anh_goc(system, monkeypatch):
    providers(monkeypatch)
    scan_id = send(system)
    with system.factory() as db:
        ref = db.get(Scan, scan_id).image_ref
    assert (system.config.image_path / ref).is_file()

    res = system.client.delete(f"/api/scans/{scan_id}")
    assert res.status_code == 200
    assert res.json() == {"scans": 1, "images": 1}
    assert not (system.config.image_path / ref).exists()
    assert system.client.get(f"/api/scans/{scan_id}").status_code == 404


def test_anh_dung_chung_khong_bi_xoa_theo(system, monkeypatch):
    """Hai ban quet cung mot tam anh -> MOT tep. Xoa mot ban quet khong duoc
    lam ban quet con lai mat anh."""
    providers(monkeypatch)
    mot, hai = send(system), send(system)
    with system.factory() as db:
        ref = db.get(Scan, mot).image_ref
        assert db.get(Scan, hai).image_ref == ref      # cung ma bam that

    assert system.client.delete(f"/api/scans/{mot}").json() == {"scans": 1, "images": 0}
    assert (system.config.image_path / ref).is_file()
    assert system.client.get(f"/api/scans/{hai}/image").status_code == 200

    # Xoa not ban quet cuoi cung thi tep moi di.
    assert system.client.delete(f"/api/scans/{hai}").json() == {"scans": 1, "images": 1}
    assert not (system.config.image_path / ref).exists()


def test_xoa_ban_quet_khong_ton_tai_tra_404(system):
    assert system.client.delete("/api/scans/khong-co").status_code == 404


def test_xoa_ban_quet_khong_xoa_ho_so_da_luu(system, monkeypatch):
    """Ho so la thu nguoi dung CO Y giu lai; ban quet chi la duong no di vao."""
    providers(monkeypatch)
    scan_id = send(system)
    contact_id, _ = ho_so(system, scan_id)

    system.client.delete(f"/api/scans/{scan_id}")
    assert dem(system, Contact, id=contact_id) == 1


# --- Xoa ho so ------------------------------------------------------------

def test_xoa_ho_so_xoa_ca_ban_quet_email_dien_thoai_dia_chi(system, monkeypatch):
    providers(monkeypatch)
    scan_id = send(system)
    contact_id, org_id = ho_so(system, scan_id)
    with system.factory() as db:
        ref = db.get(Scan, scan_id).image_ref

    res = system.client.delete(f"/api/contacts/{contact_id}")
    assert res.status_code == 200
    assert res.json() == {"contacts": 1, "scans": 1, "images": 1}

    assert dem(system, Contact) == 0
    assert dem(system, ContactEmail) == 0
    assert dem(system, ContactPhone) == 0
    assert dem(system, Address) == 0
    assert dem(system, ContactProfile) == 0
    assert dem(system, Scan) == 0
    assert not (system.config.image_path / ref).exists()

    # Doanh nghiep dung chung cho nhieu ho so, khong phai du lieu ca nhan.
    assert dem(system, Organization, id=org_id) == 1


def test_xoa_ho_so_giu_anh_ma_ban_quet_khac_dang_dung(system, monkeypatch):
    """Phep kiem ma ke hoach doi: xoa ho so thi anh dung chung cua ban quet
    khac VAN CON."""
    providers(monkeypatch)
    cua_ho_so, cua_nguoi_khac = send(system), send(system)
    contact_id, _ = ho_so(system, cua_ho_so)
    with system.factory() as db:
        ref = db.get(Scan, cua_ho_so).image_ref

    assert system.client.delete(f"/api/contacts/{contact_id}").json()["images"] == 0
    assert (system.config.image_path / ref).is_file()
    assert system.client.get(f"/api/scans/{cua_nguoi_khac}/image").status_code == 200


def test_xoa_ho_so_khong_co_profile_van_duoc(system):
    """Ho so cu thieu `ContactProfile` thi cang phai xoa duoc, khong phai 409."""
    with system.factory() as db:
        contact = Contact(full_name_original="Cu", name_norm="cu")
        db.add(contact)
        db.commit()
        contact_id = contact.id
    assert system.client.delete(f"/api/contacts/{contact_id}").status_code == 200


def test_xoa_ho_so_khong_ton_tai_tra_404(system):
    assert system.client.delete("/api/contacts/khong-co").status_code == 404


# --- Thoi han luu tru -----------------------------------------------------

def gia_co(system, scan_id, created_at):
    with system.factory() as db:
        db.get(Scan, scan_id).created_at = created_at
        db.commit()


def test_don_qua_han_xoa_ban_quet_cu_va_giu_ban_quet_moi(system, monkeypatch):
    providers(monkeypatch)
    cu, moi = send(system), send(system)
    gia_co(system, cu, "2020-01-01T00:00:00+00:00")

    with system.factory() as db:
        ket_qua = erasure.purge_expired(db, system.config.image_path, days=30)
    assert ket_qua["scans"] == 1
    # Anh van con vi ban quet moi dung chung ma bam.
    assert ket_qua["images"] == 0
    assert dem(system, Scan, id=cu) == 0
    assert dem(system, Scan, id=moi) == 1


def test_khong_dat_thoi_han_thi_khong_xoa_gi(system, monkeypatch):
    """Mac dinh `RETENTION_DAYS=0` phai la GIU MAI MAI, khong phai xoa sach."""
    providers(monkeypatch)
    cu = send(system)
    gia_co(system, cu, "2020-01-01T00:00:00+00:00")

    with system.factory() as db:
        assert erasure.purge_expired(db, system.config.image_path, days=0) == {
            "skipped": True, "scans": 0, "images": 0}
    assert dem(system, Scan, id=cu) == 1


def test_don_theo_lich_chi_chay_lai_sau_mot_gio(system, monkeypatch):
    """Duong quet goi `maybe_purge` sau MOI lan quet; no phai tu ha tan suat,
    khong thi moi anh trong mot lo 10 tam la mot luot quet ca bang `scans`."""
    monkeypatch.setattr(erasure, "_lan_don_gan_nhat", 0.0)
    goi = []
    monkeypatch.setattr(erasure, "purge_expired",
                        lambda db, image_dir, days: goi.append(days))
    config = system.config.model_copy(update={"retention_days": 30})

    erasure.maybe_purge(config, system.factory)
    erasure.maybe_purge(config, system.factory)
    assert goi == [30]
