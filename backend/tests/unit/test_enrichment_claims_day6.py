from app.services.enrich.fetcher import Page
from app.services.enrich.discover import seed_url, identity_matches, candidate_pages
from app.services.enrich.summarize import Claim, validate_claims


def page(url="https://example.com/", text="Example Inc. builds industrial sensors."):
    return Page(url, "Company", text, [], "2026-09-11T00:00:00+00:00")


def claim(value="industrial sensors", snippet="Example Inc. builds industrial sensors.", url="https://example.com/", attribute="products_services"):
    return Claim(attribute=attribute, value=value, evidence_snippet=snippet, source_url=url)


def test_snippet_value_and_url_must_all_belong_to_fetched_page():
    candidates = [claim(), claim(value="invented business"), claim(snippet="Fabricated sentence about industrial sensors."),
                  claim(url="https://other.example/")]
    accepted, rejected = validate_claims(candidates, [page()], True)
    assert len(accepted) == 1 and rejected == 3
    assert accepted[0]["status"] == "verified"


def test_identity_mismatch_and_undated_size_remain_unverified():
    accepted, _ = validate_claims([claim()], [page()], False)
    assert accepted[0]["status"] == "unverified"
    text = "Example Inc. has 120 employees."
    accepted, _ = validate_claims([claim("120 employees", text, attribute="company_size")], [page(text=text)], True)
    assert accepted[0]["status"] == "unverified"


def test_japanese_dated_headcount_is_supported():
    text = "従業員数：120名 (2024年4月時点)"
    accepted, _ = validate_claims([claim("120名 (2024年4月時点)", text, attribute="company_size")], [page(text=text)], True)
    assert accepted[0]["status"] == "verified"


def test_conflicting_sources_keep_both_values():
    first = "Company has 120 employees (2024)."
    second = "Company has 140 employees (2025)."
    pages = [page(text=first), page("https://example.com/about", second)]
    accepted, _ = validate_claims([claim("120 employees (2024)", first, attribute="company_size"),
        claim("140 employees (2025)", second, pages[1].url, "company_size")], pages, True)
    assert len(accepted) == 2 and {item["status"] for item in accepted} == {"conflicting"}


def test_discovery_priority_and_absence_without_name_search():
    draft = {"fields": {"websites": [{"value": "https://official.example/about"}],
                        "emails": [{"value": "jane@other.example"}]}}
    assert seed_url(draft) == ("https://official.example/", "website_on_card")
    draft["fields"]["websites"] = []
    assert seed_url(draft) == ("https://other.example/", "email_domain_candidate")
    draft["fields"]["emails"] = [{"value": "jane@gmail.com"}]
    assert seed_url(draft) == (None, "no_domain_on_card")


def test_identity_uses_company_or_complete_phone_not_person_name():
    assert identity_matches({"fields": {"company_names": [{"value": "株式会社サンプル"}]}}, "ようこそ 株式会社サンプル")
    assert not identity_matches({"fields": {"full_names": [{"value": "Jane Doe"}]}}, "Jane Doe")
    assert not identity_matches({"fields": {"phones": [{"value": "0312345678"}]}}, "9990312345678")


def test_candidate_pages_stay_on_site_and_are_bounded():
    home = page()
    home.links = ["https://evil.example/about", "https://example.com/services", "https://example.com/company"]
    links = candidate_pages(home, 5)
    assert len(links) == 4 and all(link.startswith("https://example.com/") for link in links)
