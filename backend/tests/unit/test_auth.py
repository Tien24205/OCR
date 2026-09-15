"""Kiem tra lop xac thuc API va gioi han tan suat.

VI SAO CAN LOP NAY: truoc khi co no, `curl http://host:8000/api/contacts`
khong kem gi ca tra ve HTTP 200 va toan bo kho ho so doi tac. Da kiem chung
bang chinh lenh do tren dich vu dang chay ngay 15/09.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import GioiHanTanSuat, doc_khoa, gan_xac_thuc, khoa_hop_le


def app_co_khoa(khoa: list[str], moi_phut: int = 60) -> TestClient:
    app = FastAPI()
    gan_xac_thuc(app, khoa, moi_phut)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/contacts")
    def contacts():
        return {"items": []}

    return TestClient(app)


# --- Che do BAT ----------------------------------------------------------

def test_khong_co_khoa_thi_bi_tu_choi():
    r = app_co_khoa(["bi-mat"]).get("/api/contacts")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_khoa_sai_bi_tu_choi():
    r = app_co_khoa(["bi-mat"]).get("/api/contacts",
                                    headers={"X-API-Key": "doan-bua"})
    assert r.status_code == 401


def test_khoa_dung_thi_qua():
    r = app_co_khoa(["bi-mat"]).get("/api/contacts",
                                    headers={"X-API-Key": "bi-mat"})
    assert r.status_code == 200


def test_nhan_ca_dang_bearer():
    """Nhieu cong cu tich hop chi biet gui `Authorization: Bearer`."""
    r = app_co_khoa(["bi-mat"]).get(
        "/api/contacts", headers={"Authorization": "Bearer bi-mat"})
    assert r.status_code == 200


def test_health_van_mo_de_giam_sat_duoc():
    """He thong giam sat phai biet dich vu con song ma khong can khoa.

    An toan vi /api/health chi tra ve co true/false, khong bao gio tra ve gia
    tri khoa nao.
    """
    r = app_co_khoa(["bi-mat"]).get("/api/health")
    assert r.status_code == 200


def test_loi_tra_ve_dung_dang_cua_API():
    """Dang khac se buoc giao dien va he thong tich hop xu ly rieng mot
    truong hop - va thuong thi ho quen."""
    body = app_co_khoa(["bi-mat"]).get("/api/contacts").json()
    assert set(body["error"]) >= {"code", "message", "retryable"}


def test_khong_lo_gia_tri_khoa_trong_thong_bao_loi():
    """Thong bao loi di ra ngoai; khong duoc chua khoa that lan khoa nguoi
    dung vua go nham."""
    r = app_co_khoa(["bi-mat"]).get("/api/contacts",
                                    headers={"X-API-Key": "go-nham"})
    assert "bi-mat" not in r.text and "go-nham" not in r.text


# --- Che do TAT ----------------------------------------------------------

def test_khong_cau_hinh_khoa_thi_khong_chan():
    """Cong cu chay tren may ca nhan phai dung duoc ngay.

    Bat buoc dat khoa moi chay se khien nguoi ta dat khoa "1234" cho xong -
    te hon la khong co khoa ma biet ro minh khong co.
    """
    r = app_co_khoa([]).get("/api/contacts")
    assert r.status_code == 200


# --- So khoa an toan -----------------------------------------------------

def test_so_khoa_dung_sai():
    assert khoa_hop_le("a", ["a", "b"]) is True
    assert khoa_hop_le("c", ["a", "b"]) is False
    assert khoa_hop_le("", ["a"]) is False
    assert khoa_hop_le("a", []) is False


def test_khong_nhan_khoa_la_tien_to_hay_hau_to():
    """Phai khop TRON VEN, khong duoc khop mot phan."""
    assert khoa_hop_le("bi", ["bi-mat"]) is False
    assert khoa_hop_le("bi-mat-hon", ["bi-mat"]) is False


# --- Doc khoa tu header --------------------------------------------------

class _Req:
    def __init__(self, **h):
        self.headers = {k.lower().replace("_", "-"): v for k, v in h.items()}


def test_doc_khoa_tu_hai_dang_header():
    assert doc_khoa(_Req(x_api_key="  abc  ")) == "abc"
    assert doc_khoa(_Req(authorization="Bearer abc")) == "abc"
    assert doc_khoa(_Req(authorization="bearer abc")) == "abc"
    assert doc_khoa(_Req()) == ""
    # Dang khac Bearer thi khong phai khoa cua ta
    assert doc_khoa(_Req(authorization="Basic abc")) == ""


def test_x_api_key_duoc_uu_tien():
    assert doc_khoa(_Req(x_api_key="a", authorization="Bearer b")) == "a"


# --- Gioi han tan suat ---------------------------------------------------

def test_chan_khi_vuot_gioi_han():
    g = GioiHanTanSuat(3)
    assert [g.cho_phep("k", 0.0) for _ in range(3)] == [True, True, True]
    assert g.cho_phep("k", 0.0) is False


def test_cua_so_truot_mo_lai_sau_mot_phut():
    g = GioiHanTanSuat(2)
    assert g.cho_phep("k", 0.0) and g.cho_phep("k", 30.0)
    assert g.cho_phep("k", 59.0) is False      # van trong cua so 60s
    assert g.cho_phep("k", 61.0) is True       # loi goi luc 0.0 da roi ra


def test_moi_khoa_dem_rieng():
    """Mot khoa bi chan khong duoc lam anh huong khoa khac."""
    g = GioiHanTanSuat(1)
    assert g.cho_phep("a", 0.0) is True
    assert g.cho_phep("a", 0.0) is False
    assert g.cho_phep("b", 0.0) is True


def test_gioi_han_bang_khong_la_khong_gioi_han():
    g = GioiHanTanSuat(0)
    assert all(g.cho_phep("k", 0.0) for _ in range(50))


def test_vuot_gioi_han_tra_429_va_bao_thu_lai_duoc():
    """429 khac 401: khoa dung, chi la goi qua nhanh - nen `retryable` phai
    la True de ben goi biet cho roi thu lai."""
    client = app_co_khoa(["bi-mat"], moi_phut=2)
    for _ in range(2):
        assert client.get("/api/contacts",
                          headers={"X-API-Key": "bi-mat"}).status_code == 200
    r = client.get("/api/contacts", headers={"X-API-Key": "bi-mat"})
    assert r.status_code == 429
    assert r.json()["error"]["retryable"] is True


def test_gioi_han_khong_ap_cho_duong_dan_mo():
    """Chan /api/health se lam he thong giam sat tuong dich vu da chet."""
    client = app_co_khoa(["bi-mat"], moi_phut=1)
    for _ in range(5):
        assert client.get("/api/health").status_code == 200


# --- Cach ly bo test khoi .env cua may -----------------------------------

def test_bo_test_luon_chay_voi_xac_thuc_TAT():
    """Canh giu cho `conftest.py` o goc du an.

    Bo test doc `backend/.env` cua may dang chay. Hom bat xac thuc len, 140
    test do ngay vi 401 - ma nguon khong hong, chi la ket qua bo test phu
    thuoc vao cau hinh ca nhan cua tung may.

    Neu ai do go dong `os.environ["API_KEYS"] = ""` trong conftest, test nay do
    voi mot thong bao ro rang - thay vi 140 loi 401 khong ai doan duoc nguyen
    nhan.
    """
    from app.config import get_settings

    assert get_settings().api_key_list == [], (
        "Bo test dang doc API_KEYS tu backend/.env. Xem conftest.py o goc du "
        "an - no phai dat API_KEYS='' truoc khi bat ky tep test nao import "
        "app.main."
    )
