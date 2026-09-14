"""Doc cau truc phan hoi cua Google Vision - chuan bi cho Ngay 15.

VI SAO BO TEST NAY QUAN TRONG HON BINH THUONG

Ma nguon `google_vision.py` CHUA TUNG CHAY MOT LAN NAO. Test provider co san
truoc day tra ve `pages=[]`, nen toan bo phan ghep chu tu cau truc
trang -> khoi -> doan -> tu -> ky tu khong duoc chay dong nao.

Neu phan do co loi, nguoi dung se phat hien bang cach dot tien goi API that -
va se tuong OCR kem, trong khi loi thuc ra nam o buoc doc phan hoi.

Bo test nay dung lai dung cau truc ma Vision tra ve de chay thu truoc.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.api_core import exceptions as gexc
from google.cloud import vision

from app.services.ocr.base import OcrError
from app.services.ocr.google_vision import GoogleVisionProvider

BREAK = vision.TextAnnotation.DetectedBreak.BreakType


def symbol(text: str, break_type=None):
    return SimpleNamespace(
        text=text,
        property=SimpleNamespace(detected_break=SimpleNamespace(type_=break_type)),
    )


def word(text: str, *, end=None):
    """Mot tu; `end` la dau ngat DUNG SAU ky tu cuoi cung."""
    symbols = [symbol(ch) for ch in text[:-1]] + [symbol(text[-1], end)]
    return SimpleNamespace(symbols=symbols)


def paragraph(words, *, confidence=0.95, languages=("ja",), box=(0, 0, 100, 40)):
    x0, y0, x1, y1 = box
    return SimpleNamespace(
        words=words,
        confidence=confidence,
        bounding_box=SimpleNamespace(vertices=[
            SimpleNamespace(x=x0, y=y0), SimpleNamespace(x=x1, y=y0),
            SimpleNamespace(x=x1, y=y1), SimpleNamespace(x=x0, y=y1),
        ]),
        property=SimpleNamespace(detected_languages=[
            SimpleNamespace(language_code=code) for code in languages
        ]),
    )


def response(paragraphs, *, text="", page_languages=("ja", "en"), error=""):
    page = SimpleNamespace(
        property=SimpleNamespace(detected_languages=[
            SimpleNamespace(language_code=code) for code in page_languages
        ]),
        blocks=[SimpleNamespace(paragraphs=paragraphs)],
    )
    return SimpleNamespace(
        error=SimpleNamespace(message=error),
        full_text_annotation=SimpleNamespace(text=text, pages=[page]),
    )


@pytest.fixture()
def provider(monkeypatch):
    client = SimpleNamespace(annotate_image=None, transport=SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(vision, "ImageAnnotatorClient", lambda *a, **k: client)
    instance = GoogleVisionProvider(language_hints=["ja", "en"], timeout_s=20)
    return instance, client


def run(provider_pair, vision_response):
    instance, client = provider_pair
    client.annotate_image = lambda **kwargs: vision_response
    return instance.recognize(b"fake-image-bytes", "image/jpeg")


# --- Ghep chu tu cau truc ky tu -------------------------------------------

def test_dau_cach_giua_cac_tu_duoc_giu(provider):
    result = run(provider, response([paragraph([
        word("山田", end=BREAK.SPACE), word("太郎"),
    ])]))
    assert result.blocks[0].text == "山田 太郎"


def test_dia_chi_nhieu_dong_khong_bi_dinh_lien(provider):
    """Loi de mac nhat: bo qua `detected_break` thi dia chi Nhat nhieu dong
    thanh mot chuoi dai khong doc duoc, va grounding se loai nham."""
    result = run(provider, response([paragraph([
        word("〒100-0001", end=BREAK.EOL_SURE_SPACE),
        word("東京都千代田区", end=BREAK.LINE_BREAK),
        word("青葉ビル7F"),
    ])]))
    assert result.blocks[0].text == "〒100-0001\n東京都千代田区\n青葉ビル7F"


def test_dau_gach_noi_cuoi_dong_duoc_giu(provider):
    result = run(provider, response([paragraph([
        word("exam", end=BREAK.HYPHEN), word("ple"),
    ])]))
    assert result.blocks[0].text == "exam-ple"


def test_khoang_trang_chac_chan_cung_thanh_dau_cach(provider):
    result = run(provider, response([paragraph([
        word("TEL:", end=BREAK.SURE_SPACE), word("03-1234-5678"),
    ])]))
    assert result.blocks[0].text == "TEL: 03-1234-5678"


def test_doan_rong_bi_bo_qua(provider):
    """Doan khong co chu nao khong duoc tao ra mot khoi rong."""
    result = run(provider, response([
        paragraph([word(" ")]),
        paragraph([word("山田")]),
    ]))
    assert [b.text for b in result.blocks] == ["山田"]


# --- Toa do, do tin cay, ngon ngu -----------------------------------------

def test_toa_do_lay_bao_toan_bo_doan(provider):
    """Toa do de danh cho Ngay 5: bam vao mot truong thi to sang dung vung
    tren anh."""
    result = run(provider, response([
        paragraph([word("山田")], box=(10, 20, 300, 80)),
    ]))
    assert result.blocks[0].bbox == (10, 20, 300, 80)


def test_do_tin_cay_cua_doan_duoc_giu(provider):
    """`ConfidenceAgent` dung gia tri nay lam mot trong bon tin hieu."""
    result = run(provider, response([paragraph([word("山田")], confidence=0.62)]))
    assert result.blocks[0].confidence == pytest.approx(0.62)


def test_do_tin_cay_bang_khong_tro_thanh_None(provider):
    """Vision tra 0.0 khi khong co thong tin - khong duoc hieu la 'rat khong
    dang tin', vi nhu vay se tru diem oan."""
    result = run(provider, response([paragraph([word("山田")], confidence=0.0)]))
    assert result.blocks[0].confidence is None


def test_ngon_ngu_cua_trang_duoc_gom_khong_trung_lap(provider):
    result = run(provider, response([paragraph([word("山田")])],
                                    page_languages=("ja", "en", "ja")))
    assert result.detected_languages == ["ja", "en"]


def test_ngon_ngu_cua_tung_doan_duoc_giu_rieng(provider):
    result = run(provider, response([
        paragraph([word("山田")], languages=("ja",)),
        paragraph([word("Yamada")], languages=("en",)),
    ]))
    assert result.blocks[0].languages == ("ja",)
    assert result.blocks[1].languages == ("en",)


def test_van_ban_tho_lay_tu_full_text_annotation(provider):
    """`raw_text` la BANG CHUNG ma grounding doi chieu - phai lay tu truong
    tong the cua Vision, khong phai tu ghep lai cac khoi."""
    result = run(provider, response([paragraph([word("山田")])],
                                    text="株式会社\n山田 太郎"))
    assert result.raw_text == "株式会社\n山田 太郎"


def test_payload_ghi_lai_so_khoi_va_so_trang(provider):
    result = run(provider, response([paragraph([word("A")]), paragraph([word("B")])]))
    assert result.payload["block_count"] == 2
    assert result.payload["page_count"] == 1


# --- Duong loi -------------------------------------------------------------

def test_loi_nam_trong_than_phan_hoi_duoc_phat_hien(provider):
    """Vision bao loi trong THAN phan hoi chu khong nem exception. Bo qua
    truong nay se khien anh loi bi coi la OCR thanh cong voi van ban rong."""
    with pytest.raises(OcrError) as exc:
        run(provider, response([], error="Bad image data"))
    assert exc.value.code == "OCR_REJECTED"
    assert exc.value.retryable is False


def test_loi_tam_thoi_duoc_danh_dau_co_the_thu_lai(provider):
    instance, client = provider

    def boom(**kwargs):
        raise gexc.TooManyRequests("quota")

    client.annotate_image = boom
    with pytest.raises(OcrError) as exc:
        instance.recognize(b"x", "image/jpeg")
    assert exc.value.retryable is True


def test_loi_vinh_vien_khong_duoc_thu_lai(provider):
    """Thu lai anh hong chi ton them tien ma khong bao gio thanh cong."""
    instance, client = provider

    def boom(**kwargs):
        raise gexc.InvalidArgument("image is corrupt")

    client.annotate_image = boom
    with pytest.raises(OcrError) as exc:
        instance.recognize(b"x", "image/jpeg")
    assert exc.value.retryable is False


def test_phan_hoi_rong_khong_no(provider):
    """Anh trang hoan toan: Vision tra ve khong co trang nao."""
    instance, client = provider
    client.annotate_image = lambda **kwargs: SimpleNamespace(
        error=SimpleNamespace(message=""),
        full_text_annotation=SimpleNamespace(text="", pages=[]),
    )
    result = instance.recognize(b"x", "image/jpeg")
    assert result.raw_text == "" and result.blocks == []


def test_goi_dung_feature_va_goi_y_ngon_ngu(provider):
    """DOCUMENT_TEXT_DETECTION chu khong phai TEXT_DETECTION, va phai dat ca
    hai ngon ngu ngay tu dau - the song ngu la truong hop binh thuong."""
    instance, client = provider
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return response([paragraph([word("A")])])

    client.annotate_image = capture
    instance.recognize(b"x", "image/jpeg")

    request = captured["request"]
    assert request.features[0].type_ == vision.Feature.Type.DOCUMENT_TEXT_DETECTION
    assert list(request.image_context.language_hints) == ["ja", "en"]
