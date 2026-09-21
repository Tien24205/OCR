"""Xac minh dich vu bang LOI GOI THAT, khac han voi "da dien cau hinh".

VI SAO TACH RA KHOI `Settings.readiness()`: ham do chi tra loi "bien moi truong
da co gia tri chua" - mot phep kiem su co mat, khong ton dong nao va chay duoc
10 giay mot lan trong healthcheck. Cau hoi that su cua nguoi dung lai la
"no co CHAY khong", va cau do chi tra loi duoc bang mot lan goi that.

Ba trang thai khac han nhau, tai lieu ra soat Ngay 1-2 (D1-02) doi phai phan
biet cho ro:

    da cau hinh        - co gia tri trong .env. KHONG bao dam gi ca.
    mock / offline     - co tinh khong goi dich vu nao.
    da xac minh        - mot lan goi that da thanh cong, luc HH:MM.

Ket qua duoc nho trong bo nho tien trinh: goi Gemini ton tien va ton han muc,
nen khong duoc chay tu dong theo moi lan ve lai giao dien. Nguoi dung bam nut
thi moi chay.
"""

from __future__ import annotations

import io
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.services.extract.base import ExtractionError
from app.services.ocr.base import OcrError
from app.services.providers import build_extractor, build_ocr

PROBE_TEXT = "TARO YAMADA\ntaro@example.co.jp"

VERIFIED = "verified"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass
class Check:
    component: str          # ocr | extract | enrich
    provider: str
    state: str              # VERIFIED | FAILED | SKIPPED
    detail: str             # mot cau cho nguoi doc - KHONG BAO GIO chua khoa
    ms: int | None = None


def _probe_image() -> bytes:
    """Anh thu nho nhat, ve bang font mac dinh cua Pillow.

    KHONG dung font he thong: ham nay chay ca trong container Linux, noi khong
    co font Windows nao. Anh chi de chung minh duong day song, khong de do
    chat luong doc chu.
    """
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((20, 60), PROBE_TEXT, fill="black", spacing=16)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _che_khoa(text: str, config) -> str:
    """Chot chan cuoi cung: ket qua nay di ra /api/health, ma health khong doi
    khoa API. Mot thong bao loi cua thu vien lo ra khoa se thanh ro ri vinh vien
    trong log giam sat."""
    for bi_mat in (config.gemini_api_key, str(config.credentials_path or "")):
        if bi_mat and len(bi_mat) > 6:
            text = text.replace(bi_mat, "***")
    return text


def _kiem_ocr(config) -> tuple[Check, int]:
    provider_name = config.ocr_provider
    if provider_name == "mock":
        return Check("ocr", provider_name, SKIPPED,
                     "Phát lại kết quả đã lưu; không gọi dịch vụ OCR nào."), 0
    try:
        provider = build_ocr(config)
    except OcrError as exc:
        return Check("ocr", provider_name, FAILED,
                     exc.message.splitlines()[0]), 0

    if provider_name in ("tesseract", "rapidocr"):
        # Ham dung da chay duoc nghia la phan mem/model da san sang - ca hai
        # provider cuc bo deu kiem dieu do ngay luc khoi tao. Con lai la bay
        # hay gap nhat cua Tesseract: cai roi nhung thieu goi ngon ngu.
        # RapidOCR khong co khai niem do (model gan lien voi ngon ngu da chon)
        # nen khong bat buoc phai co ham nay.
        thieu = (provider.missing_languages()
                 if hasattr(provider, "missing_languages") else [])
        if thieu:
            return Check("ocr", provider_name, FAILED,
                         "Thiếu gói ngôn ngữ: " + ", ".join(thieu)), 0
        return Check("ocr", provider_name, VERIFIED,
                     f"{provider_name} {provider._version}, đủ gói "
                     f"{'+'.join(config.language_hint_list)}."), 0

    # google: chi mot loi goi that moi chung minh credentials dung.
    started = time.perf_counter()
    try:
        provider.recognize(_probe_image(), "image/png")
    except OcrError as exc:
        return Check("ocr", provider_name, FAILED, exc.message), 1
    finally:
        if hasattr(provider, "close"):
            provider.close()
    ms = int((time.perf_counter() - started) * 1000)
    return Check("ocr", provider_name, VERIFIED,
                 f"Google Vision trả lời trong {ms} ms.", ms), 1


def _kiem_extract(config) -> tuple[Check, int]:
    provider_name = config.extractor
    if provider_name != "gemini":
        return Check("extract", provider_name, SKIPPED,
                     "Bộ trích xuất regex chạy cục bộ; không gọi dịch vụ."), 0
    if not config.gemini_api_key:
        return Check("extract", provider_name, FAILED,
                     "Thiếu GEMINI_API_KEY trong backend/.env."), 0
    if not config.gemini_model:
        return Check("extract", provider_name, FAILED,
                     "Thiếu GEMINI_MODEL. Chạy try_ocr.py --list-models."), 0

    started = time.perf_counter()
    try:
        extractor = build_extractor(config)
        extractor.extract(_probe_image(), "image/png", PROBE_TEXT)
    except ExtractionError as exc:
        return Check("extract", provider_name, FAILED, exc.message), 1
    ms = int((time.perf_counter() - started) * 1000)
    # Cau hoi lon nhat khong phai "co goi duoc khong" ma "model co CHAP NHAN
    # schema CardExtraction khong" - den duoc day tuc la co.
    return Check("extract", provider_name, VERIFIED,
                 f"Model {config.gemini_model} chấp nhận schema "
                 f"CardExtraction ({ms} ms).", ms), 1


def _suy_ra_enrich(config, extract: Check) -> Check:
    """Tra cuu khong co phep thu rieng: no dung chung khoa Gemini voi buoc
    trich xuat, va phan con lai la mang ra ngoai - thu chi biet duoc khi gap
    mot trang that. Vi vay day la SUY RA, khong phai da xac minh."""
    if not config.enrich_enabled:
        return Check("enrich", "tắt", SKIPPED, "ENRICH_ENABLED=false.")
    if extract.state == VERIFIED:
        return Check("enrich", "bật", SKIPPED,
                     "Dùng chung khoá Gemini đã xác minh; nguồn web chỉ biết "
                     "được khi gặp trang thật.")
    return Check("enrich", "bật", SKIPPED,
                 "Cần Gemini chạy được và nguồn web phù hợp.")


_last: dict | None = None


def last_result() -> dict | None:
    """Ket qua xac minh gan nhat cua tien trinh nay, hoac None neu chua chay."""
    return _last


def verify(config) -> dict:
    """Chay cac phep thu that. Ton toi hai lan goi dich vu."""
    global _last
    ocr, calls_ocr = _kiem_ocr(config)
    extract, calls_extract = _kiem_extract(config)
    checks = [ocr, extract, _suy_ra_enrich(config, extract)]

    ket_qua = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "service_calls": calls_ocr + calls_extract,
        # "san sang" chi tinh khi KHONG co phep thu nao that bai. Che do mock
        # bi bo qua chu khong tinh la dat - so do lay tu mock khong dung de
        # nghiem thu.
        "ready": all(c.state != FAILED for c in checks),
        "measurable": ocr.state == VERIFIED and extract.state == VERIFIED,
        "checks": [
            {**asdict(c), "detail": _che_khoa(c.detail, config)} for c in checks
        ],
    }
    _last = ket_qua
    return ket_qua
