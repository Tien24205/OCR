"""Trang chu ca nhan: loi chao, pham vi so lieu, va duong quay lai.

Phep kiem dang gia nhat o day la cai thu hai: quan tri thay so lieu cua
TOAN HE THONG, con nguoi dung thuong chi thay phan cua minh. Hai con so do
khac nhau ve ban chat, va neu giao dien khong noi ra thi quan tri se doc 40
ban quet cua nhan vien thanh thanh tich cua chinh minh.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lib.api as api

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")

SUC_KHOE = {"status": "ok", "env": "test", "config": {
    "ocr_provider": "mock", "ocr_credentials_present": False,
    "ocr_configured": True, "extractor": "heuristic",
    "gemini_key_present": False, "gemini_model_set": False,
    "enrich_enabled": True, "login_required": False}}


def so_lieu(scans=3, contacts=2) -> dict:
    return {
        "total_scans": scans, "total_contacts": contacts,
        "total_organizations": 1,
        "totals": {"scans": scans, "contacts": contacts,
                   "organizations": 1, "enrichments": 0},
        "scans_by_status": {"ocr_done": scans},
        "contacts_by_review": {}, "enrichments_by_status": {},
        "languages": {"en": scans}, "agent_actions": {},
        "missing_critical": {},
        "confidence": {"measured_scans": 0, "average": None, "below_half": 0},
        "contacts_per_day": [], "top_organizations": [],
    }


def ban_quet(**ghi_de) -> dict:
    mac_dinh = {"id": "scan-1", "status": "ocr_done", "image_ref": "a" * 64,
                "created_at": "2026-09-24T09:30:00", "contact_id": None,
                "full_name": "Nguyễn Văn An", "company_name": "Công ty A"}
    return {**mac_dinh, **ghi_de}


def chay(nguoi: dict | None, lieu=None, danh_sach=None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["nguoi_dung"] = nguoi
    at.session_state["phieu_dang_nhap"] = "phieu" if nguoi else None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: SUC_KHOE)
        mp.setattr(api, "stats", lambda: lieu if lieu is not None else so_lieu())
        mp.setattr(api, "list_scans",
                   lambda limit=12: {"items": danh_sach if danh_sach is not None
                                     else [ban_quet()]})
        at.switch_page("app_pages/dashboard.py")
        at.run()
    assert not at.exception, at.exception
    return at


def chu(at: AppTest) -> str:
    """Toan bo chu tren trang, de tim mot cau bat ke no nam o widget nao."""
    return "\n".join([x.value for x in at.markdown]
                     + [x.value for x in at.caption]
                     + [x.value for x in at.subheader]
                     + [x.value for x in at.info])


# --------------------------------------------------------------------------
# Loi chao
# --------------------------------------------------------------------------

def test_chao_bang_ten_hien_thi():
    at = chay({"id": "u1", "email": "an@cty.vn", "display_name": "Anh An",
               "role": "user"})

    assert "Chào Anh An" in chu(at)


def test_chua_dat_ten_thi_lay_phan_truoc_dau_a_cong():
    """Chao bang ca dia chi email nghe nhu mot thu tu dong."""
    at = chay({"id": "u1", "email": "an.nguyen@cty.vn", "display_name": None,
               "role": "user"})

    loi_chao = " ".join(x.value for x in at.subheader)
    assert "Chào an.nguyen" in loi_chao
    # Chi kiem O LOI CHAO. Thanh ben VAN hien dia chi day du, va do la co y:
    # do la cho de biet chinh xac minh dang o tai khoan nao.
    assert "@cty.vn" not in loi_chao


def test_chua_dang_nhap_thi_khong_chao_ai_ca():
    """Che do mo (khong bat dang nhap) van phai chay nhu truoc."""
    at = chay(None)

    assert "Chào" not in chu(at)


# --------------------------------------------------------------------------
# Pham vi so lieu - phan quan trong nhat
# --------------------------------------------------------------------------

def test_quan_tri_duoc_bao_rang_day_la_so_cua_ca_he_thong():
    at = chay({"id": "u1", "email": "sep@cty.vn", "display_name": "Sếp",
               "role": "admin"})

    van = chu(at)
    assert "toàn" in van and "hệ thống" in van


def test_nguoi_dung_thuong_duoc_bao_day_chi_la_phan_cua_minh():
    at = chay({"id": "u2", "email": "nv@cty.vn", "display_name": "NV",
               "role": "user"})

    van = chu(at)
    assert "chỉ tính phần của bạn" in van
    assert "toàn hệ thống" not in van


# --------------------------------------------------------------------------
# Duong quay lai viec dang lam do
# --------------------------------------------------------------------------

def test_hien_ban_quet_gan_nhat_kem_trang_thai():
    at = chay({"id": "u1", "email": "an@cty.vn", "display_name": "An",
               "role": "user"},
              danh_sach=[ban_quet(full_name="Trần Thị Bình",
                                  status="ocr_done")])

    van = chu(at)
    assert "Trần Thị Bình" in van
    assert "chờ bạn kiểm tra" in van


def test_bam_mo_lai_thi_dat_dung_ma_ban_quet():
    at = chay({"id": "u1", "email": "an@cty.vn", "display_name": "An",
               "role": "user"},
              danh_sach=[ban_quet(id="scan-moi-nhat")])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: SUC_KHOE)
        mp.setattr(api, "stats", lambda: so_lieu())
        mp.setattr(api, "list_scans",
                   lambda limit=12: {"items": [ban_quet(id="scan-moi-nhat")]})
        next(b for b in at.button if b.label == "Mở lại").click().run()

    assert at.session_state["current_scan_id"] == "scan-moi-nhat"


def test_loi_khi_lay_ban_quet_gan_nhat_khong_lam_hong_ca_trang():
    """Mot tien ich o dau trang khong duoc keo ca trang so lieu xuong."""
    def hong(limit=12):
        raise api.ApiError("BACKEND_UNREACHABLE", "hong", retryable=True, status=0)

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["nguoi_dung"] = {"id": "u1", "email": "an@cty.vn",
                                      "display_name": "An", "role": "user"}
    at.session_state["phieu_dang_nhap"] = "phieu"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: SUC_KHOE)
        mp.setattr(api, "stats", lambda: so_lieu())
        mp.setattr(api, "list_scans", hong)
        at.switch_page("app_pages/dashboard.py")
        at.run()

    assert not at.exception
    assert "Chào An" in chu(at)


# --------------------------------------------------------------------------
# Chua co gi
# --------------------------------------------------------------------------

def test_chua_quet_gi_thi_goi_ten_va_cho_duong_bat_dau():
    at = chay({"id": "u1", "email": "an@cty.vn", "display_name": "An",
               "role": "user"},
              lieu=so_lieu(scans=0, contacts=0), danh_sach=[])

    assert "An ơi" in chu(at)
    assert any(b.label == "Quét tấm thẻ đầu tiên" for b in at.button)
