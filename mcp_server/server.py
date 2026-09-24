"""MCP server: cho tro ly AI dung kho danh thiep, TRONG PHAM VI MOT TAI KHOAN.

    python mcp_server/server.py

VI SAO PHAN QUYEN O DAY KHONG CAN THEM GI O BACKEND

Backend da co san phan quyen theo chu so huu tu Ngay 23: mot phieu JWT chi
mo ra duoc ban quet va ho so cua chinh nguoi do. Server nay khong tu nghi ra
mot he quyen thu hai - no chi DANG NHAP nhu mot nguoi dung binh thuong roi
goi dung nhung API ma giao dien web van goi.

Nghia la "phan quyen cho tung tai khoan" duoc thuc hien bang cach moi nguoi
KHAI TAI KHOAN CUA MINH trong cau hinh MCP cua ho. Khong co duong nao de
tro ly AI nhin vuot qua pham vi do, vi gioi han khong nam o server nay ma
nam o backend - noi da co bo test rieng chung minh.

    OCR_EMAIL + OCR_PASSWORD  -> dang nhap, thay dung phan cua nguoi do
                                 (`admin` thi thay tat ca, dung nhu tren web)
    OCR_API_KEY               -> che do HE THONG, thay tat ca. Chi dat khi
                                 that su muon mot tro ly khong gan voi ai.

ponytail: mat khau nam trong cau hinh MCP duoi dang van ban thuong - cung
muc tin cay voi khoa API von da nam trong `.env`. Muon hon the thi phai
them bang khoa-theo-nguoi-dung co thu hoi duoc o backend, va do la mot tinh
nang rieng chu khong phai mot dong sua o day.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.environ.get("OCR_API_URL", "http://127.0.0.1:8000").rstrip("/")
EMAIL = os.environ.get("OCR_EMAIL", "").strip()
PASSWORD = os.environ.get("OCR_PASSWORD", "")
API_KEY = os.environ.get("OCR_API_KEY", "").strip()

# Anh danh thiep lon nhat chap nhan doc tu dia. Trung voi gioi han cua
# backend, de loi hien ra o day - kem ten tep - thay vi hien ra duoi dang
# mot ma 413 tu may chu.
MAX_BYTES = 8 * 1024 * 1024
DUOI_ANH = {".jpg", ".jpeg", ".png"}

mcp = MCPServer(
    name="danh-thiep",
    instructions=(
        "Kho danh thiep da quet cua MOT tai khoan. Moi cong cu o day chi "
        "nhin thay phan du lieu cua tai khoan dang dang nhap; khong co cach "
        "nao doc du lieu cua nguoi khac. Goi `toi_la_ai` truoc khi lam gi "
        "khac neu can biet dang lam viec duoi danh tinh nao."
    ),
)


class LoiGoi(Exception):
    """Loi da duoc dien giai cho nguoi doc, khong phai vet ngan xep."""


_phieu: str | None = None


def _dang_nhap(client: httpx.Client) -> str:
    """Doi email + mat khau lay phieu. Nem `LoiGoi` kem cach sua."""
    if not EMAIL or not PASSWORD:
        raise LoiGoi(
            "Chua cau hinh tai khoan. Dat OCR_EMAIL va OCR_PASSWORD (hoac "
            "OCR_API_KEY neu muon che do he thong) trong cau hinh MCP."
        )
    r = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code == 401:
        raise LoiGoi(f"Sai email hoac mat khau cho tai khoan {EMAIL}.")
    if r.status_code != 200:
        raise LoiGoi(f"Dang nhap that bai ({r.status_code}): {r.text[:200]}")
    return r.json()["token"]


_khach: httpx.Client | None = None


def _client() -> httpx.Client:
    """Client dung chung cho ca tien trinh.

    Dung mot client chu khong mo moi loi goi mot cai: giu lai ket noi, va
    quan trong hon - day la CHO DUY NHAT tao ket noi ra ngoai, nen bo test
    thay duoc no bang mot `TestClient` tro vao backend that ma KHONG phai
    thay `_goi`. Thay `_goi` thi phan dang nhap, thu lai khi 401 va dien
    giai loi deu khong con duoc kiem - tuc bo test se kiem chinh no.
    """
    global _khach
    if _khach is None:
        _khach = httpx.Client(base_url=API_URL, timeout=60.0)
    return _khach


def _goi(method: str, path: str, **kwargs: Any) -> Any:
    """Goi backend kem danh tinh. Tu dang nhap lai dung MOT lan khi 401.

    VI SAO THU LAI: phieu song 12 tieng. Mot tro ly chay lien nhieu ngay se
    gap phieu het han giua chung, va neu khong tu lay phieu moi thi nguoi
    dung phai khoi dong lai server ma khong hieu vi sao.

    VI SAO CHI MOT LAN: sai mat khau cung tra 401. Thu lai mai la mot vong
    lap vo tan, va con dap vao bo chan do mat khau cua backend.
    """
    global _phieu

    client = _client()

    def dau() -> dict:
        if API_KEY:
            return {"X-API-Key": API_KEY}
        return {"Authorization": f"Bearer {_phieu}"} if _phieu else {}

    if not API_KEY and _phieu is None:
        _phieu = _dang_nhap(client)

    try:
        r = client.request(method, path, headers=dau(), **kwargs)
        if r.status_code == 401 and not API_KEY:
            _phieu = _dang_nhap(client)
            r = client.request(method, path, headers=dau(), **kwargs)
    except httpx.RequestError as loi:
        raise LoiGoi(
            f"Khong ket noi duoc backend tai {API_URL}. Backend da chay "
            f"chua? Chi tiet: {loi}"
        ) from loi

    if r.status_code == 404:
        raise LoiGoi("Khong tim thay. Ban ghi khong ton tai, hoac no thuoc "
                     "tai khoan khac.")
    if r.status_code >= 400:
        try:
            thong_bao = r.json()["error"]["message"]
        except Exception:
            thong_bao = r.text[:200]
        raise LoiGoi(f"Backend tu choi ({r.status_code}): {thong_bao}")
    return r


# --------------------------------------------------------------------------
# Cong cu
# --------------------------------------------------------------------------

@mcp.tool()
def toi_la_ai() -> dict:
    """Cho biet dang lam viec duoi danh tinh nao va thay duoc pham vi nao.

    Goi truoc khi lam viec khac neu can chac chan ve pham vi du lieu.
    """
    if API_KEY:
        return {
            "che_do": "he_thong",
            "pham_vi": "Thay TAT CA du lieu, khong gan voi tai khoan nao.",
        }
    d = _goi("GET", "/api/auth/me").json()
    nguoi = d.get("user") or {}
    la_quan_tri = d.get("role") == "admin"
    return {
        "che_do": "nguoi_dung",
        "email": nguoi.get("email"),
        "ten": nguoi.get("display_name"),
        "vai": d.get("role"),
        "pham_vi": ("Quan tri: thay du lieu cua moi nguoi." if la_quan_tri
                    else "Chi thay ban quet va ho so cua chinh tai khoan nay."),
    }


@mcp.tool()
def tim_ho_so(tu_khoa: str = "", so_luong: int = 20) -> dict:
    """Tim ho so doi tac theo ten, cong ty, email hoac so dien thoai.

    `tu_khoa` de trong thi liet ke ho so moi nhat. Chi tra ve ho so trong
    pham vi cua tai khoan dang dung.
    """
    so_luong = max(1, min(so_luong, 100))
    d = _goi("GET", "/api/contacts",
             params={"q": tu_khoa, "page": 1, "size": so_luong}).json()
    return {
        "tong": d.get("total", 0),
        "ho_so": [
            {"ma": x["id"], "ten": x["name"], "cong_ty": x["company"],
             "email": x["emails"], "dien_thoai": x["phones"]}
            for x in d.get("items", [])
        ],
    }


@mcp.tool()
def xem_ho_so(ma: str) -> dict:
    """Chi tiet mot ho so: moi truong da duyet, kem doanh nghiep va tra cuu.

    `ma` lay tu `tim_ho_so`. Ho so cua tai khoan khac se bao khong tim thay.
    """
    return _goi("GET", f"/api/contacts/{ma}").json()


@mcp.tool()
def danh_sach_ban_quet(so_luong: int = 12) -> dict:
    """Cac ban quet gan day va trang thai xu ly cua chung."""
    so_luong = max(1, min(so_luong, 50))
    d = _goi("GET", "/api/scans", params={"limit": so_luong}).json()
    return {"ban_quet": [
        {"ma": x["id"], "trang_thai": x["status"], "luc": x["created_at"],
         "ten": x.get("full_name"), "cong_ty": x.get("company_name"),
         "da_luu_ho_so": bool(x.get("contact_id"))}
        for x in d.get("items", [])
    ]}


@mcp.tool()
def quet_danh_thiep(duong_dan_anh: str) -> dict:
    """Gui mot anh danh thiep (JPEG/PNG) tu dia len de nhan dien.

    Tra ve ma ban quet ngay; viec nhan dien chay o phia backend. Dung
    `xem_ban_quet` de lay ket qua sau vai giay.
    """
    duong = Path(duong_dan_anh).expanduser()
    if not duong.is_file():
        raise LoiGoi(f"Khong thay tep: {duong}")
    if duong.suffix.lower() not in DUOI_ANH:
        raise LoiGoi(f"Chi nhan JPEG hoac PNG, tep nay la {duong.suffix!r}.")
    du_lieu = duong.read_bytes()
    if len(du_lieu) > MAX_BYTES:
        raise LoiGoi(f"Anh {len(du_lieu) / 1024 / 1024:.1f} MB, vuot gioi han "
                     f"{MAX_BYTES // 1024 // 1024} MB.")

    mime = "image/png" if duong.suffix.lower() == ".png" else "image/jpeg"
    d = _goi("POST", "/api/scans",
             files={"file": (duong.name, du_lieu, mime)}).json()
    return {"ma_ban_quet": d["id"], "trang_thai": d["status"],
            "ghi_chu": "Nhan dien dang chay. Goi `xem_ban_quet` sau vai giay."}


@mcp.tool()
def xem_ban_quet(ma: str) -> dict:
    """Ket qua nhan dien cua mot ban quet: van ban OCR va cac truong doc duoc.

    `truong` chi chua gia tri da qua buoc doi chieu voi van ban OCR - he
    thong khong bia them gia tri nao khong co tren tam the.
    """
    d = _goi("GET", f"/api/scans/{ma}").json()
    truong = ((d.get("draft") or {}).get("fields")) or {}
    return {
        "ma": d["id"],
        "trang_thai": d["status"],
        "van_ban_ocr": d.get("raw_text"),
        "la_gia_lap": d.get("is_mock", False),
        "truong": {ten: [x.get("value") for x in ds]
                   for ten, ds in truong.items() if ds},
        "loi": d.get("error_message"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
