"""Phan quyen theo chu so huu (Ngay 23).

VI SAO TAP TRUNG MOT TEP: phep kiem quyen rai rac la phep kiem quyen se bi
quen. Moi truy van ban quet va ho so deu di qua hai ham o day, nen khi them
mot endpoint moi, cau hoi "endpoint nay co loc theo chu khong" co DUNG MOT
cho de tra loi.

BA LOAI NGUOI GOI, va ly do ca ba deu can ton tai:

  he thong   - goi bang khoa API. Webhook va cong cu dong bo CRM khong phai
               mot nguoi, khong co ho so rieng, nen thay tat ca.
  nguoi dung - goi bang phieu JWT. Chi thay phan cua minh; `admin` thay tat ca.
  khong ai   - che do mo (khong khoa, khong bat buoc dang nhap). Day la cach
               ca du an nay chay tu Ngay 1 den Ngay 22, va la cach bo test
               chay. Thay tat ca.

VI SAO TRA 404 CHU KHONG 403 khi ban ghi thuoc nguoi khac: 403 xac nhan ban
ghi do CO THAT. Ke do ho so bang cach thu tung ma se dem duoc chinh xac so
ban quet cua ca he thong, va biet ma nao dang duoc dung - du khong doc noi
noi dung. 404 khong noi gi ca.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.errors import ApiError


@dataclass(frozen=True)
class NguoiGoi:
    """Ai dang goi. Dien boi middleware trong `auth.py`."""

    user_id: str | None = None
    role: str | None = None
    la_he_thong: bool = False

    @property
    def la_quan_tri(self) -> bool:
        return self.role == "admin"

    @property
    def thay_tat_ca(self) -> bool:
        """Dung khi nguoi goi khong bi gioi han theo chu so huu.

        `user_id is None` va khong phai he thong nghia la che do mo. Giu
        nhanh nay la ly do 596 test cu van xanh ma khong phai sua mot dong:
        khong co ai dang nhap thi khong co gi de loc.
        """
        return self.la_he_thong or self.la_quan_tri or self.user_id is None


def nguoi_goi(request: Request) -> NguoiGoi:
    """Dependency cua FastAPI. Doc ra tu `request.state`.

    `getattr` co gia tri mac dinh vi mot so duong chay khong di qua
    middleware - `TestClient` goi thang router trong vai bo test, va khi do
    `request.state` trong khong.
    """
    return NguoiGoi(
        user_id=getattr(request.state, "user_id", None),
        role=getattr(request.state, "role", None),
        la_he_thong=getattr(request.state, "la_he_thong", False),
    )


def loc_theo_chu(stmt, cot_owner, nguoi: NguoiGoi):
    """Them dieu kien chu so huu vao mot cau SELECT.

    Ban ghi khong co chu (`owner_id IS NULL`) HIEN VOI MOI NGUOI DUNG, khong
    chi voi chu cua no. Do la co y: nhung ban quet tao truoc Ngay 23 va
    nhung ban tao bang khoa API deu khong co chu, va giau chung di nghia la
    du lieu cu bien mat khong dau vet ngay khi bat dang nhap len.
    """
    if nguoi.thay_tat_ca:
        return stmt
    return stmt.where((cot_owner == nguoi.user_id) | (cot_owner.is_(None)))


def doc_duoc(owner_id: str | None, nguoi: NguoiGoi) -> bool:
    return nguoi.thay_tat_ca or owner_id is None or owner_id == nguoi.user_id


def doi_quyen(owner_id: str | None, nguoi: NguoiGoi, ten: str = "Bản ghi") -> None:
    """Nem 404 khi ban ghi thuoc nguoi khac. Xem ghi chu dau tep."""
    if not doc_duoc(owner_id, nguoi):
        raise ApiError("NOT_FOUND", f"Không tìm thấy {ten.lower()}.", 404)
