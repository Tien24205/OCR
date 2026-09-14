"""Nha cung cap OCR: Tesseract chay ngay tren may, khong can mang.

VI SAO CO LOP NAY: Google Vision bat buoc bat billing, ma o Viet Nam mot so
phuong thuc thanh toan bi yeu cau ung truoc 800.000 d. Doi voi du an nay - 40
anh, nam gon trong han muc mien phi - cai gia do khong dang. Tesseract cho
OCR that, mien phi, khong gioi han so lan.

DIEU QUAN TRONG NHAT: co che chong bia dat (grounding) VAN DUNG NGUYEN VEN.
Grounding doi hoi hai nguon DOC LAP: mot nguon doc pixel, mot nguon suy dien.
Tesseract doc pixel, Gemini suy dien - chung van la hai nguon khac nhau. Thu
duy nhat khong duoc phep lam la de Gemini sinh ra ca `raw_text` lan cac truong,
vi khi do se thanh lay loi khai cua mot nguoi ra kiem chung chinh loi khai do.

DANH DOI THANH THAT: Tesseract doc Kanji kem hon Vision ro ret. So do chat
luong se xau hon. Nhung do la so THAT, va bao cao chi can ghi ro do tren OCR
nao - trung thuc hon la khong co so nao.
"""

from __future__ import annotations

import io
import time

from app.services.ocr.base import OcrBlock, OcrError, OcrResult

# Ma ngon ngu cua du an -> ma cua Tesseract. Tesseract dung ma ISO 639-2/T ba
# ky tu, khong phai ma hai ky tu nhu Google.
_LANG_MAP = {
    "ja": "jpn",
    "en": "eng",
    "ko": "kor",
    "zh": "chi_sim",
    "zh-Hans": "chi_sim",
    "zh-Hant": "chi_tra",
}

# --psm 3 = tu dong phan doan trang.
#
# VI SAO KHONG DUNG --psm 6: che do 6 gia dinh ca anh la MOT khoi van ban dong
# nhat. Danh thiep khong phai vay - ten, chuc danh, dia chi, dien thoai nam
# roi rac thanh nhieu khoi co khoang trong giua. Dung psm 6 se ghep nhung khoi
# khong lien quan thanh mot dong.
#
# VI SAO KHONG DUNG --psm 11: che do do tim chu nhieu nhat co the nhung khong
# giu thu tu doc. Mat thu tu la mat thong tin bo cuc ma Ngay 5 can de to sang
# vung tuong ung tren anh.
_CONFIG = "--psm 3"


def _tess_langs(hints: list[str]) -> str:
    """Ghep chuoi ngon ngu cho Tesseract, vi du "jpn+eng".

    Bo qua ma khong anh xa duoc thay vi nem loi: mot goi ngon ngu la nhu
    khong nen lam hong ca lan quet.
    """
    out: list[str] = []
    for hint in hints:
        code = _LANG_MAP.get(hint) or _LANG_MAP.get(hint.split("-")[0])
        if code and code not in out:
            out.append(code)
    return "+".join(out) or "eng"


def _group_blocks(data: dict) -> tuple[list[OcrBlock], str]:
    """Gom tung TU ma Tesseract tra ve thanh khoi cap doan van.

    Tesseract tra ve mot bang phang, moi dong mot tu, kem bon chi so long
    nhau: block_num > par_num > line_num > word_num. Gom theo
    (block_num, par_num) cho ra do min tuong duong `paragraph` cua Vision,
    de hai nha cung cap tra ve cung mot hinh dang du lieu.
    """
    n = len(data.get("text", []))
    groups: dict[tuple[int, int], dict] = {}
    order: list[tuple[int, int]] = []

    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        # Tesseract dung -1 cho o khong phai chu. Loai bo, neu khong diem tin
        # cay trung binh se bi keo xuong boi nhung o trong.
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue

        key = (int(data["block_num"][i]), int(data["par_num"][i]))
        if key not in groups:
            groups[key] = {"lines": {}, "confs": [],
                           "x0": [], "y0": [], "x1": [], "y1": []}
            order.append(key)
        g = groups[key]
        g["lines"].setdefault(int(data["line_num"][i]), []).append(text)
        g["confs"].append(conf)
        x, y = int(data["left"][i]), int(data["top"][i])
        g["x0"].append(x)
        g["y0"].append(y)
        g["x1"].append(x + int(data["width"][i]))
        g["y1"].append(y + int(data["height"][i]))

    blocks: list[OcrBlock] = []
    chunks: list[str] = []
    for key in order:
        g = groups[key]
        text = "\n".join(" ".join(words)
                         for _, words in sorted(g["lines"].items()))
        if not text.strip():
            continue
        blocks.append(OcrBlock(
            text=text,
            bbox=(min(g["x0"]), min(g["y0"]), max(g["x1"]), max(g["y1"])),
            # Tesseract cho diem 0-100; phan con lai cua he thong dung 0-1.
            confidence=round(sum(g["confs"]) / len(g["confs"]) / 100.0, 4),
            languages=(),
        ))
        chunks.append(text)

    return blocks, "\n".join(chunks)


class TesseractProvider:
    name = "tesseract"

    def __init__(self, language_hints: list[str], timeout_s: int = 20,
                 binary_path: str | None = None) -> None:
        try:
            import pytesseract
        except ImportError as exc:
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Thieu goi pytesseract. Chay: pip install pytesseract",
            ) from exc

        self._pt = pytesseract
        if binary_path:
            pytesseract.pytesseract.tesseract_cmd = binary_path
        self._langs = _tess_langs(language_hints)
        self._timeout = timeout_s

        # Kiem tra NGAY luc khoi tao chu khong doi den luc quet anh dau tien.
        # Cau hinh sai ma chi lo ra giua chung se lam hong mot ban quet that,
        # trong khi loi thuc su chi la chua cai phan mem.
        try:
            self._version = str(pytesseract.get_tesseract_version())
        except Exception as exc:
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Khong chay duoc Tesseract. Cai dat:\n"
                "  Windows: tai ban UB Mannheim tai\n"
                "    https://github.com/UB-Mannheim/tesseract/wiki\n"
                "    nho TICK cac goi ngon ngu Japanese/Korean/Chinese.\n"
                "  macOS:   brew install tesseract tesseract-lang\n"
                "  Linux:   apt install tesseract-ocr tesseract-ocr-jpn\n"
                "Neu da cai ma van bao loi, tro thang toi file chay bang\n"
                "TESSERACT_CMD trong backend/.env.",
            ) from exc

        missing = self.missing_languages()
        if missing:
            raise OcrError(
                "OCR_NOT_CONFIGURED",
                "Tesseract thieu goi ngon ngu: " + ", ".join(missing) + ".\n"
                "Chay lai trinh cai dat va tick dung cac goi do, hoac chep "
                "file .traineddata tuong ung vao thu muc tessdata.",
            )

    def missing_languages(self) -> list[str]:
        """Cac goi ngon ngu duoc yeu cau nhung chua cai."""
        try:
            have = set(self._pt.get_languages(config=""))
        except Exception:
            return []
        return [lang for lang in self._langs.split("+") if lang not in have]

    def recognize(self, image: bytes, mime: str) -> OcrResult:
        from PIL import Image, UnidentifiedImageError

        try:
            picture = Image.open(io.BytesIO(image))
            picture.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise OcrError("OCR_REJECTED",
                           "Khong doc duoc anh nay.") from exc

        started = time.perf_counter()
        try:
            data = self._pt.image_to_data(
                picture,
                lang=self._langs,
                config=_CONFIG,
                output_type=self._pt.Output.DICT,
                timeout=self._timeout,
            )
        except RuntimeError as exc:
            # pytesseract nem RuntimeError khi qua thoi gian cho.
            raise OcrError("OCR_UNAVAILABLE",
                           "Tesseract chay qua lau. Thu lai voi anh nho hon.",
                           retryable=True) from exc
        except self._pt.TesseractError as exc:
            raise OcrError("OCR_CALL_FAILED",
                           "Tesseract tu choi xu ly anh nay.") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        blocks, raw_text = _group_blocks(data)

        return OcrResult(
            raw_text=raw_text,
            provider=self.name,
            provider_version=self._version,
            blocks=blocks,
            # DE TRONG CO Y: Tesseract khong PHAT HIEN ngon ngu, no duoc BAO
            # truoc phai doc ngon ngu nao. Dien danh sach yeu cau vao day se
            # khien phan con lai cua he thong tuong day la ket qua phat hien.
            # Viec doan ngon ngu do `app.services.languages.guess_language`
            # lam, dua tren chu that doc duoc.
            detected_languages=[],
            payload={
                "block_count": len(blocks),
                "requested_languages": self._langs,
                "psm": _CONFIG,
            },
            ms=elapsed_ms,
        )
