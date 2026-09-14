"""Bo trich xuat du phong bang regex - khong can mang, khong ton tien.

VI SAO CAN: Ngay 2 la ngay rui ro cao nhat. Neu khong lay duoc quyen truy
cap Gemini, ca lich trinh dung lai. Bo nay dam bao luong chinh van chay:
email, dien thoai va website deu co dinh dang du chat che de bat bang regex.

GIOI HAN PHAI NOI RO: no doan ten nguoi va chuc danh bang tu dien nho, do
chinh xac thap hon Gemini nhieu. Day la duong lui, khong phai phuong an
tuong duong. Bao cao Ngay 9 phai ghi ro dung bo trich xuat nao.
"""

from __future__ import annotations

import re

from app.services import languages
from app.services.extract.base import CardExtraction, ExtractedValue, PhoneValue

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(
    r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/[^\s]*)?", re.IGNORECASE
)
# So dien thoai: it nhat 9 chu so, cho phep +, dau cach, gach, ngoac.
_PHONE = re.compile(r"(?:\+?\d[\d\-\s()]{7,}\d)")
_EXTENSION = re.compile(
    r"(?:内線|内|내선|分机|分機|ext\.?|EXT\.?)"
    r"\s*[:：]?\s*(\d{1,6})", re.IGNORECASE)

_COMPANY_MARKERS = (
    # Nhat
    "株式会社", "有限会社", "合同会社", "一般社団法人", "公益財団法人",
    # Han
    "주식회사", "(주)", "유한회사", "재단법인",
    # Trung
    "有限公司", "股份有限公司", "集团", "集團", "企業", "企业",
    # Anh
    "Inc.", "Inc", "Ltd.", "Ltd", "LLC", "Corp.", "Corp",
    "Corporation", "Company", "Co.", "K.K.", "GmbH", "Pte",
)
_TITLE_MARKERS = (
    # Nhat
    "代表取締役", "取締役", "部長", "課長", "係長", "主任", "社長", "専務",
    # Han
    "대표이사", "부장", "과장", "차장", "팀장", "사장", "이사",
    # Trung
    "总经理", "總經理", "经理", "經理", "主管", "总监", "總監", "董事长",
    # Anh
    "CEO", "CTO", "CFO", "COO", "President", "Director", "Manager",
    "Engineer", "Head of", "Lead", "Chief", "Officer", "Senior",
)
_DEPT_MARKERS = (
    "事業部", "営業部", "開発部", "技術部", "部", "課", "室",           # Nhat
    "영업부", "개발부", "기술부", "본부",                               # Han
    "事业部", "营销部", "研发部", "技术部",                             # Trung
    "Division", "Department", "Sales", "Marketing", "Engineering",    # Anh
)

# Ten mien cua dich vu email cong cong: KHONG duoc coi la website doanh nghiep.
_FREE_MAIL = frozenset({
    "gmail.com", "yahoo.com", "yahoo.co.jp", "outlook.com", "hotmail.com",
    "icloud.com", "docomo.ne.jp", "ezweb.ne.jp", "softbank.ne.jp", "me.com",
})


def _label_for(line: str) -> str:
    low = line.lower()
    if "fax" in low or "ファックス" in line or "ＦＡＸ" in line:
        return "fax"
    if any(k in low for k in ("mobile", "cell", "携帯")) or "090" in line or "080" in line:
        return "mobile"
    return "tel"


class HeuristicExtractor:
    name = "heuristic"

    def extract(self, image: bytes, mime: str, raw_text: str) -> CardExtraction:
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        result = CardExtraction(card_language=self._guess_language(raw_text))

        seen_emails: set[str] = set()
        seen_phones: set[str] = set()
        seen_urls: set[str] = set()

        for line in lines:
            for match in _EMAIL.findall(line):
                if match.lower() not in seen_emails:
                    seen_emails.add(match.lower())
                    result.emails.append(
                        ExtractedValue(value=match, source_text=line)
                    )

            for match in _PHONE.findall(line):
                digits = re.sub(r"\D", "", match)
                # Duoi 9 chu so thuong la ma buu dien hoac so nha, khong phai
                # so dien thoai.
                if len(digits) < 9 or digits in seen_phones:
                    continue
                seen_phones.add(digits)
                ext_match = _EXTENSION.search(line)
                result.phones.append(
                    PhoneValue(
                        value=match.strip(),
                        source_text=line,
                        label=_label_for(line),
                        extension=ext_match.group(1) if ext_match else "",
                    )
                )

            # Go email ra khoi dong TRUOC khi quet URL. Neu khong,
            # "taro@example.co.jp" bi regex URL cat thanh hai "URL" gia la
            # "taro" va "example.co.jp", va ten mien gia do con chiem cho cua
            # website that o dong khac (vi da nam trong `seen_urls`).
            line_without_emails = _EMAIL.sub(" ", line)
            for match in _URL.findall(line_without_emails):
                candidate = match.strip().rstrip(".,;")
                host = re.sub(r"^https?://", "", candidate, flags=re.I).split("/")[0]
                host = host.removeprefix("www.").lower()
                if host in _FREE_MAIL or "." not in host or host in seen_urls:
                    continue
                seen_urls.add(host)
                result.websites.append(
                    ExtractedValue(value=candidate, source_text=line)
                )

            if any(marker in line for marker in _COMPANY_MARKERS):
                result.company_names.append(
                    ExtractedValue(value=line, source_text=line)
                )
            elif any(marker in line for marker in _TITLE_MARKERS):
                result.job_titles.append(ExtractedValue(value=line, source_text=line))
            elif any(marker in line for marker in _DEPT_MARKERS):
                result.departments.append(ExtractedValue(value=line, source_text=line))

        return result

    @staticmethod
    def _guess_language(text: str) -> str:
        # Quy tac nam o `languages.py`. Ban cu chi phan biet duoc Nhat voi Anh
        # va goi moi chu Han la "ja", nen the tieng Trung bi gan nhan sai.
        return languages.guess_language(text)
