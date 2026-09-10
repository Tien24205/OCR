"""Sinh anh danh thiep TONG HOP de kiem thu duong di ky thuat.

CANH BAO PHAM VI: anh sinh ra o day la chu in ky thuat so, sac net tuyet doi.
No CHI dung de kiem tra duong ong (upload -> OCR -> trich xuat -> grounding)
chay thong. No KHONG dung de do chat luong OCR: anh qua dep se cho ket qua
lac quan, khong phan anh danh thiep chup bang dien thoai ngoai doi that.

Bo mau danh gia o Ngay 9 bat buoc phai la anh CHUP LAI tu the in ra giay.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parents[2] / "tmp" / "test-cards"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ocr"

# Font co san tren Windows co chua Kanji/Kana.
JP_FONT_CANDIDATES = [
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]

CARDS = {
    "ja-001.png": [
        ("株式会社サンプル製作所", 34),
        ("営業本部 第一営業部", 20),
        ("部長  山田 太郎", 28),
        ("", 10),
        ("〒100-0001 東京都千代田区千代田1-1-1", 18),
        ("TEL: 03-1234-5678 (内線 102)   FAX: 03-1234-5679", 18),
        ("携帯: 090-8765-4321", 18),
        ("taro.yamada@example.co.jp", 18),
        ("https://www.example.co.jp", 18),
    ],
    "en-001.png": [
        ("Example Solutions Inc.", 34),
        ("Sales Division", 20),
        ("Jane Doe", 28),
        ("Senior Account Manager", 20),
        ("", 10),
        ("500 Market Street, Suite 200", 18),
        ("San Francisco, CA 94105", 18),
        ("Tel: +1 (415) 555-0142  ext. 88", 18),
        ("jane.doe@example.com", 18),
        ("https://example.com", 18),
    ],
}


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in JP_FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size)


def render(name: str, lines: list[tuple[str, int]]) -> Path:
    # Ty le 91x55mm cua danh thiep chuan, o do phan giai vua phai.
    image = Image.new("RGB", (1050, 630), "white")
    draw = ImageDraw.Draw(image)

    y = 60
    for text, size in lines:
        if text:
            draw.text((60, y), text, font=pick_font(size), fill=(20, 20, 20))
        y += size + 16

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    image.save(out)
    return out


def write_fixture(path: Path, lines: list[tuple[str, int]]) -> Path:
    """Sinh fixture tu van ban DA BIET, khong qua OCR.

    Provider ghi la "synthetic" chu khong phai "google_vision" de khong ai
    nham lan day la ket qua OCR that. Fixture nay chi phuc vu kiem tra duong
    ong; fixture that duoc `try_ocr.py` sinh o Ngay 2 tu lan goi Vision that.
    """
    raw_text = "\n".join(text for text, _ in lines if text)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURE_DIR / (digest + ".json")
    out.write_text(
        json.dumps(
            {
                "source_file": path.name,
                "raw_text": raw_text,
                "provider": "synthetic",
                "provider_version": "make_test_card",
                "detected_languages": [],
                "blocks": [],
                "payload": {"note": "van ban da biet, khong qua OCR"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out


def main() -> int:
    for name, lines in CARDS.items():
        path = render(name, lines)
        fixture = write_fixture(path, lines)
        print("Da tao: " + str(path))
        print("        fixture " + fixture.name[:12] + "...json")
    print("")
    print("Anh tong hop - chi de kiem tra duong ong, KHONG dung de do chat luong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
