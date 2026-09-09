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


def test_trang_ho_so_bao_dung_khi_backend_chua_co_endpoint():
    """Ngay 7 moi co GET /api/contacts. Truoc do trang phai bao ro rang
    chu khong duoc vo."""
    def _raise_404(*args, **kwargs):
        raise api.ApiError("NOT_FOUND", "Not Found", False, 404)

    at = AppTest.from_file(APP, default_timeout=30)
    at.switch_page("app_pages/contacts.py")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "search_contacts", _raise_404)
        at.run()
    assert not at.exception, at.exception
    assert "Ngày 7" in at.warning[0].value
