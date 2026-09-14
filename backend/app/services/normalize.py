"""Formatting only: preserve raw values, scripts and absent fields."""
from copy import deepcopy
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

FIELDS = ("full_names", "company_names", "job_titles", "departments", "emails", "phones", "websites", "addresses")
FREE_EMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.jp", "ymail.com",
                              "outlook.com", "outlook.jp", "hotmail.com", "hotmail.co.jp", "live.com", "icloud.com"})
EMAIL = re.compile(r"[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}")
EXTENSION = re.compile(r"\s*\(?\s*(?:内線|ext\.?|extension)\s*[:：]?\s*([0-9０-９]+)\s*\)?\s*$", re.IGNORECASE)


def match_key(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def digits(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", value) if char in "0123456789")


def normalize_item(field: str, item: dict) -> dict:
    result = deepcopy(item)
    raw = item["value"]
    result.setdefault("value_raw", raw)
    value = raw.strip()
    issues = []
    if field in ("full_names", "company_names", "job_titles", "departments"):
        value = " ".join(value.split())
    elif field == "emails":
        local, separator, domain = value.rpartition("@")
        if separator:
            value = local + "@" + domain.lower()
        if not EMAIL.fullmatch(value):
            issues.append("Email chưa đúng cấu trúc; cần đối chiếu lại.")
    elif field == "phones":
        extension = item.get("extension", "").strip()
        found = EXTENSION.search(value)
        if found:
            if extension and digits(extension) != digits(found.group(1)):
                issues.append("Máy lẻ trong số điện thoại khác ô máy lẻ.")
            else:
                extension = found.group(1)
                value = value[:found.start()].rstrip()
        normalized_extension = unicodedata.normalize("NFKC", extension)
        if normalized_extension and not re.fullmatch(r"[0-9]+", normalized_extension):
            issues.append("Máy lẻ chỉ nên chứa chữ số.")
        result["extension"] = normalized_extension
        result["value_digits"] = digits(value[:found.start()] if found and issues else value)
        if not 7 <= len(result["value_digits"]) <= 15:
            issues.append("Số điện thoại cần kiểm tra độ dài.")
        if re.search(r"[^0-9+().\- \t]", unicodedata.normalize("NFKC", value)):
            issues.append("Số điện thoại chứa ký tự hoặc nhiều số cần kiểm tra.")
    elif field == "websites":
        result["website_domain"] = None
        result["is_free_email_domain"] = False
        has_scheme = re.match(r"^[a-z][a-z0-9+.-]*:", value, re.I) and not re.match(r"^[^/:\s]+:[0-9]+(?:[/?#]|$)", value)
        candidate = value if has_scheme else "https://" + value
        try:
            parsed = urlsplit(candidate)
            host = (parsed.hostname or "").lower()
            ascii_host = host.encode("idna").decode("ascii")
            if (parsed.scheme.lower() not in {"http", "https"} or not host or "." not in host
                    or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in ascii_host.split("."))
                    or parsed.username is not None or parsed.password is not None
                    or re.search(r"\s", candidate) or "\\" in candidate):
                raise ValueError("invalid website")
            port = f":{parsed.port}" if parsed.port is not None else ""
            value = urlunsplit((parsed.scheme.lower(), host + port,
                               "" if parsed.path == "/" else parsed.path, parsed.query, parsed.fragment))
            domain = host.removeprefix("www.")
            free_mail = any(domain == free or domain.endswith("." + free) for free in FREE_EMAIL_DOMAINS)
            result["is_free_email_domain"] = free_mail
            if free_mail:
                issues.append("Tên miền dịch vụ email phổ biến; không dùng làm website công ty.")
            else:
                result["website_domain"] = host
        except (ValueError, UnicodeError):
            issues.append("URL chưa hợp lệ; chỉ nhận địa chỉ web HTTP/HTTPS.")
    result["value"] = value
    result["value_norm"] = match_key(value) if field in FIELDS[:4] else value
    result["issues"] = issues
    result["needs_review"] = bool(item.get("needs_review") or issues)
    return result


def normalize_draft(grounding: dict) -> dict:
    fields = {}
    for field in FIELDS:
        fields[field] = []
        for index, item in enumerate(grounding["fields"].get(field, [])):
            verdict = next((entry["verdict"] for entry in grounding.get("report", {}).get(field, [])
                            if entry["value"] == item["value"]), "fuzzy" if item.get("needs_review") else "exact")
            item = {**item, "id": f"{field}:{index}", "source": "ocr", "grounding_verdict": verdict}
            fields[field].append(normalize_item(field, item))
    return {"fields": fields, "card_language": grounding.get("card_language", ""), "normalization_version": 2}
