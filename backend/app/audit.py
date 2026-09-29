"""Nhat ky kiem toan: ghi lai va doc ra.

`ghi()` chi THEM dong vao phien, KHONG commit: dong nhat ky phai vao CSDL
cung mot giao dich voi viec no ghi lai. Commit rieng thi hoac co nhat ky ma
viec khong xay ra (viec loi sau do), hoac viec xay ra ma khong co nhat ky
(ghi loi sau khi viec da xong) - ca hai deu la nhat ky noi sai.

KHONG GHI DU LIEU CA NHAN CUA DOI TAC. Ten ho so, email, so dien thoai khong
bao gio vao bang nay: xoa ho so thi nhat ky khong duoc con ban sao. Muon hien
ten doi tuong thi TRA LUC DOC (`_nhan_doi_tuong`) - doi tuong da xoa thi hien
"(đã xoá)", dung nhu no phai the.
"""

from __future__ import annotations

from contextvars import ContextVar

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import NguoiGoi, nguoi_goi
from app.db import get_db
from app.models import AuditLog, Contact, Scan, User

router = APIRouter(prefix="/api")

HANH_DONG = (
    "dang_nhap", "dang_nhap_that_bai", "tao_tai_khoan",
    "quet_the", "sua_ban_nhap", "luu_ho_so", "sua_ho_so",
    "xoa_ho_so", "xoa_ban_quet", "xuat_du_lieu",
)

# (ip, trinh duyet) cua yeu cau dang xu ly. Dat boi middleware trong main.py;
# ContextVar thi moi yeu cau - ke ca chay trong threadpool - thay dung cua no.
_nguon: ContextVar[tuple[str | None, str | None]] = ContextVar("audit_nguon", default=(None, None))


def dat_nguon(request):
    """Doc IP/trinh duyet cua nguoi thuc hien tu yeu cau.

    Uu tien `X-Client-IP` / `X-Client-UA`: giao dien Streamlit goi backend TU
    MAY CHU, nen IP ket noi toi day la cua may chu Streamlit, khong phai cua
    nguoi dung. Streamlit chuyen tiep IP/trinh duyet that qua hai header nay.

    ponytail: header do nguoi goi tu khai, nen mot ben co khoa API co the
    khai sai. Du cho nhat ky van hanh; muon dung lam bang chung phap ly thi
    chi nhan hai header nay tu IP cua may chu Streamlit.
    """
    h = request.headers
    ip = (h.get("x-client-ip") or h.get("cf-connecting-ip")
          or (h.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else None))
    ua = h.get("x-client-ua") or h.get("user-agent")
    return _nguon.set(((ip or None) and ip[:64], (ua or None) and ua[:300]))


def bo_nguon(token) -> None:
    _nguon.reset(token)


def ten_nguoi(db: Session, nguoi: NguoiGoi) -> str | None:
    """Email cua nguoi goi, giu lai KE CA khi tai khoan bi xoa sau nay."""
    if nguoi.la_he_thong:
        return "(khóa API)"
    if not nguoi.user_id:
        return None
    u = db.get(User, nguoi.user_id)
    return u.email if u else None


def truong_da_doi(cu: dict | None, moi: dict | None) -> list[str]:
    """TEN cac truong co gia tri khac nhau giua hai ban nhap - khong kem gia tri."""
    from app.services.normalize import FIELDS

    a = (cu or {}).get("fields") or {}
    b = (moi or {}).get("fields") or {}
    return [f for f in FIELDS
            if [x.get("value") for x in a.get(f) or []] != [x.get("value") for x in b.get(f) or []]]


def _them(db: Session, user_id: str | None, actor: str | None, hanh_dong: str,
          loai: str | None, ma: str | None, chi_tiet: dict) -> None:
    assert hanh_dong in HANH_DONG, hanh_dong
    ip, thiet_bi = _nguon.get()
    db.add(AuditLog(user_id=user_id, actor=actor, action=hanh_dong, target_type=loai,
                    target_id=ma, detail=chi_tiet, ip=ip, thiet_bi=thiet_bi))


def ghi(db: Session, nguoi: NguoiGoi, hanh_dong: str, loai: str | None = None,
        ma: str | None = None, **chi_tiet) -> None:
    """Them mot dong nhat ky vao phien hien tai. Nguoi goi tu commit."""
    _them(db, nguoi.user_id, ten_nguoi(db, nguoi), hanh_dong, loai, ma, chi_tiet)


def ghi_cho_tai_khoan(db: Session, user: User | None, email: str,
                      hanh_dong: str, **chi_tiet) -> None:
    """Cho dang nhap/dang ky: luc do chua co `NguoiGoi`, chi co tai khoan."""
    _them(db, user.id if user else None, email[:320], hanh_dong, "tai_khoan",
          user.id if user else None, chi_tiet)


def _nhan_doi_tuong(db: Session, dong: list[AuditLog]) -> dict[tuple[str, str], dict]:
    """Tra ten HIEN TAI cua doi tuong: ho so -> ten, ban quet -> so thu tu.

    Mot truy van cho moi loai doi tuong, khong phai mot truy van moi dong.
    """
    ma_hs = {x.target_id for x in dong if x.target_type == "ho_so" and x.target_id}
    ma_bq = {x.target_id for x in dong if x.target_type == "ban_quet" and x.target_id}
    nhan: dict[tuple[str, str], dict] = {}
    if ma_hs:
        for ma, ten in db.execute(select(Contact.id, Contact.full_name_original)
                                  .where(Contact.id.in_(ma_hs))):
            nhan[("ho_so", ma)] = {"ten": ten or "(chưa có tên)", "con": True}
    if ma_bq:
        for ma, so in db.execute(select(Scan.id, Scan.seq).where(Scan.id.in_(ma_bq))):
            nhan[("ban_quet", ma)] = {"ten": f"#{so}" if so else ma[:8], "con": True}
    return nhan


@router.get("/audit")
def doc_nhat_ky(db: Session = Depends(get_db),
                nguoi: NguoiGoi = Depends(nguoi_goi),
                limit: int = Query(default=200, ge=1, le=1000),
                action: str | None = Query(default=None, max_length=32),
                since: str | None = Query(default=None, max_length=40)):
    """Nhat ky hoat dong, moi nhat truoc.

    Quan tri thay cua moi nguoi; nguoi dung thuong chi thay cua minh - ke ca
    nhung lan dang nhap sai VAO tai khoan cua minh, de tu phat hien ai do
    dang do mat khau.
    """
    stmt = select(AuditLog)
    if not nguoi.thay_tat_ca:
        stmt = stmt.where(AuditLog.user_id == nguoi.user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    dong = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id)
                      .limit(limit)).all()
    nhan = _nhan_doi_tuong(db, dong)
    return {"items": [
        {"luc": x.created_at, "ai": x.actor, "hanh_dong": x.action,
         "loai": x.target_type, "ma": x.target_id, "chi_tiet": x.detail or {},
         "ip": x.ip, "thiet_bi": x.thiet_bi,
         "doi_tuong": (nhan.get((x.target_type, x.target_id))
                       or ({"ten": "(đã xoá)", "con": False}
                           if x.target_type in ("ho_so", "ban_quet") and x.target_id else None))}
        for x in dong
    ]}
