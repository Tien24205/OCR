"""Hai cach xac thuc Google Cloud - chuan bi Ngay 15.

Duong Application Default Credentials (ADC) truoc day KHONG co test nao, du
`gcloud auth application-default login` la cach nhanh nhat de bat dau tren may
ca nhan. Nguoi dung ADC lai bi bao loi sai huong, vi `.env.example` dat san mot
duong dan file khong ton tai.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.cloud import vision

from app.config import Settings
from app.services.ocr.base import OcrError
from app.services.providers import build_ocr


@pytest.fixture()
def spy(monkeypatch):
    """Ghi lai Vision client duoc dung nhu the nao, khong goi mang."""
    calls = {"default": 0, "from_file": []}
    client = SimpleNamespace(annotate_image=None,
                             transport=SimpleNamespace(close=lambda: None))

    def default(*args, **kwargs):
        calls["default"] += 1
        return client

    def from_file(path):
        calls["from_file"].append(path)
        return client

    monkeypatch.setattr(vision, "ImageAnnotatorClient", default)
    monkeypatch.setattr(vision.ImageAnnotatorClient, "from_service_account_file",
                        from_file, raising=False)
    return calls


def config(**kwargs) -> Settings:
    base = {"_env_file": None, "ocr_provider": "google"}
    base.update(kwargs)
    return Settings(**base)


# --- (a) File service account ---------------------------------------------

def test_duong_dan_tuong_doi_neo_vao_backend():
    """`./secrets/gcp-sa.json` phai tinh tu backend/, khong phai tu thu muc
    dang chay - neu khong thi khoi dong tu goc repo se tim sai cho."""
    settings = config(google_application_credentials="./secrets/gcp-sa.json")
    assert settings.credentials_path.is_absolute()
    assert settings.credentials_path.parent.name == "secrets"
    assert settings.credentials_path.parent.parent.name == "backend"


def test_duong_dan_tuyet_doi_duoc_giu_nguyen(tmp_path):
    target = tmp_path / "sa.json"
    settings = config(google_application_credentials=str(target))
    assert settings.credentials_path == target


def test_co_file_thi_dung_from_service_account_file(spy, tmp_path):
    target = tmp_path / "sa.json"
    target.write_text("{}", encoding="utf-8")
    build_ocr(config(google_application_credentials=str(target)))

    assert spy["from_file"] == [str(target)]
    assert spy["default"] == 0


# --- (b) Application Default Credentials ----------------------------------

def test_khong_dat_bien_thi_dung_ADC(spy):
    """Bien de trong nghia la dung `gcloud auth application-default login`.
    Phai khoi tao client KHONG truyen tham so, de SDK tu tim credentials."""
    build_ocr(config(google_application_credentials=None))

    assert spy["default"] == 1
    assert spy["from_file"] == []


def test_chuoi_rong_cung_duoc_hieu_la_ADC(spy):
    """`GOOGLE_APPLICATION_CREDENTIALS=` trong .env cho ra chuoi rong, khong
    phai None. Phai xu ly nhu nhau."""
    settings = config(google_application_credentials="")
    assert settings.credentials_path is None
    build_ocr(settings)
    assert spy["default"] == 1


# --- Bao cao trang thai ---------------------------------------------------

def test_readiness_phan_biet_hai_che_do(tmp_path):
    """Nguoi dung ADK khong duoc thay bao cao giong het truong hop thieu
    cau hinh - hai tinh huong khac han nhau."""
    adc = config(google_application_credentials=None).readiness()
    assert adc["ocr_auth_mode"] == "application_default"
    assert adc["ocr_credentials_present"] is False

    target = tmp_path / "sa.json"
    target.write_text("{}", encoding="utf-8")
    with_file = config(google_application_credentials=str(target)).readiness()
    assert with_file["ocr_auth_mode"] == "service_account_file"
    assert with_file["ocr_credentials_present"] is True


def test_readiness_khong_bao_gio_lo_duong_dan_hay_gia_tri_khoa(tmp_path):
    target = tmp_path / "secret-sa.json"
    target.write_text("{}", encoding="utf-8")
    report = config(google_application_credentials=str(target),
                    gemini_api_key="mot-khoa-that").readiness()

    dumped = str(report)
    assert "secret-sa.json" not in dumped
    assert "mot-khoa-that" not in dumped


# --- Thong bao loi --------------------------------------------------------

def test_thong_bao_loi_neu_ca_hai_cach(monkeypatch):
    """Nguoi dung ADC ma chi duoc bao "kiem tra GOOGLE_APPLICATION_CREDENTIALS"
    se di sai huong: ho khong can file nao ca."""
    def boom(*args, **kwargs):
        raise RuntimeError("khong tim thay credentials")

    monkeypatch.setattr(vision, "ImageAnnotatorClient", boom)
    with pytest.raises(OcrError) as exc:
        build_ocr(config(google_application_credentials=None))

    message = exc.value.message
    assert "GOOGLE_APPLICATION_CREDENTIALS" in message
    assert "application-default login" in message
