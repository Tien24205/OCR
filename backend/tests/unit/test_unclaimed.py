"""Tach van ban OCR lam hai phan: da vao truong, va phan con lai.

Phep tru nay phai DUNG THEO CA HAI HUONG:
  - Bo sot phan con lai  -> nguoi dung van khong biet tren the con chu gi.
  - Bao thua            -> moi the deu bao "con 12 dong chua xu ly", nhin mot
                            lan roi khong ai nhin nua, tinh nang thanh vo dung.
"""

from __future__ import annotations

from app.services.extract.unclaimed import split_text


def draft(**fields) -> dict:
    return {"fields": {k: [{"value": v} for v in (vs if isinstance(vs, list) else [vs])]
                       for k, vs in fields.items()}}


def texts(rows) -> list[str]:
    return [r["text"] for r in rows]


def test_gia_tri_da_vao_truong_thi_khong_bao_lai():
    raw = "株式会社青葉テクノロジー\n山田 太郎\ntaro@example.co.jp"
    con_lai = split_text(raw, draft(company_names="株式会社青葉テクノロジー",
                                    full_names="山田 太郎",
                                    emails="taro@example.co.jp"))
    assert con_lai == []


def test_chu_khong_thuoc_truong_nao_duoc_bao_kem_so_dong():
    raw = ("株式会社青葉テクノロジー\n"
           "創業1950年 — 信頼の技術\n"
           "山田 太郎\n"
           "登録番号 T1234567890123")
    con_lai = split_text(raw, draft(company_names="株式会社青葉テクノロジー",
                                    full_names="山田 太郎"))
    assert texts(con_lai) == ["創業1950年 — 信頼の技術", "登録番号 T1234567890123"]
    assert [r["line"] for r in con_lai] == [2, 4]


def test_nhan_dong_lien_he_khong_bi_coi_la_phat_hien_moi():
    """Bo so dien thoai ra thi con lai chu "TEL:" - do la nhan in san, khong
    phai thong tin. Bao no len la nhieu, va nhieu thi nguoi dung ngung doc."""
    raw = "TEL: 03-5432-1098\nFAX: 03-5432-1099\n電話: 06-6345-2100"
    con_lai = split_text(raw, draft(phones=["03-5432-1098", "03-5432-1099",
                                            "06-6345-2100"]))
    assert con_lai == []


def test_nhan_bon_ngon_ngu_deu_duoc_nhan_ra():
    raw = "휴대폰: 010-1234-5678\n手机: 137-3344-5566\n携帯: 090-1234-5678"
    con_lai = split_text(raw, draft(phones=["010-1234-5678", "137-3344-5566",
                                            "090-1234-5678"]))
    assert con_lai == []


def test_dong_bi_OCR_cat_doi_van_tinh_la_da_thuoc_truong():
    """Dia chi dai hay bi cat lam hai dong. Moi manh khong khop gia tri nao,
    nhung ca hai deu la phan cua mot truong da co - bao len la bao nham."""
    raw = "〒100-0001 東京都千代田区千代田1-2-3\n青葉ビル7F"
    con_lai = split_text(raw, draft(
        addresses="〒100-0001 東京都千代田区千代田1-2-3 青葉ビル7F"))
    assert con_lai == []


def test_truong_bi_nhieu_OCR_chen_vao_giua_van_khong_bi_bao_lai():
    """Anh chup that: OCR chen rac vao giua dia chi va cat no lam ba dong.
    Neu chi tru ca cum thi ca ba dong deu bi bao la "phat hien moi", tuc la
    dia chi nam o CA HAI phan - dung cai ma viec chia hai phan phai tranh."""
    raw = ("Kon ; 64E, Dabliwala Building, Shop No. 2, ‘\n"
           "a 。 Ground Floor, Old Hanuman Lane, Kalbadevi Road, に\n"
           "GST NO 27AHFPG2712H1ZP")
    con_lai = split_text(raw, draft(addresses=(
        "64E, Dabliwala Building, Shop No. 2, Ground Floor, "
        "Old Hanuman Lane, Kalbadevi Road, Mumbai 400 002")))
    # Chi con dong GST - thu that su khong thuoc truong nao.
    assert texts(con_lai) == ["GST NO 27AHFPG2712H1ZP"]


def test_trung_mot_doan_ngan_khong_bi_coi_la_da_thuoc_truong():
    """"co" nam trong "example.co.jp" lan trong hang nghin chu khac. Tru theo
    doan qua ngan se nuot mat chu that."""
    con_lai = split_text("Since 1950 — cong ty gia dinh",
                         draft(websites="https://www.example.co.jp"))
    assert texts(con_lai) == ["Since 1950 — cong ty gia dinh"]


def test_chu_full_width_khop_voi_gia_tri_half_width():
    """The Nhat in "ＴＥＬ：０３..." - khong chuan hoa NFKC thi dong nay bi bao
    la phat hien moi tren gan nhu moi the Nhat."""
    con_lai = split_text("ＴＥＬ：０３-５４３２-１０９８",
                         draft(phones="03-5432-1098"))
    assert con_lai == []


def test_dau_cau_va_gach_ngang_khong_dang_bao():
    con_lai = split_text("山田 太郎\n---\n・\n.", draft(full_names="山田 太郎"))
    assert con_lai == []


def test_khong_co_ban_nhap_thi_moi_dong_co_nghia_deu_la_phan_con_lai():
    """Ban quet that bai hoac chua trich xuat: van phai cho nguoi dung thay
    may doc duoc gi, thay vi mot man hinh trong."""
    con_lai = split_text("株式会社青葉\n山田 太郎", None)
    assert texts(con_lai) == ["株式会社青葉", "山田 太郎"]


def test_khong_co_van_ban_thi_tra_ve_rong():
    assert split_text(None, draft(full_names="山田 太郎")) == []
    assert split_text("", None) == []
