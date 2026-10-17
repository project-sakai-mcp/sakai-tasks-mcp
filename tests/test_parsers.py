"""Unit tests for parsers package."""

from datetime import UTC

from src.client.parsers.course_parser import parse_courses
from src.client.parsers.favorite_parser import parse_favorite_courses


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
    from datetime import datetime

    from src.client.parsers.base import parse_datetime

    # 8桁
    dt_8 = parse_datetime("20261002")
    assert dt_8 == datetime(2026, 10, 2, 0, 0, 0, tzinfo=UTC)

    # 14桁 (YYYYMMDDhhmmss)
    dt_14 = parse_datetime("20260918112848")
    assert dt_14 == datetime(2026, 9, 18, 11, 28, 48, tzinfo=UTC)

    # 17桁 (YYYYMMDDhhmmssmmm)
    dt_17 = parse_datetime("20260918112848381")
    assert dt_17 == datetime(2026, 9, 18, 11, 28, 48, 381000, tzinfo=UTC)


def test_parse_unread_forum_messages_list_format():
    from src.client.parsers.forum_parser import parse_unread_forum_messages

    sample_data = [
        {
            "messageUrl": "/portal/directtool/8fa8f830-9d75-4055-a5cd-325f3464e060",
            "messageCount": 0,
            "siteUrl": "https://tact.ac.thers.ac.jp/portal/site/g_2026_2ZSI331240",
            "siteTitle": "自然科学総合(メタバース文化論)(2026年度後学期/火５限)",
            "siteId": "g_2026_2ZSI331240",
            "forumCount": 0,
        },
        {
            "messageUrl": "/portal/directtool/a2f7da5b-ad89-4b4f-ad78-ce52cec7772e",
            "messageCount": 2,
            "siteUrl": "https://tact.ac.thers.ac.jp/portal/site/n_2025_0013212",
            "siteTitle": "物理学基礎Ⅰ(2025年度春/水２限)",
            "siteId": "n_2025_0013212",
            "forumUrl": "/portal/directtool/bdc70d1e-c918-4dd2-9f96-d7684e98fa89",
            "forumCount": 132,
        },
    ]

    items = parse_unread_forum_messages(sample_data, host="tact.ac.thers.ac.jp")
    assert len(items) == 2

    # 1件目: forumUrl なし、未読 0
    assert items[0].site_id == "g_2026_2ZSI331240"
    assert items[0].site_name == "自然科学総合(メタバース文化論)(2026年度後学期/火５限)"
    assert items[0].unread_messages_count == 0
    assert items[0].unread_forums_count == 0
    assert items[0].message_url == "https://tact.ac.thers.ac.jp/portal/directtool/8fa8f830-9d75-4055-a5cd-325f3464e060"
    assert items[0].forum_url is None
    assert items[0].site_url == "https://tact.ac.thers.ac.jp/portal/site/g_2026_2ZSI331240"

    # 2件目: forumUrl あり、未読あり
    assert items[1].site_id == "n_2025_0013212"
    assert items[1].site_name == "物理学基礎Ⅰ(2025年度春/水２限)"
    assert items[1].unread_messages_count == 2
    assert items[1].unread_forums_count == 132
    assert items[1].message_url == "https://tact.ac.thers.ac.jp/portal/directtool/a2f7da5b-ad89-4b4f-ad78-ce52cec7772e"
    assert items[1].forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/bdc70d1e-c918-4dd2-9f96-d7684e98fa89"


def test_parse_unread_forum_messages_dict_format():
    from src.client.parsers.forum_parser import parse_unread_forum_messages

    sample_dict = {
        "forums": [
            {
                "siteId": "test_site_1",
                "siteTitle": "テスト講義",
                "messageCount": 3,
                "forumCount": 5,
                "messageUrl": "/portal/directtool/msg-123",
                "forumUrl": "/portal/directtool/forum-456",
            }
        ]
    }

    items = parse_unread_forum_messages(sample_dict, host="example.edu")
    assert len(items) == 1
    assert items[0].site_id == "test_site_1"
    assert items[0].unread_messages_count == 3
    assert items[0].unread_forums_count == 5
    assert items[0].message_url == "https://example.edu/portal/directtool/msg-123"
    assert items[0].forum_url == "https://example.edu/portal/directtool/forum-456"


def test_parse_unread_forum_messages_empty_or_invalid():
    from src.client.parsers.forum_parser import parse_unread_forum_messages

    assert parse_unread_forum_messages([], host="example.edu") == []
    assert parse_unread_forum_messages({}, host="example.edu") == []
    assert parse_unread_forum_messages(None, host="example.edu") == []
    assert parse_unread_forum_messages([{"invalid": "item"}], host="example.edu") == []


def test_parse_announcements():
    from src.client.parsers.announcement_parser import parse_announcements

    raw_data = {
        "announcement_collection": [
            {
                "id": "ann-1",
                "title": "第1回休講のお知らせ",
                "siteId": "course-101",
                "siteTitle": "線形代数学",
                "createdByDisplayName": "山田 太郎",
                "createdOn": "20261001100000",
                "body": "<p>第1回の講義は<strong>休講</strong>です。<br></p>",
                "attachments": [
                    {"url": "/access/content/attachment/1.pdf", "name": "guide.pdf"}
                ],
            },
            {
                "announcementId": "ann-2",
                "title": "レポート課題提示",
                "siteId": "course-102",
                "createdOn": 1727780000000,
                "body": "レポートを提出してください",
                "attachments": [],
            },
            {
                "id": "ann-3",
                "title": "除外対象のお知らせ",
                "siteId": "course-999",
                "body": "他クラスのお知らせ",
            },
        ]
    }

    site_names = {"course-101": "線形代数学", "course-102": "アルゴリズム論"}
    site_tools = {"course-101": {"announcement": "https://tact.example.edu/portal/directtool/ann-tool-1"}}

    # site_names で course-999 が除外され、ツールURLが反映されること
    announcements = parse_announcements(
        raw_data,
        host="tact.example.edu",
        site_names=site_names,
        site_tool_pages=site_tools,
        include_details=True,
    )
    assert len(announcements) == 2
    assert announcements[0].id == "ann-1"
    assert announcements[0].title == "第1回休講のお知らせ"
    assert "休講" in (announcements[0].content or "")
    assert announcements[0].url == "https://tact.example.edu/portal/directtool/ann-tool-1"
    assert len(announcements[0].attachments) == 1
    assert announcements[0].attachments[0].url == "https://tact.example.edu/access/content/attachment/1.pdf"

    # announcement_id 指定による単一抽出
    single = parse_announcements(
        raw_data,
        host="tact.example.edu",
        announcement_id="ann-2",
    )
    assert len(single) == 1
    assert single[0].id == "ann-2"
    assert single[0].site_name == "course-102"

    # include_details=False の場合は content と attachments が空になること
    no_details = parse_announcements(
        raw_data,
        host="tact.example.edu",
        announcement_id="ann-1",
        include_details=False,
    )
    assert no_details[0].content is None
    assert no_details[0].attachments == []


def test_parse_calendar_events():
    from src.client.parsers.calendar_parser import parse_calendar_events

    data = {
        "calendar_collection": [
            {
                "eventId": "evt-1",
                "type": "Assignment",
                "siteId": "site-1",
                "title": "課題1 締切",
                "description": "<p>第1回の課題締切です。</p>",
                "firstTime": {"time": 1727780000000},
                "duration": 3600000,  # 1時間
            },
            {
                "id": "evt-2",
                "type": "Quiz",
                "siteId": "site-2",
                "siteName": "情報論",
                "title": "小テスト",
                "firstTime": "20261010150000",
            },
            {
                "id": "evt-3",
                "type": "Lecture",
                "siteId": "site-999",
                "title": "除外イベント",
            },
        ]
    }

    site_names = {"site-1": "数学", "site-2": "情報論"}
    site_tools = {"site-1": {"assignment": "https://example.edu/tool/assign-1"}}

    events = parse_calendar_events(
        data,
        host="example.edu",
        site_names=site_names,
        site_tool_pages=site_tools,
    )
    assert len(events) == 2

    # evt-1 の検証 (assignmentツールURL, duration による end_time 計算)
    assert events[0].id == "evt-1"
    assert events[0].event_type == "assignment"
    assert events[0].site_name == "数学"
    assert events[0].url == "https://example.edu/tool/assign-1"
    assert events[0].start_time is not None
    assert events[0].end_time is not None
    assert events[0].end_time > events[0].start_time

    # event_type フィルタ ("quiz")
    quiz_events = parse_calendar_events(
        data,
        host="example.edu",
        event_type="quiz",
    )
    assert len(quiz_events) == 1
    assert quiz_events[0].id == "evt-2"


def test_parse_quizzes():
    from datetime import datetime, timedelta

    from src.client.parsers.quiz_parser import parse_quizzes
    from src.models import TaskStatus, TaskType

    now = datetime.now(UTC)
    past_date = (now - timedelta(days=2)).strftime("%Y%m%d%H%M%S")
    future_date = (now + timedelta(days=2)).strftime("%Y%m%d%H%M%S")

    data = {
        "sam_pub_collection": [
            {
                "publishedAssessmentId": 101,
                "title": "公開中クイズ",
                "status": "1",
                "startDate": past_date,
                "dueDate": future_date,
                "retractDate": future_date,
                "timeLimit": 3600,
            },
            {
                "publishedAssessmentId": 102,
                "title": "締切済みクイズ",
                "status": "1",
                "dueDate": past_date,
            },
            {
                "publishedAssessmentId": 103,
                "title": "非公開下書きクイズ",
                "status": "0",  # 除外されるべき
            },
        ]
    }

    tasks = parse_quizzes(
        data,
        site_id="site-100",
        host="example.edu",
        site_name="物理学",
        tool_page_url="https://example.edu/portal/tool/samigo",
    )
    assert len(tasks) == 2

    assert tasks[0].id == "101"
    assert tasks[0].task_type == TaskType.QUIZ
    assert tasks[0].title == "公開中クイズ"
    assert tasks[0].status == TaskStatus.OPEN
    assert tasks[0].time_limit_seconds == 3600
    assert tasks[0].url == "https://example.edu/portal/tool/samigo"

    assert tasks[1].id == "102"
    assert tasks[1].status == TaskStatus.CLOSED


def test_parse_course_contents():
    from src.client.parsers.content_parser import parse_course_contents
    from src.models import MaterialType

    data = {
        "content_collection": [
            {
                "entityId": "/group/site-200",  # ルートフォルダ (除外対象)
                "type": "collection",
                "title": "site-200",
            },
            {
                "entityId": "/group/site-200/第1回",
                "type": "collection",
                "title": "第1回",
                "container": "/group/site-200/",
            },
            {
                "entityId": "/group/site-200/第1回/slide01.pdf",
                "type": "application/pdf",
                "title": "slide01.pdf",
                "url": "/access/content/group/site-200/第1回/slide01.pdf",
                "size": "1048576",
                "container": "/group/site-200/第1回/",
                "modifiedDate": "20261005120000",
                "mimeType": "application/pdf",
            },
        ]
    }

    materials = parse_course_contents(
        data,
        site_id="site-200",
        host="example.edu",
        site_name="英語講義",
    )
    assert len(materials) == 2

    # フォルダの検証
    assert materials[0].name == "第1回"
    assert materials[0].material_type == MaterialType.FOLDER
    assert materials[0].is_collection is True

    # ファイルの検証
    assert materials[1].name == "slide01.pdf"
    assert materials[1].material_type == MaterialType.FILE
    assert materials[1].is_collection is False
    assert materials[1].size_bytes == 1048576
    assert materials[1].url == "https://example.edu/access/content/group/site-200/第1回/slide01.pdf"
    assert materials[1].path == "第1回"

    # files_only=True の場合、フォルダが除外されてファイルのみになること
    files_only = parse_course_contents(
        data,
        site_id="site-200",
        host="example.edu",
        files_only=True,
    )
    assert len(files_only) == 1
    assert files_only[0].name == "slide01.pdf"

