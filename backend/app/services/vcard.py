"""Xuat ho so ra vCard 3.0 (.vcf) - nhap thang vao dien thoai hoac Outlook.

VI SAO vCard CHU KHONG PHAI CSV: CSV chi dung duoc khi co nguoi ngoi map cot.
vCard la dinh dang danh ba pho thong - mo file .vcf tren dien thoai la danh ba
tu nhan, khong can buoc trung gian nao. Day la khac biet giua "xuat duoc du
lieu" va "dung duoc ngay".

VI SAO 3.0 CHU KHONG PHAI 4.0: 3.0 duoc iOS, Android va Outlook doc duoc het.
4.0 moi hon nhung Outlook ho tro khong day du.

BA CHO DE SAI, deu duoc xu ly o day:

  1. Ky tu dac biet. Dau phay, cham phay, xuong dong trong gia tri PHAI duoc
     escape, neu khong file se hong o dung the co dau phay trong dia chi.
  2. Xuong dong. vCard yeu cau CRLF, khong phai LF.
  3. Chu Nhat. Phai la UTF-8; them BOM de Outlook tren Windows khong doc sai -
     dung ly do da gap o buoc xuat CSV.
"""

from __future__ import annotations

import re

# Thu tu uu tien khi the co nhieu ten/cong ty (vi du ban dia + romaji).
# Gia tri dau tien la chinh; cac gia tri con lai thanh dong ghi chu.
LABEL_MAP = {"tel": "WORK,VOICE", "fax": "WORK,FAX", "mobile": "CELL,VOICE"}


def escape(value: str) -> str:
    """Escape theo RFC 2426.

    Thu tu quan trong: phai escape dau gach cheo nguoc TRUOC, neu khong se
    escape hai lan nhung dau vua them vao.
    """
    return (value.replace("\\", "\\\\")
                 .replace("\n", "\\n")
                 .replace("\r", "")
                 .replace(",", "\\,")
                 .replace(";", "\\;"))


def fold(line: str) -> str:
    """Gap dong dai theo RFC 2426: toi da 75 octet, dong tiep bat dau bang dau cach.

    Dem theo OCTET chu khong phai ky tu - mot chu Kanji chiem 3 octet trong
    UTF-8, nen dem theo ky tu se tao ra dong vuot gioi han.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    parts, current = [], b""
    for char in line:
        chunk = char.encode("utf-8")
        # Dong dau duoc 75 octet, cac dong sau con 74 vi da mat 1 cho dau cach.
        limit = 75 if not parts else 74
        if len(current) + len(chunk) > limit:
            parts.append(current.decode("utf-8"))
            current = b""
        current += chunk
    if current:
        parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _values(row: dict, field: str) -> list[str]:
    return [item["value"] for item in row["draft"]["fields"].get(field, [])
            if item.get("value")]


def _items(row: dict, field: str) -> list[dict]:
    return [item for item in row["draft"]["fields"].get(field, [])
            if item.get("value")]


def build_card(row: dict) -> str:
    """Dung mot the vCard tu mot ho so."""
    names = _values(row, "full_names")
    companies = _values(row, "company_names")
    titles = _values(row, "job_titles")
    departments = _values(row, "departments")

    lines = ["BEGIN:VCARD", "VERSION:3.0"]

    display = names[0] if names else (companies[0] if companies else "(khong ten)")
    lines.append(f"FN:{escape(display)}")
    # N yeu cau 5 phan: ho;ten;dem;tien to;hau to. Khong tach ho/ten vi khong
    # co can cu - dat toan bo vao o "ho" de phan mem danh ba hien dung nguyen ban.
    lines.append(f"N:{escape(display)};;;;")

    if companies:
        # ORG cho phep don vi con: "Cong ty;Phong ban"
        org = escape(companies[0])
        if departments:
            org += ";" + escape(departments[0])
        lines.append(f"ORG:{org}")
    if titles:
        lines.append(f"TITLE:{escape(titles[0])}")

    for email in _values(row, "emails"):
        lines.append(f"EMAIL;TYPE=INTERNET,WORK:{escape(email)}")

    for phone in _items(row, "phones"):
        kind = LABEL_MAP.get(phone.get("label") or "", "WORK,VOICE")
        value = phone["value"]
        if phone.get("extension"):
            # vCard khong co truong may le rieng; quy uoc pho bien la ghi kem.
            value += f" ext. {phone['extension']}"
        lines.append(f"TEL;TYPE={kind}:{escape(value)}")

    for site in _values(row, "websites"):
        lines.append(f"URL:{escape(site)}")

    for address in _values(row, "addresses"):
        # ADR co 7 phan; khong tach duoc dia chi Nhat mot cach dang tin nen dat
        # nguyen ban vao o "duong pho" va giu ban goc o LABEL.
        one_line = re.sub(r"\s*\n\s*", " ", address).strip()
        lines.append(f"ADR;TYPE=WORK:;;{escape(one_line)};;;;")

    # Gia tri thu hai tro di (ten romaji, ten cong ty Latin) khong mat di -
    # dua vao ghi chu de nguoi dung van thay.
    extras = []
    for field, label in (("full_names", "Tên khác"), ("company_names", "Công ty khác")):
        for value in _values(row, field)[1:]:
            extras.append(f"{label}: {value}")
    if row.get("note"):
        extras.append(row["note"])
    if extras:
        lines.append(f"NOTE:{escape(' | '.join(extras))}")

    lines.append("END:VCARD")
    return "\r\n".join(fold(line) for line in lines)


def build(rows: list[dict]) -> bytes:
    """Ghep nhieu ho so thanh mot file .vcf.

    BOM UTF-8: khong co no thi Outlook tren Windows doc sai chu Nhat - dung
    van de da gap o buoc xuat CSV.
    """
    body = "\r\n".join(build_card(row) for row in rows)
    return b"\xef\xbb\xbf" + (body + "\r\n").encode("utf-8")
