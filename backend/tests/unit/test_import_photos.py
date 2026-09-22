"""Kiem tra cong cu dua anh chup that vao datasets/.

VI SAO CAN TEST NAY: hai loi nay da xay ra that (22/09) va khong cai nao lo ra
luc chay - chung chi lo ra o bao cao chat luong, duoi dang mot con so xau ma
khong ai giai thich duoc:

  1. Thu tu anh lech mot nac -> moi tam bi cham diem theo nhan cua the khac.
  2. Anh chup ca trang chua cat -> mot tam co chu cua ba the.
"""

from __future__ import annotations

import os

import pytest
from PIL import Image, ImageDraw

from scripts import import_photos as m


def anh(path, text="Tanaka", mau="white", canh=(2400, 1800)):
    im = Image.new("RGB", canh, mau)
    ImageDraw.Draw(im).text((50, 50), text, fill="black")
    im.save(path)
    return path


def test_thu_tu_theo_luc_bam_may_chu_khong_theo_ten_file(tmp_path):
    """Ten file cua may anh sap xep dung, nhung khong phai may nao cung the.

    Lech mot nac la ca 10 the bi cham diem theo nhan cua the ben canh - bo so
    do van ra day du va van trong nhu that.
    """
    sau = anh(tmp_path / "AAA.jpg")
    truoc = anh(tmp_path / "ZZZ.jpg")
    os.utime(truoc, (1_000_000, 1_000_000))
    os.utime(sau, (2_000_000, 2_000_000))

    theo_thu_tu = sorted(tmp_path.glob("*.jpg"), key=m.thoi_diem_chup)
    assert [f.name for f in theo_thu_tu] == ["ZZZ.jpg", "AAA.jpg"]


def test_anh_be_bi_chan(tmp_path):
    nho = anh(tmp_path / "nho.jpg", canh=(800, 600))
    loi, _ = m.kiem_mot_tam(nho, {"full_name": "X"}, doi_chieu=False)
    assert loi and "800x600" in loi[0]


def test_ma_the_con_nhin_thay_nghia_la_trang_chua_cat(monkeypatch, tmp_path):
    """The cat dung thi ma the bi cat mat - no nam ngoai vien the.

    Con doc duoc `ja-02` nghia la trong khung hinh van con le trang, va rat co
    the con ca the ben canh.
    """
    monkeypatch.setattr(m, "doc_the", lambda path: "ja-02 Tanaka Taro Aoba")
    loi, _ = m.kiem_mot_tam(anh(tmp_path / "a.jpg"), {"full_name": "Tanaka Taro"},
                            doi_chieu=True)
    assert any("chua cat" in x for x in loi)


def test_the_cua_bo_khac_bi_chan(monkeypatch, tmp_path):
    """Loi da xay ra 22/09: in nham bo the cu, khong ten nao co trong nhan."""
    monkeypatch.setattr(m, "doc_the", lambda path: "Marcus Feld Halbrook Logistics")
    loi, _ = m.kiem_mot_tam(anh(tmp_path / "a.jpg"),
                            {"full_name": "山田 太郎", "company_name": "株式会社青葉テクノロジー"},
                            doi_chieu=True)
    assert any("khong thay" in x for x in loi)


def test_dung_the_thi_khong_bao_gi(monkeypatch, tmp_path):
    """Khoang trang khong duoc tinh: nhan ghi `山田 太郎`, OCR tra `山田太郎`."""
    monkeypatch.setattr(m, "doc_the", lambda path: "山田太郎 株式会社青葉テクノロジー 03-5432-1098")
    loi, _ = m.kiem_mot_tam(anh(tmp_path / "a.jpg"),
                            {"full_name": "山田 太郎", "company_name": "株式会社青葉テクノロジー"},
                            doi_chieu=True)
    assert loi == []


@pytest.mark.parametrize("split,lang", [("dev", "ja"), ("eval", "zh")])
def test_nhan_doc_dung_10_the_theo_dung_thu_tu(split, lang):
    rows = m.nhan_cua(split, lang)
    assert [r["image"] for r in rows] == [f"{split}/{lang}/{i:03d}.jpg" for i in range(1, 11)]
