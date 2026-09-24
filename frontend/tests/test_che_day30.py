"""Che bot email va so dien thoai khi hien tren man hinh.

Hai dieu can giu can bang, va bo test nay canh ca hai:

  che DU     - phan dinh danh mot con nguoi phai bien mat
  che VUA DU - phan noi ve to chuc phai con lai, khong thi nguoi dung
               khong phan biet duoc hai dong gan giong nhau, va ho se bat
               "hien day du" len va de vay mai
"""

from __future__ import annotations

import pytest

from lib.che import che_chuoi, che_danh_sach, che_email, che_so


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

@pytest.mark.parametrize("goc,mong_doi", [
    ("an.nguyen@cty.vn", "an***@cty.vn"),
    ("nehaal@91springboard.com", "ne***@91springboard.com"),
    ("jane@example.com", "ja***@example.com"),
])
def test_che_phan_ten_giu_ten_mien(goc, mong_doi):
    assert che_email(goc) == mong_doi


def test_ten_mien_duoc_giu_vi_no_noi_ve_to_chuc():
    """Nguoi dung can ten mien de phan biet hai dong gan giong nhau."""
    assert che_email("an@vietcombank.com.vn").endswith("@vietcombank.com.vn")


def test_phan_truoc_dau_a_cong_khong_con_doc_duoc():
    che = che_email("nguyenvanan@cty.vn")

    assert "nguyenvanan" not in che
    assert "guyenvana" not in che


def test_email_ngan_VAN_bi_che():
    """LOI DA SUA: ban dau co nhanh "ten ngan qua thi giu nguyen", va nhanh
    do lam email ngan lot NGUYEN BAN - dung loai de doc luot qua nhat.

    Do dai sau khi che luon nhu nhau, nen no cung khong noi ra phan ten that
    dai bao nhieu."""
    assert che_email("a@b.vn") == "a***@b.vn"
    assert che_email("an@cty.vn") == "an***@cty.vn"


def test_chuoi_khong_phai_email_van_duoc_che():
    """Du lieu tu OCR co the la bat cu thu gi. Khong duoc de lot nguyen ban
    chi vi no thieu dau @."""
    che = che_email("khongphaiemailgi")

    assert "khongphaiemail" not in che
    assert "*" in che


def test_rong_thi_tra_chuoi_rong():
    assert che_email(None) == "" and che_email("") == ""


# --------------------------------------------------------------------------
# So dien thoai
# --------------------------------------------------------------------------

@pytest.mark.parametrize("goc", [
    "+91-9004488330", "024-1234-5678", "0912345678", "+81 3-1234-5678",
])
def test_che_theo_chu_so_giu_nguyen_dinh_dang(goc):
    """Giu dau `+`, dau gach va khoang trang: che ca chung se bien mot so
    dien thoai thanh mot chuoi khong ro la gi."""
    che = che_so(goc)

    assert len(che) == len(goc)
    for i, c in enumerate(goc):
        if not c.isdigit():
            assert che[i] == c, f"ky tu phan cach {c!r} bi che mat"


def test_phan_giua_cua_so_bi_che():
    che = che_so("0912345678")

    assert "2345" not in che
    assert "*" in che


def test_ma_vung_duoc_giu_de_biet_so_nuoc_nao():
    assert che_so("+91-9004488330").startswith("+91")


def test_so_qua_ngan_giu_nguyen():
    assert che_so("123") == "123"


# --------------------------------------------------------------------------
# Danh sach - o trong bang la da gia tri
# --------------------------------------------------------------------------

def test_che_tung_phan_tu_trong_danh_sach():
    ra = che_danh_sach(["an@cty.vn", "binh@cty.vn"], che_email)

    assert ra == ["an***@cty.vn", "bi***@cty.vn"]


def test_mot_chuoi_don_cung_duoc_boc_thanh_danh_sach():
    """O trong bang co the la chuoi hoac danh sach - khong duoc vo tung ky
    tu cua mot chuoi thanh nhieu dong."""
    assert che_danh_sach("an@cty.vn", che_email) == ["an***@cty.vn"]


def test_danh_sach_rong_hoac_None():
    assert che_danh_sach(None) == [] and che_danh_sach([]) == []


# --------------------------------------------------------------------------
# Khong bao gio tra ve nguyen ban khi du dai
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ham,goc", [
    (che_email, "nguyenvanan@congtylon.com.vn"),
    (che_so, "+84 912 345 678"),
    (che_chuoi, "mot chuoi du dai"),
])
def test_khong_tra_ve_dung_chuoi_goc(ham, goc):
    assert ham(goc) != goc
