"""Diem tin cay theo TUNG TRUONG phai di duoc toi ban nhap ma API tra ve.

LOI DA TUNG MAC PHAI: `ConfidenceAgent` cham diem cho tung dong va ghi vao
`grounding["draft"]`, nhung `current_draft()` khong bao gio doc khoa do - no
dung lai ban nhap tu `grounding["fields"]`. Ket qua: diem duoc tinh, duoc luu,
roi bi vut di. Giao dien chi con diem tong the.

Loi nay khong lam sap gi ca va khong test nao bat duoc, nen no ton tai am tham.
"""

from __future__ import annotations

from copy import deepcopy

from app.services.confidence import ConfidenceAgent
from app.services.drafts import current_draft, with_confidence

GROUNDING = {
    "fields": {
        "full_names": [{"value": "山田 太郎", "source_text": "部長 山田 太郎"}],
        "company_names": [{"value": "株式会社青葉", "source_text": "株式会社青葉"}],
        "emails": [{"value": "taro@example.co.jp", "source_text": "taro@example.co.jp"}],
        "phones": [{"value": "03-1234-5678", "label": "tel", "extension": ""}],
        "job_titles": [], "departments": [], "websites": [], "addresses": [],
    },
    "report": {},
    "card_language": "ja",
}


def _scored() -> dict:
    # deepcopy: GROUNDING long nhau nhieu tang, ban sao nong se khien test nay
    # sua du lieu cua test khac.
    grounding = deepcopy(GROUNDING)
    draft = current_draft(grounding)
    grounding["confidence"] = ConfidenceAgent().evaluate_scan(draft, ["ja"])
    return grounding


def test_diem_theo_truong_toi_duoc_ban_nhap():
    draft = current_draft(_scored())
    email = draft["fields"]["emails"][0]
    assert isinstance(email["confidence_score"], (int, float))
    assert "confidence_reasons" in email


def test_diem_doi_chieu_theo_gia_tri_khong_theo_vi_tri():
    """Neu so dong thay doi giua hai lan, gan theo vi tri se dan diem sang
    dong khac - sai ma khong bao loi."""
    grounding = _scored()
    # Chen mot dong moi len dau: vi tri cua moi dong cu deu dich di mot.
    grounding["fields"]["emails"] = [
        {"value": "moi@example.co.jp", "source_text": "moi@example.co.jp"},
        *grounding["fields"]["emails"],
    ]
    draft = current_draft(grounding)

    by_value = {item["value"]: item for item in draft["fields"]["emails"]}
    assert "confidence_score" in by_value["taro@example.co.jp"]
    # Dong moi chua duoc cham diem thi khong duoc muon diem cua dong khac.
    assert "confidence_score" not in by_value["moi@example.co.jp"]


def test_ban_nhap_van_dung_lai_tu_fields():
    """`fields` la nguon su that. Sua `fields` thi ban nhap phai doi theo,
    khong duoc tra ve ban da luu tu truoc."""
    grounding = _scored()
    grounding["fields"]["emails"] = []
    assert current_draft(grounding)["fields"]["emails"] == []


def test_khong_co_diem_thi_ban_nhap_van_dung():
    """Scan cu tu Ngay 4 khong co khoa confidence - khong duoc no."""
    draft = current_draft(deepcopy(GROUNDING))
    assert draft["fields"]["emails"][0]["value"] == "taro@example.co.jp"
    assert "confidence_score" not in draft["fields"]["emails"][0]


def test_with_confidence_bo_qua_muc_du_lieu_hong():
    draft = {"fields": {"emails": [{"value": "a@b.com"}]}}
    grounding = {"confidence": {"field_scores": {"emails": ["khong phai dict", None]}}}
    assert with_confidence(draft, grounding)["fields"]["emails"][0] == {"value": "a@b.com"}


# --- Hai tin hieu moi cua ConfidenceAgent ---------------------------------

def test_do_tin_cay_thap_cua_OCR_lam_giam_diem():
    """Vision co tra ve confidence cho tung doan; truoc day tin hieu nay bi
    bo qua hoan toan."""
    agent = ConfidenceAgent()
    high = agent.evaluate_field("emails", {"value": "a@b.com"}, ["en"])
    low = agent.evaluate_field(
        "emails", {"value": "a@b.com", "ocr_confidence": 0.4}, ["en"]
    )
    assert low["score"] < high["score"]
    assert "low_ocr_confidence" in low["reasons"]


def test_chu_nhat_tren_the_khong_phai_tieng_nhat_bi_giam_diem():
    """`scan_langs` truoc day la tham so chet - truyen vao ma khong dung."""
    agent = ConfidenceAgent()
    matched = agent.evaluate_field("full_names", {"value": "山田 太郎"}, ["ja"])
    mismatched = agent.evaluate_field("full_names", {"value": "山田 太郎"}, ["en"])
    assert mismatched["score"] < matched["score"]
    assert "language_mismatch" in mismatched["reasons"]


def test_ten_latin_khong_bi_phat_du_the_la_tieng_nhat():
    agent = ConfidenceAgent()
    assert agent.evaluate_field("full_names", {"value": "Jane Doe"}, ["ja"])["score"] \
        == agent.evaluate_field("full_names", {"value": "Jane Doe"}, ["en"])["score"]


# --- Tin hieu 4: nhat quan giua email va website --------------------------

def _draft(emails: list[dict], websites: list[dict]) -> dict:
    return {"fields": {"emails": emails, "websites": websites,
                       "full_names": [{"value": "A"}],
                       "company_names": [{"value": "B"}],
                       "job_titles": [], "departments": [], "phones": [],
                       "addresses": []}}


def _score(draft: dict) -> dict:
    ConfidenceAgent().evaluate_scan(draft, ["en"])
    return draft["fields"]["emails"][0]


def test_email_cung_ten_mien_voi_website_duoc_cong_diem():
    """Bang chung noi tai: ca hai truong deu duoc doc dung.

    Phan cong chi thay duoc o dong DA BI TRU DIEM o cho khac - email sach von
    da 1.0 nen bi chan tren. Dung verdict "fuzzy" (OCR doc gan dung) de kiem
    tra dung truong hop ma tin hieu nay co tac dung.
    """
    fuzzy = {"value": "jane@example.com", "grounding_verdict": "fuzzy"}
    matched = _score(_draft(
        [dict(fuzzy)],
        [{"value": "https://example.com", "website_domain": "example.com"}]))
    alone = _score(_draft([dict(fuzzy)], []))

    assert matched["confidence_score"] > alone["confidence_score"]
    assert "domain_matches_website" in matched["confidence_reasons"]


def test_email_cong_ty_khac_ten_mien_website_bi_tru_diem():
    item = _score(_draft(
        [{"value": "jane@othercorp.com"}],
        [{"value": "https://example.com", "website_domain": "example.com"}]))
    assert "domain_differs_from_website" in item["confidence_reasons"]
    assert item["confidence_score"] < 1.0


def test_email_dich_vu_cong_cong_khong_bi_phat():
    """Rat nhieu the that dung Gmail mot cach hoan toan hop le."""
    item = _score(_draft(
        [{"value": "jane@gmail.com", "is_free_email_domain": True}],
        [{"value": "https://example.com", "website_domain": "example.com"}]))
    assert "domain_differs_from_website" not in item.get("confidence_reasons", [])


def test_the_khong_co_website_thi_khong_dieu_chinh():
    item = _score(_draft([{"value": "jane@example.com"}], []))
    assert "domain_matches_website" not in item.get("confidence_reasons", [])
    assert "domain_differs_from_website" not in item.get("confidence_reasons", [])


def test_gia_tri_do_nguoi_dung_sua_khong_bi_cham_lai():
    item = _score(_draft(
        [{"value": "jane@othercorp.com", "source": "user"}],
        [{"value": "https://example.com", "website_domain": "example.com"}]))
    assert "domain_differs_from_website" not in item.get("confidence_reasons", [])
