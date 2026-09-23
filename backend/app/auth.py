"""Xac thuc API bang khoa, kem gioi han tan suat.

VI SAO CAN: truoc lop nay, mot lenh `curl http://host:8000/api/contacts` khong
kem gi ca tra ve HTTP 200 va toan bo kho ho so doi tac. Do la ly do webhook
phai tat mac dinh - khong the cho phep bat ky ai dat mot dia chi de he thong
gui du lieu toi.

VI SAO DUNG MIDDLEWARE CHU KHONG DUNG DEPENDENCY: `Depends(...)` phai gan vao
TUNG endpoint. Nguoi them endpoint moi co the quen, va khi quen thi khong co
gi bao - endpoint do lang le mo toang. Middleware chan moi duong dan, ke ca
duong dan viet sau lop nay, nen no HONG VE PHIA DONG thay vi hong ve phia mo.

VI SAO CO CHE DO TAT: cong cu nay chay tren may ca nhan la chinh. Bat buoc
dat khoa moi chay duoc se khien nguoi ta dat khoa "1234" cho xong - te hon la
khong co khoa ma biet ro minh khong co. Nen:

    API_KEYS trong        -> khong xac thuc, VA noi ro dieu do o /api/health
                             cung nhu o dong log khi khoi dong
    API_KEYS co gia tri   -> bat buoc, moi loi goi deu phai kem khoa

Cach nay khong bao gio "tuong la an toan ma khong phai": trang thai that luon
hien ra.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Nhung duong dan KHONG doi khoa.
#
#   /api/health  - de he thong giam sat biet dich vu con song. No chi tra ve
#                  co true/false, khong bao gio tra ve gia tri khoa nao.
#   /docs, ...   - tai lieu API. Doc duoc tai lieu khong dong nghia goi duoc.
#   /api/auth/*  - dang ky va dang nhap. Doi khoa o day thi khong ai lay
#                  duoc khoa bao gio: muon dang nhap phai da dang nhap.
PUBLIC_PATHS = frozenset({
    "/api/health", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect",
    "/api/auth/register", "/api/auth/login",
})


# --------------------------------------------------------------------------
# Mat khau (Ngay 23)
# --------------------------------------------------------------------------
#
# VI SAO scrypt CUA THU VIEN CHUAN CHU KHONG PHAI bcrypt/passlib: khong can
# them goi nao. scrypt nam san trong `hashlib`, duoc thiet ke dung cho viec
# nay, va con TON BO NHO chu khong chi ton CPU - nen mot dan GPU khong rut
# ngan duoc thoi gian do nhu voi cac ham bam thong thuong.
#
# VI SAO KHONG DUNG sha256: sha256 duoc thiet ke de chay NHANH. Do dung la
# dieu ta khong muon o day - nhanh nghia la ke lay duoc CSDL cung do duoc
# nhanh. scrypt cham co chu dich.

SCRYPT_N = 2 ** 14      # ~46ms moi lan bam tren may van phong thong thuong
SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32

# Do dai toi thieu. Khong ep them quy tac "phai co ky tu dac biet": quy tac
# do day nguoi ta toi "Matkhau@123" - dai 11 ky tu va doan duoc trong vai
# giay. Do dai la thu duy nhat that su lam cho viec do kho hon.
MAT_KHAU_TOI_THIEU = 10


def bam_mat_khau(mat_khau: str) -> str:
    """Tra ve chuoi TU MO TA: `scrypt$n$r$p$salt_hex$hash_hex`.

    Tu mo ta nghia la chuoi mang theo ca tham so da dung de sinh ra no. Khi
    sau nay can tang `n` len cho may moi, nhung mat khau cu VAN kiem tra
    duoc bang tham so cu cua chinh chung - khong can bat ai doi mat khau, va
    khong can mot cot "phien ban thuat toan" rieng.
    """
    muoi = secrets.token_bytes(16)
    bam = hashlib.scrypt(mat_khau.encode("utf-8"), salt=muoi,
                         n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=DKLEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${muoi.hex()}${bam.hex()}"


def mat_khau_dung(mat_khau: str, da_luu: str) -> bool:
    """So mat khau voi chuoi da luu. Khong bao gio nem loi ra ngoai.

    Mot ban ghi hong trong CSDL phai thanh "sai mat khau", khong duoc thanh
    HTTP 500: 500 noi cho nguoi go rang tai khoan nay CO THAT va dang hong,
    con 401 thi khong noi gi ca.
    """
    try:
        thuat_toan, n, r, pp, muoi_hex, bam_hex = da_luu.split("$")
        if thuat_toan != "scrypt":
            return False
        lai = hashlib.scrypt(
            mat_khau.encode("utf-8"), salt=bytes.fromhex(muoi_hex),
            n=int(n), r=int(r), p=int(pp), dklen=len(bytes.fromhex(bam_hex)),
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return secrets.compare_digest(lai.hex(), bam_hex)


# --------------------------------------------------------------------------
# Phieu dang nhap JWT (Ngay 23)
# --------------------------------------------------------------------------

THUAT_TOAN_JWT = "HS256"


def tao_phieu(user_id: str, role: str, bi_mat: str, song_phut: int) -> str:
    bay_gio = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "role": role,
            "iat": bay_gio,
            "exp": bay_gio + timedelta(minutes=song_phut),
        },
        bi_mat,
        algorithm=THUAT_TOAN_JWT,
    )


def doc_phieu(phieu: str, bi_mat: str) -> dict | None:
    """Giai ma phieu. Tra None khi phieu sai, het han, hoac bi sua.

    `algorithms=[HS256]` la BAT BUOC ghi ro. Khong ghi thi thu vien chap nhan
    ca thuat toan ma phieu TU KHAI trong phan dau cua no - ke tan cong chi
    viec khai `alg: none` va tu cap cho minh mot phieu quan tri.
    """
    if not phieu or not bi_mat:
        return None
    try:
        return jwt.decode(phieu, bi_mat, algorithms=[THUAT_TOAN_JWT])
    except jwt.PyJWTError:
        return None


def khoa_hop_le(trinh_ra: str, cho_phep: list[str]) -> bool:
    """So khoa bang phep so THOI GIAN KHONG DOI.

    VI SAO KHONG DUNG `in`: phep so chuoi thong thuong dung ngay khi gap ky tu
    khac nhau dau tien, nen thoi gian tra loi ro ri thong tin ve do dai tien to
    dung. Ke tan cong do thoi gian co the do tung ky tu mot.

    `compare_digest` luon chay het do dai, nen thoi gian khong noi len gi.
    """
    if not trinh_ra:
        return False
    # Duyet HET danh sach, khong dung som khi da khop - de so lan so sanh
    # khong phu thuoc vao vi tri khoa dung trong danh sach.
    khop = False
    for k in cho_phep:
        if secrets.compare_digest(trinh_ra, k):
            khop = True
    return khop


def doc_khoa(request: Request) -> str:
    """Lay khoa tu `X-API-Key`, hoac tu `Authorization: Bearer ...`."""
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


class GioiHanTanSuat:
    """Dem so loi goi cua tung khoa trong mot cua so thoi gian truot.

    GIOI HAN DA BIET, GHI RA DE KHONG AI TUONG NHAM: bo dem nay nam TRONG BO
    NHO cua mot tien trinh. Nghia la:

      - chay nhieu tien trinh (hoac nhieu ban sao) thi moi ban dem rieng,
        tong so loi goi thuc te se cao hon gioi han da dat
      - khoi dong lai la mat sach bo dem

    Voi mot cong cu chay mot tien trinh thi the la du. Muon dung that o moi
    truong nhieu ban sao thi phai chuyen bo dem ra Redis hoac tuong duong -
    ghi ro trong roadmap chu khong de nguoi ta tu phat hien.
    """

    def __init__(self, moi_phut: int) -> None:
        self._moi_phut = moi_phut
        self._lich_su: dict[str, deque[float]] = defaultdict(deque)

    def xoa_het(self) -> None:
        """Xoa sach bo dem.

        Ton tai cho BO TEST: bo dem nay song o cap module nen no vat qua tung
        test, va test thu muoi mot se do vi muoi test truoc do da tieu het
        han muc - mot kieu do khong lien quan gi den thu dang kiem.
        """
        self._lich_su.clear()

    def cho_phep(self, khoa: str, bay_gio: float | None = None) -> bool:
        if self._moi_phut <= 0:          # 0 hoac am = khong gioi han
            return True
        bay_gio = time.monotonic() if bay_gio is None else bay_gio
        moc = self._lich_su[khoa]
        while moc and bay_gio - moc[0] >= 60.0:
            moc.popleft()
        if len(moc) >= self._moi_phut:
            return False
        moc.append(bay_gio)
        return True


def _tu_choi(code: str, message: str, status: int) -> JSONResponse:
    """Tra loi theo DUNG dang loi ma phan con lai cua API dung.

    Neu dang khac, giao dien va cac he thong tich hop se phai xu ly rieng mot
    truong hop - va thuong thi ho quen.
    """
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message,
                           "retryable": status == 429}},
    )


def gan_xac_thuc(app, cac_khoa: list[str], moi_phut: int,
                 bi_mat_jwt: str = "", bat_buoc: bool = False) -> None:
    """Gan middleware xac thuc vao app.

    Goi ham nay ngay sau khi tao app, TRUOC khi khai bao endpoint cung duoc -
    middleware trong Starlette chay cho moi request bat ke thu tu khai bao.

    HAI LOAI NGUOI GOI, MOT CHO KIEM TRA:

      khoa API  - mot HE THONG (webhook, cong cu dong bo CRM). Khong phai
                  mot nguoi, nen khong co ho so rieng va thay duoc tat ca.
      phieu JWT - mot NGUOI da dang nhap. Co `owner_id`, va chi thay phan
                  cua minh tru khi la quan tri.

    Ca hai deu den qua `Authorization: Bearer ...`, nen phai thu khoa truoc
    roi moi thu phieu. Thu nguoc lai cung ra ket qua dung nhung ton mot lan
    giai ma vo ich cho moi loi goi cua he thong tich hop.

    VI SAO MIDDLEWARE LUON DUOC GAN, KE CA KHI KHONG BAT BUOC XAC THUC: no
    con lam mot viec thu hai ngoai viec chan - no DOC ra nguoi goi la ai va
    dat vao `request.state`. Khong gan thi `owner_id` khong bao gio duoc
    dien, va phan phan quyen se im lang khong chay. Chan hay khong la quyet
    dinh rieng, nam o `_duoc_vao()` ben duoi.
    """
    if not cac_khoa and not bat_buoc:
        logger.warning(
            "Khong bat buoc xac thuc: ai goi duoc cung doc duoc toan bo ho so. "
            "Dat AUTH_REQUIRED=true (hoac API_KEYS) khi chay that."
        )
    else:
        logger.info("Xac thuc: BAT (%d khoa API, dang nhap %s, %d loi goi/phut)",
                    len(cac_khoa), "bat buoc" if bat_buoc else "tuy chon", moi_phut)

    gioi_han = GioiHanTanSuat(moi_phut)

    @app.middleware("http")
    async def _kiem_tra(request: Request, call_next):
        # Mac dinh: khong ai ca. Route nao doc `request.state` cung thay
        # duoc gia tri nay, ke ca tren duong dan cong khai.
        request.state.user_id = None
        request.state.role = None
        request.state.la_he_thong = False

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        trinh_ra = doc_khoa(request)

        if cac_khoa and khoa_hop_le(trinh_ra, cac_khoa):
            request.state.role = "service"
            request.state.la_he_thong = True
            danh_tinh = "he-thong"
        else:
            phieu = doc_phieu(trinh_ra, bi_mat_jwt)
            if phieu:
                request.state.user_id = phieu.get("sub")
                request.state.role = phieu.get("role") or "user"
                danh_tinh = f"user:{request.state.user_id}"
            elif cac_khoa or bat_buoc:
                # KHONG ghi gia tri khoa vao log, ke ca khoa sai: nguoi dung
                # hay go nham khoa that vao cho khac, va log thuong duoc chia
                # se rong hon nguoi ta tuong.
                logger.warning("Tu choi %s %s: %s", request.method,
                               request.url.path,
                               "khoa/phieu khong hop le" if trinh_ra
                               else "khong co khoa hay phieu")
                return _tu_choi(
                    "UNAUTHORIZED",
                    "Cần đăng nhập, hoặc gửi kèm header `X-API-Key`.",
                    401,
                )
            else:
                # Che do mo: giu nguyen hanh vi cu, khong danh tinh.
                return await call_next(request)

        if not gioi_han.cho_phep(danh_tinh):
            return _tu_choi(
                "RATE_LIMITED",
                f"Vượt quá {moi_phut} lời gọi mỗi phút. Thử lại sau ít giây.",
                429,
            )

        return await call_next(request)
