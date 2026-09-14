"""Nhan dien he chu viet - nguon su that duy nhat cho ca du an.

VI SAO TACH RA: cac dai Unicode truoc day bi nhan ban o `confidence.py` va
`heuristic.py`. Khi them tieng Han va tieng Trung, chi sua mot cho se lam hai
cho lech nhau ma khong bao loi - loai sai lech am tham kho tim nhat.

PHAM VI CUA DE BAI: de goc (`De2.docx.pdf`, muc 2) neu bon ngon ngu - Anh,
Han, Nhat, Trung. MVP ban dau chi lam Anh + Nhat; module nay mo rong ra du bon.

MOT GIOI HAN PHAI NOI RO: phan biet tieng Nhat voi tieng Trung bang chu viet
la KHONG chac chan. Kanji va Hanzi dung chung dai Unicode. Chi khi co Kana
(rieng tieng Nhat) hoac Hangul (rieng tieng Han) thi moi ket luan duoc. Van
ban toan chu Han khong kem dau hieu nao khac se tra ve `han` - khong doan bua.
"""

from __future__ import annotations

# Dai ky tu. Nguon: bang phan khoi Unicode.
RANGES: dict[str, tuple[tuple[str, str], ...]] = {
    # Hiragana + Katakana: CHI co trong tieng Nhat.
    "kana": (("぀", "ゟ"), ("゠", "ヿ"), ("ㇰ", "ㇿ")),
    # Hangul: CHI co trong tieng Han.
    "hangul": (("가", "힯"), ("ᄀ", "ᇿ"), ("㄰", "㆏")),
    # Chu Han: DUNG CHUNG giua tieng Nhat (Kanji) va tieng Trung (Hanzi),
    # va xuat hien ca trong tieng Han cu (Hanja). Khong tu no ket luan duoc.
    "han": (("一", "鿿"), ("㐀", "䶿"), ("豈", "﫿")),
}

CJK_SCRIPTS = frozenset({"kana", "hangul", "han"})

# Ma ngon ngu cho Google Vision `languageHints` va cho nhan trong nhan chuan.
SUPPORTED = ("en", "ja", "ko", "zh")


def scripts_in(text: str) -> set[str]:
    """Cac he chu co mat trong van ban."""
    found: set[str] = set()
    for char in text or "":
        if char.isascii() and char.isalpha():
            found.add("latin")
            continue
        for name, ranges in RANGES.items():
            if any(low <= char <= high for low, high in ranges):
                found.add(name)
                break
    return found


def has_cjk(text: str) -> bool:
    """Van ban co chua chu CJK (Kana, Hangul hoac chu Han) khong."""
    return bool(scripts_in(text) & CJK_SCRIPTS)


# Dau hieu rieng cua tung ngon ngu, dung khi van ban chi co chu Han.
# "山田 太郎" khong co Kana nen khong the ket luan tu he chu; nhung "株式会社"
# thi chi dung o Nhat, con "有限公司" chi dung o Trung Quoc.
JA_MARKERS = ("株式会社", "有限会社", "合同会社", "社団法人", "財団法人", "〒")
ZH_MARKERS = ("有限公司", "股份有限公司", "集团", "集團", "责任公司", "責任公司")


def guess_language(text: str) -> str:
    """Doan ngon ngu cua the tu he chu viet.

    Tra ve `en`, `ja`, `ko`, `zh`, `han`, `mixed` hoac `other`.

    QUY TAC, theo do chac chan giam dan:
      1. Co Kana   -> `ja`  (Kana khong dung o dau khac)
      2. Co Hangul -> `ko`  (Hangul khong dung o dau khac)
      3. Chi co chu Han, nhung co dau hieu rieng -> `ja` hoac `zh`
      4. Chi co chu Han, khong dau hieu nao -> `han`
      5. Co CJK lan chu Latin -> `mixed`

    VI SAO BUOC 4 KHONG DOAN BUA: ten nguoi Nhat viet toan Kanji ("山田 太郎")
    khong the phan biet duoc voi ten tieng Trung chi bang he chu. Ban dau ham
    nay tra ve "zh" cho moi truong hop chi co chu Han - tuc gan nhan sai cho
    phan lon the tieng Nhat. Tra ve `han` la trung thuc: "chu Han, chua xac
    dinh duoc ngon ngu".

    Ket qua nay la TIN HIEU HO TRO, khong duoc dung de quyet dinh thay nguoi
    dung hay de bo qua mot truong.
    """
    found = scripts_in(text)
    cjk = found & CJK_SCRIPTS
    latin = "latin" in found

    if not cjk:
        return "en" if latin else "other"
    if latin:
        return "mixed"
    if "kana" in found:
        return "ja"
    if "hangul" in found:
        return "ko"

    if any(marker in text for marker in JA_MARKERS):
        return "ja"
    if any(marker in text for marker in ZH_MARKERS):
        return "zh"
    return "han"


def matches_hint(text: str, language_codes: list[str]) -> bool:
    """Chu viet trong van ban co phu hop voi ngon ngu OCR phat hien duoc khong.

    Dung lam mot tin hieu cua `ConfidenceAgent`: gia tri chua chu CJK trong khi
    OCR bao the la tieng Anh la dau hieu it nhat mot trong hai bi doc sai.
    """
    if not language_codes or not has_cjk(text):
        return True
    return any(code.split("-")[0].lower() in {"ja", "ko", "zh", "yue"}
               for code in language_codes)
