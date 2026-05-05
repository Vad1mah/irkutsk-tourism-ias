"""Test image_url extraction for 101hotels parser."""

import pytest


def test_101hotels_extract_image_url_from_photos():
    from app.parsers.hotels_101hotels import _extract_image_url

    # Sample API response shape
    raw = {
        "photos": [
            {"url": "https://cdn.101hotels.ru/abc123.jpg", "is_main": True},
            {"url": "https://cdn.101hotels.ru/xyz456.jpg"},
        ],
    }
    assert _extract_image_url(raw) == "https://cdn.101hotels.ru/abc123.jpg"


def test_101hotels_no_image_when_empty():
    from app.parsers.hotels_101hotels import _extract_image_url

    assert _extract_image_url({}) is None
    assert _extract_image_url({"photos": []}) is None


def test_101hotels_extract_image_url_from_string_photos():
    """Some APIs return photo as string array, not dict array."""
    from app.parsers.hotels_101hotels import _extract_image_url

    raw = {"photos": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]}
    assert _extract_image_url(raw) == "https://example.com/img1.jpg"
