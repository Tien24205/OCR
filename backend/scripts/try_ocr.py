"""Spike OCR cua Ngay 2 - chay doc lap, khong can backend hay giao dien.

MUC DICH: chung minh OCR va trich xuat truong hoat dong that voi ca tieng Anh
va tieng Nhat, TRUOC khi dau tu thoi gian vao giao dien. Neu de den khi ung
dung hoan thien moi phat hien dich vu khong dung duoc thi da mat vai ngay.

CACH DUNG:

    # 1. Xem model Gemini nao tai khoan cua ban dang dung duoc
    python backend/scripts/try_ocr.py --list-models

    # 2. Chay tren anh that (dat GEMINI_MODEL trong backend/.env truoc)
    python backend/scripts/try_ocr.py datasets/dev/ja/001.jpg datasets/dev/en/001.jpg

    # 3. Chi chay OCR, bo qua Gemini
    python backend/scripts/try_ocr.py --no-extract anh.jpg

Ket qua duoc luu vao backend/tests/fixtures/ocr/<sha256>.json, sau do bo
kiem thu dung lai lam du lieu gia lap - nghia la test chay tren du lieu THAT
ma khong can goi mang.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Console Windows mac dinh dung cp1252 va se nem UnicodeEncodeError khi in
# chu Nhat. Ep UTF-8 ngay tu dau - neu khong, ban se tuong OCR loi trong khi
# thuc ra chi la loi hien thi cua terminal.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.config import get_settings  # noqa: E402
from app.services.extract.base import ExtractionError  # noqa: E402
from app.services.extract.grounding import ground_extraction  # noqa: E402
from app.services.extract.heuristic import HeuristicExtractor  # noqa: E402
from app.services.ocr.base import OcrError  # noqa: E402

FIXTURE_DIR = BACKEND_DIR / "tests" / "fixtures" / "ocr"
MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
VERDICT_FLAG = {"exact": "OK  ", "fuzzy": "?   ", "unverified": "LOAI"}
SEP = "=" * 70


def list_models(settings) -> int:
    """Liet ke model dang dung duoc.

    Vi sao can: ten model Gemini thay doi theo thoi gian va theo tung tai
    khoan. Doan ten roi hardcode la cach chac chan de gap loi 404 kho hieu.
    Hoi thang API la cach duy nhat biet chinh xac.
    """
    if not settings.gemini_api_key:
        print("Thieu GEMINI_API_KEY trong backend/.env")
        return 1

    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    header = "MODEL".ljust(45) + "VAO".rjust(9) + "RA".rjust(9)
    print(header)
    print("-" * len(header))

    found = 0
    for model in client.models.list():
        if "generateContent" not in (model.supported_actions or []):
            continue
        found += 1
        name = (model.name or "").removeprefix("models/")
        print(
            name.ljust(45)
            + str(model.input_token_limit or 0).rjust(9)
            + str(model.output_token_limit or 0).rjust(9)
        )

    if not found:
        print("Khong co model nao ho tro generateContent.")
        return 1

    print("")
    print("Chon mot ten o tren, dat vao GEMINI_MODEL trong backend/.env")
    return 0


def build_ocr(settings):
    if settings.ocr_provider == "mock":
        from app.services.ocr.mock import MockOcrProvider

        return MockOcrProvider()

    from app.services.ocr.google_vision import GoogleVisionProvider

    return GoogleVisionProvider(
        language_hints=settings.language_hint_list,
        timeout_s=settings.ocr_timeout_s,
    )


def build_extractor(settings, force_heuristic: bool):
    if force_heuristic or settings.extractor == "heuristic":
        return HeuristicExtractor()

    from app.services.extract.gemini import GeminiExtractor

    return GeminiExtractor(
        api_key=settings.gemini_api_key or "",
        model=settings.gemini_model or "",
        temperature=settings.gemini_temperature,
    )


def save_fixture(path: Path, digest: str, ocr_result, extraction, grounded,
                 extract_ms: int) -> Path:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    fixture = {
        "source_file": path.name,
        "raw_text": ocr_result.raw_text,
        "provider": ocr_result.provider,
        "provider_version": ocr_result.provider_version,
        "detected_languages": ocr_result.detected_languages,
        "blocks": [
            {
                "text": b.text,
                "bbox": list(b.bbox),
                "confidence": b.confidence,
                "languages": list(b.languages),
            }
            for b in ocr_result.blocks
        ],
        "payload": ocr_result.payload,
        "extraction": extraction.model_dump() if extraction else None,
        "grounding": grounded["report"] if grounded else None,
        "ms_ocr": ocr_result.ms,
        "ms_extract": extract_ms,
    }
    out = FIXTURE_DIR / (digest + ".json")
    out.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def process(path: Path, ocr, extractor, save: bool) -> dict | None:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    mime = MIMES.get(path.suffix.lower(), "image/jpeg")

    print("")
    print(SEP)
    print(str(path) + "  (" + format(len(data) / 1024, ",.0f") + " KB, "
          + digest[:12] + ")")
    print(SEP)

    try:
        ocr_result = ocr.recognize(data, mime)
    except OcrError as exc:
        print("  OCR LOI [" + exc.code + "] " + exc.message)
        return None

    langs = ocr_result.detected_languages or ["khong ro"]
    print("")
    print("--- OCR (" + ocr_result.provider + ", " + str(ocr_result.ms)
          + " ms, ngon ngu phat hien: " + ", ".join(langs) + ") ---")
    print(ocr_result.raw_text or "(rong)")

    if extractor is None:
        return None

    started = time.perf_counter()
    try:
        extraction = extractor.extract(data, mime, ocr_result.raw_text)
    except ExtractionError as exc:
        print("")
        print("  TRICH XUAT LOI [" + exc.code + "] " + exc.message)
        return None
    extract_ms = int((time.perf_counter() - started) * 1000)

    grounded = ground_extraction(extraction, ocr_result.raw_text)
    counts = grounded["counts"]

    print("")
    print("--- TRICH XUAT (" + extractor.name + ", " + str(extract_ms)
          + " ms, ngon ngu the: " + (grounded["card_language"] or "?") + ") ---")
    for field, items in grounded["report"].items():
        for item in items:
            print("  " + VERDICT_FLAG[item["verdict"]] + " "
                  + field.ljust(15) + " " + item["value"])

    print("")
    print("  Doi chieu voi van ban OCR: " + str(counts["exact"])
          + " khop nguyen van, " + str(counts["fuzzy"]) + " khop gan dung, "
          + str(counts["unverified"]) + " KHONG CO TREN THE (da loai)")
    if counts["unverified"]:
        print("  >> Truong bi loai la du lieu model tu sinh. Day chinh la so"
              " lieu cot 'Tu sinh' cua bao cao Ngay 9.")

    if save:
        out = save_fixture(path, digest, ocr_result, extraction, grounded,
                           extract_ms)
        print("")
        print("  Da luu fixture: " + str(out.relative_to(BACKEND_DIR.parent)))

    return {
        "name": path.name,
        "ms_ocr": ocr_result.ms,
        "ms_extract": extract_ms,
        "counts": counts,
        "chars": len(ocr_result.raw_text),
    }


def print_summary(results: list[dict], total: int) -> None:
    print("")
    print(SEP)
    print("TONG KET " + str(len(results)) + "/" + str(total) + " anh")
    print(SEP)
    print("ANH".ljust(28) + "KY TU".rjust(6) + "OCR ms".rjust(8)
          + "XUAT ms".rjust(9) + "KHOP".rjust(6) + "GAN".rjust(5)
          + "LOAI".rjust(6))
    for r in results:
        c = r["counts"]
        print(
            r["name"][:27].ljust(28)
            + str(r["chars"]).rjust(6)
            + str(r["ms_ocr"]).rjust(8)
            + str(r["ms_extract"]).rjust(9)
            + str(c["exact"]).rjust(6)
            + str(c["fuzzy"]).rjust(5)
            + str(c["unverified"]).rjust(6)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike OCR Ngay 2")
    parser.add_argument("images", nargs="*", type=Path)
    parser.add_argument("--list-models", action="store_true",
                        help="Liet ke model Gemini dung duoc roi thoat")
    parser.add_argument("--no-extract", action="store_true",
                        help="Chi chay OCR, bo qua buoc trich xuat truong")
    parser.add_argument("--heuristic", action="store_true",
                        help="Ep dung bo trich xuat regex thay vi Gemini")
    parser.add_argument("--no-save", action="store_true",
                        help="Khong ghi fixture")
    args = parser.parse_args()

    settings = get_settings()

    if args.list_models:
        return list_models(settings)

    if not args.images:
        parser.print_help()
        return 1

    missing = [p for p in args.images if not p.is_file()]
    if missing:
        for p in missing:
            print("Khong tim thay: " + str(p))
        return 1

    print("OCR       : " + settings.ocr_provider)
    print("Trich xuat: " + ("(bo qua)" if args.no_extract else settings.extractor))
    print("Ngon ngu  : " + ", ".join(settings.language_hint_list))

    try:
        ocr = build_ocr(settings)
        extractor = None if args.no_extract else build_extractor(
            settings, args.heuristic
        )
    except (OcrError, ExtractionError) as exc:
        print("")
        print("Khong khoi tao duoc: [" + exc.code + "] " + exc.message)
        return 1

    results = []
    for image_path in args.images:
        result = process(image_path, ocr, extractor, save=not args.no_save)
        if result:
            results.append(result)

    if results:
        print_summary(results, len(args.images))

    return 0 if len(results) == len(args.images) else 1


if __name__ == "__main__":
    sys.exit(main())
