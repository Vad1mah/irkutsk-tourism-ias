"""Тесты извлечения адреса из JSON-LD парсера culture.ru."""


def test_culture_rf_extracts_address_from_jsonld_dict():
    from app.parsers.events_culture_rf import _extract_address_from_jsonld
    sample = {"location": {"address": {"streetAddress": "ул. Тимирязева, 35"}}}
    assert _extract_address_from_jsonld(sample) == "ул. Тимирязева, 35"


def test_culture_rf_extracts_address_from_string():
    from app.parsers.events_culture_rf import _extract_address_from_jsonld
    assert _extract_address_from_jsonld({"location": {"address": "ул. Карла Маркса, 14"}}) == "ул. Карла Маркса, 14"


def test_culture_rf_no_address_when_missing():
    from app.parsers.events_culture_rf import _extract_address_from_jsonld
    assert _extract_address_from_jsonld({}) is None
    assert _extract_address_from_jsonld({"location": "string only"}) is None
