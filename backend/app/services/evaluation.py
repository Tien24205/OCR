"""So sanh ket qua trich xuat voi nhan chuan - logic thuan, khong I/O.

Tach khoi `scripts/evaluate.py` de viet test duoc ma khong can anh, khong can
mang va khong can dich vu that.

QUY TAC SO SANH DUOC CHOT O DAY, TRUOC KHI DO

Ke hoach Ngay 9 yeu cau chot quy tac truoc khi nhin ket qua, va khong duoc
noi long sau khi thay diem thap. Vi vay chung nam trong ma nguon co test,
khong phai quyet dinh tuy hung luc viet bao cao:

    email       bo khoang trang, ha thap toan bo -> so bang nhau
    dien thoai  chi giu chu so                   -> so bang nhau
    website     bo scheme, bo "www.", bo "/" cuoi -> so bang nhau
    ten/cong ty NFKC + casefold + bo khoang trang -> so bang nhau (chat)
    chuc danh   nhu tren
    dia chi     nhu tren, nhung chap nhan khop >= 90% ky tu

Dia chi noi long hon vi no thuong xuong dong tren the, va OCR co the ghep
dau cach khac nhau. Ten va cong ty thi phai dung nguyen van - do la yeu cau
cua de bai.

BON CON SO CHO MOI TRUONG

    correct   nhan co, may doc dung
    wrong     may doc ra mot gia tri nhung khong khop nhan nao
    missed    nhan co, may khong doc ra
    spurious  NHAN KHONG CO GI, ma may van tra ve mot gia tri

`spurious` la con so quan trong nhat cua ca bao cao: the khong in email ma
he thong van tra ve email nghia la du lieu duoc bia ra. Phai bao cao rieng,
khong duoc gop vao `wrong`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field as dc_field
from difflib import SequenceMatcher

# Ten truong trong CardExtraction -> ten truong trong labels.jsonl
FIELD_MAP = {
    "full_names": "full_name",
    "company_names": "company_name",
    "job_titles": "job_titles",
    "departments": "departments",
    "emails": "emails",
    "phones": "phones",
    "websites": "websites",
    "addresses": "addresses",
}

# Truong co ban Latin di kem tren the song ngu. Duoc tinh la DUNG neu bat
# duoc, nhung KHONG tinh la bo sot neu khong bat duoc - de bai yeu cau "ho
# tro nhieu gia tri", khong yeu cau bat buoc bat du moi bien the.
ALT_MAP = {"full_names": "full_name_alt", "company_names": "company_name_alt"}

STRICT_FIELDS = frozenset({"full_names", "company_names", "job_titles", "departments"})
ADDRESS_RATIO = 0.90


def _nfkc(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def canon(field: str, value: str) -> str:
    """Dua mot gia tri ve dang dung de so sanh."""
    value = (value or "").strip()
    if field == "emails":
        return value.casefold()
    if field == "phones":
        return "".join(ch for ch in unicodedata.normalize("NFKC", value) if ch.isdigit())
    if field == "websites":
        host = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
        return _nfkc(host.removeprefix("www.").rstrip("/"))
    return _nfkc(value)


def same(field: str, expected: str, got: str) -> bool:
    a, b = canon(field, expected), canon(field, got)
    if not a or not b:
        return False
    if a == b:
        return True
    if field == "addresses":
        return SequenceMatcher(None, a, b).ratio() >= ADDRESS_RATIO
    return False


def _as_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    out = []
    for item in raw:
        if isinstance(item, dict):          # phones: {"value": ..., ...}
            if item.get("value"):
                out.append(str(item["value"]))
        elif item:
            out.append(str(item))
    return out


def expected_values(label: dict, field: str) -> tuple[list[str], list[str]]:
    """Tra ve (bat buoc, tuy chon) cho mot truong."""
    required = _as_list(label.get(FIELD_MAP[field]))
    optional = _as_list(label.get(ALT_MAP[field])) if field in ALT_MAP else []
    return required, optional


@dataclass
class FieldResult:
    expected: int = 0
    correct: int = 0
    wrong: int = 0
    missed: int = 0
    spurious: int = 0
    variants_expected: int = 0
    variants_correct: int = 0
    wrong_values: list[str] = dc_field(default_factory=list)
    missed_values: list[str] = dc_field(default_factory=list)
    spurious_values: list[str] = dc_field(default_factory=list)

    def add(self, other: FieldResult) -> None:
        self.expected += other.expected
        self.correct += other.correct
        self.wrong += other.wrong
        self.missed += other.missed
        self.spurious += other.spurious
        self.variants_expected += other.variants_expected
        self.variants_correct += other.variants_correct

    @property
    def recall(self) -> float | None:
        """Ty le doc dung tren so gia tri THUC SU CO tren the."""
        return self.correct / self.expected if self.expected else None


def compare_field(field: str, label: dict, got: list[str]) -> FieldResult:
    required, optional = expected_values(label, field)
    result = FieldResult(expected=len(required), variants_expected=len(optional))

    unmatched_required = list(required)
    unmatched_optional = list(optional)
    leftovers: list[str] = []

    for value in got:
        hit = next((e for e in unmatched_required if same(field, e, value)), None)
        if hit is not None:
            unmatched_required.remove(hit)
            result.correct += 1
            continue
        hit = next((e for e in unmatched_optional if same(field, e, value)), None)
        if hit is not None:
            unmatched_optional.remove(hit)
            result.variants_correct += 1
            continue
        leftovers.append(value)

    result.missed = len(unmatched_required)
    result.missed_values = list(unmatched_required)

    # Phan biet hai loai loi KHAC NHAU VE BAN CHAT:
    #   the CO truong do nhung may doc sai   -> wrong
    #   the KHONG CO truong do ma may van tra -> spurious (du lieu bia ra)
    if required:
        result.wrong = len(leftovers)
        result.wrong_values = leftovers
    else:
        result.spurious = len(leftovers)
        result.spurious_values = leftovers

    return result


def compare_card(label: dict, fields: dict[str, list[str]]) -> dict[str, FieldResult]:
    """So sanh mot the. `fields` la {ten_truong: [gia tri]} sau grounding."""
    skip = set(label.get("uncertain") or [])
    out: dict[str, FieldResult] = {}
    for field in FIELD_MAP:
        # Truong ma chinh nguoi gan nhan cung khong doc noi tu anh thi loai
        # khoi phep do, thay vi tinh oan la loi cua may.
        if field in skip or FIELD_MAP[field] in skip:
            continue
        out[field] = compare_field(field, label, fields.get(field, []))
    return out


def aggregate(cards: list[tuple[str, dict[str, FieldResult]]]) -> dict:
    """Gop ket qua theo (ngon ngu, truong) va theo ngon ngu."""
    by_lang_field: dict[tuple[str, str], FieldResult] = {}
    for lang, per_field in cards:
        for field, result in per_field.items():
            key = (lang, field)
            by_lang_field.setdefault(key, FieldResult()).add(result)
    return by_lang_field


def grounding_quality(label: dict, report: dict, raw_text: str = "") -> dict:
    """Do chinh chot chan grounding: no loai bo dung hay loai nham?

    `report` la `grounding["report"]` - moi gia tri kem verdict, ke ca gia tri
    da bi loai. Day la ly do bao cao phai giu lai ca phan bi loai.

    LOI DA SUA - CHI SO NAY TUNG DANH DONG HAI THU KHAC HAN NHAU:

    Mot gia tri bi loai ma lai co that tren the co the den tu HAI nguyen nhan
    doi hoi hai phan ung nguoc nhau:

      (a) OCR khong doc ra gia tri do. Grounding LAM DUNG - no tu choi thu
          khong co bang chung. Loi nam o OCR, khong nam o nguong.
      (b) OCR CO doc ra, nhung grounding van loai. Day moi la loai nham that
          su, va no do chinh nguong `_FUZZY_THRESHOLD` gay ra.

    Do that ngay 15/09 voi Tesseract: 10/10 gia tri bi loai deu thuoc loai (a).
    Bao cao cu gop chung lai va in "Ty le loai nham: 100%" - ai doc cung se
    ket luan nguong bi hong roi di noi long no, tuc lam yeu chinh co che chong
    bia dat MA KHONG CO LY DO. Mot chi so gay hieu nham o day nguy hiem hon la
    khong co chi so nao.

    `raw_text` la van ban OCR that. Khong truyen vao thi khong tach duoc hai
    nguyen nhan, va ca hai deu bi dem vao `rejected_but_correct` nhu truoc.
    """
    rejected = 0
    rejected_but_correct = 0
    ocr_khong_doc_ra = 0
    nguong_qua_chat = 0
    # Dung `_nfkc` cua chinh tang do, KHONG muon `norm_for_match` cua
    # grounding: quy tac so sanh cua tang do phai doc lap voi thu no dang
    # cham diem, neu khong thi no cham diem bang chinh thuoc do cua bi cao.
    bang_chung = _nfkc(raw_text) if raw_text else ""

    for field, items in (report or {}).items():
        if field not in FIELD_MAP:
            continue
        required, optional = expected_values(label, field)
        truth = required + optional
        for item in items:
            if item.get("verdict") != "unverified":
                continue
            rejected += 1
            gia_tri = item.get("value", "")
            if not any(same(field, e, gia_tri) for e in truth):
                continue
            rejected_but_correct += 1
            if not bang_chung:
                continue
            # Gia tri co nam trong van ban OCR khong? Co thi nguong qua chat;
            # khong thi OCR da doc sot va grounding tu choi la dung.
            chuan = _nfkc(gia_tri)
            if chuan and chuan in bang_chung:
                nguong_qua_chat += 1
            else:
                ocr_khong_doc_ra += 1

    return {
        "rejected": rejected,
        "rejected_but_correct": rejected_but_correct,
        # Hai cot duoi day tach nguyen nhan. Chi co nghia khi truyen raw_text.
        "ocr_khong_doc_ra": ocr_khong_doc_ra,
        "nguong_qua_chat": nguong_qua_chat,
    }
