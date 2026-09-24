"""Che bot email va so dien thoai khi hien tren man hinh.

VI SAO CAN: trang Ho so hien mot bang day du email va so dien thoai cua
doi tac. Ai di ngang qua ban lam viec, hay mot khung hinh chia se man hinh
trong cuoc hop, la doc duoc het - khong can dang nhap, khong de lai dau
vet nao.

DAY KHONG PHAI MOT LOP BAO MAT. Du lieu van duoc gui day du xuong trinh
duyet va van xuat ra duoc; ai co quyen xem thi van xem duoc bang mot cu
bam. No chi cat cai nhin luot qua, va chi lam dung viec do.

NGUYEN TAC CHE: giu lai du de NHAN RA, bo di du de KHONG DOC DUOC.

    an.nguyen@cty.vn    ->  an***@cty.vn
    +91-9004488330      ->  +91-90*******30

Ten mien va dau so duoc giu vi chung noi ve TO CHUC chu khong ve ca nhan,
va nguoi dung can chung de phan biet hai dong gan giong nhau. Phan bi bo la
phan dinh danh mot con nguoi cu the.
"""

from __future__ import annotations

# Giu bao nhieu ky tu dau va cuoi. Con so nho co chu dich: giu nhieu hon
# thi che thanh trang tri, vi ba bon ky tu dau cua mot dia chi thuong da du
# de doan ra ca dia chi.
GIU_DAU_EMAIL = 2
GIU_DAU_SO = 2
GIU_CUOI_SO = 2

# Duoi muc nay thi khong phai so dien thoai nua, chi la rac OCR doc nham -
# che no khong bao ve gi ma chi lam nguoi dung tuong du lieu bi hong.
SO_NGAN_NHAT = 6


def che_email(gia_tri: str | None) -> str:
    """`an.nguyen@cty.vn` -> `an***@cty.vn`. Giu nguyen ten mien."""
    if not gia_tri:
        return ""
    chuoi = str(gia_tri)
    if "@" not in chuoi:
        return che_chuoi(chuoi)
    ten, _, mien = chuoi.partition("@")
    # LUON che, ke ca khi phan ten rat ngan. Khong co nhanh "ngan qua thi
    # giu nguyen" vi nhanh do lam email ngan lot NGUYEN BAN - dung loai de
    # doc luot qua nhat. Va vi do dai sau khi che luon nhu nhau, no cung
    # khong noi ra phan ten that dai bao nhieu.
    return f"{ten[:GIU_DAU_EMAIL]}***@{mien}"


def che_so(gia_tri: str | None) -> str:
    """`+91-9004488330` -> `+91-90*******30`.

    Che theo CHU SO, khong che theo ky tu: giu nguyen dau `+`, dau gach va
    khoang trang de so van doc ra duoc la so nuoc nao, dinh dang nao. Che ca
    dau phan cach se bien mot so dien thoai thanh mot chuoi khong ro la gi.
    """
    if not gia_tri:
        return ""
    chuoi = str(gia_tri)
    chu_so = [i for i, c in enumerate(chuoi) if c.isdigit()]
    if len(chu_so) < SO_NGAN_NHAT:
        return chuoi
    # Giu dau so (ma vung) va vai chu so cuoi; che phan giua.
    giau = set(chu_so[GIU_DAU_SO + 1:len(chu_so) - GIU_CUOI_SO])
    return "".join("*" if i in giau else c for i, c in enumerate(chuoi))


def che_chuoi(gia_tri: str | None) -> str:
    """Che chung cho chuoi khong ro dinh dang."""
    if not gia_tri:
        return ""
    chuoi = str(gia_tri)
    # Khong giu ky tu cuoi nhu ban dau: voi mot chuoi ngan thi giu ca dau
    # lan cuoi la lo gan het.
    return f"{chuoi[:GIU_DAU_EMAIL]}***" if len(chuoi) > GIU_DAU_EMAIL else "***"


def che_danh_sach(gia_tri, ham=che_email) -> list[str]:
    """Che tung phan tu. O trong bang co the la mot chuoi hoac mot danh sach."""
    if gia_tri is None:
        return []
    if isinstance(gia_tri, str):
        return [ham(gia_tri)]
    return [ham(x) for x in gia_tri]
