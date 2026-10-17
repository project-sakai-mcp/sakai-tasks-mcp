"""Tests for models and policy filtering of unread messages and forums."""


from src.config import AIPolicyMode, Config
from src.models import (
    CourseDashboard,
    UnreadForumMessage,
)
from src.policy import (
    filter_dashboard,
    filter_unread_forum_messages,
)


def test_unread_forum_message_model():
    msg = UnreadForumMessage(
        site_id="site_1",
        site_name="講義1",
        unread_messages_count=2,
        unread_forums_count=5,
        message_url="https://tact.ac.thers.ac.jp/portal/directtool/m1",
        forum_url="https://tact.ac.thers.ac.jp/portal/directtool/f1",
        site_url="https://tact.ac.thers.ac.jp/portal/site/site_1",
    )
    assert msg.site_id == "site_1"
    assert msg.site_name == "講義1"
    assert msg.unread_messages_count == 2
    assert msg.unread_forums_count == 5
    assert msg.message_url == "https://tact.ac.thers.ac.jp/portal/directtool/m1"
    assert msg.forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/f1"


def test_filter_unread_forum_messages(monkeypatch):
    items = [
        UnreadForumMessage(site_id="allowed_site", site_name="OK Course", unread_messages_count=1),
        UnreadForumMessage(site_id="blocked_site", site_name="NG Course", unread_messages_count=3),
    ]

    def mock_get_course_policy(site_id: str) -> AIPolicyMode:
        if site_id == "blocked_site":
            return AIPolicyMode.BLOCKED
        return AIPolicyMode.ALLOW_ALL

    monkeypatch.setattr(Config, "get_course_policy", mock_get_course_policy)

    filtered = filter_unread_forum_messages(items)
    assert len(filtered) == 1
    assert filtered[0].site_id == "allowed_site"
    assert filtered[0].unread_messages_count == 1


def test_filter_dashboard_preserves_unread_info(monkeypatch):
    monkeypatch.setattr(Config, "get_course_policy", lambda site_id: AIPolicyMode.ALLOW_ALL)

    dashboard = CourseDashboard(
        site_id="site_1",
        site_name="講義1",
        unread_messages_count=4,
        unread_forums_count=8,
        message_url="https://tact.ac.thers.ac.jp/portal/directtool/m1",
        forum_url="https://tact.ac.thers.ac.jp/portal/directtool/f1",
    )

    filtered = filter_dashboard(dashboard)
    assert filtered.site_id == "site_1"
    assert filtered.unread_messages_count == 4
    assert filtered.unread_forums_count == 8
    assert filtered.message_url == "https://tact.ac.thers.ac.jp/portal/directtool/m1"
    assert filtered.forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/f1"


def test_filter_courses(monkeypatch):
    from src.models import CourseSite
    from src.policy import filter_courses

    courses = [
        CourseSite(id="c_allow", name="許可講義"),
        CourseSite(id="c_blocked", name="ブロック講義"),
    ]
    monkeypatch.setattr(
        Config,
        "get_course_policy",
        lambda sid: AIPolicyMode.BLOCKED if sid == "c_blocked" else AIPolicyMode.ALLOW_ALL,
    )
    result = filter_courses(courses)
    assert len(result) == 1
    assert result[0].id == "c_allow"


def test_filter_tasks_policy_modes(monkeypatch):
    from src.models import Attachment, SakaiTask, TaskStatus, TaskType
    from src.policy import MASKED_INSTRUCTION_TEXT, filter_tasks

    task = SakaiTask(
        id="t1",
        title="課題1",
        task_type=TaskType.ASSIGNMENT,
        site_id="course_1",
        site_name="講義1",
        status=TaskStatus.OPEN,
        instructions="問題文全文",
        max_points=100.0,
        attachments=[Attachment(id="att1", name="doc.pdf", url="https://example.edu/doc.pdf")],
    )

    # 1. BLOCKED -> 除外
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.BLOCKED)
    assert filter_tasks([task]) == []

    # 2. SCHEDULE_ONLY -> 指示文マスク、max_points None、添付空
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.SCHEDULE_ONLY)
    res_sched = filter_tasks([task])
    assert len(res_sched) == 1
    assert res_sched[0].instructions == MASKED_INSTRUCTION_TEXT
    assert res_sched[0].max_points is None
    assert res_sched[0].attachments == []

    # 3. TEXT_ONLY -> 添付URLのみ None
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.TEXT_ONLY)
    res_text = filter_tasks([task])
    assert len(res_text) == 1
    assert res_text[0].instructions == "問題文全文"
    assert res_text[0].attachments[0].url is None

    # 4. ALLOW_ALL -> そのまま
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.ALLOW_ALL)
    res_all = filter_tasks([task])
    assert res_all[0].instructions == "問題文全文"
    assert res_all[0].attachments[0].url == "https://example.edu/doc.pdf"


def test_filter_announcements_policy_modes(monkeypatch):
    from src.models import Announcement, Attachment
    from src.policy import MASKED_ANNOUNCEMENT_TEXT, filter_announcements

    item = Announcement(
        id="a1",
        title="連絡",
        site_id="c1",
        site_name="講義1",
        content="詳細本文",
        attachments=[Attachment(id="att2", name="info.pdf", url="https://example.edu/info.pdf")],
    )

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.BLOCKED)
    assert filter_announcements([item]) == []

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.SCHEDULE_ONLY)
    res_sched = filter_announcements([item])
    assert res_sched[0].content == MASKED_ANNOUNCEMENT_TEXT
    assert res_sched[0].attachments == []

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.TEXT_ONLY)
    res_text = filter_announcements([item])
    assert res_text[0].attachments[0].url is None

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.ALLOW_ALL)
    res_all = filter_announcements([item])
    assert res_all[0].content == "詳細本文"


def test_filter_calendar_events_policy_modes(monkeypatch):
    from src.models import CalendarEvent
    from src.policy import filter_calendar_events

    ev = CalendarEvent(id="e1", title="イベント", site_id="c1", description="詳細情報")

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.BLOCKED)
    assert filter_calendar_events([ev]) == []

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.SCHEDULE_ONLY)
    res = filter_calendar_events([ev])
    assert res[0].description is None

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.ALLOW_ALL)
    assert filter_calendar_events([ev])[0].description == "詳細情報"


def test_filter_course_materials_and_downloads(monkeypatch):
    import pytest

    from src.models import CourseMaterial, MaterialType
    from src.policy import check_download_allowed_by_url, filter_course_materials

    mat = CourseMaterial(
        id="m1",
        site_id="site_100",
        name="slide.pdf",
        material_type=MaterialType.FILE,
        is_collection=False,
        url="https://example.edu/access/content/group/site_100/slide.pdf",
    )

    # filter_course_materials
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.BLOCKED)
    with pytest.raises(ValueError):
        filter_course_materials([mat], "site_100")

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.SCHEDULE_ONLY)
    assert filter_course_materials([mat], "site_100") == []

    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.TEXT_ONLY)
    res_text = filter_course_materials([mat], "site_100")
    assert res_text[0].url is None

    # check_download_allowed_by_url
    url = "https://tact.ac.thers.ac.jp/access/content/group/site_100/slide.pdf"
    invalid_url = "https://example.com/external/file.pdf"

    # 不正URL
    with pytest.raises(PermissionError, match="could not be identified"):
        check_download_allowed_by_url(invalid_url)

    # BLOCKED
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.BLOCKED)
    with pytest.raises(PermissionError, match="is denied"):
        check_download_allowed_by_url(url)

    # TEXT_ONLY
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.TEXT_ONLY)
    with pytest.raises(PermissionError, match="is prohibited"):
        check_download_allowed_by_url(url)

    # ALLOW_ALL -> 成功
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.ALLOW_ALL)
    check_download_allowed_by_url(url)  # No exception
