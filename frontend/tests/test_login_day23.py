"""Ngay 23: cong dang nhap o giao dien.

Cau hoi bo test nay tra loi: khi backend bat buoc dang nhap, giao dien co
that su CHAN duong vao khong - hay no chi them mot trang dang nhap ma nguoi
ta van bam qua duoc bang thanh dieu huong.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import lib.api as api

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def suc_khoe(doi_dang_nhap: bool) -> dict:
    return {"status": "ok", "env": "test", "config": {
        "ocr_provider": "mock", "ocr_credentials_present": False,
        "ocr_configured": True, "extractor": "heuristic",
        "gemini_key_present": False, "gemini_model_set": False,
        "enrich_enabled": True, "login_required": doi_dang_nhap}}


@pytest.fixture(autouse=True)
def _khong_goi_mang(monkeypatch):
    """Xem ghi chu cung ten trong `test_review_day4.py`."""
    monkeypatch.setattr(api, "list_scans", lambda limit=12: {"items": []})
    monkeypatch.setattr(api, "organization_choices", lambda: {"items": []})

    def _chan(method, path, **kwargs):
        raise api.ApiError("BACKEND_UNREACHABLE", f"(test) {method} {path}",
                           retryable=True, status=0)

    monkeypatch.setattr(api, "_request", _chan)


def o(at: AppTest, key: str):
    """O nhap theo `key`. AppTest ban nay khong nhan `at.text_input(key=...)`."""
    return next(t for t in at.text_input if t.key == key)


def nut(at: AppTest, nhan: str):
    """Nut theo nhan. Nut gui form nam chung trong `at.button`, khong co
    danh sach `form_submit_button` rieng."""
    return next(b for b in at.button if b.label == nhan)


def chay(doi_dang_nhap: bool, phieu: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["phieu_dang_nhap"] = phieu
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: suc_khoe(doi_dang_nhap))
        at.run()
    assert not at.exception, at.exception
    return at


def test_khong_bat_dang_nhap_thi_vao_thang_nhu_truoc(monkeypatch):
    """596 test cu chay o che do nay - no khong duoc doi."""
    at = chay(doi_dang_nhap=False)

    assert at.segmented_control, "trang Quet the phai hien ra nhu cu"


def test_bat_dang_nhap_ma_chua_co_phieu_thi_chi_thay_trang_dang_nhap():
    at = chay(doi_dang_nhap=True)

    nhan = [b.label for b in at.button]
    assert "Đăng nhập" in nhan and "Tạo tài khoản" in nhan
    # Va KHONG thay cong cu quet the: bon trang kia phai VANG MAT khoi thanh
    # dieu huong, khong phai co mat roi bi chan khi bam vao.
    assert not at.segmented_control


def test_co_phieu_roi_thi_dung_duoc_ung_dung():
    at = chay(doi_dang_nhap=True, phieu="phieu-gia-dinh-la-con-han")

    assert at.segmented_control, "co phieu roi van bi chan o trang dang nhap"


def test_dang_nhap_thanh_cong_thi_luu_phieu_vao_phien():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["phieu_dang_nhap"] = None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: suc_khoe(True))
        mp.setattr(api, "dang_nhap", lambda e, m: {
            "token": "phieu-moi", "user": {"id": "u1", "email": e, "role": "user",
                                           "display_name": None}})
        at.run()
        o(at, "vao_email").set_value("an@cty.vn")
        o(at, "vao_mk").set_value("matkhaudaiday12")
        nut(at, "Đăng nhập").click().run()

    assert at.session_state["phieu_dang_nhap"] == "phieu-moi"
    assert at.session_state["nguoi_dung"]["email"] == "an@cty.vn"


def test_sai_mat_khau_thi_bao_loi_va_khong_luu_phieu():
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["phieu_dang_nhap"] = None

    def tu_choi(email, mat_khau):
        raise api.ApiError("BAD_CREDENTIALS", "Email hoặc mật khẩu không đúng.",
                           retryable=False, status=401)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: suc_khoe(True))
        mp.setattr(api, "dang_nhap", tu_choi)
        at.run()
        o(at, "vao_email").set_value("an@cty.vn")
        o(at, "vao_mk").set_value("saibetroi")
        nut(at, "Đăng nhập").click().run()

    assert not at.session_state["phieu_dang_nhap"]
    assert any("không đúng" in e.value for e in at.error)


def test_hai_o_mat_khau_khong_khop_thi_khong_goi_api():
    """Bat loi ngay canh o nhap, khong day sang may chu roi doi 422 ve."""
    goi = []
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["phieu_dang_nhap"] = None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: suc_khoe(True))
        mp.setattr(api, "dang_ky", lambda *a, **k: goi.append(a))
        at.run()
        o(at, "moi_email").set_value("an@cty.vn")
        o(at, "moi_mk").set_value("matkhaudaiday12")
        o(at, "moi_mk2").set_value("gomotcaikhac12")
        nut(at, "Tạo tài khoản").click().run()

    assert goi == []
    assert any("chưa khớp" in e.value for e in at.error)


def test_dang_xuat_xoa_ca_ban_quet_dang_mo():
    """Giu lai `current_scan_id` thi nguoi dang nhap sau mo trung ban quet
    cua nguoi truoc va nhan 404 khong ro ly do."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["phieu_dang_nhap"] = "phieu-cu"
    at.session_state["nguoi_dung"] = {"id": "u1", "email": "an@cty.vn",
                                      "role": "user", "display_name": "An"}
    at.session_state["current_scan_id"] = "scan-cua-nguoi-truoc"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "health", lambda: suc_khoe(True))
        at.run()
        next(b for b in at.sidebar.button if b.label == "Đăng xuất").click().run()

    assert not at.session_state["phieu_dang_nhap"]
    assert at.session_state["current_scan_id"] is None
