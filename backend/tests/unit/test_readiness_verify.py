"""Xac minh dich vu that - phan biet "da cau hinh" voi "chay duoc".

D1-02 trong ra-soat-ngay-1-2.md: den xanh cu chi noi ".env co gia tri", ma
nguoi doc lai hieu la "dich vu chay duoc". Hai cau do khac han nhau, va cai
gia cua viec nham la phat hien ra luc dang do 40 the.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import readiness
from app.services.extract.base import ExtractionError
from app.services.ocr.base import OcrError


def config(**kwargs) -> Settings:
    base = {"_env_file": None, "ocr_provider": "mock", "extractor": "heuristic",
            "enrich_enabled": False}
    base.update(kwargs)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _quen_ket_qua_cu(monkeypatch):
    monkeypatch.setattr(readiness, "_last", None)


# --- Che do gia lap khong duoc tinh la da xac minh ------------------------

def test_mock_bi_bo_qua_chu_khong_duoc_bao_la_dat():
    kq = readiness.verify(config())
    trang_thai = {c["component"]: c["state"] for c in kq["checks"]}
    assert trang_thai["ocr"] == "skipped"
    assert trang_thai["extract"] == "skipped"
    assert kq["service_calls"] == 0
    # Khong loi nao, nhung cung KHONG dung de do chat luong.
    assert kq["ready"] is True
    assert kq["measurable"] is False


# --- OCR ------------------------------------------------------------------

def test_tesseract_thieu_goi_ngon_ngu_la_that_bai(monkeypatch):
    """Cai roi nhung quen goi tieng Nhat la bay hay gap nhat, va no khong lam
    ham dung bao loi - chi den luc doc the Nhat moi lo ra."""
    class GiaLap:
        _version = "5.5.0"

        def missing_languages(self):
            return ["jpn"]

    monkeypatch.setattr(readiness, "build_ocr", lambda c: GiaLap())
    kq = readiness.verify(config(ocr_provider="tesseract"))
    ocr = kq["checks"][0]
    assert ocr["state"] == "failed"
    assert "jpn" in ocr["detail"]
    assert kq["ready"] is False
    assert kq["service_calls"] == 0     # kiem cuc bo, khong ton han muc


def test_tesseract_du_goi_la_da_xac_minh(monkeypatch):
    class GiaLap:
        _version = "5.5.0"

        def missing_languages(self):
            return []

    monkeypatch.setattr(readiness, "build_ocr", lambda c: GiaLap())
    ocr = readiness.verify(config(ocr_provider="tesseract"))["checks"][0]
    assert ocr["state"] == "verified"
    assert "5.5.0" in ocr["detail"]


def test_ocr_chua_cai_duoc_bao_bang_cau_dau_tien_cua_loi(monkeypatch):
    def no(config):
        raise OcrError("OCR_NOT_CONFIGURED",
                       "Khong chay duoc Tesseract. Cai dat:\nhttps://…")

    monkeypatch.setattr(readiness, "build_ocr", no)
    ocr = readiness.verify(config(ocr_provider="tesseract"))["checks"][0]
    assert ocr["state"] == "failed"
    assert ocr["detail"] == "Khong chay duoc Tesseract. Cai dat:"


# --- Trich xuat -----------------------------------------------------------

def test_gemini_thieu_khoa_khong_ton_loi_goi_nao():
    kq = readiness.verify(config(extractor="gemini", gemini_api_key=""))
    extract = kq["checks"][1]
    assert extract["state"] == "failed"
    assert "GEMINI_API_KEY" in extract["detail"]
    assert kq["service_calls"] == 0


def test_gemini_chap_nhan_schema_moi_tinh_la_xac_minh(monkeypatch):
    goi = []

    class GiaLap:
        def extract(self, image, mime, raw_text):
            goi.append((mime, raw_text))
            return object()

    monkeypatch.setattr(readiness, "build_extractor", lambda c: GiaLap())
    kq = readiness.verify(config(extractor="gemini", gemini_api_key="x" * 40,
                                 gemini_model="gemini-3.5-flash-lite"))
    extract = kq["checks"][1]
    assert extract["state"] == "verified"
    assert "CardExtraction" in extract["detail"]
    assert kq["service_calls"] == 1
    assert goi and goi[0][0] == "image/png"   # co gui anh that, khong chi van ban


def test_schema_bi_tu_choi_la_that_bai_va_van_tinh_la_da_goi(monkeypatch):
    def no(config):
        raise ExtractionError("EXTRACT_BAD_SCHEMA", "Model trả JSON sai schema.")

    monkeypatch.setattr(readiness, "build_extractor", no)
    kq = readiness.verify(config(extractor="gemini", gemini_api_key="x" * 40,
                                 gemini_model="m"))
    assert kq["checks"][1]["state"] == "failed"
    assert kq["ready"] is False
    assert kq["service_calls"] == 1


# --- Chot chan bao mat ----------------------------------------------------

def test_ket_qua_khong_bao_gio_chua_khoa(monkeypatch):
    """Ket qua nay di ra /api/health, ma health khong doi khoa API. Mot thu
    vien lo khoa trong thong bao loi se thanh ro ri vinh vien trong log."""
    khoa = "AQ.Ab8_that_su_la_khoa_that_0123456789"

    def no(config):
        raise ExtractionError("EXTRACT_CALL_FAILED", f"401 Unauthorized: {khoa}")

    monkeypatch.setattr(readiness, "build_extractor", no)
    kq = readiness.verify(config(extractor="gemini", gemini_api_key=khoa,
                                 gemini_model="m"))
    assert khoa not in str(kq)
    assert "***" in kq["checks"][1]["detail"]


# --- Bo nho ket qua -------------------------------------------------------

def test_health_khong_tu_goi_dich_vu_ma_doc_lai_ket_qua_da_luu():
    """Neu /api/health tu xac minh thi healthcheck cua Docker (10 giay mot
    lan) se dot han muc Gemini ma khong ai yeu cau."""
    assert readiness.last_result() is None
    kq = readiness.verify(config())
    assert readiness.last_result() == kq


def test_health_tra_ve_None_truoc_khi_xac_minh_va_ket_qua_sau_do(monkeypatch):
    """Noi day hai dau: giao dien doc `verified` tu /api/health, nen neu
    endpoint xac minh khong ghi vao cho health doc thi nut bam xong van khong
    thay gi doi."""
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(readiness, "_last", None)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["verified"] is None

        ket_qua = client.post("/api/readiness/verify").json()
        assert ket_qua["checked_at"]

        sau = client.get("/api/health").json()["verified"]
        assert sau == ket_qua
