"""Dang ky, dang nhap, va xem minh la ai (Ngay 23)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.access import NguoiGoi, nguoi_goi
from app.auth import (
    MAT_KHAU_TOI_THIEU,
    GioiHanTanSuat,
    bam_mat_khau,
    doc_khoa,
    doc_phieu,
    mat_khau_dung,
    tao_phieu,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import User, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth")


# `/api/auth/login` nam trong PUBLIC_PATHS, nen no KHONG di qua bo gioi han
# tan suat cua middleware - neu khong chan o day thi day la mot cua do mat
# khau khong gioi han, va la lo hong nang nhat ma trang dang nhap co the co.
#
# Chan theo DIA CHI IP chu khong theo email: chan theo email thi ke tan cong
# doi email moi lan thu la thoat, con nguoi that thi bi khoa ngoai chinh tai
# khoan cua minh chi vi co ke khac go sai ten ho.
#
# ponytail: bo dem trong bo nho mot tien trinh, giong GioiHanTanSuat cua khoa
# API. Chay nhieu ban sao thi moi ban dem rieng; chuyen sang Redis khi that
# su chay nhieu ban sao.
DANG_NHAP_MOI_PHUT = 10
_chan_dang_nhap = GioiHanTanSuat(DANG_NHAP_MOI_PHUT)


# VI SAO KHONG DUNG `EmailStr`: no keo theo goi `email-validator` chi de
# kiem mot thu ta khong thuc su can. He thong nay KHONG gui thu; email o day
# chi la ten dang nhap. Kiem theo dung RFC se loai ca nhung dia chi hop le
# it gap, va van khong tra loi duoc cau hoi duy nhat co y nghia - hop thu do
# co that khong - vi chi mot buc thu xac nhan moi tra loi duoc.
#
# Nen chi chan LOI GO NHAM that su: thieu `@`, thieu ten mien, co khoang trang.
MAU_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class DangKy(BaseModel):
    email: str = Field(min_length=5, max_length=320, pattern=MAU_EMAIL)
    password: str = Field(min_length=MAT_KHAU_TOI_THIEU, max_length=256)
    display_name: str | None = Field(default=None, max_length=120)


class DangNhap(BaseModel):
    # KHONG dat `pattern` o day: dang nhap phai tra ve "sai email hoac mat
    # khau" chu khong phai loi 422 ve dinh dang. Loi 422 noi cho nguoi go
    # rang chuoi do THAM CHI khong phai email - mot manh thong tin khong can
    # cho, va mot duong ma phia dang nhap khong nen tra loi khac di.
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


def _ho_so(user: User) -> dict:
    """Ho so tra ra ngoai. KHONG BAO GIO kem `password_hash`."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": user.created_at,
    }


def _phat_phieu(user: User, config: Settings) -> dict:
    return {
        "user": _ho_so(user),
        "token": tao_phieu(user.id, user.role, config.jwt_signing_key,
                           config.jwt_ttl_minutes),
        "token_type": "Bearer",
        "expires_in": config.jwt_ttl_minutes * 60,
    }


def _chan_neu_cua_dong(request: Request, db: Session, config: Settings) -> None:
    """Chan nguoi la tu tao tai khoan khi `REGISTRATION_OPEN=false`.

    HAI NGOAI LE, ca hai deu can thiet:

    1. CHUA CO TAI KHOAN NAO -> van nhan. Dong cua tu dau ma khong co ngoai
       le nay thi khong ai dang ky duoc, nen khong bao gio co quan tri, nen
       khong bao gio mo lai duoc cua: he thong tu khoa chet minh. Doi lai la
       mot khe ho giua luc dich vu len va luc ban dang ky - hay dang ky NGAY,
       truoc khi tro ten mien ve.

    2. QUAN TRI goi -> nhan, va day la duong de quan tri tao tai khoan cho
       nguoi khac. Dung lai endpoint nay thay vi them mot endpoint rieng:
       cung mot phep kiem dinh dang, cung mot cach bam mat khau.

    PHAI TU DOC PHIEU O DAY: `/api/auth/register` nam trong `PUBLIC_PATHS`,
    nen middleware xac thuc tra ve som va KHONG dien `request.state`. Doc
    `nguoi_goi(request)` o day se luon thay "khong ai ca" - ke ca khi quan
    tri that dang gui phieu - va `NguoiGoi(user_id=None)` lai duoc coi la
    che do mo, tuc la thay tat ca. Tin vao no o day thi phep kiem nay luon
    lot.
    """
    if config.registration_open:
        return
    if db.scalar(select(func.count()).select_from(User)) == 0:
        return
    phieu = doc_phieu(doc_khoa(request), config.jwt_signing_key)
    if phieu and phieu.get("role") == "admin":
        return
    raise ApiError(
        "REGISTRATION_CLOSED",
        "Trang này không mở đăng ký. Liên hệ quản trị viên để được cấp tài khoản.",
        403,
    )


def _chan_neu_qua_nhieu(request: Request) -> None:
    ip = request.client.host if request.client else "khong-ro"
    if not _chan_dang_nhap.cho_phep(ip):
        raise ApiError(
            "RATE_LIMITED",
            f"Quá {DANG_NHAP_MOI_PHUT} lần đăng nhập mỗi phút. Thử lại sau ít phút.",
            429, retryable=True,
        )


@router.get("/registration")
def trang_thai_dang_ky(db: Session = Depends(get_db),
                       config: Settings = Depends(get_settings)) -> dict:
    """Trang dang nhap co nen hien o "Tao tai khoan" khong.

    KHONG gop vao `/api/health`: health bi healthcheck goi 10 giay mot lan va
    co y KHONG dung toi CSDL, de no con tra loi duoc khi CSDL hong - do la
    luc nguoi van hanh can no nhat.

    `open` la ket qua DA TINH, khong phai co cau hinh tho: khi chua co tai
    khoan nao thi cua van mo du `REGISTRATION_OPEN=false`, vi nguoi dau tien
    phai vao duoc. Tra ve co tho se bat giao dien tu suy lai luat do, va hai
    ban sao cua mot luat thi som muon lech nhau.
    """
    chua_co_ai = db.scalar(select(func.count()).select_from(User)) == 0
    return {"open": bool(config.registration_open or chua_co_ai)}


@router.post("/register", status_code=201)
def dang_ky(body: DangKy, request: Request, db: Session = Depends(get_db),
            config: Settings = Depends(get_settings)) -> dict:
    """Tao tai khoan.

    NGUOI DAU TIEN LA QUAN TRI. Khong co nhanh nay thi khong ai la quan tri
    bao gio - khong the phong quyen cho chinh minh, va cung khong the phong
    cho nguoi khac. Doi lai, ai dang ky truoc tien tren mot he thong moi thi
    nam quyen; do la ly do AUTH_REQUIRED nen duoc bat NGAY khi trien khai
    that, chu khong phai sau khi da mo cho nguoi dung vao.
    """
    _chan_neu_qua_nhieu(request)
    _chan_neu_cua_dong(request, db, config)

    email = body.email.strip()
    email_norm = email.casefold()

    la_nguoi_dau_tien = db.scalar(select(func.count()).select_from(User)) == 0
    user = User(
        email=email,
        email_norm=email_norm,
        display_name=(body.display_name or "").strip() or None,
        password_hash=bam_mat_khau(body.password),
        role="admin" if la_nguoi_dau_tien else "user",
    )
    db.add(user)
    try:
        db.flush()
        audit.ghi_cho_tai_khoan(db, user, email, "tao_tai_khoan", vai_tro=user.role)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Cung mot cau cho moi ly do trung: khong xac nhan email nao da co
        # tai khoan tren he thong nay.
        raise ApiError("EMAIL_TAKEN", "Email này đã được đăng ký.", 409) from None

    logger.info("Tai khoan moi %s (role=%s)", user.id, user.role)
    return _phat_phieu(user, config)


@router.post("/login")
def dang_nhap(body: DangNhap, request: Request, db: Session = Depends(get_db),
              config: Settings = Depends(get_settings)) -> dict:
    """Doi email + mat khau lay phieu.

    MOT CAU TRA LOI DUY NHAT cho ca ba truong hop sai (khong co tai khoan,
    sai mat khau, tai khoan bi khoa): khac cau la bien trang dang nhap thanh
    cong cu do xem email nao co tai khoan o day.

    VAN BAM MAT KHAU KE CA KHI KHONG CO TAI KHOAN: khong bam thi loi goi do
    tra ve nhanh hon han loi goi co tai khoan (~46ms), va chinh do chenh lech
    do noi ra email nao ton tai - dung thu vua giau o tren.
    """
    _chan_neu_qua_nhieu(request)

    email_norm = body.email.strip().casefold()
    user = db.scalar(select(User).where(User.email_norm == email_norm))

    bam_that = user.password_hash if user else _BAM_GIA
    dung = mat_khau_dung(body.password, bam_that)

    if user is None or not dung or not user.is_active:
        # Ghi ca lan THAT BAI: nhieu dong lien tiep vao mot tai khoan la dau
        # hieu do mat khau, va chu tai khoan thay duoc chung trong nhat ky.
        # Ly do chi nam trong nhat ky (chu tai khoan va quan tri doc), KHONG
        # tra ra cau tra loi dang nhap - o do van la mot cau cho moi truong hop.
        ly_do = ("khong_co_tai_khoan" if user is None else
                 "tai_khoan_bi_khoa" if not user.is_active else "sai_mat_khau")
        audit.ghi_cho_tai_khoan(db, user, body.email.strip(), "dang_nhap_that_bai", ly_do=ly_do)
        db.commit()
        raise ApiError("BAD_CREDENTIALS", "Email hoặc mật khẩu không đúng.", 401)

    user.last_login_at = utcnow()
    audit.ghi_cho_tai_khoan(db, user, user.email, "dang_nhap")
    db.commit()
    return _phat_phieu(user, config)


@router.get("/me")
def toi_la_ai(db: Session = Depends(get_db),
              nguoi: NguoiGoi = Depends(nguoi_goi)) -> dict:
    """Ho so cua nguoi dang goi. Giao dien dung de biet da dang nhap chua."""
    if nguoi.la_he_thong:
        return {"user": None, "role": "service"}
    if not nguoi.user_id:
        raise ApiError("NOT_AUTHENTICATED", "Chưa đăng nhập.", 401)
    user = db.get(User, nguoi.user_id)
    if user is None or not user.is_active:
        # Phieu con han nhung tai khoan da bi xoa hoac khoa.
        raise ApiError("NOT_AUTHENTICATED", "Phiên không còn hiệu lực.", 401)
    return {"user": _ho_so(user), "role": user.role}


# Bam cua mot mat khau khong ai dat duoc, tinh MOT LAN luc nap module. Dung
# lam doi thu gia cho nhanh "khong co tai khoan" o `dang_nhap`, de duong do
# ton dung bang thoi gian voi duong co tai khoan.
_BAM_GIA = bam_mat_khau("khong-phai-mat-khau-cua-ai-ca")
