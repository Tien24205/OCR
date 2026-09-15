"""Kiem tra cong cu doi chieu so lieu tai lieu voi ma nguon.

VI SAO CO CONG CU DO: trong ba ngay, so test trong tai lieu phai sua tay nam
lan va lan nao cung bo sot it nhat mot tep. Lan chay dau tien cua cong cu con
tim ra mot cho khong ai de y: README ghi "20 endpoint" trong khi that ra la 24.
"""

from __future__ import annotations

import pytest

from scripts import check_docs


@pytest.fixture
def kho(tmp_path, monkeypatch):
    """Dung mot kho gia voi mot tai lieu song va mot bao cao lich su."""
    (tmp_path / "Document").mkdir()
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(check_docs, "LIVING_DOCS", ["song.md"])
    return tmp_path


THAT = {"test": 462, "endpoint": 24}


def test_bat_duoc_so_test_cu(kho):
    (kho / "song.md").write_text("Du an co 449 test tu dong.", encoding="utf-8")
    loi = check_docs.kiem_tra(THAT, sua=False)
    assert len(loi) == 1
    assert "ghi 449 test, thuc te 462" in loi[0]


def test_bat_duoc_so_endpoint_cu(kho):
    """Cho nay that su bi bo sot trong du an: README ghi 20, thuc te 24."""
    (kho / "song.md").write_text("mo ta day du 20 endpoint, bang ma loi",
                                 encoding="utf-8")
    loi = check_docs.kiem_tra(THAT, sua=False)
    assert "ghi 20 endpoint, thuc te 24" in loi[0]


def test_so_dung_thi_khong_bao(kho):
    (kho / "song.md").write_text("462 test, 24 endpoint.", encoding="utf-8")
    assert check_docs.kiem_tra(THAT, sua=False) == []


def test_fix_sua_dung_cho(kho):
    p = kho / "song.md"
    p.write_text("Co 449 test va 20 endpoint.", encoding="utf-8")

    check_docs.kiem_tra(THAT, sua=True)

    assert p.read_text(encoding="utf-8") == "Co 462 test va 24 endpoint."


def test_khong_dung_vao_bao_cao_lich_su(kho, monkeypatch):
    """Bao cao theo ngay la ANH CHUP mot thoi diem, khong phai tai lieu song.

    "116 test pass" trong bao cao Ngay 5 la su that cua hom do. Sua no thanh
    462 se bien mot ban ghi lich su thanh mot loi noi doi.
    """
    lich_su = kho / "Document" / "ngay-5.md"
    lich_su.write_text("**116 test pass**", encoding="utf-8")
    (kho / "song.md").write_text("462 test", encoding="utf-8")

    check_docs.kiem_tra(THAT, sua=True)

    assert lich_su.read_text(encoding="utf-8") == "**116 test pass**"


def test_khong_tu_sua_so_test_CHAY_QUA(kho):
    """LOI DA SUA cua chinh cong cu nay o lan chay dau.

    So test chay qua phu thuoc vao may: test can Tesseract tu bo qua neu chua
    cai. Mau cu bat ca "N pass" nen no doi "462 test - 461 pass, 1 tu bo qua"
    thanh "462 test - 462 pass, 1 tu bo qua" - mot cau tu mau thuan.
    """
    p = kho / "song.md"
    goc = "462 test - 461 pass, 1 tu bo qua"
    p.write_text(goc, encoding="utf-8")

    loi = check_docs.kiem_tra(THAT, sua=True)

    assert loi == [], f"khong duoc dung toi so 'pass': {loi}"
    assert p.read_text(encoding="utf-8") == goc


def test_bao_khi_thieu_tep(kho):
    loi = check_docs.kiem_tra(THAT, sua=False)
    assert "khong tim thay tep" in loi[0]
