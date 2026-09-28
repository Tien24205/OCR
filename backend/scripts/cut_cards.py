"""Cat 8 trang A4 trong `datasets/print/` thanh 80 tam danh thiep rieng.

    python backend/scripts/cut_cards.py

Ket qua: `datasets/the-cat/<split>/<lang>/001.png` ... `010.png`

VI SAO CAN CONG CU NAY

`make_card_sheets.py` sinh ra TRANG A4 de in, cat bang tay, roi chup lai -
va do van la duong duy nhat de co SO DO THAT. Nhung khi chi muon THU CHUC
NANG (mot ngon ngu moi co chay khong, doi model xong con doc duoc khong),
cho mot vong in-cat-chup la qua dat.

Cong cu nay cat thang tu tep PNG goc, nen co ngay 80 tam de thu.

TAI SAO KHONG GHI VAO `datasets/dev/` VA `datasets/eval/`

Do la noi `evaluate.py` doc de DO CHAT LUONG, va chung duoc thiet ke cho
ANH CHUP BANG DIEN THOAI: nghieng, mo, choi den, van giay. Anh cat tu tep
goc thi SAC NET tuyet doi.

Do tren anh sac net roi goi do la "do chinh xac cua he thong" la tu lua
minh - con so se dep hon thuc te rat nhieu, va no khong tra loi duoc cau
hoi that: he thong doc duoc bao nhieu tren mot tam the CHUP BANG DIEN THOAI.

Nen chung di vao mot thu muc RIENG, va thu muc do nam trong .gitignore.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
NGUON = ROOT / "datasets" / "print"
DICH = ROOT / "datasets" / "the-cat"

# Phai KHOP voi `make_card_sheets.py` - do la nguon sinh ra cac trang nay.
DPI = 300
MM = DPI / 25.4
A4 = (int(210 * MM), int(297 * MM))      # 2480 x 3508
CARD = (int(91 * MM), int(55 * MM))      # 1075 x 650
COLS, ROWS = 2, 5

# Thut vao mot chut de khong dinh duong vien cat. Vien la net VE de nguoi ta
# cat theo, khong phai noi dung the - de lai thi OCR doc no thanh rac.
LE = 4

TRANG = [(lang, split) for lang in ("en", "ja", "ko", "zh")
         for split in ("dev", "eval")]


def cat_mot_trang(tep: Path, ra: Path) -> int:
    sheet = Image.open(tep)
    if sheet.size != A4:
        print(f"  ! {tep.name}: kich thuoc {sheet.size}, mong doi {A4} - "
              f"trang nay co the sinh boi mot ban khac cua make_card_sheets.py")

    ra.mkdir(parents=True, exist_ok=True)
    grid_w, grid_h = COLS * CARD[0], ROWS * CARD[1]
    x0, y0 = (A4[0] - grid_w) // 2, (A4[1] - grid_h) // 2

    for i in range(COLS * ROWS):
        col, row = i % COLS, i // COLS
        x, y = x0 + col * CARD[0], y0 + row * CARD[1]
        the = sheet.crop((x + LE, y + LE, x + CARD[0] - LE, y + CARD[1] - LE))
        the.save(ra / f"{i + 1:03d}.png", format="PNG", optimize=True)
    return COLS * ROWS


def main() -> int:
    if not NGUON.is_dir():
        print(f"khong thay {NGUON}\n"
              f"Chay `python backend/scripts/make_card_sheets.py` truoc.")
        return 1

    tong, thieu = 0, []
    for lang, split in TRANG:
        tep = NGUON / f"sheet-{lang}-{split}.png"
        if not tep.is_file():
            thieu.append(tep.name)
            continue
        n = cat_mot_trang(tep, DICH / split / lang)
        tong += n
        print(f"  {tep.name:24} -> {split}/{lang}/001..{n:03d}.png")

    if thieu:
        print("\n  THIEU trang:", ", ".join(thieu))

    # Tep trang tron la dau hieu cat lech luoi - bat ngay thay vi de nguoi ta
    # phat hien sau khi da quet ca 80 tam.
    nho = [p for p in DICH.rglob("*.png") if p.stat().st_size < 8_000]
    print(f"\n  da cat {tong} tam vao {DICH.relative_to(ROOT)}")
    print(f"  tam nghi ngo trong (duoi 8 KB): {len(nho)}")
    if nho:
        for p in nho[:5]:
            print("   ", p.relative_to(DICH))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
