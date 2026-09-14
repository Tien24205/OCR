"""Kiem tra nha cung cap OCR Tesseract ma KHONG can cai Tesseract.

CACH LAM: `image_to_data` tra ve mot dict cac danh sach song song. Bo test
nay dung lai dung hinh dang do - gom ca nhung truong hop that hay gap ma
tai lieu khong noi: o trong, diem tin cay -1, nhieu doan trong mot khoi.

VI SAO LAM VAY: neu doi phai cai Tesseract moi chay duoc test thi vung code
nay se khong bao gio duoc kiem tra trong CI, va loi gom khoi se chi lo ra
luc dang quet anh that.

Rieng mot test o cuoi CO goi Tesseract that, va tu bo qua khi may chua cai.
"""

from __future__ import annotations

import pytest

from app.services.extract.grounding import norm_for_match
from app.services.ocr.base import OcrError
from app.services.ocr.tesseract import _group_blocks, _tess_langs


def data(rows: list[tuple]) -> dict:
    """Dung dict kieu `image_to_data` tu cac dong (block, par, line, text, conf).

    Toa do sinh tu dong: moi tu rong 50, cao 20, xep theo chi so dong.
    """
    keys = ["block_num", "par_num", "line_num", "text", "conf",
            "left", "top", "width", "height"]
    out: dict[str, list] = {k: [] for k in keys}
    for i, (block, par, line, text, conf) in enumerate(rows):
        for key, value in zip(keys, [block, par, line, text, conf,
                                     i * 50, line * 20, 50, 20]):
            out[key].append(value)
    return out


# --- Anh xa ngon ngu ------------------------------------------------------

def test_anh_xa_ma_ngon_ngu_sang_ma_ba_ky_tu():
    """Tesseract dung ISO 639-2/T, khong dung ma hai ky tu nhu Google."""
    assert _tess_langs(["ja", "en"]) == "jpn+eng"
    assert _tess_langs(["ko", "zh"]) == "kor+chi_sim"


def test_bo_qua_ma_khong_biet_thay_vi_nem_loi():
    """Mot ma la khong duoc lam hong ca lan quet."""
    assert _tess_langs(["ja", "vi", "en"]) == "jpn+eng"


def test_khong_bao_gio_tra_ve_chuoi_rong():
    """Chuoi rong se lam Tesseract chay voi ngon ngu mac dinh khong doan duoc."""
    assert _tess_langs([]) == "eng"
    assert _tess_langs(["vi"]) == "eng"


def test_khong_lap_ma_khi_hint_trung_nhau():
    """"zh" va "zh-Hans" cung tro toi chi_sim; lap lai se lam Tesseract loi."""
    assert _tess_langs(["zh", "zh-Hans"]) == "chi_sim"


# --- Gom khoi -------------------------------------------------------------

def test_gom_tu_thanh_dong_va_doan():
    rows = [
        (1, 1, 1, "Yamada", 96), (1, 1, 1, "Taro", 94),
        (1, 1, 2, "Sales", 90), (1, 1, 2, "Manager", 88),
        (2, 1, 1, "Aoba", 92), (2, 1, 1, "Inc.", 91),
    ]
    blocks, raw = _group_blocks(data(rows))

    assert len(blocks) == 2
    assert blocks[0].text == "Yamada Taro\nSales Manager"
    assert blocks[1].text == "Aoba Inc."
    assert raw == "Yamada Taro\nSales Manager\nAoba Inc."


def test_loai_o_trong_va_diem_am():
    """Tesseract chen o rong voi conf = -1 giua cac tu.

    Neu khong loai, diem tin cay trung binh bi keo xuong boi nhung o khong
    phai chu - lam ca he thong tuong ban quet toi hon thuc te.
    """
    rows = [
        (1, 1, 1, "", -1), (1, 1, 1, "Yamada", 90),
        (1, 1, 1, "   ", -1), (1, 1, 1, "Taro", 80),
    ]
    blocks, raw = _group_blocks(data(rows))

    assert len(blocks) == 1
    assert blocks[0].text == "Yamada Taro"
    # Trung binh cua 90 va 80, doi sang thang do 0-1 ma he thong dung.
    assert blocks[0].confidence == pytest.approx(0.85)


def test_diem_tin_cay_doi_sang_thang_0_1():
    """Tesseract cho 0-100; phan con lai cua he thong dung 0-1.

    Tron hai thang do se lam moi nguong tin cay sai ca tram lan.
    """
    blocks, _ = _group_blocks(data([(1, 1, 1, "Aoba", 100)]))
    assert blocks[0].confidence == 1.0


def test_hai_doan_trong_cung_mot_khoi_khong_bi_ghep():
    """block_num giong nhau nhung par_num khac la hai doan RIENG BIET."""
    rows = [(1, 1, 1, "Tokyo", 90), (1, 2, 1, "03-1234-5678", 90)]
    blocks, _ = _group_blocks(data(rows))
    assert [b.text for b in blocks] == ["Tokyo", "03-1234-5678"]


def test_bbox_bao_tron_moi_tu_trong_khoi():
    rows = [(1, 1, 1, "Yamada", 90), (1, 1, 2, "Taro", 90)]
    blocks, _ = _group_blocks(data(rows))
    x0, y0, x1, y1 = blocks[0].bbox
    assert (x0, y0) == (0, 20)      # tu dau o left=0, dong 1 -> top=20
    assert (x1, y1) == (100, 60)    # tu hai o left=50 rong 50; dong 2 -> 40+20


def test_du_lieu_rong_khong_no():
    blocks, raw = _group_blocks(data([]))
    assert blocks == [] and raw == ""


def test_moi_o_deu_bi_loai_thi_tra_ve_rong():
    """Anh khong co chu nao: phai tra ve rong, khong duoc nem loi."""
    blocks, raw = _group_blocks(data([(1, 1, 1, "", -1), (1, 1, 1, " ", -1)]))
    assert blocks == [] and raw == ""


# --- Lien he voi grounding ------------------------------------------------

def test_khoang_trang_thua_giua_kanji_khong_pha_viec_so_khop():
    """Tesseract hay chen khoang trang giua cac chu Kanji.

    Day la ly do KHONG can sua `raw_text`: `norm_for_match` da xoa sach moi
    khoang trang truoc khi so sanh, nen tat xau nay cua Tesseract tu vo hieu.
    Sua raw_text se lam hong bang chung goc ma chang duoc gi.
    """
    _, raw = _group_blocks(data([
        (1, 1, 1, "株式", 88), (1, 1, 1, "会社", 86), (1, 1, 1, "青葉", 84),
    ]))

    assert raw == "株式 会社 青葉"                     # co khoang trang thua
    assert norm_for_match(raw) == norm_for_match("株式会社青葉")


# --- Loi cau hinh ---------------------------------------------------------

def test_bao_loi_ro_rang_khi_chua_cai_tesseract(monkeypatch):
    """Thong bao phai chi ra cach cai, khong chi noi "that bai"."""
    from app.services.ocr import tesseract as mod

    class FakePt:
        class pytesseract:
            tesseract_cmd = ""

        @staticmethod
        def get_tesseract_version():
            raise OSError("khong tim thay tesseract")

    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakePt)

    with pytest.raises(OcrError) as caught:
        mod.TesseractProvider(["ja", "en"])

    assert caught.value.code == "OCR_NOT_CONFIGURED"
    assert "UB-Mannheim" in caught.value.message
    assert "TESSERACT_CMD" in caught.value.message


def test_bao_ro_goi_ngon_ngu_nao_con_thieu(monkeypatch):
    """Cai Tesseract nhung quen tick goi tieng Nhat la loi rat hay gap.

    Bao "Tesseract loi" chung chung se khien nguoi dung go cai lai ca phan
    mem. Phai noi thang thieu goi NAO.
    """
    from app.services.ocr import tesseract as mod

    class FakePt:
        class pytesseract:
            tesseract_cmd = ""

        @staticmethod
        def get_tesseract_version():
            return "5.3.3"

        @staticmethod
        def get_languages(config=""):
            return ["eng", "osd"]          # thieu jpn

    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakePt)

    with pytest.raises(OcrError) as caught:
        mod.TesseractProvider(["ja", "en"])

    assert "jpn" in caught.value.message
    assert "eng" not in caught.value.message.split("thieu goi ngon ngu:")[1]


# --- Chay that, tu bo qua neu may chua cai --------------------------------

def _tesseract_san_sang() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return "eng" in pytesseract.get_languages(config="")
    except Exception:
        return False


@pytest.mark.skipif(not _tesseract_san_sang(),
                    reason="may nay chua cai Tesseract")
def test_doc_duoc_chu_tu_anh_that():
    """Chay Tesseract that tren mot anh sinh tai cho.

    Day la test duy nhat trong file cham vao phan mem that. No tra loi cau
    hoi ma moi test gia lap o tren khong tra loi duoc: duong noi giua ung
    dung va Tesseract co that su thong khong.
    """
    import io

    from PIL import Image, ImageDraw

    from app.services.ocr.tesseract import TesseractProvider

    picture = Image.new("RGB", (420, 120), "white")
    ImageDraw.Draw(picture).text((20, 40), "HELLO WORLD", fill="black")
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")

    result = TesseractProvider(["en"]).recognize(buffer.getvalue(), "image/png")

    assert "HELLO" in result.raw_text.upper()
    assert result.provider == "tesseract"
    assert result.provider_version                # phai ghi lai phien ban that
    assert result.detected_languages == []        # Tesseract khong phat hien
