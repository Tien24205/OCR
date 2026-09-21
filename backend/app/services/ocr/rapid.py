"""Nha cung cap OCR: RapidOCR - model PP-OCR chay bang ONNX Runtime.

VI SAO THEM NHA CUNG CAP THU BA: Tesseract doc Hangul hong han. Tren the
`_dryrun/dev/ko/001.jpg`, ten `김민준` ra thanh `Oo] xX` va ten cong ty mat
hoan toan. Google Vision doc tot nhung doi tai khoan thanh toan. RapidOCR
chay cuc bo, giay phep Apache-2.0, khong ton dong nao, va doc dung ca ba
he chu CJK.

CHON MODEL THEO NGON NGU. Thu vien chi chap nhan mot so to hop:

    JAPAN  : PPOCRV4/MOBILE
    KOREAN : PPOCRV4/MOBILE, PPOCRV5/MOBILE
    CH     : PPOCRV4|PPOCRV5 x MOBILE|SERVER
    EN     : PPOCRV4|PPOCRV5 x MOBILE

Moi to hop khac bi nem `ValueError("Invalid OCR configuration.")` ngay luc
khoi tao, nen khong duoc doan.

DANH DOI DA DO DUOC, phai biet truoc khi chon: model tieng Nhat doc Kanji
dung hon (`携帯`) nhung doc chu Latin te hon - email `taro.yamada@...` ra
thanh `taro.yamadag...`, URL mat dau. Model mac dinh (Trung/v6) thi nguoc
lai. Khong co lua chon nao thang moi mat; phai do bang `evaluate.py` tren
tung ngon ngu.

MODEL TAI VE LAN CHAY DAU va nam trong `site-packages`. May khong co mang o
lan chay dau se hong - loi nem ra phai noi dung dieu do.
"""

from __future__ import annotations

import io
import time

from app.services.ocr.base import OcrBlock, OcrError, OcrResult

# Gợi ý ngôn ngữ -> tham số model. Chỉ các tổ hợp thư viện chấp nhận.
_THEO_NGON_NGU = {
    "ko": ("KOREAN", "PPOCRV5"),
    "ja": ("JAPAN", "PPOCRV4"),
}


class RapidOcrProvider:
    """OCR cuc bo bang PP-OCR tren ONNX Runtime."""

    name = "rapidocr"

    def __init__(self, language_hints: list[str], timeout_s: int = 20) -> None:
        try:
            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
        except ImportError as exc:
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Thieu goi rapidocr. Chay:\n"
                "    pip install rapidocr onnxruntime",
            ) from exc

        self._hints = [h.strip().lower() for h in language_hints if h.strip()]
        self._timeout = timeout_s

        # Ngon ngu dau tien co model rieng se quyet dinh; khong co thi dung
        # mac dinh cua thu vien (Trung/Anh), von doc chu Latin tot nhat.
        # BO PHAT HIEN VUNG CHU quan trong hon bo nhan dang, va do la dieu
        # khong hien nhien. Voi bo phat hien mac dinh (v6 small), the Han mat
        # han dong dia chi - doc dung nhung 9 dong chi thay 7, va phep do ghi
        # do la "sot" chu khong phai "sai". Doi sang v4/SERVER thi dong do
        # hien tro lai. Chi tiet so do o Document/3-bao-cao/nang-cap-ocr-21-09.md
        params: dict = {
            "Det.ocr_version": OCRVersion.PPOCRV4,
            "Det.model_type": ModelType.SERVER,
        }
        self._lang_model = "mac dinh"
        for hint in self._hints:
            if hint in _THEO_NGON_NGU:
                lang, version = _THEO_NGON_NGU[hint]
                params.update({
                    "Rec.lang_type": getattr(LangRec, lang),
                    "Rec.ocr_version": getattr(OCRVersion, version),
                    "Rec.model_type": ModelType.MOBILE,
                })
                self._lang_model = f"{lang}/{version}"
                break

        # Khoi tao NGAY luc dung provider chu khong doi den anh dau tien: tai
        # model lan dau ton vai giay va can mang, hong o giua mot ban quet
        # that thi mat ban quet do.
        try:
            self._engine = RapidOCR(params=params)
        except Exception as exc:                        # thu vien nem Exception tho
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Khong khoi tao duoc RapidOCR. Lan chay dau can mang de tai "
                "model ve site-packages.\n"
                f"Chi tiet: {exc}",
            ) from exc

        # Goi khong xuat `__version__`; doc tu metadata cua ban cai. Phien ban
        # phai co that trong `provider_version` vi no duoc luu vao tung ban
        # quet - "?" thi sau nay khong truy lai duoc so do sinh ra boi ban nao.
        try:
            from importlib.metadata import version

            phien_ban = version("rapidocr")
        except Exception:
            phien_ban = "?"
        self._version = f"{phien_ban} ({self._lang_model})"

    def recognize(self, image: bytes, mime: str) -> OcrResult:
        import numpy as np
        from PIL import Image, UnidentifiedImageError

        try:
            picture = Image.open(io.BytesIO(image))
            picture.load()
            picture = picture.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise OcrError("OCR_REJECTED", "Khong doc duoc anh nay.") from exc

        started = time.perf_counter()
        try:
            ket_qua = self._engine(np.asarray(picture))
        except Exception as exc:
            raise OcrError("OCR_CALL_FAILED",
                           "RapidOCR tu choi xu ly anh nay.") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        blocks = _thanh_khoi(ket_qua)
        return OcrResult(
            raw_text="\n".join(b.text for b in blocks),
            provider=self.name,
            provider_version=self._version,
            blocks=blocks,
            # DE TRONG CO Y, giong tesseract.py: RapidOCR duoc BAO truoc phai
            # doc ngon ngu nao, no khong PHAT HIEN ngon ngu. Viec doan ngon
            # ngu do `app.services.languages.guess_language` lam tu chu that.
            detected_languages=[],
            payload={
                "block_count": len(blocks),
                "requested_languages": "+".join(self._hints),
                "lang_model": self._lang_model,
            },
            ms=elapsed_ms,
        )


def _thanh_khoi(ket_qua) -> list[OcrBlock]:
    """Doi ket qua RapidOCR thanh `OcrBlock` - kieu duy nhat phan con lai
    cua he thong biet.

    Hop bon diem duoc quy ve hinh chu nhat bao quanh: `OcrBlock` chi giu
    (x_min, y_min, x_max, y_max), va Ngay 5 chi can to sang mot vung.
    """
    texts = list(getattr(ket_qua, "txts", None) or [])
    boxes = getattr(ket_qua, "boxes", None)
    scores = list(getattr(ket_qua, "scores", None) or [])

    blocks = []
    for i, text in enumerate(texts):
        if not (text or "").strip():
            continue
        bbox = (0, 0, 0, 0)
        if boxes is not None and i < len(boxes):
            diem = boxes[i]
            xs = [int(p[0]) for p in diem]
            ys = [int(p[1]) for p in diem]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        blocks.append(OcrBlock(
            text=text,
            bbox=bbox,
            confidence=float(scores[i]) if i < len(scores) else None,
        ))
    return blocks
