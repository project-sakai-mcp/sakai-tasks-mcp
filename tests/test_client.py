"""Unit tests for SakaiClient, timeouts, and error handling."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.client import SakaiClient, SakaiTimeoutError
from src.config import Config
from src.gui.api import SettingsApi
from src.gui.data_builder import SettingsUIData


def test_default_timeout_is_30_seconds():
    """デフォルトの REQUEST_TIMEOUT が 30.0 秒であることを検証"""
    assert Config.REQUEST_TIMEOUT == 30.0
    client = SakaiClient(host="test.sakai.edu")
    assert client.timeout == 30.0


@pytest.mark.asyncio
async def test_get_assignments_uses_site_endpoints_in_parallel():
    """get_assignments が講義別エンドポイント /direct/assignment/site/{site_id}.json を並行取得することを検証"""
    client = SakaiClient(host="test.sakai.edu")

    mock_sites = {
        "site1": "Mathematics",
        "site2": "Physics",
    }
    mock_tool_pages = {
        "site1": {"assignment": "https://test.sakai.edu/portal/site1"},
        "site2": {"assignment": "https://test.sakai.edu/portal/site2"},
    }

    client._resolve_site_context = AsyncMock(return_value=(mock_sites, mock_tool_pages))

    async def mock_get_json(endpoint, default=None, **kwargs):
        if "site1" in endpoint:
            return {
                "assignment_collection": [
                    {
                        "id": "a1",
                        "context": "site1",
                        "title": "Math Assignment 1",
                        "dueTime": {"epochSecond": 1800000000},
                        "status": "OPEN",
                    }
                ]
            }
        elif "site2" in endpoint:
            return {
                "assignment_collection": [
                    {
                        "id": "a2",
                        "context": "site2",
                        "title": "Physics Assignment 1",
                        "dueTime": {"epochSecond": 1800000000},
                        "status": "OPEN",
                    }
                ]
            }
        return default

    client._get_json = AsyncMock(side_effect=mock_get_json)

    tasks = await client.get_assignments()

    assert len(tasks) == 2
    task_titles = {t.title for t in tasks}
    assert "Math Assignment 1" in task_titles
    assert "Physics Assignment 1" in task_titles
    assert client._get_json.call_count == 2


@pytest.mark.asyncio
async def test_get_assignments_raises_sakai_timeout_error():
    """get_assignments で一部の講義がタイムアウトした場合に SakaiTimeoutError が送出されることを検証"""
    client = SakaiClient(host="test.sakai.edu", timeout=30.0)

    mock_sites = {
        "site1": "Mathematics",
        "site2": "Physics",
    }
    mock_tool_pages = {"site1": {}, "site2": {}}
    client._resolve_site_context = AsyncMock(return_value=(mock_sites, mock_tool_pages))

    async def mock_get_json(endpoint, default=None, **kwargs):
        if "site2" in endpoint:
            raise httpx.ReadTimeout("Read timed out")
        return {"assignment_collection": []}

    client._get_json = AsyncMock(side_effect=mock_get_json)

    with pytest.raises(SakaiTimeoutError) as exc_info:
        await client.get_assignments()

    err = exc_info.value
    assert err.timeout == 30.0
    assert any("Physics" in s for s in err.failed_sites)
    assert "Request to Sakai LMS timed out" in str(err)
    assert "Physics" in str(err)
    assert "open_settings" in str(err)


@pytest.mark.asyncio
async def test_get_quizzes_raises_sakai_timeout_error():
    """get_quizzes でタイムアウトが発生した場合に SakaiTimeoutError が送出されることを検証"""
    client = SakaiClient(host="test.sakai.edu", timeout=30.0)

    mock_sites = {"site1": "Chemistry"}
    mock_tool_pages = {"site1": {}}
    client._resolve_site_context = AsyncMock(return_value=(mock_sites, mock_tool_pages))
    client._get_json = AsyncMock(side_effect=httpx.ReadTimeout("Read timed out"))

    with pytest.raises(SakaiTimeoutError) as exc_info:
        await client.get_quizzes()

    err = exc_info.value
    assert err.timeout == 30.0
    assert "Chemistry" in str(err)
    assert "Request to Sakai LMS timed out" in str(err)


@pytest.mark.asyncio
async def test_fetch_timeout_not_suppressed_by_default():
    """_fetch でタイムアウトが発生した場合、default が指定されていても握りつぶさず SakaiTimeoutError を発生させることを検証"""
    client = SakaiClient(host="test.sakai.edu", timeout=30.0)

    with patch.object(client, "_request", side_effect=httpx.ConnectTimeout("Connect timed out")):
        with pytest.raises(SakaiTimeoutError) as exc_info:
            await client._fetch(
                method="GET",
                endpoint="/direct/test.json",
                default={"fallback": True},
            )

    assert "Request to Sakai LMS timed out after 30.0s" in str(exc_info.value)


def test_settings_api_saves_request_timeout(tmp_path, monkeypatch):
    """SettingsApi.save_settings で request_timeout が Config に反映されることを検証"""
    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)

    ui_data = SettingsUIData(
        sakai_host="tact.ac.thers.ac.jp",
        presets={},
        default_deadline_days=30,
        default_announcement_limit=7,
        request_timeout=30.0,
        courses=[],
    )
    api = SettingsApi(ui_data)

    payload = {
        "sakai_host": "tact.ac.thers.ac.jp",
        "default_deadline_days": 14,
        "default_announcement_limit": 10,
        "request_timeout": 45.0,
        "courses": [],
    }
    result = api.save_settings(payload)
    assert result is True
    assert Config.REQUEST_TIMEOUT == 45.0


@pytest.mark.asyncio
async def test_get_unread_forum_messages_filtering():
    """get_unread_forum_messages の favorites_only および site_id 絞り込みを検証"""
    from src.models import CourseSite

    client = SakaiClient(host="tact.ac.thers.ac.jp")

    sample_api_response = [
        {
            "siteId": "site_fav_1",
            "siteTitle": "お気に入り講義1",
            "messageCount": 2,
            "forumCount": 0,
            "messageUrl": "/portal/directtool/m1",
        },
        {
            "siteId": "site_fav_2",
            "siteTitle": "お気に入り講義2",
            "messageCount": 0,
            "forumCount": 5,
            "forumUrl": "/portal/directtool/f2",
        },
        {
            "siteId": "site_non_fav",
            "siteTitle": "過去講義",
            "messageCount": 10,
            "forumCount": 10,
        },
    ]

    client._get_json = AsyncMock(return_value=sample_api_response)
    client.get_courses = AsyncMock(
        return_value=[
            CourseSite(id="site_fav_1", name="お気に入り講義1", is_favorite=True),
            CourseSite(id="site_fav_2", name="お気に入り講義2", is_favorite=True),
        ]
    )

    # 1. favorites_only=True (デフォルト)
    fav_items = await client.get_unread_forum_messages()
    assert len(fav_items) == 2
    assert {i.site_id for i in fav_items} == {"site_fav_1", "site_fav_2"}

    # 2. favorites_only=False (全講義)
    all_items = await client.get_unread_forum_messages(favorites_only=False)
    assert len(all_items) == 3

    # 3. site_id 指定
    single_item = await client.get_unread_forum_messages(site_id="site_fav_1")
    assert len(single_item) == 1
    assert single_item[0].site_id == "site_fav_1"
    assert single_item[0].unread_messages_count == 2


@pytest.mark.asyncio
async def test_get_course_dashboard_includes_unread_forum_messages():
    """get_course_dashboard が未読メッセージ・フォーラム数をダッシュボードに統合することを検証"""
    from src.models import UnreadForumMessage

    client = SakaiClient(host="tact.ac.thers.ac.jp")

    client._resolve_site_context = AsyncMock(return_value=({"site_1": "Test Course"}, {}))
    client.get_assignments = AsyncMock(return_value=[])
    client.get_quizzes = AsyncMock(return_value=[])
    client.get_announcements = AsyncMock(return_value=[])
    client.get_course_materials = AsyncMock(return_value=[])
    client.get_unread_forum_messages = AsyncMock(
        return_value=[
            UnreadForumMessage(
                site_id="site_1",
                site_name="Test Course",
                unread_messages_count=3,
                unread_forums_count=7,
                message_url="https://tact.ac.thers.ac.jp/portal/directtool/msg-1",
                forum_url="https://tact.ac.thers.ac.jp/portal/directtool/forum-1",
            )
        ]
    )

    dashboard = await client.get_course_dashboard(site_id="site_1")

    assert dashboard.site_id == "site_1"
    assert dashboard.site_name == "Test Course"
    assert dashboard.unread_messages_count == 3
    assert dashboard.unread_forums_count == 7
    assert dashboard.message_url == "https://tact.ac.thers.ac.jp/portal/directtool/msg-1"
    assert dashboard.forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/forum-1"

