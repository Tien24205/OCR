"""Goi y cat vien anh danh thiep (Ngay 27).

VI SAO CAT: anh chup bang dien thoai thuong co tam the chiem chua toi mot
nua khung hinh, phan con lai la mat ban. Phan do khong mang chu nao nhung
van di qua OCR, va no keo do phan giai thuc te cua vung co chu xuong.

VI SAO CHI LA GOI Y, KHONG TU CAT: anh da gui la BANG CHUNG GOC - `raw_text`
va `extraction_json` deu duoc do lai voi no. Tu cat truoc khi gui nghia la
bang chung goc da bi mot thuat toan doan mo sua truoc khi ai kip nhin. Nen
nguoi dung thay CA HAI ban va tu chon; thu duoc gui di dung la thu ho da
nhin thay.

ponytail: cat theo TRUC NGANG/DOC, khong nan phoi canh. Anh chup cheo se
duoc cat dung vien ngoai cua the nhung van con cheo. Nan phoi canh can tim
bon goc va mot phep bien doi - viec do `cv2.findContours` +
`getPerspectiveTransform` lam duoc trong muoi dong, nhung `cv2` KHONG nam
trong requirements cua du an (no chi theo `rapidocr` vao may phat trien).
Them mot goi 113 MB cho mot buoc lam dep la khong dang; nang cap khi nao
`cv2` tro thanh phu thuoc that su.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter

# Anh duoc thu nho truoc khi do. Khong lam vay thi mot anh 12 MP ton vai
# tram mili giay moi lan chay lai script - va Streamlit chay lai script rat
# nhieu lan.
CANH_DO = 480

# Nguong nang luong vien, tinh theo ti le so voi dong/cot manh nhat. Thap
# qua thi bong do tren mat ban cung duoc tinh la vien the; cao qua thi mot
# the nen nhat tren ban trang bi cat vao trong.
NGUONG = 0.18

# Chua vien nho quanh vung tim duoc, theo ti le canh anh. Cat sat qua thi
# mat not chu o mep the.
LE = 0.015

# Duoi muc nay thi khong dang goi y: nguoi dung phai nhin hai tam anh va ra
# mot quyet dinh, de doi lay mot thay doi ho khong nhin thay.
CAT_TOI_THIEU = 0.08

# Tren muc nay thi nhieu kha nang da cat nham - vi du bat trung mot vet
# sang chu khong phai tam the.
#
# DAT CAO CO Y (92%). Nguong nay tung la 70%, va do la mot loi: the chup xa
# chi chiem mot phan nam khung hinh se can cat 80% - tuc dung truong hop
# viec cat co ich nhat lai bi tu choi. Chi loai nhung ban cat de lai chua
# toi 8% khung hinh, vi o muc do thi gan nhu chac chan da bat trung mot vet
# sang chu khong phai tam the.
CAT_TOI_DA = 0.92


def _vung_co_vien(xam: np.ndarray) -> tuple[int, int, int, int] | None:
    """Khung bao cua vung co nhieu vien nhat. Tra (trai, tren, phai, duoi)."""
    # Do lon gradient: cho nao sang toi doi dot ngot thi cho do co vien. Mat
    # ban tron mau cho gradient gan 0, tam the cho gradient cao o bon mep va
    # o moi dong chu.
    dy = np.abs(np.diff(xam, axis=0)).sum(axis=1)
    dx = np.abs(np.diff(xam, axis=1)).sum(axis=0)

    def khoang(nang_luong: np.ndarray) -> tuple[int, int] | None:
        if nang_luong.size == 0 or nang_luong.max() <= 0:
            return None
        manh = np.flatnonzero(nang_luong >= nang_luong.max() * NGUONG)
        if manh.size == 0:
            return None
        return int(manh[0]), int(manh[-1])

    doc, ngang = khoang(dy), khoang(dx)
    if doc is None or ngang is None:
        return None
    return ngang[0], doc[0], ngang[1], doc[1]


def goi_y_cat(du_lieu: bytes) -> tuple[int, int, int, int] | None:
    """Khung cat goi y cho anh, theo toa do cua anh GOC. None = khong goi y.

    Tra `None` khi khong tim duoc gi dang tin, khi phan cat di qua it de
    dang bat nguoi dung quyet dinh, hoac khi no nhieu den muc dang ngo.
    """
    try:
        with Image.open(BytesIO(du_lieu)) as anh:
            anh.load()
            rong_goc, cao_goc = anh.size
            nho = anh.convert("L")
            nho.thumbnail((CANH_DO, CANH_DO))
            # Lam mo nhe: van go tren mat ban va hat nhieu cua camera deu
            # tao gradient, va chung du de keo khung bao ra sat mep anh.
            nho = nho.filter(ImageFilter.GaussianBlur(1.2))
            xam = np.asarray(nho, dtype=np.int32)
    except Exception:
        # Anh hong thi duong gui van co phep kiem rieng cua no; o day chi
        # can khong goi y gi ca.
        return None

    vung = _vung_co_vien(xam)
    if vung is None:
        return None

    ty_le_x = rong_goc / xam.shape[1]
    ty_le_y = cao_goc / xam.shape[0]
    le_x, le_y = rong_goc * LE, cao_goc * LE

    trai = max(0, int(vung[0] * ty_le_x - le_x))
    tren = max(0, int(vung[1] * ty_le_y - le_y))
    phai = min(rong_goc, int(vung[2] * ty_le_x + le_x))
    duoi = min(cao_goc, int(vung[3] * ty_le_y + le_y))

    if phai - trai < 40 or duoi - tren < 40:
        return None

    con_lai = ((phai - trai) * (duoi - tren)) / (rong_goc * cao_goc)
    da_cat = 1 - con_lai
    if not (CAT_TOI_THIEU <= da_cat <= CAT_TOI_DA):
        return None
    return trai, tren, phai, duoi


def cat(du_lieu: bytes, khung: tuple[int, int, int, int]) -> tuple[bytes, str]:
    """Cat anh theo khung, tra ve (bytes, mime).

    GIU NGUYEN DINH DANG GOC: doi JPEG sang PNG lam tep phong len vai lan,
    con doi PNG sang JPEG thi them nhieu nen JPEG vao mot anh von khong co -
    va nhieu do roi vao dung buoc OCR.
    """
    with Image.open(BytesIO(du_lieu)) as anh:
        anh.load()
        dinh_dang = anh.format or "PNG"
        da_cat = anh.crop(khung)
        ra = BytesIO()
        if dinh_dang == "JPEG":
            # `quality=95` va tat lay mau mau: anh nay se di vao OCR, va nen
            # manh lam nhoe net chu nho - dung thu OCR can nhat.
            da_cat.convert("RGB").save(ra, format="JPEG", quality=95, subsampling=0)
            return ra.getvalue(), "image/jpeg"
        da_cat.save(ra, format="PNG")
        return ra.getvalue(), "image/png"
