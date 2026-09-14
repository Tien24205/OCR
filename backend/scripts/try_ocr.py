"""Spike OCR cua Ngay 2 - chay doc lap, khong can backend hay giao dien.

MUC DICH: chung minh OCR va trich xuat truong hoat dong that voi ca tieng Anh
va tieng Nhat, TRUOC khi dau tu thoi gian vao giao dien. Neu de den khi ung
dung hoan thien moi phat hien dich vu khong dung duoc thi da mat vai ngay.

CACH DUNG:

    # 1. Xem model Gemini nao tai khoan cua ban dang dung duoc
    python backend/scripts/try_ocr.py --list-models

    # 1b. Kiem tra credentials chay duoc - chi ton 2 loi goi
    python backend/scripts/try_ocr.py --check

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


def tiny_card() -> bytes:
    """Anh nho nhat con doc duoc, de kiem tra san sang voi chi phi thap nhat."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    for path in ("C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if Path(path).is_file():
            font = ImageFont.truetype(path, 40)
            break
    else:
        font = ImageFont.load_default(40)
    draw.text((30, 30), "\u5c71\u7530 \u592a\u90ce", font=font, fill=(0, 0, 0))
    draw.text((30, 100), "taro@example.co.jp", font=font, fill=(0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def preflight(settings) -> int:
    """Kiem tra cau hinh bang DUNG HAI loi goi dich vu.

    VI SAO CAN: chay thang 40 anh khi cau hinh sai se cho 40 loi giong nhau,
    kho biet loi nam o dau va van bi tinh tien nhung lan goi thanh cong. Lenh
    nay tra loi bon cau hoi rieng biet:

      1. Credentials cua Vision co doc duoc khong?
      2. Vision co that su tra ve chu tieng Nhat khong?
      3. GEMINI_MODEL co ton tai voi tai khoan nay khong?
      4. Model co CHAP NHAN schema `CardExtraction` khong?

    Cau 4 la an so lon nhat cua ca du an: schema do chua tung duoc mot model
    nao chap nhan lan nao.
    """
    print(SEP)
    print("KIEM TRA SAN SANG")
    print(SEP)

    ready = True
    calls = 0
    image = tiny_card()

    # --- 1 & 2. OCR ---
    print("")
    print("[1/2] OCR - " + settings.ocr_provider)
    if settings.ocr_provider == "tesseract":
        # Tesseract chay cuc bo nen khong co credentials de kiem, nhung co hai
        # thu khac hay hong hon: chua cai phan mem, va cai roi nhung quen tick
        # goi tieng Nhat. Ca hai deu lo ra ngay o ham dung.
        try:
            from app.services.providers import build_ocr

            provider = build_ocr(settings)
            calls += 1
            result = provider.recognize(image, "image/png")
            print("      OK   - Tesseract " + provider._version
                  + ", " + str(result.ms) + " ms")
            print("      OK   - goi ngon ngu: "
                  + result.payload.get("requested_languages", "?"))
            text = (result.raw_text or "").strip().replace("\n", " / ")
            print("      Doc duoc tu anh thu: " + (text or "(trong)"))
            print("      LUU Y - Tesseract doc Kanji kem hon Vision. So do")
            print("              chat luong se xau hon, nhung van la so that.")
        except OcrError as exc:
            print("      LOI  - [" + exc.code + "]")
            for dong in exc.message.splitlines():
                print("             " + dong)
            ready = False
    elif settings.ocr_provider != "google":
        print("      BO QUA - OCR_PROVIDER dang la '" + settings.ocr_provider
              + "'. Dat OCR_PROVIDER=google (can billing) hoac"
              " OCR_PROVIDER=tesseract")
        print("               (mien phi, chay cuc bo) trong backend/.env.")
    else:
        creds = settings.credentials_path
        if creds and not Path(creds).is_file():
            print("      LOI  - khong tim thay file credentials: " + str(creds))
            print("             Neu ban dung `gcloud auth application-default"
                  " login`, hay DE TRONG bien")
            print("             GOOGLE_APPLICATION_CREDENTIALS trong"
                  " backend/.env.")
            ready = False
        else:
            if creds is None:
                print("      Dung Application Default Credentials"
                      " (khong dat file service account).")
            try:
                from app.services.providers import build_ocr

                provider = build_ocr(settings)
                calls += 1
                result = provider.recognize(image, "image/png")
                text = (result.raw_text or "").strip().replace("\n", " / ")
                print("      OK   - " + str(result.ms) + " ms, doc duoc: " + text)
                has_jp = any("\u3040" <= ch <= "\u9fff" for ch in result.raw_text)
                print("      " + ("OK   - chu Nhat qua duoc backend nguyen ven"
                                  if has_jp else
                                  "CANH BAO - khong thay chu Nhat trong ket qua"))
                if hasattr(provider, "close"):
                    provider.close()
            except OcrError as exc:
                print("      LOI  - [" + exc.code + "] " + exc.message)
                ready = False

    # --- 3 & 4. Gemini ---
    print("")
    print("[2/2] Gemini - trich xuat truong co schema")
    if settings.extractor != "gemini":
        print("      BO QUA - EXTRACTOR dang la '" + settings.extractor
              + "'. Dat EXTRACTOR=gemini trong backend/.env de kiem tra.")
    elif not settings.gemini_api_key:
        print("      LOI  - thieu GEMINI_API_KEY")
        ready = False
    elif not settings.gemini_model:
        print("      LOI  - thieu GEMINI_MODEL. Chay --list-models de xem"
              " tai khoan nay dung duoc model nao.")
        ready = False
    else:
        try:
            from app.services.providers import build_extractor

            extractor = build_extractor(settings)
            calls += 1
            extraction = extractor.extract(
                image, "image/png", "\u5c71\u7530 \u592a\u90ce\ntaro@example.co.jp")
            print("      OK   - model '" + settings.gemini_model
                  + "' chap nhan schema CardExtraction")
            names = [v.value for v in extraction.full_names]
            emails = [v.value for v in extraction.emails]
            print("      Ho ten doc duoc : " + (", ".join(names) or "(khong co)"))
            print("      Email doc duoc  : " + (", ".join(emails) or "(khong co)"))
        except ExtractionError as exc:
            print("      LOI  - [" + exc.code + "] " + exc.message)
            if exc.code == "EXTRACT_BAD_SCHEMA":
                print("      >> Model tra ve JSON khong dung schema. Thu model"
                      " khac, hoac bao lai de sua schema.")
            ready = False

    print("")
    print(SEP)
    if ready and settings.ocr_provider == "google" and settings.extractor == "gemini":
        print("SAN SANG. Buoc tiep theo:")
        print("  1. In 4 trang trong datasets/print/, cat, chup lai 40 the")
        print("  2. python backend/scripts/try_ocr.py datasets/dev/ja/001.jpg")
        print("  3. python backend/scripts/evaluate.py --split dev")
    else:
        print("CHUA SAN SANG. Sua cac loi o tren roi chay lai lenh nay.")
    print(SEP)
    print("So loi goi dich vu da dung: " + str(calls))
    return 0 if ready else 1


def build_ocr(settings):
    from app.services.providers import build_ocr as create_provider
    return create_provider(settings)


def build_extractor(settings, force_heuristic: bool):
    if force_heuristic or settings.extractor == "heuristic":
        return HeuristicExtractor()

    from app.services.providers import build_extractor as create_extractor
    return create_extractor(settings)


def save_fixture(path: Path, digest: str, ocr_result, extraction, grounded,
                 extract_ms: int) -> Path | None:
    """Ghi ket qua lam du lieu gia lap cho bo kiem thu.

    LOI DA SUA: truoc day ham nay ghi de vo dieu kien. Chay lai script voi
    `OCR_PROVIDER=mock` se doc fixture roi ghi no lai voi nhan provider
    "mock:...", tuc lam hong chinh ban ghi OCR that vua ton tien tao ra -
    va khong bao gi ca.

    Nay: ket qua tu mock khong bao gio duoc phep ghi de.
    """
    if str(ocr_result.provider).startswith("mock"):
        print("")
        print("  Bo qua ghi fixture: dang chay o che do mock, ghi lai se lam")
        print("  hong ban ghi OCR that. Dat OCR_PROVIDER=google de sinh moi.")
        return None

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
        # LOI DA SUA: truoc day return None o day, gay HAI hau qua:
        #   - Ket qua OCR khong duoc luu, nen `--no-extract` vo dung: chay xong
        #     roi khong con gi de dung lai.
        #   - Nguoi goi coi None la that bai va tra ma thoat 1, du OCR da chay
        #     thanh cong.
        if save:
            out = save_fixture(path, digest, ocr_result, None, None, 0)
            if out is not None:
                print("")
                print("  Da luu fixture: "
                      + str(out.relative_to(BACKEND_DIR.parent)))
        return {
            "name": path.name,
            "ms_ocr": ocr_result.ms,
            "ms_extract": 0,
            "counts": {"exact": 0, "fuzzy": 0, "unverified": 0},
            "chars": len(ocr_result.raw_text),
        }

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
        if out is not None:
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
    parser.add_argument("--check", action="store_true",
                        help="Kiem tra credentials bang 1 loi goi Vision + "
                             "1 loi goi Gemini roi thoat")
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

    if args.check:
        return preflight(settings)

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
