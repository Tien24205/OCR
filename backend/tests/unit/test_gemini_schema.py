"""Schema `CardExtraction` co duoc Gemini chap nhan khong - chuan bi Ngay 15.

DAY LA AN SO LON NHAT CUA DU AN. Schema nay chua tung duoc mot model nao chap
nhan lan nao, va neu no sai thi toan bo tang trich xuat khong chay - phat hien
ra dieu do bang cach dot tien goi API la cach dat nhat.

CACH TRA LOI MA KHONG CAN GOI API: SDK google-genai chuyen pydantic model sang
schema cua Gemini bang `_transformers.t_schema()` TRUOC khi gui di. Chay dung
phep chuyen doi do la biet schema co hop le hay khong.

Con lai mot phan khong kiem duoc offline: may chu co the tu choi vi ly do khac
(gioi han do sau, so luong truong). Nhung phan lon rui ro nam o buoc chuyen doi.
"""

from __future__ import annotations

import pytest
from google.genai import _transformers as transformers
from google.genai import types

from app.services.extract.base import CardExtraction
from app.services.extract.gemini import SYSTEM_INSTRUCTION


@pytest.fixture(scope="module")
def schema() -> types.Schema:
    return transformers.t_schema(None, CardExtraction)


def test_schema_chuyen_doi_duoc(schema):
    """Neu SDK khong chuyen doi duoc, loi se xay ra o moi lan goi that."""
    assert schema is not None
    assert schema.type == types.Type.OBJECT
    assert schema.properties


def test_du_tam_truong_va_dung_kieu(schema):
    expected = {
        "full_names", "company_names", "job_titles", "departments",
        "emails", "phones", "websites", "addresses",
    }
    assert expected <= set(schema.properties)

    for name in expected:
        prop = schema.properties[name]
        assert prop.type == types.Type.ARRAY, name
        assert prop.items.type == types.Type.OBJECT, name

    assert schema.properties["card_language"].type == types.Type.STRING


def test_khong_co_kieu_nullable_hay_anyOf(schema):
    """DAY LA QUY TAC THIET KE, khong phai chi tiet ngau nhien.

    Moi truong deu la DANH SACH thay vi `X | None`. Hai ly do:

      - Nghiep vu: danh thiep Nhat thuong in ten va ten cong ty bang hai he
        chu (Kanji + romaji). Ca hai deu that, khong phai mot dung mot sai.
      - Ky thuat: JSON Schema cua Gemini xu ly danh sach on dinh hon kieu
        nullable; `anyOf` la nguon loi kho chan doan.

    Neu ai do them mot truong `Optional[...]`, test nay do ngay thay vi de lo
    ra thanh loi 400 luc chay that.
    """
    raw = schema.model_dump_json(exclude_none=True)
    assert "nullable" not in raw
    assert "anyOf" not in raw and "any_of" not in raw


def test_so_dien_thoai_giu_du_nhan_va_may_le(schema):
    phones = schema.properties["phones"].items.properties
    assert {"value", "source_text", "label", "extension"} <= set(phones)
    # May le phai la CHUOI: co the co so 0 dau.
    assert phones["extension"].type == types.Type.STRING


def test_moi_gia_tri_deu_co_source_text(schema):
    """`source_text` la co so cua buoc doi chieu chong bia du lieu. Thieu no o
    bat ky truong nao thi truong do khong kiem chung duoc."""
    for name, prop in schema.properties.items():
        if prop.type != types.Type.ARRAY:
            continue
        assert "source_text" in prop.items.properties, name


def test_schema_khong_long_qua_sau(schema):
    """Gemini gioi han do sau cua schema. Cau truc hien tai la
    object -> array -> object -> string, tuc 3 tang."""
    def depth(node, level=1):
        if node.properties:
            return max(depth(p, level + 1) for p in node.properties.values())
        if node.items is not None:
            return depth(node.items, level + 1)
        return level

    assert depth(schema) <= 4


# --- Cau lenh he thong ----------------------------------------------------

def test_cau_lenh_cam_bia_du_lieu():
    """Cau lenh khong phai bao dam - chot chan la `grounding.py`. Nhung no van
    phai noi ro yeu cau, vi no giam ty le bia ngay tu dau."""
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "khong bia" in lowered or "khong suy doan" in lowered


def test_cau_lenh_coi_noi_dung_tren_anh_la_du_lieu():
    """Chu tren danh thiep la dau vao khong dang tin. Neu the co cau chu trong
    giong menh lenh, model phai bo qua."""
    assert "chi dan" in SYSTEM_INSTRUCTION or "DU LIEU" in SYSTEM_INSTRUCTION


def test_cau_lenh_cam_phien_am_va_dao_ho_ten():
    """Hai quy tac du lieu bat buoc cua de bai."""
    assert "romaji" in SYSTEM_INSTRUCTION.lower()
    assert "dao thu tu" in SYSTEM_INSTRUCTION.lower()


def test_cau_lenh_cam_tu_them_ma_quoc_gia():
    assert "+81" in SYSTEM_INSTRUCTION


def test_prompt_lan_hai_khac_lan_dau():
    """Tang agentic doc lai bang "prompt khac" khi thieu ten/cong ty. Neu hai
    prompt giong nhau thi lan doc lai chi ton tien ma khong doi ket qua."""
    from app.services.extract import gemini
    import inspect

    source = inspect.getsource(gemini.GeminiExtractor._extract)
    assert "SECOND PASS" in source
    assert "retry" in source
