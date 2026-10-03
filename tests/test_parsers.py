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
def test_parse_assignments_submission_status():
    from src.client.parsers.assignment_parser import parse_assignments
    from src.models import TaskStatus

    # 未提出（Sakaiが空の未開始レコードを返すケース）
    unsubmitted_data = {
        "assignment_collection": [
            {
                "id": "task_1",
                "title": "未提出課題",
                "context": "site_1",
                "status": "OPEN",
                "submissions": [
                    {
                        "status": "開始されていません",
                        "submitted": True,
                        "userSubmission": False,
                    }
                ],
            }
        ]
    }
    tasks = parse_assignments(unsubmitted_data, host="tact.ac.thers.ac.jp")
    assert len(tasks) == 1
    assert tasks[0].is_submitted is False
    assert tasks[0].status == TaskStatus.OPEN

    # 提出済み
    submitted_data = {
        "assignment_collection": [
            {
                "id": "task_2",
                "title": "提出済み課題",
                "context": "site_1",
                "status": "OPEN",
                "submissions": [
                    {
                        "status": "提出日時 2026/10/02 22:32",
                        "submitted": True,
                        "userSubmission": True,
                    }
                ],
            }
        ]
    }
    tasks = parse_assignments(submitted_data, host="tact.ac.thers.ac.jp")
    assert len(tasks) == 1
    assert tasks[0].is_submitted is True
    assert tasks[0].status == TaskStatus.SUBMITTED


def test_parse_datetime_compact_formats():
    from datetime import datetime, timezone
    from src.client.parsers.base import parse_datetime

    # 8桁
    dt_8 = parse_datetime("20261002")
    assert dt_8 == datetime(2026, 10, 2, 0, 0, 0, tzinfo=timezone.utc)

    # 14桁 (YYYYMMDDhhmmss)
    dt_14 = parse_datetime("20260918112848")
    assert dt_14 == datetime(2026, 9, 18, 11, 28, 48, tzinfo=timezone.utc)

    # 17桁 (YYYYMMDDhhmmssmmm)
    dt_17 = parse_datetime("20260918112848381")
    assert dt_17 == datetime(2026, 9, 18, 11, 28, 48, 381000, tzinfo=timezone.utc)
