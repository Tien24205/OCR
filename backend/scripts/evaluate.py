"""Do chat luong trich xuat tren bo mau co nhan chuan - Ngay 9.

MUC DICH: bien "216 test pass" thanh so lieu that. Test xanh chi chung minh
ma nguon tu nhat quan; no khong noi gi ve viec he thong doc dung bao nhieu
phan tram cac truong tren danh thiep that.

QUAN TRONG: do tren KET QUA TU DONG, TRUOC KHI NGUOI DUNG SUA. Day la ly do
`scans.extraction_json` duoc thiet ke bat bien ngay tu Ngay 1.

CACH DUNG

    # Do tren bo eval (mac dinh) - chi chay MOT LAN de lay so bao cao
    python backend/scripts/evaluate.py

    # Do tren bo dev trong luc phat trien
    python backend/scripts/evaluate.py --split dev

    # Thu nhanh vai the
    python backend/scripts/evaluate.py --split dev --limit 3

KET QUA
    reports/evaluation.md      bang bao cao cho nguoi doc
    reports/evaluation.json    so lieu tho de doi chieu ve sau

KY LUAT DO LUONG

Bo `eval/` chi duoc chay MOT LAN de lay so bao cao. Moi lan ban nhin ket qua
tren mot anh eval roi sua ma nguon cho no chay dung, anh do mat gia tri danh
gia. Trong qua trinh phat trien, dung `--split dev`.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import get_settings  # noqa: E402
from app.services.evaluation import (  # noqa: E402
    FIELD_MAP,
    FieldResult,
    compare_card,
    grounding_quality,
)
from app.services.extract.base import ExtractionError  # noqa: E402
from app.services.extract.grounding import ground_extraction  # noqa: E402
from app.services.ocr.base import OcrError  # noqa: E402

DATASETS = ROOT / "datasets"
LABELS = DATASETS / "labels.jsonl"
REPORTS = ROOT / "reports"
MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

FIELD_VI = {
    "full_names": "Họ tên",
    "company_names": "Công ty",
    "job_titles": "Chức danh",
    "departments": "Phòng ban",
    "emails": "Email",
    "phones": "Điện thoại",
    "websites": "Website",
    "addresses": "Địa chỉ",
}

LANG_VI = {
    "en": "tiếng Anh",
    "ja": "tiếng Nhật",
    "ko": "tiếng Hàn",
    "zh": "tiếng Trung",
}


def load_labels(split: str, limit: int | None,
                image_root: Path) -> tuple[list[dict], list[str]]:
    if not LABELS.is_file():
        raise SystemExit(f"Khong tim thay {LABELS}")

    rows, missing = [], []
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if split != "all" and not row["image"].startswith(split + "/"):
            continue
        if (image_root / row["image"]).is_file():
            rows.append(row)
        else:
            missing.append(row["image"])
    if limit:
        rows = rows[:limit]
    return rows, missing


# Bao nhieu lan thu lai va cho bao lau giua cac lan.
#
# VI SAO PHAI THU LAI: Gemini tra 503 "high demand" mot cach ngau nhien. Neu
# bo luon the do, con so chat luong se bi tron lan giua hai thu khac han nhau:
# OCR doc sai (dieu can do) va Google het cho (dieu khong lien quan). Mot lan
# chay 40 the gap vai cai 503 rai rac se cho ket qua thap gia tao, va lan chay
# sau lai ra so khac - khong con so sanh duoc giua cac lan.
#
# CHI thu lai loi CO CO the thu lai. Loi vinh vien (anh hong, sai quyen) ma
# thu lai thi chi keo dai lan chay ma khong doi duoc ket qua.
_RETRIES = 3
_BACKOFF_S = (2, 6)

# Nhung loi khien phan con lai cua lan chay chac chan cung hong. Gap la dung
# han, khong chay tiep.
_DUNG_HAN = {"EXTRACT_QUOTA_EXCEEDED"}


def run_with_retry(row: dict, ocr, extractor, image_root: Path,
                   log=print) -> tuple[dict, int]:
    """Chay mot the, thu lai khi gap loi tam thoi. Tra ve (ket qua, so lan thu lai)."""
    last: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            return run_one(row, ocr, extractor, image_root), attempt
        except (OcrError, ExtractionError) as exc:
            last = exc
            if not exc.retryable or attempt == _RETRIES - 1:
                raise
            wait = _BACKOFF_S[min(attempt, len(_BACKOFF_S) - 1)]
            log(f"      tam thoi [{exc.code}], chờ {wait}s rồi thử lại "
                f"({attempt + 2}/{_RETRIES})")
            time.sleep(wait)
    raise last  # khong bao gio toi day, nhung de kieu tra ve ro rang


def run_one(row: dict, ocr, extractor, image_root: Path) -> dict:
    """Chay tron duong ong tren mot anh va so voi nhan."""
    path = image_root / row["image"]
    data = path.read_bytes()
    mime = MIMES.get(path.suffix.lower(), "image/jpeg")

    started = time.perf_counter()
    ocr_result = ocr.recognize(data, mime)
    ms_ocr = ocr_result.ms or int((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    extraction = extractor.extract(data, mime, ocr_result.raw_text)
    ms_extract = int((time.perf_counter() - started) * 1000)

    grounded = ground_extraction(extraction, ocr_result.raw_text)
    fields = {
        name: [item["value"] for item in items]
        for name, items in grounded["fields"].items()
    }

    return {
        "image": row["image"],
        "lang": row["lang"],
        "per_field": compare_card(row, fields),
        "grounding": grounding_quality(row, grounded["report"],
                                       ocr_result.raw_text),
        "ms_ocr": ms_ocr,
        "ms_extract": ms_extract,
        "raw_chars": len(ocr_result.raw_text),
    }


def totals(cards: list[dict]) -> dict[tuple[str, str], FieldResult]:
    out: dict[tuple[str, str], FieldResult] = defaultdict(FieldResult)
    for card in cards:
        for field, result in card["per_field"].items():
            out[(card["lang"], field)].add(result)
    return out


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_table(agg, lang: str) -> list[str]:
    lines = [
        "| Trường | Có trên thẻ | Đúng | Sai | Bỏ sót | **Tự sinh** | Tỷ lệ đúng |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    total = FieldResult()
    for field in FIELD_MAP:
        r = agg.get((lang, field))
        if r is None:
            continue
        total.add(r)
        lines.append(
            f"| {FIELD_VI[field]} | {r.expected} | {r.correct} | {r.wrong} | "
            f"{r.missed} | {r.spurious} | {pct(r.recall)} |"
        )
    lines.append(
        f"| **Tổng** | **{total.expected}** | **{total.correct}** | "
        f"**{total.wrong}** | **{total.missed}** | **{total.spurious}** | "
        f"**{pct(total.recall)}** |"
    )
    return lines


def write_csv(cards: list[dict], path: Path) -> None:
    """Bang so lieu dang CSV de mo bang Excel hoac dua vao bang tinh.

    Ghi kem BOM UTF-8 - khong co no thi Excel tren Windows doc sai chu Nhat,
    dung ly do da gap o buoc xuat du lieu Ngay 7.
    """
    agg = totals(cards)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ngon_ngu", "truong", "co_tren_the", "dung", "sai",
                         "bo_sot", "tu_sinh", "ty_le_dung"])
        for (lang, field), r in sorted(agg.items()):
            writer.writerow([
                lang, field, r.expected, r.correct, r.wrong, r.missed,
                r.spurious,
                "" if r.recall is None else f"{r.recall:.4f}",
            ])


def examples(cards: list[dict], count: int = 2) -> tuple[list[dict], list[dict]]:
    """Chon vai the chay tot nhat va vai the sai nhieu nhat.

    DoD cua Ngay 9 yeu cau CA HAI. Chi dua vi du that bai thi bao cao tro nen
    bi quan sai lech; chi dua vi du thanh cong thi thanh khoe diem.
    """
    def errors(card: dict) -> int:
        return sum(r.wrong + r.missed + r.spurious
                   for r in card["per_field"].values())

    def expected(card: dict) -> int:
        return sum(r.expected for r in card["per_field"].values())

    ranked = sorted(cards, key=lambda c: (errors(c), -expected(c)))
    good = [c for c in ranked if errors(c) == 0][:count]
    bad = [c for c in reversed(ranked) if errors(c) > 0][:count]
    return good, bad


def build_report(cards: list[dict], missing: list[str], settings, split: str,
                 image_root: Path) -> str:
    agg = totals(cards)
    langs = sorted({c["lang"] for c in cards})
    now = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    dry_run = image_root.name == "_dryrun"
    out = [
        "# Báo cáo chất lượng trích xuất",
        "",
        f"Ngày đo: {now} · Bộ mẫu: `{split}` · Số thẻ đã đo: **{len(cards)}**",
        "",
        "## Điều kiện đo",
        "",
        "| Mục | Giá trị |",
        "| --- | --- |",
        f"| Nhà cung cấp OCR | `{settings.ocr_provider}` |",
        f"| Bộ trích xuất | `{settings.extractor}` |",
        f"| Model | `{settings.gemini_model or '—'}` |",
        f"| Gợi ý ngôn ngữ | `{', '.join(settings.language_hint_list)}` |",
        "",
    ]

    if dry_run:
        out += [
            "> **CHẠY KHÔ — số liệu này vô nghĩa để nghiệm thu.**",
            "> Ảnh lấy từ `datasets/_dryrun/`: ảnh số sắc nét tuyệt đối, không "
            "phải ảnh chụp. Chỉ dùng để kiểm chứng công cụ đo chạy đúng.",
            "",
        ]

    if settings.ocr_provider == "mock" or settings.extractor == "heuristic":
        out += [
            "> **Cảnh báo: đây KHÔNG phải số đo của hệ thống thật.**",
            f"> Đang chạy với OCR `{settings.ocr_provider}` và bộ trích xuất "
            f"`{settings.extractor}`.",
            "> Muốn có số liệu nghiệm thu, đặt `OCR_PROVIDER=google` và "
            "`EXTRACTOR=gemini` trong `backend/.env` rồi chạy lại.",
            "",
        ]

    if missing:
        out += [
            f"> **Thiếu {len(missing)} ảnh** đã có nhãn nhưng chưa chụp. "
            "Các thẻ đó không được tính vào bảng dưới.",
            "",
        ]

    out += [
        "## Quy tắc so sánh",
        "",
        "Chốt trong `app/services/evaluation.py` và có test, **trước khi đo** — "
        "không nới lỏng sau khi thấy kết quả.",
        "",
        "| Trường | Quy tắc |",
        "| --- | --- |",
        "| Email | bỏ khoảng trắng, hạ thấp toàn bộ |",
        "| Điện thoại | chỉ giữ chữ số |",
        "| Website | bỏ scheme, bỏ `www.`, bỏ `/` cuối |",
        "| Tên, công ty, chức danh, phòng ban | NFKC + casefold + bỏ khoảng trắng, **khớp chính xác** |",
        "| Địa chỉ | như trên, chấp nhận khớp ≥ 90% ký tự |",
        "",
        "**Cột “Tự sinh”** đếm giá trị mà hệ thống trả về trong khi thẻ *không hề có* "
        "trường đó. Đây là dữ liệu bịa ra, tách riêng khỏi cột “Sai” (có trường "
        "nhưng đọc nhầm).",
        "",
    ]

    for lang in langs:
        n = sum(1 for c in cards if c["lang"] == lang)
        out += [f"## Kết quả — {LANG_VI.get(lang, lang)} ({n} thẻ)", ""]
        out += render_table(agg, lang)
        out.append("")

    # --- Chat luong cua chinh chot chan grounding ---
    rejected = sum(c["grounding"]["rejected"] for c in cards)
    wrongly = sum(c["grounding"]["rejected_but_correct"] for c in cards)
    do_ocr = sum(c["grounding"].get("ocr_khong_doc_ra", 0) for c in cards)
    do_nguong = sum(c["grounding"].get("nguong_qua_chat", 0) for c in cards)
    out += [
        "## Chốt chặn chống bịa dữ liệu",
        "",
        f"- Giá trị bị grounding loại: **{rejected}**",
        f"- Trong đó giá trị có thật trên thẻ: **{wrongly}**",
        "",
        "Con số thứ hai **không phải** thước đo của grounding, vì nó gộp hai "
        "nguyên nhân đòi hỏi hai phản ứng ngược nhau:",
        "",
        "| Nguyên nhân | Số lượng | Nghĩa là |",
        "| --- | ---: | --- |",
        f"| OCR không đọc ra giá trị | {do_ocr} | **Grounding làm đúng** — nó từ "
        "chối thứ không có bằng chứng. Muốn cải thiện thì cải thiện OCR |",
        f"| OCR đọc ra nhưng vẫn bị loại | {do_nguong} | **Đây mới là loại nhầm "
        "thật** — do ngưỡng `_FUZZY_THRESHOLD` quá chặt |",
        "",
    ]
    if rejected:
        out.append(
            f"Tỷ lệ loại nhầm thật: **{do_nguong / rejected * 100:.1f}%** "
            f"({do_nguong}/{rejected}). Chỉ con số này mới đo ngưỡng; "
            "cao thì ngưỡng đang vứt đi dữ liệu mà OCR đã đọc được."
        )
        if do_ocr and not do_nguong:
            out.append("")
            out.append(
                "**Mọi lần loại đều do OCR đọc sót, không lần nào do ngưỡng.** "
                "Nới lỏng ngưỡng ở đây sẽ không cứu được giá trị nào — vì giá "
                "trị đó không hề có trong văn bản OCR để mà đối chiếu — nhưng "
                "sẽ làm yếu cơ chế chống bịa đặt."
            )
    else:
        out.append("Không có giá trị nào bị loại trong lần đo này.")
    out.append("")

    # --- Thoi gian ---
    if cards:
        ocr_ms = [c["ms_ocr"] for c in cards]
        ext_ms = [c["ms_extract"] for c in cards]
        out += [
            "## Thời gian xử lý",
            "",
            "| Bước | Trung vị | Nhỏ nhất | Lớn nhất |",
            "| --- | ---: | ---: | ---: |",
            f"| OCR | {statistics.median(ocr_ms):.0f} ms | {min(ocr_ms)} ms | {max(ocr_ms)} ms |",
            f"| Trích xuất | {statistics.median(ext_ms):.0f} ms | {min(ext_ms)} ms | {max(ext_ms)} ms |",
            "",
        ]

    # --- The co van de nhat ---
    def errors(card: dict) -> int:
        return sum(r.wrong + r.missed + r.spurious for r in card["per_field"].values())

    good, bad = examples(cards)
    if good:
        out += ["## Ví dụ đọc đúng hoàn toàn", ""]
        for card in good:
            fields = card["per_field"]
            total = sum(r.expected for r in fields.values())
            out.append(f"**`{card['image']}`** — đọc đúng {total}/{total} giá trị "
                       f"({card['ms_ocr']} ms OCR + {card['ms_extract']} ms trích xuất)")
        out.append("")

    worst = sorted((c for c in cards if errors(c)), key=errors, reverse=True)[:5]
    if worst:
        out += ["## Thẻ sai nhiều nhất", ""]
        for card in worst:
            out.append(f"**`{card['image']}`** — {errors(card)} lỗi")
            for field, r in card["per_field"].items():
                for value in r.missed_values:
                    out.append(f"- {FIELD_VI[field]}: bỏ sót `{value}`")
                for value in r.wrong_values:
                    out.append(f"- {FIELD_VI[field]}: đọc sai thành `{value}`")
                for value in r.spurious_values:
                    out.append(f"- {FIELD_VI[field]}: **tự sinh** `{value}`")
            out.append("")

    out += [
        "## Giới hạn của phép đo này",
        "",
        "- Bộ `eval/` chỉ giữ giá trị đánh giá nếu **chưa từng được dùng để sửa "
        "mã nguồn**. Mỗi lần nhìn kết quả trên một ảnh eval rồi chỉnh code cho "
        "nó chạy đúng, ảnh đó mất giá trị. Trong quá trình phát triển dùng "
        "`--split dev`.",
        f"- Bộ mẫu {len(cards)} thẻ chỉ cho biết chất lượng trong phạm vi đã thử. "
        "Không suy rộng ra mọi loại danh thiếp.",
        "- Thẻ sinh từ `make_card_sheets.py` không có logo, nền màu đậm, in nhũ "
        "hay chữ dọc. Thẻ thật có những thứ đó.",
        "- Đo trên kết quả **tự động, trước khi người dùng sửa**. Chất lượng sau "
        "khi người dùng duyệt sẽ cao hơn và là con số khác.",
    ]
    if dry_run:
        out.append("- **Chạy khô**: ảnh số sắc nét, không phải ảnh chụp. "
                   "Không dùng làm số liệu nghiệm thu.")
    out.append("")
    return "\n".join(out)


def compare(rows: list[dict], settings, image_root: Path, out_dir: Path) -> int:
    """Chay hai bo trich xuat tren CUNG mot bo anh va so sanh.

    VI SAO DUNG CHUNG MOT LAN GOI OCR: neu goi OCR hai lan thi khac biet co the
    den tu OCR chu khong phai tu bo trich xuat, va con ton gap doi tien.
    """
    from app.services.providers import build_extractor, build_ocr

    ocr = build_ocr(settings)
    variants = {}
    for name in ("heuristic", "gemini"):
        try:
            variants[name] = build_extractor(
                settings.model_copy(update={"extractor": name}))
        except (OcrError, ExtractionError) as exc:
            print(f"Bo qua '{name}': [{exc.code}] {exc.message}")

    if len(variants) < 2:
        print("\nCan ca hai bo trich xuat moi so sanh duoc. "
              "Dat GEMINI_API_KEY va GEMINI_MODEL trong backend/.env.")
        return 1

    results: dict[str, list[dict]] = {}
    for name, extractor in variants.items():
        print(f"\n--- {name} ---")
        cards = []
        for index, row in enumerate(rows, 1):
            try:
                card = run_one(row, ocr, extractor, image_root)
            except (OcrError, ExtractionError) as exc:
                print(f"  [{index}/{len(rows)}] {row['image']}  LOI {exc.code}")
                continue
            cards.append(card)
            err = sum(r.wrong + r.missed + r.spurious
                      for r in card["per_field"].values())
            print(f"  [{index}/{len(rows)}] {row['image']}  {err} loi")
        results[name] = cards

    lines = ["# So sánh bộ trích xuất", "",
             "Cùng một lần gọi OCR cho cả hai, nên khác biệt đến từ bộ trích "
             "xuất chứ không phải từ OCR.", "",
             "| Trường | Ngôn ngữ | Có trên thẻ | "
             + " | ".join(f"{n}: đúng" for n in results) + " |",
             "| --- | --- | ---: | " + " | ".join("---:" for _ in results) + " |"]

    aggregates = {name: totals(cards) for name, cards in results.items()}
    keys = sorted({key for agg in aggregates.values() for key in agg})
    for lang, field in keys:
        first = next(iter(aggregates.values())).get((lang, field))
        if first is None:
            continue
        cells = []
        for agg in aggregates.values():
            r = agg.get((lang, field))
            cells.append(f"{r.correct} ({pct(r.recall)})" if r else "—")
        lines.append(f"| {FIELD_VI[field]} | {lang} | {first.expected} | "
                     + " | ".join(cells) + " |")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "comparison.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("")
    print("\n".join(lines))
    print(f"\nDa ghi {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Đo chất lượng trích xuất (Ngày 9)")
    parser.add_argument("--split", default="eval", choices=["eval", "dev", "all"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=REPORTS)
    parser.add_argument("--compare", action="store_true",
                        help="Chay ca hai bo trich xuat tren cung bo anh va "
                             "in bang so sanh")
    parser.add_argument("--dataset", type=Path, default=DATASETS,
                        help="Thư mục chứa ảnh (mặc định datasets/). "
                             "Dùng datasets/_dryrun để chạy thử.")
    args = parser.parse_args()

    settings = get_settings()
    image_root = args.dataset if args.dataset.is_absolute() else ROOT / args.dataset
    rows, missing = load_labels(args.split, args.limit, image_root)

    print(f"Bộ mẫu   : {args.split}")
    print(f"OCR      : {settings.ocr_provider}")
    print(f"Trích xuất: {settings.extractor}")
    print(f"Thư mục ảnh: {image_root.relative_to(ROOT)}")
    print(f"Ảnh có   : {len(rows)}   ·   thiếu ảnh: {len(missing)}")

    if not rows:
        print("\nChưa có ảnh nào để đo.")
        print("Chạy `python backend/scripts/make_card_sheets.py`, in ra, cắt, "
              "chụp lại rồi lưu vào datasets/<split>/<lang>/NNN.jpg")
        return 1

    from app.services.providers import build_extractor, build_ocr

    if args.compare:
        return compare(rows, settings, image_root, args.out)

    try:
        ocr, extractor = build_ocr(settings), build_extractor(settings)
    except (OcrError, ExtractionError) as exc:
        print(f"\nKhông khởi tạo được: [{exc.code}] {exc.message}")
        return 1

    cards, failures = [], []
    retried = 0
    for i, row in enumerate(rows, 1):
        try:
            card, attempts = run_with_retry(row, ocr, extractor, image_root)
        except (OcrError, ExtractionError) as exc:
            failures.append((row["image"], exc.code, exc.message))
            print(f"  [{i}/{len(rows)}] {row['image']}  LỖI {exc.code}")
            if exc.code in _DUNG_HAN:
                # Het han muc thi cac the con lai chac chan cung that bai. Chay
                # tiep chi de in them 30 dong loi giong het nhau, va neu han
                # muc co hoi phuc giua chung thi con te hon: bo mau do duoc
                # nua nay nua kia, khong con dai dien cho cai gi ca.
                print(f"\n  DUNG SOM sau {i}/{len(rows)} thẻ: {exc.message}")
                break
            continue
        retried += 1 if attempts else 0
        cards.append(card)
        err = sum(r.wrong + r.missed + r.spurious for r in card["per_field"].values())
        print(f"  [{i}/{len(rows)}] {row['image']}  {err} lỗi")

    if not cards:
        print("\nKhông thẻ nào chạy được.")
        return 1

    if retried:
        print(f"\n  {retried}/{len(cards)} thẻ phải thử lại vì lỗi tạm thời.")

    args.out.mkdir(parents=True, exist_ok=True)
    report = build_report(cards, missing, settings, args.split, image_root)
    (args.out / "evaluation.md").write_text(report, encoding="utf-8")
    write_csv(cards, args.out / "evaluation.csv")

    raw = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "ocr_provider": settings.ocr_provider,
        "extractor": settings.extractor,
        "gemini_model": settings.gemini_model,
        "cards_measured": len(cards),
        # So the phai thu lai moi xong. Ghi lai vi day la DIEU KIEN DO, khong
        # phai ket qua do: con so cao nghia la dich vu hom do chap chon, va
        # nguoi doc bao cao can biet dieu do khi so hai lan chay voi nhau.
        "cards_needing_retry": retried,
        "images_missing": missing,
        "failures": [{"image": i, "code": c, "message": m} for i, c, m in failures],
        "per_card": [
            {
                "image": c["image"], "lang": c["lang"],
                "ms_ocr": c["ms_ocr"], "ms_extract": c["ms_extract"],
                "grounding": c["grounding"],
                "fields": {
                    f: {"expected": r.expected, "correct": r.correct, "wrong": r.wrong,
                        "missed": r.missed, "spurious": r.spurious,
                        "missed_values": r.missed_values,
                        "wrong_values": r.wrong_values,
                        "spurious_values": r.spurious_values}
                    for f, r in c["per_field"].items()
                },
            }
            for c in cards
        ],
    }
    (args.out / "evaluation.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    agg = totals(cards)
    print(f"\n{'NGÔN NGỮ':<10}{'CÓ THẬT':>9}{'ĐÚNG':>7}{'SAI':>6}{'SÓT':>6}{'TỰ SINH':>9}{'TỶ LỆ':>8}")
    for lang in sorted({c["lang"] for c in cards}):
        t = FieldResult()
        for field in FIELD_MAP:
            if (lang, field) in agg:
                t.add(agg[(lang, field)])
        print(f"{lang:<10}{t.expected:>9}{t.correct:>7}{t.wrong:>6}{t.missed:>6}"
              f"{t.spurious:>9}{pct(t.recall):>8}")

    print(f"\nĐã ghi {args.out / 'evaluation.md'}")
    print(f"       {args.out / 'evaluation.csv'}")
    print(f"       {args.out / 'evaluation.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
