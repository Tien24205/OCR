"""Kiem tra datasets/labels.jsonl truoc khi dung de do chat luong (Ngay 9).

Chay:  python backend/scripts/check_labels.py

Bat cac loi khien phep do o Ngay 9 tro nen sai:
  - JSON hong hoac thieu truong bat buoc
  - Anh duoc gan nhan nhung file khong ton tai (va nguoc lai)
  - Trung anh, sai gia tri `lang`
  - Bo eval chua du 10 anh moi ngon ngu
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "datasets"
LABELS = DATASETS / "labels.jsonl"

REQUIRED = ("image", "lang")
KNOWN_FIELDS = {
    "image", "lang", "full_name", "company_name", "job_titles", "departments",
    "emails", "phones", "websites", "addresses", "uncertain", "note",
    "full_name_alt", "company_name_alt",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
# Bon ngon ngu cua de goc. Them ngon ngu moi thi sua o day va o
# make_card_sheets.FONT_SETS - khong con cho nao khac ghi danh sach nay.
LANGS = ("en", "ja", "ko", "zh")


def main() -> int:
    if not LABELS.is_file():
        print(f"Khong tim thay {LABELS}")
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    labelled: set[str] = set()
    split_lang = Counter()

    for lineno, line in enumerate(LABELS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"dong {lineno}: JSON hong - {exc}")
            continue

        for field in REQUIRED:
            if field not in row:
                errors.append(f"dong {lineno}: thieu truong bat buoc '{field}'")
        if "image" not in row:
            continue

        image = row["image"]
        if image in labelled:
            errors.append(f"dong {lineno}: anh '{image}' bi gan nhan hai lan")
        labelled.add(image)

        if row.get("lang") not in set(LANGS):
            errors.append(f"dong {lineno}: lang phai la mot trong "
                          f"{'/'.join(LANGS)}")

        for unknown in set(row) - KNOWN_FIELDS:
            warnings.append(f"dong {lineno}: truong la '{unknown}'")

        for phone in row.get("phones", []):
            if not isinstance(phone, dict) or "value" not in phone:
                errors.append(f"dong {lineno}: phones phai la [{{'value': ...}}]")
            elif not isinstance(phone["value"], str):
                # Bat loi kinh dien: 0312345678 doc thanh so se mat so 0 dau.
                errors.append(f"dong {lineno}: so dien thoai phai la CHUOI")

        parts = image.split("/")
        if len(parts) == 3 and parts[0] in {"dev", "eval"}:
            split_lang[(parts[0], parts[1])] += 1
        else:
            errors.append(f"dong {lineno}: 'image' phai co dang "
                          f"dev|eval/{'|'.join(LANGS)}/ten.jpg")

        if not (DATASETS / image).is_file():
            warnings.append(f"dong {lineno}: chua co file anh '{image}'")

    on_disk = {
        str(p.relative_to(DATASETS)).replace("\\", "/")
        for p in DATASETS.rglob("*")
        if p.suffix.lower() in IMAGE_SUFFIXES
    }
    for missing in sorted(on_disk - labelled):
        warnings.append(f"anh '{missing}' co tren dia nhung chua duoc gan nhan")

    print(f"Da doc {len(labelled)} nhan.")
    for split in ("dev", "eval"):
        for lang in LANGS:
            n = split_lang[(split, lang)]
            mark = "OK " if n >= 10 else "-- "
            print(f"  {mark}{split}/{lang}: {n}/10")

    for w in warnings:
        print(f"  [canh bao] {w}")
    for e in errors:
        print(f"  [LOI] {e}")

    if errors:
        print(f"\n{len(errors)} loi phai sua truoc khi do chat luong.")
        return 1
    print("\nKhong co loi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
