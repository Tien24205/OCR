"""Test xuat vCard 3.0.

Loi vCard khong bao gi ca - file van tai ve duoc, chi la danh ba nhap vao
sai hoac thieu. Nen moi quy tac dinh dang phai co test rieng.
"""

from __future__ import annotations

import pytest

from app.services import vcard


def row(**fields) -> dict:
    base = {"full_names": [], "company_names": [], "job_titles": [],
            "departments": [], "emails": [], "phones": [], "websites": [],
            "addresses": []}
    for name, values in fields.items():
        if name == "note":
            continue
        base[name] = [v if isinstance(v, dict) else {"value": v} for v in values]
    return {"id": "x", "note": fields.get("note", ""), "draft": {"fields": base}}


def card(**fields) -> str:
    return vcard.build_card(row(**fields))


def lines(text: str) -> list[str]:
    """Gop lai cac dong da bi gap de kiem tra noi dung."""
    out: list[str] = []
    for line in text.split("\r\n"):
        if line.startswith(" ") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


# --- Dinh dang bat buoc ---------------------------------------------------

def test_dung_CRLF_khong_phai_LF():
    """vCard yeu cau CRLF. Chi dung LF thi mot so ung dung khong doc duoc."""
    text = card(full_names=["Jane Doe"])
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")


def test_co_BOM_de_outlook_doc_dung_chu_nhat():
    data = vcard.build([row(full_names=["山田 太郎"])])
    assert data.startswith(b"\xef\xbb\xbf")


def test_mo_va_dong_the_dung_chuan():
    text = card(full_names=["Jane Doe"])
    assert lines(text)[0] == "BEGIN:VCARD"
    assert lines(text)[1] == "VERSION:3.0"
    assert lines(text)[-1] == "END:VCARD"


# --- Escape ky tu dac biet ------------------------------------------------

@pytest.mark.parametrize("raw,expect", [
    ("Smith, Jane", "Smith\\, Jane"),
    ("A;B", "A\\;B"),
    ("dong1\ndong2", "dong1\\ndong2"),
    ("C:\\path", "C:\\\\path"),
])
def test_ky_tu_dac_biet_duoc_escape(raw, expect):
    """Dau phay chua escape trong dia chi se lam hong toan bo the."""
    assert vcard.escape(raw) == expect


def test_escape_gach_cheo_truoc_roi_moi_den_dau_phay():
    """Sai thu tu thi se escape hai lan chinh dau vua them vao."""
    assert vcard.escape("a\\,b") == "a\\\\\\,b"


def test_ten_cong_ty_co_dau_phay_khong_lam_hong_the():
    text = card(company_names=["AOBA TECHNOLOGY CO., LTD."])
    org = next(x for x in lines(text) if x.startswith("ORG:"))
    assert org == "ORG:AOBA TECHNOLOGY CO.\\, LTD."


# --- Gap dong dai ---------------------------------------------------------

def test_gap_dong_dem_theo_octet_khong_phai_ky_tu():
    """Mot Kanji chiem 3 octet. Dem theo ky tu se tao dong vuot 75 octet va
    mot so ung dung se cat mat phan duoi."""
    long_ja = "東京都千代田区千代田" * 6
    text = card(addresses=[long_ja])
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 76, line


def test_gap_dong_khong_cat_giua_mot_ky_tu():
    """Cat giua 3 octet cua mot Kanji se tao byte hong."""
    text = card(addresses=["東京都千代田区千代田" * 6])
    for line in text.split("\r\n"):
        line.encode("utf-8").decode("utf-8")      # khong duoc nem loi


def test_gap_dong_ghep_lai_duoc_nguyen_ban():
    address = "東京都千代田区千代田" * 6
    text = card(addresses=[address])
    adr = next(x for x in lines(text) if x.startswith("ADR"))
    assert address in adr


# --- Anh xa truong --------------------------------------------------------

def test_nhan_so_dien_thoai_duoc_anh_xa():
    text = card(phones=[
        {"value": "03-1111-2222", "label": "tel"},
        {"value": "03-1111-2223", "label": "fax"},
        {"value": "090-3333-4444", "label": "mobile"},
    ])
    body = "\r\n".join(lines(text))
    assert "TEL;TYPE=WORK,VOICE:03-1111-2222" in body
    assert "TEL;TYPE=WORK,FAX:03-1111-2223" in body
    assert "TEL;TYPE=CELL,VOICE:090-3333-4444" in body


def test_so_may_le_khong_bi_mat():
    """vCard khong co truong may le rieng - ghi kem vao so."""
    text = card(phones=[{"value": "03-1111-2222", "label": "tel",
                         "extension": "102"}])
    assert "03-1111-2222 ext. 102" in "\r\n".join(lines(text))


def test_phong_ban_thanh_don_vi_con_cua_ORG():
    text = card(company_names=["株式会社青葉"], departments=["営業本部"])
    org = next(x for x in lines(text) if x.startswith("ORG:"))
    assert org == "ORG:株式会社青葉;営業本部"


def test_ho_ten_khong_bi_tach_ho_va_ten():
    """Khong co can cu de tach ho/ten tieng Nhat - dat nguyen ban de phan mem
    danh ba hien dung nhu tren the."""
    text = card(full_names=["山田 太郎"])
    assert "N:山田 太郎;;;;" in lines(text)
    assert "FN:山田 太郎" in lines(text)


def test_gia_tri_thu_hai_khong_bi_vut_di():
    """The song ngu co ten Kanji va ten romaji. vCard chi co mot FN, nhung gia
    tri con lai phai vao ghi chu chu khong duoc bien mat."""
    text = card(full_names=["山田 太郎", "Taro Yamada"],
                company_names=["株式会社青葉", "AOBA CO."])
    note = next(x for x in lines(text) if x.startswith("NOTE:"))
    assert "Taro Yamada" in note and "AOBA CO." in note


def test_ho_so_trong_van_tao_duoc_the_hop_le():
    """Khong co ten lan cong ty: van phai ra the doc duoc, khong duoc no."""
    text = card()
    assert lines(text)[0] == "BEGIN:VCARD"
    assert any(x.startswith("FN:") for x in lines(text))


def test_nhieu_ho_so_ghep_thanh_mot_file():
    data = vcard.build([row(full_names=["A"]), row(full_names=["B"])]).decode("utf-8-sig")
    assert data.count("BEGIN:VCARD") == 2
    assert data.count("END:VCARD") == 2
    assert data.endswith("\r\n")
