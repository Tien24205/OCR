"""Chia van ban OCR lam hai phan: da vao truong, va phan con lai.

VI SAO CAN: schema `CardExtraction` chi giu tam truong cua de bai. Danh thiep
that con in nhieu thu khac - khau hieu, ten chi nhanh, so giay phep, tai khoan
mang xa hoi, dong tieng Anh song song, ma so thue. Truoc day nhung dong do
duoc OCR doc ra roi bi bo im lang: nguoi dung nhin ban nhap va khong he biet
tren the con chu ma may da thay.

VI SAO KHONG HOI THEM MODEL: phan con lai duoc TRU RA tu chinh van ban OCR,
nen no khong the bia. Hoi Gemini "con gi nua khong" vua ton tien vua mo lai
dung canh cua ma grounding sinh ra de dong. O day phep tru la deterministic:
cai gi OCR doc duoc ma khong khop truong nao thi hien nguyen van, kem so dong.

GIOI HAN PHAI NOI RO: day la van ban THO theo dong, khong phai truong co ten.
No tra loi "may con thay gi nua", khong tra loi "cai do la gi".
"""

from __future__ import annotations

from app.services.extract.grounding import norm_for_match

# Nhan dong lien he tren the - bo di thi con lai moi la thong tin that. Phai
# co du bon ngon ngu cua de goc, khong thi "TEL" bi coi la mot phat hien moi.
NHAN_DONG = (
    "tel", "fax", "mobile", "phone", "email", "e-mail", "mail", "web", "url",
    "http", "https", "ext",
    "電話", "携帯", "内線", "ファックス",
    "전화", "휴대폰", "팩스", "내선",
    "电话", "手机", "传真", "分机",
    "〒",
)

# It hon hai ky tu co nghia thi khong dang bao: dau gach, dau cham, so trang.
TOI_THIEU = 2

# Mot dong chi duoc bao khi phan la chiem phan dang ke cua chinh no, HOAC du
# dai de tu no la mot thong tin.
#
# VI SAO CAN CA HAI VE: tren anh chup that, mot dong dia chi da vao truong con
# dinh vai ky tu rac ("Kon ;", "まこ", "に"). Chi dung nguong tuyet doi thi ba
# ky tu rac do du de bao ca dong dia chi len lan nua - chu cua truong nam o ca
# hai phan. Nhung dung MOT MINH ty le thi "部長" (hai ky tu, chiem 100% dong)
# se bi bo, ma do lai la thu that su chua duoc gan truong.
TY_LE_TOI_THIEU = 0.4
DU_DAI = 8


def _rut_gon(text: str | None) -> str:
    """Chuan hoa de SO SANH: NFKC, thuong hoa, bo khoang trang va dau cau.

    PHAI dung dung mot ham nay cho ca hai ve. Chuan hoa dong theo mot kieu va
    gia tri theo kieu khac thi "〒100-0001 東京都…" khong bao gio khop voi dia
    chi da trich xuat, va mot dia chi Nhat binh thuong bi bao la "phat hien
    moi" tren gan nhu moi tam the.
    """
    return "".join(ch for ch in norm_for_match(text) if ch.isalnum())


# Doan ngan hon nguong nay ma trung voi mot gia tri thi coi la trung ngau
# nhien - "co" nam trong ca "example.co.jp" lan mot khau hieu bat ky.
DOAN_TOI_THIEU = 6


def _tru_manh(con: str, v: str) -> str:
    """Tru nhung DOAN cua dong nam trong gia tri `v`, khong chi tru ca cum.

    VI SAO CAN: tren anh chup that, OCR chen nhieu vao GIUA mot truong. Dia
    chi bi cat lam ba dong, moi dong dinh them vai ky tu rac:

        "Kon ; 64E, Dabliwala Building, Shop No. 2, '"

    Tru ca cum khong an vi ca cum khong nam gon trong dong nao; ket qua la
    dia chi DA VAO TRUONG lai bi bao lai o phan con lai, tuc la cung mot chu
    nam o ca hai phan - dung cai ma viec chia hai phan phai tranh.
    """
    ket, i = [], 0
    while i < len(con):
        j = len(con)
        while j - i >= DOAN_TOI_THIEU and con[i:j] not in v:
            j -= 1
        if j - i >= DOAN_TOI_THIEU:
            i = j                      # ca doan nay thuoc gia tri -> bo
        else:
            ket.append(con[i])
            i += 1
    return "".join(ket)


def _con_lai(dong: str, gia_tri: list[str]) -> str:
    """Phan cua mot dong khong thuoc bat ky gia tri nao da trich xuat."""
    con = _rut_gon(dong)
    if not con:
        return ""
    # Tru tu gia tri DAI NHAT tro xuong: tru "example.co.jp" truoc thi phan
    # con lai khong con dinh manh cua "example.com" nam long trong do.
    for v in sorted(gia_tri, key=len, reverse=True):
        if v:
            con = _tru_manh(con.replace(v, ""), v)
    for nhan in NHAN_DONG:
        con = con.replace(_rut_gon(nhan), "")
    return con


def split_text(raw_text: str | None, draft: dict | None) -> list[dict]:
    """Cac dong OCR doc duoc nhung chua thuoc truong nao.

    Tra ve [{"line": <so dong tinh tu 1>, "text": <nguyen van>}]. Nguyen van
    giu dung nhu OCR tra ve - khong chuan hoa, vi day la bang chung.
    """
    if not raw_text:
        return []

    gia_tri = []
    for muc in ((draft or {}).get("fields") or {}).values():
        for item in muc if isinstance(muc, list) else []:
            gia_tri.append(_rut_gon(
                item.get("value") if isinstance(item, dict) else item))
    gia_tri = [v for v in gia_tri if v]

    ket_qua = []
    for so_dong, dong in enumerate(raw_text.splitlines(), start=1):
        ca_dong = _rut_gon(dong)
        con = _con_lai(dong, gia_tri)
        if len(con) < TOI_THIEU:
            continue
        # Dong bi OCR cat lam doi cua mot dia chi dai van la phan da thuoc
        # truong, du mot minh no khong khop gia tri nao.
        if any(con in v for v in gia_tri):
            continue
        if len(con) < DU_DAI and len(con) / len(ca_dong) < TY_LE_TOI_THIEU:
            continue
        ket_qua.append({"line": so_dong, "text": dong.strip()})
    return ket_qua
