"""Kiem tra viec thu lai cua cong cu do chat luong.

VI SAO CAN: Gemini tra 503 "high demand" mot cach ngau nhien. Lan chay thu
dau tien cua duong do that bai ca 20/20 the chi vi ly do nay - khong phai vi
OCR doc sai.

Neu bo luon the gap 503, con so chat luong se tron lan hai thu khac han nhau:
OCR doc sai (dieu can do) va Google het cho (dieu khong lien quan). Lan chay
hom nay va lan chay ngay mai se ra so khac nhau ma khong ai giai thich duoc.
"""

from __future__ import annotations

import pytest

from app.services.extract.base import ExtractionError
from app.services.ocr.base import OcrError
from scripts import evaluate


@pytest.fixture(autouse=True)
def _khong_cho_that(monkeypatch):
    """Bo qua thoi gian cho de test chay nhanh."""
    monkeypatch.setattr(evaluate.time, "sleep", lambda _: None)


def chay(loi_lan_luot: list[Exception | None]):
    """Dung mot `run_one` gia tra ve loi theo thu tu da dinh.

    Tra ve (ket qua, so lan thu lai, so lan da goi).
    """
    goi = {"n": 0}

    def gia(row, ocr, extractor, image_root):
        i = goi["n"]
        goi["n"] += 1
        loi = loi_lan_luot[i] if i < len(loi_lan_luot) else None
        if loi is not None:
            raise loi
        return {"image": row["image"], "ok": True}

    return gia, goi


def test_thu_lai_loi_tam_thoi_roi_thanh_cong(monkeypatch):
    gia, goi = chay([OcrError("OCR_UNAVAILABLE", "ban", retryable=True), None])
    monkeypatch.setattr(evaluate, "run_one", gia)

    card, so_lan_thu_lai = evaluate.run_with_retry(
        {"image": "dev/ja/001.jpg"}, None, None, None, log=lambda *_: None)

    assert card["ok"] is True
    assert so_lan_thu_lai == 1
    assert goi["n"] == 2


def test_khong_thu_lai_loi_vinh_vien(monkeypatch):
    """Anh hong hay sai quyen thi thu lai chi keo dai lan chay.

    Day la ly do phai ton trong co `retryable` thay vi thu lai moi loi.
    """
    gia, goi = chay([ExtractionError("EXTRACT_REJECTED", "anh hong",
                                     retryable=False), None])
    monkeypatch.setattr(evaluate, "run_one", gia)

    with pytest.raises(ExtractionError):
        evaluate.run_with_retry({"image": "x.jpg"}, None, None, None,
                                log=lambda *_: None)

    assert goi["n"] == 1, "loi vinh vien ma van goi lai"


def test_bo_cuoc_sau_khi_het_ngan_sach(monkeypatch):
    """Het so lan thu thi nem loi that, khong nuot im lang."""
    loi = OcrError("OCR_UNAVAILABLE", "ban", retryable=True)
    gia, goi = chay([loi, loi, loi, loi])
    monkeypatch.setattr(evaluate, "run_one", gia)

    with pytest.raises(OcrError):
        evaluate.run_with_retry({"image": "x.jpg"}, None, None, None,
                                log=lambda *_: None)

    assert goi["n"] == evaluate._RETRIES


def test_thanh_cong_ngay_lan_dau_khong_cho(monkeypatch):
    gia, goi = chay([None])
    monkeypatch.setattr(evaluate, "run_one", gia)

    card, so_lan_thu_lai = evaluate.run_with_retry(
        {"image": "x.jpg"}, None, None, None, log=lambda *_: None)

    assert so_lan_thu_lai == 0 and goi["n"] == 1


def test_het_quota_thi_khong_thu_lai_va_dung_han(monkeypatch):
    """Ma nay phai vua khong duoc thu lai, vua nam trong danh sach dung han.

    Neu thieu mot trong hai: thu lai se dot not han muc con lai, con chay tiep
    se in them hang chuc dong loi giong het nhau roi cung khong co ket qua.
    """
    het = ExtractionError("EXTRACT_QUOTA_EXCEEDED", "het han muc ngay",
                          retryable=False)
    gia, goi = chay([het, None])
    monkeypatch.setattr(evaluate, "run_one", gia)

    with pytest.raises(ExtractionError):
        evaluate.run_with_retry({"image": "x.jpg"}, None, None, None,
                                log=lambda *_: None)

    assert goi["n"] == 1, "het quota ma van goi lai"
    assert "EXTRACT_QUOTA_EXCEEDED" in evaluate._DUNG_HAN


def test_co_bao_cho_nguoi_dung_biet_dang_thu_lai(monkeypatch):
    """Lan chay im lang roi bong lau gap doi se lam nguoi dung tuong treo."""
    gia, _ = chay([OcrError("OCR_UNAVAILABLE", "ban", retryable=True), None])
    monkeypatch.setattr(evaluate, "run_one", gia)

    dong: list[str] = []
    evaluate.run_with_retry({"image": "x.jpg"}, None, None, None,
                            log=dong.append)

    assert len(dong) == 1
    assert "OCR_UNAVAILABLE" in dong[0]
