"""Test cho chot chan chong bia du lieu.

Day la bo test quan trong nhat cua du an. Neu grounding hong, mo hinh sinh
co the dua du lieu khong co tren the vao ho so doi tac ma khong ai biet.

Moi test o day deu la mot cach ma he thong CO THE bi bia du lieu.
"""

from __future__ import annotations

from app.services.extract.base import CardExtraction, ExtractedValue, PhoneValue
from app.services.extract.grounding import ground, ground_extraction, norm_for_match

CARD_JA = """株式会社サンプル製作所
営業本部 第一営業部
部長  山田 太郎
〒100-0001 東京都千代田区千代田1-1-1
TEL: 03-1234-5678 (内線 102)
taro.yamada@example.co.jp
https://www.example.co.jp"""

CARD_EN = """Example Solutions Inc.
Jane Doe
Senior Account Manager
Tel: +1 (415) 555-0142
jane.doe@example.com"""


# --- Truong hop bia du lieu: BAT BUOC phai bi loai ------------------------

def test_email_bia_ra_bi_loai():
    """Kieu bia pho bien nhat: ghep ten nguoi voi ten mien cong ty.

    Email nay 'hop ly' den muc nguoi doc luot qua se tin. Chi co phep doi
    chieu voi van ban goc moi phat hien duoc.
    """
    assert ground("info@example.co.jp", CARD_JA, "email").verdict == "unverified"
    assert ground("yamada@example.co.jp", CARD_JA, "email").verdict == "unverified"


def test_ten_nguoi_khac_bi_loai():
    assert ground("鈴木 一郎", CARD_JA, "name").verdict == "unverified"
    assert ground("John Smith", CARD_EN, "name").verdict == "unverified"


def test_so_dien_thoai_bia_bi_loai():
    assert ground("03-9999-0000", CARD_JA, "phone").verdict == "unverified"


def test_website_doan_tu_ten_mien_email_bi_loai():
    """The tieng Anh khong in website. Model co the doan tu ten mien email."""
    assert ground("https://example.com", CARD_EN, "url").verdict == "unverified"


def test_mot_ky_tu_sai_trong_email_van_bi_loai():
    """Voi email, mot ky tu sai la mot email KHAC HAN - phai loai, khong
    duoc cho qua dang 'khop gan dung'."""
    assert ground("tarq.yamada@example.co.jp", CARD_JA, "email").verdict == "unverified"


# --- Truong hop that: phai duoc nhan --------------------------------------

def test_gia_tri_co_that_duoc_nhan_nguyen_van():
    for value, kind in [
        ("taro.yamada@example.co.jp", "email"),
        ("山田 太郎", "name"),
        ("株式会社サンプル製作所", "company"),
        ("03-1234-5678", "phone"),
        ("https://www.example.co.jp", "url"),
    ]:
        assert ground(value, CARD_JA, kind).verdict == "exact", value


def test_full_width_khop_voi_half_width():
    """Danh thiep Nhat thuong in so bang ky tu full-width. Khong co NFKC thi
    day la hai chuoi khac nhau va gia tri that se bi loai oan."""
    assert ground("ＴＥＬ：０３-１２３４-５６７８", CARD_JA, "phone").verdict == "exact"
    assert norm_for_match("ＡＢＣ１２３") == norm_for_match("abc123")


def test_ocr_nham_ky_tu_giong_nhau_van_duoc_nhan_kem_co():
    """OCR hay doc '0' thanh 'O' va '1' thanh 'l'. Truong hop nay khong phai
    bia du lieu, nen duoc nhan nhung phai gan co de nguoi dung kiem tra."""
    verdict = ground("taro.yamada@exampIe.co.jp", CARD_JA, "email")
    assert verdict.verdict == "fuzzy"
    assert verdict.needs_review is True
    assert verdict.accepted is True


def test_ten_lech_mot_ky_tu_duoc_nhan_kem_co():
    verdict = ground("株式会社サンプル製作洗", CARD_JA, "company")
    assert verdict.verdict == "fuzzy"
    assert verdict.needs_review is True


def test_chuoi_rong_khong_bao_gio_duoc_nhan():
    assert ground("", CARD_JA, "name").verdict == "unverified"
    assert ground("   ", CARD_JA, "name").verdict == "unverified"


# --- Loc toan bo ket qua trich xuat ---------------------------------------

def test_ground_extraction_loai_truong_bia_va_giu_truong_that():
    extraction = CardExtraction(
        full_names=[
            ExtractedValue(value="山田 太郎", source_text="部長  山田 太郎"),
            ExtractedValue(value="鈴木 一郎", source_text="bia ra"),
        ],
        emails=[
            ExtractedValue(value="taro.yamada@example.co.jp", source_text="..."),
            ExtractedValue(value="info@example.co.jp", source_text="bia ra"),
        ],
        phones=[
            PhoneValue(value="03-1234-5678", label="tel", extension="102"),
            PhoneValue(value="080-0000-0000", label="mobile"),
        ],
        card_language="ja",
    )

    result = ground_extraction(extraction, CARD_JA)

    assert [v["value"] for v in result["fields"]["full_names"]] == ["山田 太郎"]
    assert [v["value"] for v in result["fields"]["emails"]] == [
        "taro.yamada@example.co.jp"
    ]
    assert [v["value"] for v in result["fields"]["phones"]] == ["03-1234-5678"]

    # Con so nay chinh la cot "Tu sinh" cua bao cao Ngay 9.
    assert result["counts"]["unverified"] == 3
    assert result["counts"]["exact"] == 3


def test_bao_cao_giu_lai_ca_truong_bi_loai():
    """Truong bi loai KHONG duoc bien mat khoi bao cao - do la so lieu de do
    ty le model tu sinh du lieu."""
    extraction = CardExtraction(
        emails=[ExtractedValue(value="fake@nowhere.com", source_text="x")]
    )
    result = ground_extraction(extraction, CARD_JA)

    assert result["fields"]["emails"] == []
    assert len(result["report"]["emails"]) == 1
    assert result["report"]["emails"][0]["verdict"] == "unverified"


def test_so_dien_thoai_giu_nhan_va_so_may_le_khi_duoc_nhan():
    extraction = CardExtraction(
        phones=[PhoneValue(value="03-1234-5678", label="tel", extension="102")]
    )
    kept = ground_extraction(extraction, CARD_JA)["fields"]["phones"][0]

    assert kept["label"] == "tel"
    assert kept["extension"] == "102"


# --- Loi da tung mac phai: chuoi con lot luoi -----------------------------
# Ban dau grounding kiem tra bang phep "chuoi con nam trong van ban". Cach do
# cho qua moi gia tri bia dat ma tinh co la mot phan cua gia tri that. Bo test
# duoi day khoa lai hanh vi so trong token.

def test_email_la_duoi_cua_email_that_van_bi_loai():
    """"yamada@..." nam gon trong "taro.yamada@..." nhung la email KHAC."""
    assert ground("yamada@example.co.jp", CARD_JA, "email").verdict == "unverified"
    assert ground("doe@example.com", CARD_EN, "email").verdict == "unverified"


def test_subdomain_khac_bi_loai():
    """"www" la but danh quy uoc nen duoc bo qua (xem test ke tiep), nhung
    mot subdomain that su khac thi tro toi noi khac va phai bi loai."""
    for fake in ("https://mail.example.co.jp", "https://shop.example.co.jp",
                 "https://example.jp"):
        assert ground(fake, CARD_JA, "url").verdict == "unverified", fake


def test_url_cung_trang_khac_cach_viet_van_duoc_nhan():
    """Bo scheme va www khong lam doi trang web, nen van phai khop."""
    for variant in ("www.example.co.jp", "example.co.jp",
                    "http://www.example.co.jp/"):
        assert ground(variant, CARD_JA, "url").verdict == "exact", variant


def test_so_dien_thoai_khac_cach_viet_van_duoc_nhan():
    for variant in ("03 1234 5678", "0312345678", "03.1234.5678"):
        assert ground(variant, CARD_JA, "phone").verdict == "exact", variant


def test_gia_tri_qua_ngan_khong_duoc_nhan():
    """Mot ky tu khop duoc voi gan nhu moi van ban, nen phep doi chieu mat
    y nghia. Khong duoc coi la da kiem chung."""
    assert ground("山", CARD_JA, "name").verdict == "unverified"
