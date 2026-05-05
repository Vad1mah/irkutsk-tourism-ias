"""Тесты для helper-функций парсера Kassir.ru: извлечение адреса и описания."""


def test_kassir_extracts_venue_address_from_jsonld():
    """JSON-LD location.address.streetAddress → ParsedEvent.address."""
    from app.parsers.events_kassir import _extract_address_from_jsonld

    sample = {
        "location": {
            "name": "Иркутская филармония",
            "address": {
                "streetAddress": "ул. Дзержинского, 2",
                "addressLocality": "Иркутск",
            },
        },
    }
    addr = _extract_address_from_jsonld(sample)
    assert addr is not None
    assert "Дзержинского" in addr


def test_kassir_extracts_address_from_string():
    """JSON-LD location.address as plain string → returned as-is."""
    from app.parsers.events_kassir import _extract_address_from_jsonld

    sample = {
        "location": {"address": "ул. Ленина, 5"},
    }
    addr = _extract_address_from_jsonld(sample)
    assert addr == "ул. Ленина, 5"


def test_kassir_extracts_no_address_when_missing():
    from app.parsers.events_kassir import _extract_address_from_jsonld

    assert _extract_address_from_jsonld({}) is None
    assert _extract_address_from_jsonld({"location": "Just a string"}) is None
    assert _extract_address_from_jsonld({"location": {}}) is None
