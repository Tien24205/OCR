"""Nhan dien he chu viet - moc 19/09, mo rong ra bon ngon ngu cua de goc.

De goc (`De2.docx.pdf` muc 2) neu bon ngon ngu: Anh, Han, Nhat, Trung. MVP ban
dau chi lam Anh + Nhat. Bo test nay khoa lai phan mo rong.

Diem quan trong nhat cua module: no KHONG DOAN BUA khi khong du can cu.
"""

from __future__ import annotations

import pytest

from app.services import languages as L


# --- He chu rieng biet: ket luan chac chan --------------------------------

def test_kana_chac_chan_la_tieng_nhat():
    """Hiragana va Katakana khong dung o ngon ngu nao khac."""
    assert L.guess_language("ヤマダ タロウ") == "ja"
    assert L.guess_language("かぶしきがいしゃ") == "ja"


def test_hangul_chac_chan_la_tieng_han():
    assert L.guess_language("김민준") == "ko"
    assert L.guess_language("주식회사 한빛") == "ko"


def test_chu_latin_la_tieng_anh():
    assert L.guess_language("Jane Doe") == "en"


def test_tron_CJK_voi_latin_la_song_ngu():
    assert L.guess_language("山田 Taro") == "mixed"
    assert L.guess_language("株式会社サンプル SAMPLE CO.") == "mixed"


# --- Chu Han: vung mo ho, va cach xu ly trung thuc -------------------------

def test_chi_co_chu_han_khong_dau_hieu_thi_KHONG_DOAN_BUA():
    """LOI DA MAC PHAI: ban dau tra ve "zh" cho moi van ban chi co chu Han,
    tuc gan nhan sai cho phan lon ten nguoi Nhat.

    "山田 太郎" va "王小明" khong the phan biet duoc chi bang he chu. Tra ve
    `han` la trung thuc; doan mot trong hai la sai mot nua so truong hop.
    """
    assert L.guess_language("山田 太郎") == "han"
    assert L.guess_language("王小明") == "han"


def test_dau_hieu_rieng_cua_tieng_nhat_giup_phan_biet():
    """"株式会社" chi dung o Nhat, nen du toan chu Han van ket luan duoc."""
    assert L.guess_language("株式会社青葉") == "ja"
    assert L.guess_language("〒100-0001 東京都千代田区") == "ja"


def test_dau_hieu_rieng_cua_tieng_trung_giup_phan_biet():
    assert L.guess_language("北京科技有限公司") == "zh"
    assert L.guess_language("上海集团") == "zh"


def test_van_ban_rong_va_so_khong_thuoc_ngon_ngu_nao():
    assert L.guess_language("") == "other"
    assert L.guess_language("03-1234-5678") == "other"


# --- Nhan dien he chu ------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("あア", {"kana"}),
    ("한글", {"hangul"}),
    ("漢字", {"han"}),
    ("abc", {"latin"}),
    ("山田 Taro", {"han", "latin"}),
    ("株式会社サンプル", {"han", "kana"}),
])
def test_nhan_dien_he_chu(text, expected):
    assert L.scripts_in(text) == expected


def test_has_cjk_nhan_ra_ca_ba_he_chu_CJK():
    """Ban cu chi kiem Kana va chu Han, BO SOT Hangul - nen ten tieng Han
    khong duoc nhan la CJK va tin hieu ngon ngu im lang khong kich hoat."""
    assert L.has_cjk("山田")
    assert L.has_cjk("김민준")      # day la truong hop tung bi bo sot
    assert L.has_cjk("ヤマダ")
    assert not L.has_cjk("Jane Doe")


# --- Doi chieu voi ngon ngu OCR phat hien duoc -----------------------------

def test_chu_latin_luon_phu_hop_moi_ngon_ngu():
    """Ten Latin tren the tieng Nhat la chuyen binh thuong."""
    assert L.matches_hint("Jane Doe", ["ja"])
    assert L.matches_hint("Jane Doe", ["en"])


def test_chu_CJK_tren_the_bao_la_tieng_anh_la_dau_hieu_bat_thuong():
    assert not L.matches_hint("山田 太郎", ["en"])
    assert not L.matches_hint("김민준", ["en"])


@pytest.mark.parametrize("code", ["ja", "ja-JP", "ko", "ko-KR", "zh", "zh-Hans", "yue"])
def test_moi_ma_ngon_ngu_CJK_deu_duoc_chap_nhan(code):
    """Vision tra ve ma dang `ja-JP`, khong phai `ja`."""
    assert L.matches_hint("山田 太郎", [code])


def test_khong_co_goi_y_thi_khong_phat():
    """Thieu thong tin khong phai la bang chung co loi."""
    assert L.matches_hint("山田 太郎", [])


# --- Bo trich xuat regex ---------------------------------------------------

def test_regex_nhan_ra_cong_ty_tieng_han_va_tieng_trung():
    from app.services.extract.heuristic import HeuristicExtractor

    extractor = HeuristicExtractor()
    for raw, expected in [
        ("주식회사 한빛소프트\n김민준", "주식회사 한빛소프트"),
        ("北京科技有限公司\n王小明", "北京科技有限公司"),
        ("株式会社青葉\n山田 太郎", "株式会社青葉"),
    ]:
        result = extractor.extract(b"", "image/png", raw)
        assert [v.value for v in result.company_names] == [expected], raw


def test_regex_nhan_ra_chuc_danh_tieng_han_va_tieng_trung():
    from app.services.extract.heuristic import HeuristicExtractor

    extractor = HeuristicExtractor()
    assert any("대표이사" in v.value
               for v in extractor.extract(b"", "p", "대표이사 김민준").job_titles)
    assert any("总经理" in v.value
               for v in extractor.extract(b"", "p", "总经理 王小明").job_titles)
