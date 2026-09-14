"""Test cho quy tac so sanh dung o Ngay 9.

Ke hoach yeu cau chot quy tac so sanh TRUOC khi nhin ket qua, va khong duoc
noi long sau khi thay diem thap. Bo test nay la cach thuc thi dieu do: muon
noi long quy tac thi phai sua test, va viec sua se nam trong lich su Git.
"""

from __future__ import annotations

from app.services.evaluation import (
    canon,
    compare_card,
    compare_field,
    grounding_quality,
    same,
)

LABEL_JA = {
    "image": "eval/ja/001.jpg",
    "lang": "ja",
    "full_name": "山田 太郎",
    "company_name": "株式会社青葉テクノロジー",
    "job_titles": ["部長"],
    "departments": ["営業本部 第一営業部"],
    "emails": ["taro.yamada@example.co.jp"],
    "phones": [{"value": "03-5432-1098", "label": "tel"},
               {"value": "090-1234-5678", "label": "mobile"}],
    "websites": ["https://www.example.co.jp"],
    "addresses": ["〒100-0001 東京都千代田区千代田1-2-3 青葉ビル7F"],
    "uncertain": [],
}


# --- Quy tac chuan hoa truoc khi so sanh ----------------------------------

def test_email_bo_qua_hoa_thuong():
    assert same("emails", "Taro.Yamada@Example.co.jp", "taro.yamada@example.co.jp")


def test_dien_thoai_bo_qua_dau_phan_cach():
    for variant in ("03-5432-1098", "03 5432 1098", "0354321098", "03.5432.1098"):
        assert same("phones", "03-5432-1098", variant), variant


def test_dien_thoai_full_width_van_khop():
    assert same("phones", "03-5432-1098", "０３－５４３２－１０９８")


def test_website_bo_scheme_va_www():
    for variant in ("https://www.example.co.jp", "http://example.co.jp",
                    "www.example.co.jp", "example.co.jp/"):
        assert same("websites", "https://www.example.co.jp", variant), variant


def test_ten_phai_dung_nguyen_van():
    assert same("full_names", "山田 太郎", "山田太郎")        # khac khoang trang: OK
    assert not same("full_names", "山田 太郎", "山田 太朗")   # khac mot ky tu: SAI


def test_cong_ty_sai_mot_ky_tu_la_sai():
    """Khong duoc dung khop mo cho ten cong ty - hai cong ty khac nhau."""
    assert not same("company_names", "株式会社青葉テクノロジー",
                    "株式会社青葉テクノロシー")


def test_dia_chi_cho_phep_lech_nho():
    """Dia chi thuong xuong dong tren the, OCR ghep dau cach khac nhau."""
    assert same("addresses",
                "〒100-0001 東京都千代田区千代田1-2-3 青葉ビル7F",
                "〒100-0001\n東京都千代田区千代田1-2-3\n青葉ビル7F")
    assert not same("addresses",
                    "〒100-0001 東京都千代田区千代田1-2-3 青葉ビル7F",
                    "〒530-0001 大阪府大阪市北区梅田2-4-9")


def test_chuoi_rong_khong_bao_gio_khop():
    assert not same("emails", "", "")
    assert not same("full_names", "山田 太郎", "")


def test_canon_website_bo_duoi_gach_cheo():
    assert canon("websites", "https://www.example.co.jp/") == "example.co.jp"


# --- Bon con so cho moi truong --------------------------------------------

def test_doc_dung_het_thi_khong_co_loi():
    r = compare_field("phones", LABEL_JA, ["03-5432-1098", "090-1234-5678"])
    assert (r.expected, r.correct, r.wrong, r.missed, r.spurious) == (2, 2, 0, 0, 0)
    assert r.recall == 1.0


def test_bo_sot_duoc_dem_rieng():
    r = compare_field("phones", LABEL_JA, ["03-5432-1098"])
    assert (r.correct, r.missed) == (1, 1)
    assert r.missed_values == ["090-1234-5678"]


def test_doc_sai_khac_voi_bo_sot():
    r = compare_field("emails", LABEL_JA, ["info@example.co.jp"])
    assert (r.correct, r.wrong, r.missed, r.spurious) == (0, 1, 1, 0)


def test_the_khong_co_truong_ma_may_van_tra_ve_la_TU_SINH():
    """Con so quan trong nhat cua bao cao: du lieu bia ra.

    Phai tach khoi 'doc sai' - doc sai la co truong nhung doc nham; tu sinh
    la the khong he co truong do.
    """
    label = dict(LABEL_JA, emails=[])
    r = compare_field("emails", label, ["yamada@example.co.jp"])
    assert (r.expected, r.wrong, r.spurious) == (0, 0, 1)
    assert r.spurious_values == ["yamada@example.co.jp"]
    assert r.recall is None        # khong co gi de doc thi khong tinh ty le


def test_bien_the_latin_la_TUY_CHON():
    """The song ngu: bat duoc ban romaji thi duoc cong diem, khong bat duoc
    cung khong bi tinh la bo sot. De bai yeu cau 'ho tro nhieu gia tri',
    khong yeu cau bat buoc bat du moi bien the."""
    label = dict(LABEL_JA, full_name="中村 由美", full_name_alt="Yumi Nakamura")

    only_primary = compare_field("full_names", label, ["中村 由美"])
    assert (only_primary.correct, only_primary.missed) == (1, 0)
    assert only_primary.variants_correct == 0
    assert only_primary.variants_expected == 1

    both = compare_field("full_names", label, ["中村 由美", "Yumi Nakamura"])
    assert (both.correct, both.variants_correct, both.wrong) == (1, 1, 0)


def test_truong_uncertain_bi_loai_khoi_phep_do():
    """Truong ma chinh nguoi gan nhan khong doc noi tu anh thi khong tinh."""
    label = dict(LABEL_JA, uncertain=["addresses"])
    result = compare_card(label, {"addresses": ["sai hoan toan"]})
    assert "addresses" not in result
    assert "emails" in result


def test_moi_gia_tri_chi_khop_mot_lan():
    """Tra ve cung mot email hai lan khong duoc tinh la dung hai lan."""
    r = compare_field("emails", LABEL_JA,
                      ["taro.yamada@example.co.jp", "taro.yamada@example.co.jp"])
    assert (r.correct, r.wrong) == (1, 1)


# --- Do chat luong cua chinh chot chan grounding --------------------------

def test_grounding_loai_dung_du_lieu_bia():
    report = {"emails": [{"value": "info@example.co.jp", "verdict": "unverified"}]}
    assert grounding_quality(LABEL_JA, report) == {
        "rejected": 1, "rejected_but_correct": 0
    }


def test_grounding_loai_nham_gia_tri_dung_duoc_ghi_nhan():
    """Grounding loai mot gia tri CO THAT tren the - day la loi cua grounding,
    khong phai cua OCR. Phai do duoc, neu khong se khong biet nguong
    _FUZZY_THRESHOLD dat sai."""
    report = {"emails": [{"value": "taro.yamada@example.co.jp",
                          "verdict": "unverified"}]}
    assert grounding_quality(LABEL_JA, report) == {
        "rejected": 1, "rejected_but_correct": 1
    }


# --- Xuat CSV va chon vi du (Ngay 9) --------------------------------------

def _card(image, lang, per_field, ms_ocr=100, ms_extract=200):
    return {"image": image, "lang": lang, "per_field": per_field,
            "grounding": {"rejected": 0, "rejected_but_correct": 0},
            "ms_ocr": ms_ocr, "ms_extract": ms_extract, "raw_chars": 50}


def test_chon_ca_vi_du_dung_va_vi_du_sai():
    """DoD Ngay 9 yeu cau CA HAI. Chi dua vi du that bai thi bao cao bi quan
    sai lech; chi dua vi du thanh cong thi thanh khoe diem."""
    from app.services.evaluation import FieldResult

    from scripts.evaluate import examples

    perfect = {"emails": FieldResult(expected=2, correct=2)}
    broken = {"emails": FieldResult(expected=2, correct=0, missed=2, wrong=1)}
    cards = [_card("a.jpg", "ja", perfect), _card("b.jpg", "ja", perfect),
             _card("c.jpg", "en", broken)]

    good, bad = examples(cards)
    assert {c["image"] for c in good} == {"a.jpg", "b.jpg"}
    assert [c["image"] for c in bad] == ["c.jpg"]


def test_khong_co_the_nao_dung_hoan_toan_thi_khong_bia_vi_du():
    from app.services.evaluation import FieldResult

    from scripts.evaluate import examples

    broken = {"emails": FieldResult(expected=1, correct=0, missed=1)}
    good, bad = examples([_card("a.jpg", "ja", broken)])
    assert good == []
    assert [c["image"] for c in bad] == ["a.jpg"]


def test_csv_co_BOM_de_excel_doc_dung_chu_nhat(tmp_path):
    """Khong co BOM thi Excel tren Windows doc sai chu Nhat - dung loi da gap
    o buoc xuat du lieu Ngay 7."""
    from app.services.evaluation import FieldResult

    from scripts.evaluate import write_csv

    path = tmp_path / "evaluation.csv"
    write_csv([_card("a.jpg", "ja",
                     {"emails": FieldResult(expected=2, correct=1, missed=1)})],
              path)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    text = path.read_text(encoding="utf-8-sig")
    assert "ngon_ngu,truong" in text
    assert "ja,emails,2,1,0,1,0,0.5000" in text


def test_csv_de_trong_ty_le_khi_the_khong_co_truong_do(tmp_path):
    """Khong co gi de doc thi khong co ty le - ghi 0% se gay hieu nham."""
    from app.services.evaluation import FieldResult

    from scripts.evaluate import write_csv

    path = tmp_path / "e.csv"
    write_csv([_card("a.jpg", "en",
                     {"emails": FieldResult(expected=0, spurious=1)})], path)
    assert "en,emails,0,0,0,0,1," in path.read_text(encoding="utf-8-sig")
