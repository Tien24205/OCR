"""Ngay 27: goi y cat vien anh danh thiep.

Phan kho cua mot buoc doan mo khong phai la "no co chay khong" ma la "no co
biet luc nao NEN IM LANG khong". Mot ham luon tra ve mot khung cat nao do
se cat nham vao the, va nguoi dung se mat long tin sau vai lan.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from lib.autocrop import CAT_TOI_DA, CAT_TOI_THIEU, cat, goi_y_cat


def anh_the(nen=(210, 205, 200), the=(255, 255, 255),
            khung=(60, 45, 440, 295), co=(500, 340), dinh_dang="PNG") -> bytes:
    """Mot tam the sang tren nen xam, co vai dong chu."""
    im = Image.new("RGB", co, nen)
    ve = ImageDraw.Draw(im)
    ve.rectangle(khung, fill=the)
    for i in range(3):
        y = khung[1] + 30 + i * 28
        ve.rectangle([khung[0] + 20, y, khung[2] - 40 - i * 30, y + 8],
                     fill=(40, 40, 40))
    ra = BytesIO()
    im.save(ra, format=dinh_dang)
    return ra.getvalue()


def test_tim_duoc_tam_the_tren_nen():
    khung = goi_y_cat(anh_the())

    assert khung is not None
    trai, tren, phai, duoi = khung
    # Khung phai bao lay the that (60,45)-(440,295), sai so trong khoang le.
    assert trai <= 70 and tren <= 55
    assert phai >= 430 and duoi >= 285


def test_anh_da_cat_sat_thi_khong_goi_y_gi():
    """The chiem gan het khung hinh: cat them chi lam nguoi dung phai quyet
    dinh mot viec khong thay doi gi."""
    kin = anh_the(khung=(6, 6, 494, 334))

    assert goi_y_cat(kin) is None


def test_anh_tron_mot_mau_khong_goi_y():
    ra = BytesIO()
    Image.new("RGB", (400, 300), (180, 180, 180)).save(ra, format="PNG")

    assert goi_y_cat(ra.getvalue()) is None


def test_du_lieu_hong_khong_lam_no_van_ang():
    """Duong gui co phep kiem anh rieng cua no; o day chi can im lang."""
    assert goi_y_cat(b"day khong phai anh") is None
    assert goi_y_cat(b"") is None


def test_ty_le_cat_luon_nam_trong_khoang_cho_phep():
    du_lieu = anh_the()
    khung = goi_y_cat(du_lieu)

    with Image.open(BytesIO(du_lieu)) as im:
        rong, cao = im.size
    da_cat = 1 - ((khung[2] - khung[0]) * (khung[3] - khung[1])) / (rong * cao)

    assert CAT_TOI_THIEU <= da_cat <= CAT_TOI_DA


# --------------------------------------------------------------------------
# Cat
# --------------------------------------------------------------------------

def test_cat_giu_nguyen_dinh_dang_png():
    du_lieu = anh_the(dinh_dang="PNG")
    ra, mime = cat(du_lieu, goi_y_cat(du_lieu))

    assert mime == "image/png"
    with Image.open(BytesIO(ra)) as im:
        assert im.format == "PNG"


def test_cat_giu_nguyen_dinh_dang_jpeg():
    """Doi JPEG sang PNG lam tep phong len vai lan; doi PNG sang JPEG them
    nhieu nen vao dung buoc OCR can net nhat."""
    du_lieu = anh_the(dinh_dang="JPEG")
    ra, mime = cat(du_lieu, goi_y_cat(du_lieu))

    assert mime == "image/jpeg"
    with Image.open(BytesIO(ra)) as im:
        assert im.format == "JPEG"


def test_anh_cat_ra_nho_hon_va_dung_kich_thuoc_khung():
    du_lieu = anh_the()
    khung = goi_y_cat(du_lieu)
    ra, _ = cat(du_lieu, khung)

    with Image.open(BytesIO(ra)) as im:
        assert im.size == (khung[2] - khung[0], khung[3] - khung[1])
    with Image.open(BytesIO(du_lieu)) as goc:
        assert im.size[0] < goc.size[0]


@pytest.mark.parametrize("nen,the", [
    ((235, 235, 235), (255, 255, 255)),      # the trang tren nen sang
    ((30, 30, 30), (250, 250, 250)),         # the trang tren nen toi
])
def test_chay_duoc_voi_do_tuong_phan_khac_nhau(nen, the):
    """Nen sang gan bang mau the la ca kho nhat - anh chup tren ban trang."""
    khung = goi_y_cat(anh_the(nen=nen, the=the))

    assert khung is None or (khung[2] > khung[0] and khung[3] > khung[1])
