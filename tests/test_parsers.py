"""Unit tests for parsers package."""

from src.client.parsers.favorite_parser import parse_favorite_courses
from src.client.parsers.course_parser import parse_courses


def test_parse_favorite_courses():
    data = {
        "favoriteSiteIds": [
            "n_2026_1001389",
            "n_2026_1001240",
            "~workspace_user",  # should be excluded
            "",
        ],
        "autoFavoritesEnabled": True,
    }
    courses = parse_favorite_courses(data, host="tact.ac.thers.ac.jp")
    assert len(courses) == 2
    assert all(c.is_favorite for c in courses)
    site_ids = {c.id for c in courses}
    assert site_ids == {"n_2026_1001389", "n_2026_1001240"}


def test_parse_courses_with_favorites():
    site_json = {
        "site_collection": [
            {"id": "site_a", "title": "講義A", "sitePages": []},
            {"id": "site_b", "title": "講義B", "sitePages": []},
            {"id": "site_c", "title": "講義C", "sitePages": []},
        ]
    }
    fav_ids = {"site_a", "site_c"}
    courses = parse_courses(site_json, host="tact.ac.thers.ac.jp", favorite_site_ids=fav_ids)

    assert len(courses) == 3
    c_map = {c.id: c for c in courses}
    assert c_map["site_a"].is_favorite is True
    assert c_map["site_b"].is_favorite is False
    assert c_map["site_c"].is_favorite is True
