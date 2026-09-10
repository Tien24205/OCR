"""Chot chan chong bia du lieu.

VAN DE: Gemini la mo hinh sinh. Duoc dua anh mot danh thiep khong co email,
no van co the tra ve mot email "hop ly" ghep tu ten nguoi va ten mien cong ty.
De bai yeu cau ro "khong tu dien du lieu khong doc duoc".

VI SAO KHONG DUNG PROMPT DE GIAI QUYET: cau lenh "khong duoc bia" lam giam
ty le bia chu khong triet tieu no, va khong the do luong duoc. Chot chan phai
la mot phep kiem tra co the chay va co the viet test.

CACH LAM: `raw_text` tu Google Vision la BANG CHUNG - no den truc tiep tu
diem anh, khong qua mo hinh sinh. Moi gia tri Gemini tra ve deu phai doi
chieu duoc voi bang chung do. Khong doi chieu duoc thi bi loai khoi ban nhap.

Ket qua co ba muc:
  exact       - tim thay nguyen van  -> nhan
  fuzzy       - lech it, do OCR nham ky tu -> nhan nhung gan co "can kiem tra"
  unverified  - khong tim thay       -> LOAI, ghi lai de bao cao Ngay 9
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

Verdict = Literal["exact", "fuzzy", "unverified"]

# Dung de cat van ban OCR thanh TOKEN tron ven. Xem `_tokens_of` ben duoi.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/[^\s]*)?", re.IGNORECASE
)
_PHONE_RE = re.compile(r"\+?\d[\d\-\s()./]{7,}\d")

# Nhung cap ky tu ma OCR hay doc nham lan nhau. Quy ve cung mot dai dien de
# "0" va "O" khong bi tinh la hai ky tu khac nhau khi doi chieu.
_CONFUSABLES = str.maketrans({
    "0": "o", "1": "l", "5": "s", "8": "b", "2": "z",
    "|": "l", "!": "l", "i": "l",
    "-": "", "\u2010": "", "\u2011": "", "\u2012": "", "\u2013": "",
    "\u2014": "", "\uff0d": "", "_": "", ".": "", ",": "", "(": "", ")": "",
})

# Nguong khop cho truong tu do (ten, cong ty, dia chi): cho phep sai khoang
# 1 ky tu tren moi 10. Chat hon thi OCR nham mot net Kanji la truot; long
# hon thi hai cong ty khac ten bi coi la mot.
_FUZZY_THRESHOLD = 0.90

_STRICT_KINDS = frozenset({"email", "phone", "url"})


@dataclass(frozen=True)
class Grounding:
    value: str
    kind: str
    verdict: Verdict
    score: float

    @property
    def accepted(self) -> bool:
        return self.verdict != "unverified"

    @property
    def needs_review(self) -> bool:
        return self.verdict == "fuzzy"


def norm_for_match(text: str | None) -> str:
    """Chuan hoa de SO KHOP (khong bao gio de hien thi).

    NFKC quy ky tu full-width ve half-width. Danh thiep Nhat thuong in
    "ＴＥＬ：０３-１２３４"; khong co buoc nay thi no khong khop voi
    "TEL:03-1234" ma Gemini tra ve.
    """
    if not text:
        return ""
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def _collapse(text: str) -> str:
    return text.translate(_CONFUSABLES)


def _best_window_ratio(needle: str, haystack: str) -> float:
    """Ty le khop cao nhat khi truot `needle` doc theo `haystack`.

    Dung thay cho thu vien fuzzy matching ben ngoai: van ban mot danh thiep
    chi vai tram ky tu nen chi phi khong dang ke, va bot mot phu thuoc.
    Thu ca cua so ngan/dai hon mot ky tu de chiu duoc truong hop OCR them
    hoac nuot mot ky tu.
    """
    n = len(needle)
    if n == 0 or not haystack:
        return 0.0

    best = 0.0
    for width in (n, n + 1, n - 1):
        if width <= 0 or width > len(haystack):
            continue
        for i in range(len(haystack) - width + 1):
            ratio = SequenceMatcher(None, needle, haystack[i : i + width]).ratio()
            if ratio > best:
                best = ratio
                if best == 1.0:
                    return best
    return best


def _digits(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", text) if ch.isdigit())


def _canon_url(text: str) -> str:
    host_and_path = re.sub(r"^https?://", "", text.strip(), flags=re.IGNORECASE)
    return norm_for_match(host_and_path.removeprefix("www.").rstrip("/"))


def _tokens_of(kind: str, raw_text: str) -> set[str]:
    """Cat van ban OCR thanh cac token TRON VEN thuoc loai `kind`.

    VI SAO KHONG DUNG PHEP KIEM TRA CHUOI CON:

    The co that email "taro.yamada@example.co.jp". Neu model bia ra
    "yamada@example.co.jp", phep kiem tra chuoi con se cho qua - vi chuoi bia
    ay dung la mot phan duoi cua chuoi that. Ket qua: mot email khong ton tai
    duoc ghi vao ho so doi tac va khong ai phat hien.

    Voi email, URL va so dien thoai, don vi so sanh phai la CA TOKEN chu
    khong phai mot doan bat ky trong van ban.
    """
    normalized = unicodedata.normalize("NFKC", raw_text)

    if kind == "email":
        return {norm_for_match(m) for m in _EMAIL_RE.findall(normalized)}

    if kind == "url":
        # Go email ra truoc: neu khong, "jane.doe@example.com" se sinh ra
        # token URL gia "example.com" va mot website bia dat se duoc chap nhan.
        without_emails = _EMAIL_RE.sub(" ", normalized)
        return {_canon_url(m) for m in _URL_RE.findall(without_emails)}

    if kind == "phone":
        # So sanh bang chuoi chu so: the in "03-1234-5678", model co the tra
        # ve "03 1234 5678" - cung mot so, khac cach viet.
        return {
            d for m in _PHONE_RE.findall(normalized) if len(d := _digits(m)) >= 9
        }

    return set()


def _ground_strict(value: str, raw_text: str, kind: str) -> Grounding:
    """Doi chieu email / URL / so dien thoai bang phep so trong token."""
    tokens = _tokens_of(kind, raw_text)

    if kind == "phone":
        needle = _digits(value)
        if not needle:
            return Grounding(value, kind, "unverified", 0.0)
        if needle in tokens:
            return Grounding(value, kind, "exact", 1.0)
        return Grounding(value, kind, "unverified", 0.0)

    needle = _canon_url(value) if kind == "url" else norm_for_match(value)
    if not needle:
        return Grounding(value, kind, "unverified", 0.0)

    if needle in tokens:
        return Grounding(value, kind, "exact", 1.0)

    # Chi tha cho viec OCR doc nham ky tu giong nhau (0/O, 1/l). KHONG dung
    # khop mo o day: mot ky tu sai trong email la mot email khac han.
    collapsed = _collapse(needle)
    if any(collapsed == _collapse(token) for token in tokens):
        return Grounding(value, kind, "fuzzy", 0.95)

    return Grounding(value, kind, "unverified", 0.0)


def ground(value: str, raw_text: str, kind: str) -> Grounding:
    """Doi chieu mot gia tri voi van ban OCR goc."""
    if kind in _STRICT_KINDS:
        return _ground_strict(value, raw_text, kind)

    needle = norm_for_match(value)
    haystack = norm_for_match(raw_text)

    # Gia tri qua ngan khop duoc voi hau het moi van ban, nen phep doi chieu
    # mat y nghia. Mot ky tu don khong bao gio la mot truong hop le.
    if len(needle) < 2:
        return Grounding(value, kind, "unverified", 0.0)

    if needle in haystack:
        return Grounding(value, kind, "exact", 1.0)

    # Ten/cong ty/dia chi: chap nhan sai lech nho do OCR doc nham net chu.
    score = _best_window_ratio(needle, haystack)
    if score >= _FUZZY_THRESHOLD:
        return Grounding(value, kind, "fuzzy", score)
    return Grounding(value, kind, "unverified", score)


# Anh xa tu ten truong trong CardExtraction sang "kind" dung khi doi chieu.
_FIELD_KINDS = {
    "full_names": "name",
    "company_names": "company",
    "job_titles": "title",
    "departments": "department",
    "emails": "email",
    "phones": "phone",
    "websites": "url",
    "addresses": "address",
}


def ground_extraction(extraction, raw_text: str) -> dict:
    """Doi chieu toan bo ket qua trich xuat.

    Tra ve ban da loc + bao cao. Bao cao duoc luu vao `scans.grounding_json`;
    Ngay 9 no chinh la so lieu cot "Tu sinh" trong bang danh gia.
    """
    kept: dict[str, list] = {}
    report: dict[str, list[dict]] = {}
    counts = {"exact": 0, "fuzzy": 0, "unverified": 0}

    for field, kind in _FIELD_KINDS.items():
        items = getattr(extraction, field, []) or []
        kept[field] = []
        report[field] = []

        for item in items:
            # Doi chieu bang chinh gia tri, khong bang `source_text`: model co
            # the bia ca hai, nhung gia tri moi la thu duoc luu vao ho so.
            verdict = ground(item.value, raw_text, kind)
            counts[verdict.verdict] += 1
            report[field].append({
                "value": item.value,
                "verdict": verdict.verdict,
                "score": round(verdict.score, 3),
            })
            if verdict.accepted:
                kept[field].append({
                    "value": item.value,
                    "source_text": item.source_text,
                    "needs_review": verdict.needs_review,
                    **(
                        {"label": item.label, "extension": item.extension}
                        if kind == "phone"
                        else {}
                    ),
                })

    return {
        "fields": kept,
        "report": report,
        "counts": counts,
        "card_language": getattr(extraction, "card_language", ""),
    }
