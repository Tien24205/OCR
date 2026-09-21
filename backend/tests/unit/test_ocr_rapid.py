"""Kiem tra nha cung cap RapidOCR ma KHONG can cai rapidocr.

Cung ly do nhu `test_ocr_tesseract.py`: neu doi phai cai ca ONNX Runtime
(~200 MB) moi chay duoc test thi vung code nay khong bao gio duoc kiem trong
CI, va loi doi ket qua se chi lo ra luc dang quet anh that.

Mot test o cuoi CO chay RapidOCR that, va tu bo qua khi may chua cai.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from app.services.ocr.base import OcrError
from app.services.ocr.rapid import RapidOcrProvider, _thanh_khoi


def ket_qua(txts, boxes=None, scores=None):
    """Dung lai dung hinh dang `RapidOCROutput` ma thu vien tra ve."""
    return SimpleNamespace(txts=txts, boxes=boxes, scores=scores)


def hop(x0, y0, x1, y1):
    """Hop bon diem, dung thu tu RapidOCR tra ve: trai-tren theo chieu kim."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# --- Doi ket qua thanh OcrBlock -------------------------------------------

def test_hop_bon_diem_duoc_quy_ve_chu_nhat_bao_quanh():
    """`OcrBlock` chi giu (x_min, y_min, x_max, y_max). Anh chup nghieng cho
    hop hinh thoi, nen phai lay bao quanh chu khong lay hai diem bat ky."""
    khoi = _thanh_khoi(ket_qua(["山田 太郎"], [[[65, 90], [586, 88], [587, 138], [65, 139]]],
                               [0.97]))
    assert len(khoi) == 1
    assert khoi[0].bbox == (65, 88, 587, 139)
    assert khoi[0].confidence == pytest.approx(0.97)


def test_dong_trong_bi_bo_qua():
    khoi = _thanh_khoi(ket_qua(["山田", "   ", ""], [hop(0, 0, 1, 1)] * 3, [1.0, 1.0, 1.0]))
    assert [k.text for k in khoi] == ["山田"]


def test_thieu_toa_do_hay_diem_tin_cay_khong_lam_hong_ca_ban_quet():
    """Thu vien co the tra `boxes=None` khi khong tim thay vung chu nao. Mot
    ban quet that khong duoc chet vi thieu toa do - chu van dung gia tri."""
    khoi = _thanh_khoi(ket_qua(["taro@example.co.jp"], None, None))
    assert khoi[0].text == "taro@example.co.jp"
    assert khoi[0].bbox == (0, 0, 0, 0)
    assert khoi[0].confidence is None


def test_khong_doc_duoc_chu_nao_thi_tra_ve_rong_chu_khong_nem_loi():
    assert _thanh_khoi(ket_qua(None, None, None)) == []


# --- Chon model theo ngon ngu ---------------------------------------------

def gia_lap_thu_vien(monkeypatch, ghi_lai: dict):
    """Thay `rapidocr` bang mot module gia, de test chay khong can cai that."""
    import sys
    from enum import Enum

    class LangRec(Enum):
        JAPAN = "japan"
        KOREAN = "korean"
        CH = "ch"

    class OCRVersion(Enum):
        PPOCRV4 = "v4"
        PPOCRV5 = "v5"

    class ModelType(Enum):
        MOBILE = "mobile"
        SERVER = "server"

    class RapidOCR:
        def __init__(self, params=None):
            ghi_lai["params"] = params

        def __call__(self, image):
            return ket_qua(["山田 太郎"], [hop(0, 0, 10, 10)], [1.0])

    gia = SimpleNamespace(LangRec=LangRec, OCRVersion=OCRVersion,
                          ModelType=ModelType, RapidOCR=RapidOCR)
    monkeypatch.setitem(sys.modules, "rapidocr", gia)
    return gia


@pytest.mark.parametrize("hints,mong_doi", [
    (["ko", "en"], "KOREAN/PPOCRV5"),
    (["ja", "en"], "JAPAN/PPOCRV4"),
    (["en"], "mac dinh"),
    (["zh", "en"], "mac dinh"),
])
def test_chon_model_theo_goi_y_ngon_ngu(monkeypatch, hints, mong_doi):
    """Goi y ngon ngu quyet dinh model. Chon sai thi Hangul ra o vuong ma
    khong co loi nao duoc nem."""
    ghi = {}
    gia_lap_thu_vien(monkeypatch, ghi)
    provider = RapidOcrProvider(hints)
    assert mong_doi in provider._version


def test_luon_dung_bo_phat_hien_manh_hon_mac_dinh(monkeypatch):
    """Bo phat hien mac dinh (v6 small) BO SOT dong dia chi tren the Han:
    doc dung nhung 9 dong chi thay 7, va phep do ghi do la "sot". Day la lua
    chon da doi ket qua do duoc, nen phai khoa lai."""
    ghi = {}
    gia = gia_lap_thu_vien(monkeypatch, ghi)
    RapidOcrProvider(["ko"])
    assert ghi["params"]["Det.ocr_version"] is gia.OCRVersion.PPOCRV4
    assert ghi["params"]["Det.model_type"] is gia.ModelType.SERVER


def test_ngon_ngu_dau_tien_co_model_rieng_thang(monkeypatch):
    """`ja,ko` phai ra model Nhat chu khong phai model cua ngon ngu cuoi."""
    gia_lap_thu_vien(monkeypatch, {})
    assert "JAPAN" in RapidOcrProvider(["ja", "ko"])._version


def test_thieu_thu_vien_bao_dung_cach_cai_chu_khong_nem_ImportError(monkeypatch):
    """Loi ImportError tho di ra ngoai se thanh 500 va nguoi dung khong biet
    phai lam gi. Ca duong ong cua du an chi hieu `OcrError`."""
    import builtins

    that = builtins.__import__

    def chan(name, *args, **kwargs):
        if name == "rapidocr":
            raise ImportError("khong co")
        return that(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", chan)
    with pytest.raises(OcrError) as loi:
        RapidOcrProvider(["ja"])
    assert loi.value.code == "OCR_NOT_CONFIGURED"
    assert "pip install rapidocr" in loi.value.message


def test_anh_hong_bi_tu_choi_bang_OCR_REJECTED(monkeypatch):
    gia_lap_thu_vien(monkeypatch, {})
    provider = RapidOcrProvider(["ja"])
    with pytest.raises(OcrError) as loi:
        provider.recognize(b"khong phai anh", "image/jpeg")
    assert loi.value.code == "OCR_REJECTED"


def test_ket_qua_khong_tu_nhan_da_phat_hien_ngon_ngu(monkeypatch):
    """Giong tesseract.py: provider duoc BAO truoc phai doc ngon ngu nao, no
    khong PHAT HIEN ngon ngu. Dien danh sach yeu cau vao `detected_languages`
    se khien phan con lai cua he thong tuong day la ket qua phat hien."""
    from PIL import Image

    gia_lap_thu_vien(monkeypatch, {})
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buffer, format="PNG")

    ket = RapidOcrProvider(["ja", "en"]).recognize(buffer.getvalue(), "image/png")
    assert ket.detected_languages == []
    assert ket.provider == "rapidocr"
    assert ket.payload["requested_languages"] == "ja+en"
    assert ket.raw_text == "山田 太郎"


# --- Mot test chay that, tu bo qua khi chua cai ---------------------------

def test_doc_duoc_the_han_that():
    """Ly do ton tai cua ca nha cung cap nay: Tesseract doc `김민준` thanh
    `Oo] xX`. Neu RapidOCR cung hong thi khong con ly do giu no."""
    pytest.importorskip("rapidocr", reason="chua cai rapidocr")
    from pathlib import Path

    anh = (Path(__file__).resolve().parents[3]
           / "datasets" / "_dryrun" / "dev" / "ko" / "001.jpg")
    if not anh.is_file():
        pytest.skip("chua sinh anh chay kho")

    ket = RapidOcrProvider(["ko", "en"]).recognize(anh.read_bytes(), "image/jpeg")
    assert "김민준" in ket.raw_text
    assert "minjun.kim@example.co.kr" in ket.raw_text
