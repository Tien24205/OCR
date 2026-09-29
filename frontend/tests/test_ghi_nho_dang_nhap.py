"""Ghi nho dang nhap: luu PHIEU trong cookie HttpOnly, khong luu mat khau.

Ba dieu phai dung: cookie khong doc duoc tu JavaScript va khong dat duoc tu
trang khac; mo lai trang thi vao thang nhung chi khi backend con nhan phieu;
dang xuat thi xoa cookie va khong tu dang nhap lai.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import streamlit as st
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from streamlit.testing.v1 import AppTest

import lib.api as api
from asgi_app import TEN_COOKIE, _phien

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
NGUON = {"Origin": "http://testserver"}


def _may() -> TestClient:
    return TestClient(Starlette(routes=[Route("/phien", _phien, methods=["POST", "DELETE"])]))


# --- Route dat / xoa cookie ------------------------------------------------

def test_dat_cookie_httponly_samesite_co_han():
    r = _may().post("/phien", json={"token": "phieu-abc", "max_age": 3600}, headers=NGUON)
    assert r.status_code == 204
    cookie = r.headers["set-cookie"].lower()
    assert f"{TEN_COOKIE}=phieu-abc" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=3600" in cookie


def test_trang_khac_khong_dat_duoc_cookie():
    """Login CSRF: trang la ep trinh duyet vao tai khoan cua ke tan cong."""
    may = _may()
    assert may.post("/phien", json={"token": "x", "max_age": 60},
                    headers={"Origin": "https://ke-xau.example"}).status_code == 403
    assert may.post("/phien", json={"token": "x", "max_age": 60}).status_code == 403


def test_xoa_cookie_khi_dang_xuat():
    r = _may().delete("/phien", headers=NGUON)
    assert r.status_code == 204
    assert f'{TEN_COOKIE}=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()


def test_than_hong_bi_tu_choi():
    may = _may()
    assert may.post("/phien", json={"max_age": 60}, headers=NGUON).status_code == 400
    assert may.post("/phien", json={"token": "x", "max_age": 0}, headers=NGUON).status_code == 400


# --- Giao dien ---------------------------------------------------------------

def _suc_khoe() -> dict:
    return {"status": "ok", "env": "test", "config": {
        "ocr_provider": "mock", "ocr_credentials_present": False, "ocr_configured": True,
        "extractor": "heuristic", "gemini_key_present": False, "gemini_model_set": False,
        "enrich_enabled": True, "login_required": True}}


@pytest.fixture
def mp_app(monkeypatch):
    monkeypatch.setattr(api, "health", _suc_khoe)
    monkeypatch.setattr(api, "cua_dang_ky_mo", lambda: True)
    monkeypatch.setattr(api, "list_scans", lambda **kw: {"items": []})
    return monkeypatch


def _cookie(monkeypatch, gia_tri: dict) -> None:
    monkeypatch.setattr(type(st.context), "cookies", property(lambda self: gia_tri))


def test_tick_ghi_nho_thi_gui_lenh_dat_cookie(mp_app):
    mp_app.setattr(api, "dang_nhap", lambda e, m: {
        "token": "phieu-moi", "expires_in": 43200,
        "user": {"id": "u1", "email": "an@cty.vn", "role": "user"}})
    at = AppTest.from_file(APP, default_timeout=30).run()
    next(t for t in at.text_input if t.key == "vao_email").set_value("an@cty.vn")
    next(t for t in at.text_input if t.key == "vao_mk").set_value("matkhaudaiday12")
    next(c for c in at.checkbox if c.key == "vao_nho").check()
    next(b for b in at.button if b.label == "Đăng nhập").click().run()

    assert not at.exception, at.exception
    assert at.session_state["phieu_dang_nhap"] == "phieu-moi"
    lenh = [h.proto.body for h in at.get("html")]
    assert any("/phien" in x and "POST" in x and "phieu-moi" in x for x in lenh)


def test_khong_tick_thi_khong_luu_gi(mp_app):
    mp_app.setattr(api, "dang_nhap", lambda e, m: {
        "token": "phieu-moi", "expires_in": 43200,
        "user": {"id": "u1", "email": "an@cty.vn", "role": "user"}})
    at = AppTest.from_file(APP, default_timeout=30).run()
    next(t for t in at.text_input if t.key == "vao_email").set_value("an@cty.vn")
    next(t for t in at.text_input if t.key == "vao_mk").set_value("matkhaudaiday12")
    next(b for b in at.button if b.label == "Đăng nhập").click().run()

    assert not any("/phien" in h.proto.body for h in at.get("html"))


def test_mo_lai_trang_con_cookie_hop_le_thi_vao_thang(mp_app):
    _cookie(mp_app, {TEN_COOKIE: "phieu-cu"})
    mp_app.setattr(api, "toi_la_ai", lambda: {
        "user": {"id": "u1", "email": "an@cty.vn", "role": "user"}, "role": "user"})
    at = AppTest.from_file(APP, default_timeout=30).run()

    assert not at.exception, at.exception
    assert at.session_state["phieu_dang_nhap"] == "phieu-cu"
    assert at.session_state["nguoi_dung"]["email"] == "an@cty.vn"
    assert not any(b.label == "Đăng nhập" for b in at.button)


def test_cookie_het_han_thi_ve_trang_dang_nhap_va_xoa_cookie(mp_app):
    _cookie(mp_app, {TEN_COOKIE: "phieu-het-han"})

    def _tu_choi():
        raise api.ApiError("NOT_AUTHENTICATED", "Phiên không còn hiệu lực.", False, 401)

    mp_app.setattr(api, "toi_la_ai", _tu_choi)
    at = AppTest.from_file(APP, default_timeout=30).run()

    assert not at.exception, at.exception
    assert not at.session_state["phieu_dang_nhap"]
    assert any(b.label == "Đăng nhập" for b in at.button)
    assert any("DELETE" in h.proto.body for h in at.get("html"))


def test_dang_xuat_thi_xoa_cookie_va_khong_tu_vao_lai(mp_app):
    _cookie(mp_app, {TEN_COOKIE: "phieu-cu"})
    mp_app.setattr(api, "toi_la_ai", lambda: {
        "user": {"id": "u1", "email": "an@cty.vn", "role": "user"}, "role": "user"})
    at = AppTest.from_file(APP, default_timeout=30).run()

    next(b for b in at.sidebar.button if b.label == "Đăng xuất").click().run()

    assert not at.exception, at.exception
    assert not at.session_state["phieu_dang_nhap"]          # cookie van con o lan chay nay
    assert any(b.label == "Đăng nhập" for b in at.button)
    assert any("DELETE" in h.proto.body for h in at.get("html"))
