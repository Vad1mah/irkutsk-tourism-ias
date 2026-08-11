"""Unit-тесты на price_min extractor."""



def test_extract_price_min_from_text_rubles():
    from app.parsers.events_zeroevent import _extract_price_min
    assert _extract_price_min("Билеты от 500 руб.") == 500


def test_extract_price_min_from_text_symbol():
    from app.parsers.events_zeroevent import _extract_price_min
    assert _extract_price_min("Стоимость от 1500₽, дети бесплатно") == 1500


def test_extract_price_min_no_price():
    from app.parsers.events_zeroevent import _extract_price_min
    assert _extract_price_min("Бесплатно") is None
    assert _extract_price_min("") is None
    assert _extract_price_min(None) is None  # type: ignore


def test_extract_price_min_short_form():
    """Различные форматы: 'от 100 р.', 'от 100 р', 'от 250 рублей'."""
    from app.parsers.events_zeroevent import _extract_price_min
    assert _extract_price_min("от 100 р.") == 100
    assert _extract_price_min("Цена: от 250 рублей") == 250
