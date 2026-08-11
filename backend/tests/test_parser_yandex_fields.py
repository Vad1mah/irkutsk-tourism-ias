"""Unit-тесты на извлечение полей age_restriction и full description из JSON-LD."""
from datetime import time



def _make_jsonld_event(name="Концерт",
                       start="2026-06-01T19:30:00",
                       desc="Описание длиной более 300 символов." * 30,
                       age="12-99",
                       image="https://example.com/img.jpg") -> dict:
    return {
        "@type": "Event",
        "name": name,
        "startDate": start,
        "typicalAgeRange": age,
        "description": desc,
        "image": image,
        "location": {"name": "Концертный зал"},
    }


def test_yandex_parses_age_restriction_from_typicalAgeRange():
    """typicalAgeRange '12-99' → age_restriction='12+'."""
    from app.parsers.events_yandex import parse_yandex_jsonld_event
    parsed = parse_yandex_jsonld_event(
        _make_jsonld_event(age="12-99"),
        source_url="https://afisha.yandex.ru/irkutsk/test1",
    )
    assert parsed.get("age_restriction") == "12+"


def test_yandex_parses_age_restriction_zero_means_no_restriction():
    """typicalAgeRange '0-99' → age_restriction is None."""
    from app.parsers.events_yandex import parse_yandex_jsonld_event
    parsed = parse_yandex_jsonld_event(
        _make_jsonld_event(age="0-99"),
        source_url="https://afisha.yandex.ru/irkutsk/test2",
    )
    assert parsed.get("age_restriction") is None


def test_yandex_keeps_full_description_up_to_2000_chars():
    """description up to 2000 chars (was 300 before)."""
    from app.parsers.events_yandex import parse_yandex_jsonld_event
    long_desc = "X" * 1500
    parsed = parse_yandex_jsonld_event(
        _make_jsonld_event(desc=long_desc),
        source_url="https://afisha.yandex.ru/irkutsk/test3",
    )
    assert parsed.get("description") == long_desc
    assert len(parsed.get("description", "")) >= 1000


def test_yandex_parses_time_start_from_iso():
    """startDate '2026-06-01T19:30:00' → time_start=time(19, 30)."""
    from app.parsers.events_yandex import parse_yandex_jsonld_event
    parsed = parse_yandex_jsonld_event(
        _make_jsonld_event(start="2026-06-01T19:30:00"),
        source_url="https://afisha.yandex.ru/irkutsk/test4",
    )
    ts = parsed.get("time_start")
    assert ts is not None
    if isinstance(ts, time):
        assert ts.hour == 19 and ts.minute == 30
    elif isinstance(ts, str):
        assert "19:30" in ts
