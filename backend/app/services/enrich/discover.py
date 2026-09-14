from urllib.parse import urlsplit, urlunsplit, urljoin

from app.services.normalize import normalize_item, FREE_EMAIL_DOMAINS, EMAIL, match_key, digits


def seed_url(draft: dict) -> tuple[str | None, str]:
    fields = draft["fields"]
    for item in fields.get("websites", []):
        url = normalize_item("websites", item)
        if url.get("website_domain"):
            parts = urlsplit(url["value"])
            return urlunsplit((parts.scheme, parts.netloc, "/", "", "")), "website_on_card"
    for item in fields.get("emails", []):
        email = item["value"].strip()
        if EMAIL.fullmatch(email):
            domain = email.rsplit("@", 1)[1].lower()
            if not any(domain == free or domain.endswith("." + free) for free in FREE_EMAIL_DOMAINS):
                return f"https://{domain}/", "email_domain_candidate"
    return None, "no_domain_on_card"


def identity_matches(draft: dict, text: str) -> bool:
    fields = draft["fields"]
    normalized = match_key(text)
    for field in ("company_names", "addresses"):
        for item in fields.get(field, []):
            value = match_key(item["value"])
            if len(value) >= (4 if field == "company_names" else 10) and value in normalized:
                return True
    # Compare complete telephone-like tokens rather than a suffix or joined text.
    import re
    import unicodedata
    tokens = {digits(token) for token in re.findall(r"\+?\d[\d() .\t-]{7,}\d", unicodedata.normalize("NFKC", text))}
    return any(len(number := digits(item["value"])) >= 9 and number in tokens for item in fields.get("phones", []))


def candidate_pages(homepage, limit: int) -> list[str]:
    origin = urlsplit(homepage.url)
    chosen = []
    terms = ("about", "company", "corporate", "profile", "会社", "企業", "products", "services", "製品", "事業")
    for link in homepage.links:
        part = urlsplit(link)
        if part.hostname == origin.hostname and any(term in part.path.lower() for term in terms):
            if link != homepage.url and link not in chosen:
                chosen.append(link)
    for path in ("/about", "/company", "/products", "/services"):
        url = urljoin(homepage.url, path)
        if url != homepage.url and url not in chosen:
            chosen.append(url)
    return chosen[:max(0, limit - 1)]
