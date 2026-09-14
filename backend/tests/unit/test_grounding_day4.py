from app.services.extract.base import CardExtraction, PhoneValue, ExtractedValue
from app.services.extract.grounding import ground, ground_extraction


def test_email_punctuation_is_significant():
    assert ground('taroyamada@example.com', 'taro.yamada@example.com', 'email').verdict == 'unverified'


def test_phone_tokens_do_not_join_lines_or_slash_separated_numbers():
    for separator in ('\n', ' / '):
        raw = '03-1234-5678' + separator + '090-1234-5678'
        assert ground('03-1234-5678', raw, 'phone').verdict == 'exact'
        assert ground('031234567809012345678', raw, 'phone').verdict == 'unverified'


def test_url_path_and_query_are_not_discarded_or_lowercased():
    assert ground('example.com/team', 'https://example.com/Team', 'url').verdict == 'unverified'
    assert ground('example.com', 'https://example.com?ID=1', 'url').verdict == 'unverified'
    for candidate in ('example.com/team', 'example.com?ID=2', 'example.com'):
        assert ground(candidate, 'https://example.com/Team?ID=1', 'url').verdict == 'unverified'
    assert ground('example.com?ID=2', 'example.com?ID=1', 'url').verdict == 'unverified'


def test_phone_metadata_belongs_to_that_number():
    raw = 'TEL: 03-1234-5678 ext. 102 / FAX: 03-9876-5432 ext. 204'
    result = ground_extraction(CardExtraction(phones=[
        PhoneValue(value='03-9876-5432', label='tel', extension='102'),
        PhoneValue(value='03-1234-5678', label='tel', extension='102'),
    ]), raw)['fields']['phones']
    assert result[0]['label'] == '' and result[0]['extension'] == ''
    assert result[0]['needs_review']
    assert result[1]['label'] == 'tel' and result[1]['extension'] == '102'


def test_fabricated_source_text_is_not_presented_as_evidence():
    result = ground_extraction(CardExtraction(emails=[
        ExtractedValue(value='jane@example.com', source_text='invented evidence'),
    ]), 'jane@example.com')['fields']['emails'][0]
    assert result['source_text'] == '' and result['needs_review']
