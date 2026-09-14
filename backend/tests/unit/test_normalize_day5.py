from copy import deepcopy

import pytest

from app.services.normalize import normalize_item, normalize_draft, match_key


@pytest.mark.parametrize("field,raw,expected", [
    ("full_names", "  山田　 太郎 \t", "山田 太郎"),
    ("full_names", "  Jane  Doe ", "Jane Doe"),
    ("company_names", " ＡＢＣ　株式会社 ", "ＡＢＣ 株式会社"),
    ("job_titles", "  Senior   Manager ", "Senior Manager"),
    ("departments", " 営業　部 ", "営業 部"),
    ("emails", " Jane.Doe+sales@EXAMPLE.COM ", "Jane.Doe+sales@example.com"),
    ("addresses", " \n〒100-0001 東京都\n千代田区　1-1 \n", "〒100-0001 東京都\n千代田区　1-1"),
    ("websites", " EXAMPLE.COM/Team?ID=A#Top ", "https://example.com/Team?ID=A#Top"),
    ("websites", "http://EXAMPLE.COM/", "http://example.com"),
    ("websites", "EXAMPLE.COM:8080/Team/", "https://example.com:8080/Team/"),
])
def test_formatting_preserves_content_and_raw(field, raw, expected):
    result = normalize_item(field, {"value": raw})
    assert result["value"] == expected and result["value_raw"] == raw
    assert not result["issues"]


@pytest.mark.parametrize("raw,base,number,extension", [
    (" 03-1234-5678 (内線 １０２) ", "03-1234-5678", "0312345678", "102"),
    ("+1 (415) 555-0142 ext. 9", "+1 (415) 555-0142", "14155550142", "9"),
    ("０３-１２３４-５６７８", "０３-１２３４-５６７８", "0312345678", ""),
])
def test_phone_digits_extension_and_no_inferred_country(raw, base, number, extension):
    result = normalize_item("phones", {"value": raw})
    assert result["value"] == base and result["value_raw"] == raw
    assert result["value_digits"] == number and result["extension"] == extension
    assert not result["issues"]


@pytest.mark.parametrize("value", ["a..b@example.com", "a@exam ple.com", "a@-example.com", "name without email"])
def test_invalid_email_is_flagged_not_invented(value):
    result = normalize_item("emails", {"value": value})
    assert result["value"] == value and result["needs_review"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:pass@example.com", "https://bad..com", "https://example.com:wrong"])
def test_invalid_websites_do_not_supply_company_domain(url):
    result = normalize_item("websites", {"value": url})
    assert result["website_domain"] is None and result["needs_review"]
    assert result["value"] == url


@pytest.mark.parametrize("domain", ["GMAIL.COM", "www.yahoo.co.jp", "outlook.com"])
def test_free_mail_is_not_company_website(domain):
    result = normalize_item("websites", {"value": domain})
    assert result["is_free_email_domain"] and result["website_domain"] is None
    assert result["needs_review"]


def test_matching_key_does_not_replace_display_name():
    assert match_key(" ＡＢＣ　山田 ") == "abc山田"
    assert normalize_item("full_names", {"value": "ＡＢＣ　山田"})["value"] == "ＡＢＣ 山田"


def test_draft_is_non_mutating_and_preserves_multiple_names_and_absence():
    evidence = {"fields": {"full_names": [{"value": " 山田 太郎 "}, {"value": "Taro Yamada"}],
                           "emails": [{"value": "jane@example.com"}]}, "card_language": "mixed"}
    original = deepcopy(evidence)
    draft = normalize_draft(evidence)
    assert evidence == original
    assert len(draft["fields"]["full_names"]) == 2
    assert draft["fields"]["websites"] == []  # Never derive it from email.
    assert draft["fields"]["addresses"] == []


def test_conflicting_extensions_are_preserved_and_flagged():
    result = normalize_item("phones", {"value": "03-1234-5678 ext. 102", "extension": "204"})
    assert result["value_raw"] == "03-1234-5678 ext. 102" and result["extension"] == "204"
    assert result["value_digits"] == "0312345678" and result["needs_review"]
