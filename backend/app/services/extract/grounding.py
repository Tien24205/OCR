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
    r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:[/?#][^\s]*)?", re.IGNORECASE
)
_PHONE_RE = re.compile(r"\+?\d[\d\- \t().]{7,}\d")

# Nhung cap ky tu ma OCR hay doc nham lan nhau. Quy ve cung mot dai dien de
# "0" va "O" khong bi tinh la hai ky tu khac nhau khi doi chieu.
_CONFUSABLES = str.maketrans({
    "0": "o", "1": "l", "5": "s", "8": "b", "2": "z",
    "|": "l", "!": "l", "i": "l",
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
    text = unicodedata.normalize("NFKC", text).strip()
    host_and_path = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    parts = re.split(r"(?=[/?#])", host_and_path, maxsplit=1)
    host = parts[0].casefold().removeprefix("www.")
    suffix = parts[1] if len(parts) > 1 else ""
    return host + ("" if suffix == "/" else suffix)


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
    tokens: set[str] = set()
    for doan in _cac_doan_ung_vien(raw_text, kind):
        if kind == "email":
            tokens |= {norm_for_match(m) for m in _EMAIL_RE.findall(doan)}
        elif kind == "url":
            # Go email ra truoc: neu khong, "jane.doe@example.com" se sinh ra
            # token URL gia "example.com" va mot website bia dat se duoc chap
            # nhan.
            without_emails = _EMAIL_RE.sub(" ", doan)
            tokens |= {_canon_url(m) for m in _URL_RE.findall(without_emails)}
        elif kind == "phone":
            # So sanh bang chuoi chu so: the in "03-1234-5678", model co the
            # tra ve "03 1234 5678" - cung mot so, khac cach viet.
            tokens |= {d for m in _PHONE_RE.findall(doan)
                       if len(d := _digits(m)) >= 9}
    return tokens


def _cac_doan_ung_vien(raw_text: str, kind: str):
    """Sinh ra van ban OCR, cong them tung CAP DONG LIEN TIEP duoc noi lien.

    VI SAO CAN NOI DONG: OCR hay cat mot token lam doi giua chung. Do that tren
    anh the ngay 15/09, Tesseract tra ve:

        https://www.example.co.
        Jp

    Ca chuoi `https://www.example.co.jp` DEU nam tren tam the - OCR chi chen
    them mot dau ngat dong vao giua. Dau ngat do la HIEN VAT cua OCR, khong
    phai noi dung. Khong noi lai thi grounding loai mot website co that, va do
    that cho thay 100% so lan loai deu la loai oan kieu nay.

    VI SAO LAM VAY LA AN TOAN - khong he noi long chong bia dat:

      - Chi THEM token, khong bao gio bot. Moi token deu sinh ra tu chinh chu
        ma OCR doc duoc, khong phai tu suy dien.
      - Chi noi HAI dong lien tiep, khong noi ca van ban. Noi tat ca se tao ra
        nhung chuoi dai vo nghia va co the ghep nham hai token cach xa nhau.
      - De mot gia tri bia dat duoc chap nhan nho buoc nay, no phai TRUNG KHIT
        voi phan noi cua hai dong that lien nhau - tuc la chinh truong hop gia
        tri do co that tren the nhung bi cat dong.

    VI SAO NHAT QUAN VOI PHAN CON LAI: `norm_for_match` da xoa sach moi khoang
    trang khi doi chieu ten, cong ty va dia chi. Nhanh token truoc day khong
    lam vay, nen no kho tinh hon phan con lai cua he thong ma khong co ly do.

    KHONG AP DUNG CHO SO DIEN THOAI: so dien thoai duoc so sanh bang chuoi chu
    so, nen noi hai dong lai se bien hai so that nam canh nhau

        03-1234-5678
        090-1234-5678

    thanh mot so 21 chu so KHONG he ton tai - va no se duoc chap nhan nhu bang
    chung. Da co test khoa dieu nay tu Ngay 4
    (`test_phone_tokens_do_not_join_lines_or_slash_separated_numbers`), va test
    do dung: chinh no bat duoc ban sua dau tien cua ham nay.

    Email va URL khong gap rui ro do vi chung khong so bang chuoi chu so: mot
    gia tri bia dat phai TRUNG KHIT ca chuoi thi moi qua duoc, ma noi hai dong
    chi tao ra chuoi ghep - khong tao ra phan duoi hay phan dau cua chuoi that.
    """
    normalized = unicodedata.normalize("NFKC", raw_text)
    yield normalized

    if kind == "phone":
        return

    lines = [ln.strip() for ln in normalized.splitlines()]
    for truoc, sau in zip(lines, lines[1:]):
        if truoc and sau:
            yield truoc + sau


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
    if kind == "email" and any(collapsed == _collapse(token) for token in tokens):
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


def _phone_metadata(item, raw_text: str) -> dict:
    """Keep a label/extension only when attached to this exact phone token."""
    labels = {"tel": r"\b(?:tel(?:ephone)?|phone)\b|電話",
              "fax": r"\bfax\b|ファックス",
              "mobile": r"\b(?:mobile|cell)\b|携帯"}
    label, extension = "", ""
    for line in unicodedata.normalize("NFKC", raw_text).splitlines():
        matches = list(_PHONE_RE.finditer(line))
        for index, match in enumerate(matches):
            if _digits(match.group()) != _digits(item.value):
                continue
            before = line[matches[index - 1].end() if index else 0:match.start()]
            after = line[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(line)]
            # The nearest explicit label before the number wins.
            candidates = [(m.start(), kind) for kind, pattern in labels.items()
                          for m in re.finditer(pattern, before, re.IGNORECASE)]
            if candidates and max(candidates)[1] == item.label.lower():
                label = item.label.lower()
            ext = re.match(r"\s*\(?\s*(?:ext\.?|内線|内)\s*[:：]?\s*(\d+)\b", after, re.IGNORECASE)
            if ext and ext.group(1) == unicodedata.normalize("NFKC", item.extension).strip():
                extension = item.extension
    return {"label": label, "extension": extension}


def _bang_chung_hop_le(source_text: str, raw_text: str) -> str:
    """Tra ve `source_text` neu no that su co trong van ban OCR, khong thi "".

    Model duoc yeu cau dan kem doan van ban goc lam BANG CHUNG cho moi gia tri.
    Model co the bia ca doan nay, nen phai kiem - va doan bia thi bi xoa, dong
    thoi truong bi gan co "can xem lai".

    LOI DA SUA: phep kiem truoc day la `source_text in raw_text` - so chuoi con
    THO, khong chuan hoa gi ca. Trong khi chinh GIA TRI thi di qua NFKC va xoa
    khoang trang.

    Hai muc do kho tinh khac nhau nay gay hau qua that: Tesseract chen khoang
    trang giua cac chu CJK, nen OCR tra ve

        株 式 会 社 青葉 テク ノロ ジー

    con model dan bang chung la `株式会社青葉テクノロジー`. Gia tri thi khop
    `exact`, nhung bang chung truot phep so chuoi con - the la truong da duoc
    XAC MINH XONG van bi gan co "can xem lai", va o bang chung bi xoa trang.

    Do that tren mot the tieng Nhat: 3/6 truong bi gan co oan kieu nay. Mot co
    canh bao bat o gan nhu moi cho se lam nguoi duyet thoi nhin no - luc do no
    con te hon la khong co co, vi nhung truong dang ngo that su se chim lan
    giua dam canh bao vo nghia. Va o bang chung bi xoa lai lay mat dung thu
    giup ho doi chieu.

    Chuan hoa o day KHONG lam yeu phep kiem: mot doan bang chung bia dat van
    khong xuat hien trong van ban OCR da chuan hoa.
    """
    if not source_text:
        return ""
    if source_text in raw_text:
        return source_text
    chuan = norm_for_match(source_text)
    if chuan and chuan in norm_for_match(raw_text):
        return source_text
    return ""


def ground_extraction(extraction, raw_text: str) -> dict:
    """Doi chieu toan bo ket qua trich xuat.

    Tra ve ban da loc + bao cao. Bao cao duoc luu vao `scans.grounding_json`;
    Unverified means absent from OCR, not proof of fabrication: OCR can miss text.
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
                source = _bang_chung_hop_le(item.source_text, raw_text)
                metadata = _phone_metadata(item, raw_text) if kind == "phone" else {}
                metadata_changed = kind == "phone" and (
                    metadata["label"] != item.label or metadata["extension"] != item.extension
                )
                kept[field].append({
                    "value": item.value,
                    "source_text": source,
                    "needs_review": verdict.needs_review or metadata_changed or bool(item.source_text and not source),
                    **metadata,
                })

    return {
        "fields": kept,
        "report": report,
        "counts": counts,
        "card_language": getattr(extraction, "card_language", ""),
    }
