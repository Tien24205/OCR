"""Kiem tra cong cu sinh the mau - moc mo rong bon ngon ngu.

VI SAO CAN TEST NAY: hai loi cua cong cu nay khong lo ra luc chay, ma lo ra
sau khi da IN, CAT va CHUP 80 tam the - luc do sua lai la lam lai tu dau.

  1. Font thieu glyph: Pillow ve o vuong .notdef va khong bao loi gi ca.
  2. Nhan lech voi anh: nhan sinh tu du lieu, anh ve tu du lieu, nhung neu
     mot nhanh nao do quen ve mot truong thi nhan van ghi truong do - va phep
     do Ngay 9 se tinh may doc sai trong khi tren the khong he co chu do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import make_card_sheets as m

_FONTS_CO_SAN = all(
    Path(p).is_file()
    for faces in m.FONT_SETS.values() for p in faces.values()
)
can_font = pytest.mark.skipif(
    not _FONTS_CO_SAN,
    reason="thieu font he thong (may khong phai Windows) - phep do glyph khong chay duoc",
)


@can_font
def test_chot_chan_bat_duoc_font_thieu_glyph():
    """Ve the Han bang font Nhat phai bi chan, khong duoc lang le ve o vuong."""
    with pytest.raises(SystemExit) as loi:
        m.assert_glyphs(m.KO_DEV, "ja")
    bao = str(loi.value)
    assert "O VUONG" in bao
    assert "YuGoth" in bao          # chi dich danh font sai
    assert "김" in bao or "한" in bao  # va chi dich danh ky tu hong


@can_font
@pytest.mark.parametrize("cards,lang", [(c, l) for _n, c, l, _s, _co in m.SHEETS])
def test_moi_trang_ve_duoc_bang_font_cua_chinh_no(cards, lang):
    m.assert_glyphs(cards, lang)


@pytest.mark.parametrize("name,cards,lang,split,code", m.SHEETS)
def test_moi_trang_du_mot_trang_in(name, cards, lang, split, code):
    assert len(cards) == m.COLS * m.ROWS


def test_dev_va_eval_khong_dung_chung_the():
    """Ro ri du lieu giua hai bo lam so do Ngay 9 mat y nghia."""
    for lang in {l for _n, _c, l, _s, _co in m.SHEETS}:
        bo = {}
        for _name, cards, cl, split, _code in m.SHEETS:
            if cl == lang:
                bo[split] = {c["company"] for c in cards}
        assert not (bo["dev"] & bo["eval"]), f"{lang}: the trung giua dev va eval"


@pytest.mark.parametrize("name,cards,lang,split,code", m.SHEETS)
def test_nhan_chi_ghi_nhung_gi_that_su_co_tren_the(name, cards, lang, split, code):
    """Moi gia tri trong nhan phai xuat hien nguyen van trong van ban cua the."""
    for i, card in enumerate(cards):
        tren_the = m.ocr_text(card, lang)
        nhan = m.label_row(card, lang, split, i)
        for khoa in ("full_name", "company_name"):
            assert nhan[khoa] in tren_the, f"{name}#{i + 1}: {khoa} khong co tren the"
        for khoa in ("job_titles", "departments", "emails", "websites"):
            for gia_tri in nhan[khoa]:
                assert gia_tri in tren_the, f"{name}#{i + 1}: {gia_tri} khong co tren the"
        for dien_thoai in nhan["phones"]:
            assert dien_thoai["value"] in tren_the
