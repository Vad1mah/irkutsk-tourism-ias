"""Регрессия: yandex должен брать title↔url из JSON-LD, а не из markdown-эвристики.

Баг: markdown-путь (_parse_event_block) брал «первый url в блоке», из-за чего
карусельные/соседние ссылки попадали в чужие события («Майкл» → ссылка на стендап
Бебуришвили). JSON-LD даёт name+url из одного schema.org-узла → пара гарантирована.
"""
import json

from app.parsers.events_yandex import YandexAfishaParser

_SAMPLE_EVENTS = [
    {
        "@type": "Event",
        "name": "Мари Краймбрери",
        "url": "https://afisha.yandex.ru/irkutsk/concert/mari-kraymbreri-tour",
        "startDate": "2026-09-27",
        "offers": {"@type": "Offer", "price": 2000, "priceCurrency": "RUB"},
        "location": {"@type": "Place", "name": "Дворец спорта «Труд»", "address": "ул. Ленина, 48"},
    },
    {
        "@type": "Event",
        "name": "Андрей Бебуришвили",
        "url": "https://afisha.yandex.ru/irkutsk/standup/andrei-beburishvili-standup",
        "startDate": "2026-11-26",
    },
]
_HTML = (
    '<html><head><script type="application/ld+json">'
    + json.dumps(_SAMPLE_EVENTS, ensure_ascii=False)
    + "</script></head><body></body></html>"
)


def test_jsonld_pairs_title_with_its_own_url():
    parser = YandexAfishaParser("irkutsk")
    events = parser._extract_jsonld_events(_HTML)
    by_title = {e.title: e for e in events}

    assert "Мари Краймбрери" in by_title
    url = by_title["Мари Краймбрери"].url or ""
    # КРИТИЧНО: ссылка ведёт на саму Краймбрери, не на чужой стендап/спорт
    assert "mari-kraymbreri" in url
    assert "standup" not in url
    # JSON-LD обогащает цену/площадку
    assert by_title["Мари Краймбрери"].price_min == 2000
    assert by_title["Мари Краймбрери"].location == "Дворец спорта «Труд»"


def test_jsonld_handles_no_events_gracefully():
    parser = YandexAfishaParser("irkutsk")
    assert parser._extract_jsonld_events("<html><body>no ld json</body></html>") == []
    assert parser._extract_jsonld_events("") == []
