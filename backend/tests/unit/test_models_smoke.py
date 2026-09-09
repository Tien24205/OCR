"""Kiem chung cac gia dinh nen tang cua tang du lieu.

Ba test nay bat cac loi im lang - loai loi khong bao lam sap ung dung
nhung lam hong du lieu, va thuong chi bi phat hien o Ngay 9 khi da muon.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Contact,
    ContactEmail,
    ContactPhone,
    Organization,
    Scan,
    norm_key,
)


def test_khoa_ngoai_duoc_thuc_thi(db):
    """SQLite MAC DINH TAT khoa ngoai. Neu PRAGMA khong duoc bat, test nay
    that bai - va do la dau hieu ON DELETE CASCADE trong models.py vo hieu."""
    db.add(ContactEmail(
        contact_id="khong-ton-tai",
        value_raw="a@b.com",
        value_norm="a@b.com",
        source="ocr",
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_tieng_nhat_di_qua_db_khong_doi(db):
    """Checklist bat buoc: giu dung chu Nhat qua luu va tai lai."""
    org = Organization(
        name_original="株式会社サンプル",
        name_norm=norm_key("株式会社サンプル"),
        website="https://example.co.jp",
        website_domain="example.co.jp",
    )
    db.add(org)
    db.flush()

    contact = Contact(
        organization_id=org.id,
        full_name_original="山田 太郎",
        name_norm=norm_key("山田 太郎"),
        job_titles=["営業部長"],
        departments=["営業部"],
        review_status="draft",
    )
    db.add(contact)
    db.commit()
    db.expire_all()

    loaded = db.get(Contact, contact.id)
    assert loaded.full_name_original == "山田 太郎"
    assert loaded.job_titles == ["営業部長"]        # cot JSON giu duoc list
    assert loaded.organization.name_original == "株式会社サンプル"


def test_norm_key_gop_full_width_va_half_width(db):
    """NFKC la ly do 'ＴＥＬ：０３' tim kiem ra 'TEL:03'."""
    assert norm_key("ＴＥＬ：０３-１２３４") == norm_key("TEL:03-1234")
    assert norm_key("  Yamada  Taro ") == "yamadataro"
    assert norm_key(None) == ""


def test_so_dien_thoai_giu_nguyen_so_0_dau_va_dau_cong(db):
    """Quy tac bat bien #2: so dien thoai LUON la chuoi."""
    contact = Contact(
        full_name_original="Test", name_norm="test", review_status="draft"
    )
    db.add(contact)
    db.flush()

    db.add(ContactPhone(
        contact_id=contact.id,
        value_raw="+81 3-1234-5678",
        value_digits="81312345678",
        extension="102",
        label="tel",
        source="ocr",
    ))
    db.commit()
    db.expire_all()

    phone = db.get(Contact, contact.id).phones[0]
    assert phone.value_raw == "+81 3-1234-5678"    # khong mat dau + va dau cach
    assert phone.extension == "102"


def test_scan_giu_bang_chung_goc_khi_contact_bi_xoa(db):
    """Quy tac bat bien #1: extraction_json la bang chung, khong duoc mat
    khi ho so bi xoa - Ngay 9 con phai do tren no."""
    contact = Contact(
        full_name_original="Test", name_norm="test", review_status="reviewed"
    )
    db.add(contact)
    db.flush()

    scan = Scan(
        image_ref="a" * 64,
        image_mime="image/jpeg",
        image_bytes=1234,
        status="committed",
        raw_text="山田 太郎\nExample Inc.",
        extraction_json={"full_name": {"value": "山田 太郎"}},
        contact_id=contact.id,
    )
    db.add(scan)
    db.commit()

    db.delete(contact)
    db.commit()
    db.expire_all()

    kept = db.get(Scan, scan.id)
    assert kept is not None                         # ON DELETE SET NULL, khong CASCADE
    assert kept.contact_id is None
    assert kept.raw_text == "山田 太郎\nExample Inc."
    assert kept.extraction_json["full_name"]["value"] == "山田 太郎"
