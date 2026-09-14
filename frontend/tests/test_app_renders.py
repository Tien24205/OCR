"""Kiem tra ca ba trang Streamlit chay duoc, khong nem exception.

Dung `AppTest`: chay app headless ngay trong tien trinh pytest, khong can mo
trinh duyet cung khong can server. Backend duoc gia lap nen test KHONG goi mang.

Loi ma bo test nay bat duoc: sai ten icon Material Symbols, sai tham so widget,
loi chinh ta trong `st.session_state`, va truong hop backend chet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lib.api as api

# AppTest giai duong dan tuong doi theo FILE GOI no, khong theo thu muc dang
# chay - nen dung duong dan tuyet doi de test chay duoc tu bat ky dau.
APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Chan moi loi goi backend that."""
    monkeypatch.setattr(api, "health", lambda: {
        "status": "ok",
        "env": "test",
        "config": {
            "ocr_provider": "mock",
            "ocr_credentials_present": False,
            "extractor": "heuristic",
            "gemini_key_present": False,
            "gemini_model_set": False,
            "enrich_enabled": True,
        },
    })


def _run(page: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    if page:
        at.switch_page(page)
    at.run()
    assert not at.exception, at.exception
    return at


def test_trang_quet_the_chay_duoc():
    at = _run()
    # Nguoi dung phai chon duoc giua camera va tai anh (FR-01, FR-02:
    # camera bi tu choi van dung duoc duong tai anh).
    assert at.segmented_control[0].options == ["Chụp bằng camera", "Tải ảnh lên"]


def test_banner_trang_thai_hien_o_sidebar():
    at = _run()
    assert any("Backend đang chạy" in s.value for s in at.sidebar.success)


def test_trang_kiem_tra_khong_co_ban_quet():
    """Vao thang trang Kiem tra khi chua quet gi thi phai co huong dan,
    khong duoc nem KeyError."""
    at = _run("app_pages/review.py")
    assert at.info[0].value.startswith("Chưa có bản quét nào")


def test_trang_ho_so_hien_loi_api_khong_vo_giao_dien():
    """Day 7 endpoint exists; unexpected API errors stay visible."""
    def _raise_404(*args, **kwargs):
        raise api.ApiError("NOT_FOUND", "Not Found", False, 404)

    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/contacts.py")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "search_contacts", _raise_404)
        at.run()
    assert not at.exception, at.exception
    assert at.error[0].value == "Not Found"


# --- Trang Tong quan (Bang dieu khien) -----------------------------------

EMPTY_STATS = {
    "totals": {"scans": 0, "contacts": 0, "organizations": 0, "enrichments": 0},
    "scans_by_status": {}, "contacts_by_review": {}, "enrichments_by_status": {},
    "languages": {}, "agent_actions": {}, "missing_critical": {},
    "confidence": {"measured_scans": 0, "average": None, "below_half": 0},
    "contacts_per_day": [], "top_organizations": [],
}

FULL_STATS = {
    "totals": {"scans": 12, "contacts": 9, "organizations": 5, "enrichments": 7},
    "scans_by_status": {"committed": 9, "ocr_done": 2, "failed": 1},
    "contacts_by_review": {"reviewed": 9},
    "enrichments_by_status": {"verified": 5, "not_found": 2},
    "languages": {"ja": 7, "en": 5},
    "agent_actions": {"proceed": 20, "retry": 3, "escalate": 2},
    "missing_critical": {"missing_name": 1},
    "confidence": {"measured_scans": 12, "average": 0.82, "below_half": 1},
    "contacts_per_day": [{"date": "2026-09-13", "contacts": 4},
                         {"date": "2026-09-14", "contacts": 5}],
    "top_organizations": [{"organization": "株式会社青葉テクノロジー", "contacts": 3}],
}


def test_tong_quan_khi_kho_du_lieu_rong(monkeypatch):
    """Chua quet gi thi phai huong dan, khong duoc ve bieu do rong hay no."""
    monkeypatch.setattr(api, "stats", lambda: EMPTY_STATS)
    at = _run("app_pages/dashboard.py")
    assert any("Chưa có bản quét nào" in i.value for i in at.info)


def test_tong_quan_hien_day_du_so_lieu(monkeypatch):
    monkeypatch.setattr(api, "stats", lambda: FULL_STATS)
    at = _run("app_pages/dashboard.py")
    values = [m.value for m in at.metric]
    assert "12" in values and "9" in values
    assert any("82%" in str(v) for v in values)


def test_tong_quan_bao_loi_khi_backend_chet(monkeypatch):
    def _down():
        raise api.ApiError("BACKEND_UNREACHABLE", "Khong ket noi duoc", True, 0)

    monkeypatch.setattr(api, "stats", _down)
    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/dashboard.py")
    at.run()
    assert not at.exception, at.exception
    assert at.error
