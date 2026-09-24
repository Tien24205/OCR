"""MCP server: danh tinh, pham vi du lieu, va cach bao loi.

Bo test nay chay voi mot backend THAT (uvicorn trong tien trinh qua
TestClient) chu khong gia lap HTTP, vi dieu can chung minh nam o CHO GIAP
giua hai ben: server nay co that su mang theo danh tinh khong, va backend
co that su chan khong. Gia lap lop HTTP se lam ca hai cau hoi do bien mat.
"""

from __future__ import annotations

import io

import pytest

pytest.importorskip("mcp", reason="chua cai mcp (pip install -r mcp_server/requirements.txt)")

from PIL import Image                                         # noqa: E402
from sqlalchemy import create_engine                          # noqa: E402
from sqlalchemy.orm import sessionmaker                       # noqa: E402
from fastapi.testclient import TestClient                     # noqa: E402

import app.main as main                                       # noqa: E402
import app.pipeline as pipeline                               # noqa: E402
from app.config import Settings, get_settings                 # noqa: E402
from app.db import get_db                                     # noqa: E402
from app.models import Base                                   # noqa: E402

import server as mcp_server                                   # noqa: E402

MAT_KHAU = "matkhaudaiday12"


@pytest.fixture()
def he_thong(tmp_path, monkeypatch):
    """Backend that, va `server` duoc noi thang vao no qua `_client()`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'mcp.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    config = Settings(_env_file=None, image_dir=tmp_path / "anh",
                      ocr_provider="mock", extractor="heuristic")

    def csdl():
        with factory() as db:
            yield db

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(pipeline, "_sleep", lambda s: None)
    main.app.dependency_overrides[get_db] = csdl
    main.app.dependency_overrides[get_settings] = lambda: config
    main.app.dependency_overrides[main.get_session_factory] = lambda: factory

    with TestClient(main.app) as client:
        # NOI VAO BACKEND BANG CACH THAY `_client()`, khong thay `_goi`.
        #
        # `TestClient` cua Starlette la mot lop con cua `httpx.Client`, nen
        # `_goi` khong biet minh dang goi qua mang hay goi thang vao ung
        # dung. Nho vay toan bo phan dang nhap, gan phieu, thu lai khi 401
        # va dien giai loi deu duoc kiem THAT - thay `_goi` thi bo test se
        # di kiem chinh no, khong kiem duoc gi cua server.
        monkeypatch.setattr(mcp_server, "_client", lambda: client)
        monkeypatch.setattr(mcp_server, "_phieu", None)
        monkeypatch.setattr(mcp_server, "API_KEY", "")

        anh = io.BytesIO()
        Image.new("RGB", (60, 40), "white").save(anh, format="PNG")
        yield type("HeThong", (), {"client": client, "anh": anh.getvalue(),
                                   "tmp": tmp_path})()

    main.app.dependency_overrides.clear()
    engine.dispose()


def tao(he_thong, email: str) -> None:
    r = he_thong.client.post("/api/auth/register",
                             json={"email": email, "password": MAT_KHAU})
    assert r.status_code == 201, r.text


def dang_nhap_bang(monkeypatch, email: str, mat_khau: str = MAT_KHAU) -> None:
    """Doi danh tinh cua server, dung nhu doi cau hinh MCP cua mot nguoi."""
    monkeypatch.setattr(mcp_server, "EMAIL", email)
    monkeypatch.setattr(mcp_server, "PASSWORD", mat_khau)
    monkeypatch.setattr(mcp_server, "_phieu", None)


# --------------------------------------------------------------------------
# Danh tinh
# --------------------------------------------------------------------------

def test_khai_bao_du_sau_cong_cu():
    """Bot mot cong cu ma quen sua tai lieu thi tro ly goi vao cho trong."""
    import asyncio

    ten = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}

    assert ten == {"toi_la_ai", "tim_ho_so", "xem_ho_so",
                   "danh_sach_ban_quet", "quet_danh_thiep", "xem_ban_quet"}


def test_moi_cong_cu_deu_co_mo_ta():
    """Tro ly chon cong cu bang mo ta. Thieu mo ta la chon mo."""
    import asyncio

    for t in asyncio.run(mcp_server.mcp.list_tools()):
        assert t.description and len(t.description) > 30, t.name


def test_toi_la_ai_bao_dung_tai_khoan_va_pham_vi(he_thong, monkeypatch):
    tao(he_thong, "sep@cty.vn")
    tao(he_thong, "nv@cty.vn")
    dang_nhap_bang(monkeypatch, "nv@cty.vn")

    d = mcp_server.toi_la_ai()

    assert d["email"] == "nv@cty.vn"
    assert d["vai"] == "user"
    assert "chinh tai khoan nay" in d["pham_vi"]


def test_quan_tri_duoc_noi_ro_la_thay_tat_ca(he_thong, monkeypatch):
    tao(he_thong, "sep@cty.vn")                 # nguoi dau tien = admin
    dang_nhap_bang(monkeypatch, "sep@cty.vn")

    d = mcp_server.toi_la_ai()

    assert d["vai"] == "admin"
    assert "moi nguoi" in d["pham_vi"]


def test_sai_mat_khau_bao_ro_tai_khoan_nao(he_thong, monkeypatch):
    """Cau bao loi phai du de nguoi dung sua duoc cau hinh MCP cua ho."""
    tao(he_thong, "an@cty.vn")
    dang_nhap_bang(monkeypatch, "an@cty.vn", "saibetroi999")

    with pytest.raises(mcp_server.LoiGoi) as loi:
        mcp_server.toi_la_ai()

    assert "an@cty.vn" in str(loi.value)


# --------------------------------------------------------------------------
# Pham vi du lieu - ly do tinh nang nay ton tai
# --------------------------------------------------------------------------

def test_nguoi_nay_khong_thay_ban_quet_cua_nguoi_kia(he_thong, monkeypatch):
    tao(he_thong, "quantri@cty.vn")
    tao(he_thong, "an@cty.vn")
    tao(he_thong, "binh@cty.vn")

    dang_nhap_bang(monkeypatch, "an@cty.vn")
    cua_an = mcp_server.quet_danh_thiep(_anh(he_thong))["ma_ban_quet"]
    assert len(mcp_server.danh_sach_ban_quet()["ban_quet"]) == 1

    dang_nhap_bang(monkeypatch, "binh@cty.vn")
    assert mcp_server.danh_sach_ban_quet()["ban_quet"] == []
    with pytest.raises(mcp_server.LoiGoi):
        mcp_server.xem_ban_quet(cua_an)


def test_quan_tri_thay_ban_quet_cua_nhan_vien(he_thong, monkeypatch):
    tao(he_thong, "sep@cty.vn")
    tao(he_thong, "nv@cty.vn")

    dang_nhap_bang(monkeypatch, "nv@cty.vn")
    cua_nv = mcp_server.quet_danh_thiep(_anh(he_thong))["ma_ban_quet"]

    dang_nhap_bang(monkeypatch, "sep@cty.vn")
    assert mcp_server.xem_ban_quet(cua_nv)["ma"] == cua_nv


def test_tim_ho_so_khong_tra_ve_ho_so_cua_nguoi_khac(he_thong, monkeypatch):
    tao(he_thong, "quantri@cty.vn")
    tao(he_thong, "an@cty.vn")
    tao(he_thong, "binh@cty.vn")

    dang_nhap_bang(monkeypatch, "binh@cty.vn")

    assert mcp_server.tim_ho_so()["tong"] == 0


# --------------------------------------------------------------------------
# Doc anh tu dia
# --------------------------------------------------------------------------

def _anh(he_thong) -> str:
    duong = he_thong.tmp / "the.png"
    duong.write_bytes(he_thong.anh)
    return str(duong)


def test_tep_khong_ton_tai_bao_ro_duong_dan(he_thong, monkeypatch):
    tao(he_thong, "an@cty.vn")
    dang_nhap_bang(monkeypatch, "an@cty.vn")

    with pytest.raises(mcp_server.LoiGoi) as loi:
        mcp_server.quet_danh_thiep(str(he_thong.tmp / "khong-co.png"))

    assert "khong-co.png" in str(loi.value)


def test_tu_choi_dinh_dang_khong_phai_anh_truoc_khi_gui_len(he_thong, monkeypatch):
    """Chan o day thi nguoi dung thay ten tep sai, chu khong thay ma 400."""
    tao(he_thong, "an@cty.vn")
    dang_nhap_bang(monkeypatch, "an@cty.vn")
    tep = he_thong.tmp / "ho-so.pdf"
    tep.write_bytes(b"%PDF-1.4")

    with pytest.raises(mcp_server.LoiGoi) as loi:
        mcp_server.quet_danh_thiep(str(tep))

    assert ".pdf" in str(loi.value)


def test_anh_qua_lon_bi_chan_tai_cho(he_thong, monkeypatch):
    tao(he_thong, "an@cty.vn")
    dang_nhap_bang(monkeypatch, "an@cty.vn")
    to = he_thong.tmp / "to.png"
    to.write_bytes(b"x" * (mcp_server.MAX_BYTES + 1))

    with pytest.raises(mcp_server.LoiGoi) as loi:
        mcp_server.quet_danh_thiep(str(to))

    assert "MB" in str(loi.value)
