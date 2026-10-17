"""Unit tests for FastMCP server tool endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import AIPolicyMode, Config
from src.models import (
    Announcement,
    Attachment,
    CalendarEvent,
    CourseMaterial,
    CourseSite,
    MaterialType,
    SakaiTask,
    TaskStatus,
    TaskType,
)
from src.server import (
    download_material,
    get_announcements,
    get_assignments,
    get_calendar_events,
    get_course_materials,
    get_quizzes,
    get_settings,
    list_courses,
)


@pytest.fixture
def mock_sakai_client(monkeypatch):
    """SakaiClient のモックを差し込むフィクスチャ"""
    mock_client = AsyncMock()
    monkeypatch.setattr(Config, "SAKAI_HOST", "tact.ac.thers.ac.jp")
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.ALLOW_ALL)
    with patch("src.server.get_client", return_value=mock_client):
        yield mock_client


@pytest.mark.asyncio
async def test_list_courses_tool(mock_sakai_client):
    """list_courses ツールの正常系 (summary_only / 全情報)"""
    mock_sakai_client.get_courses.return_value = [
        CourseSite(id="c1", name="数学", is_favorite=True, description="詳細な説明文"),
        CourseSite(id="c2", name="英語", is_favorite=False, description="詳細な説明文2"),
    ]

    # 1. summary_only=True (デフォルト) -> description 等が省略される
    res_summary = await list_courses(favorites_only=True, summary_only=True)
    assert len(res_summary) == 2
    assert res_summary[0].id == "c1"
    assert res_summary[0].description is None

    # 2. summary_only=False -> 全情報が返る
    res_full = await list_courses(favorites_only=False, summary_only=False)
    assert len(res_full) == 2
    assert res_full[0].description == "詳細な説明文"


@pytest.mark.asyncio
async def test_get_assignments_tool(mock_sakai_client):
    """get_assignments ツールの正常系"""
    mock_sakai_client.get_assignments.return_value = [
        SakaiTask(
            id="a1",
            title="レポート1",
            task_type=TaskType.ASSIGNMENT,
            site_id="c1",
            site_name="数学",
            status=TaskStatus.OPEN,
            instructions="問題文",
            attachments=[Attachment(id="att1", name="sample.pdf", url="https://example.edu/sample.pdf")],
        )
    ]

    res = await get_assignments(site_id="c1", include_details=True)
    assert len(res) == 1
    assert res[0].id == "a1"
    assert res[0].title == "レポート1"
    assert res[0].instructions == "問題文"


@pytest.mark.asyncio
async def test_get_quizzes_tool(mock_sakai_client):
    """get_quizzes ツールの正常系"""
    mock_sakai_client.get_quizzes.return_value = [
        SakaiTask(
            id="q1",
            title="小テスト1",
            task_type=TaskType.QUIZ,
            site_id="c1",
            site_name="数学",
            status=TaskStatus.OPEN,
        )
    ]

    res = await get_quizzes(site_id="c1")
    assert len(res) == 1
    assert res[0].id == "q1"
    assert res[0].task_type == TaskType.QUIZ


@pytest.mark.asyncio
async def test_get_announcements_tool(mock_sakai_client):
    """get_announcements ツールの正常系"""
    mock_sakai_client.get_announcements.return_value = [
        Announcement(
            id="ann1",
            title="休講案内",
            site_id="c1",
            site_name="数学",
            content="休講です",
        )
    ]

    res = await get_announcements(site_id="c1", include_details=True)
    assert len(res) == 1
    assert res[0].id == "ann1"
    assert res[0].content == "休講です"


@pytest.mark.asyncio
async def test_get_calendar_events_tool(mock_sakai_client):
    """get_calendar_events ツールの正常系"""
    mock_sakai_client.get_calendar_events.return_value = [
        CalendarEvent(
            id="ev1",
            title="提出期限",
            site_id="c1",
            site_name="数学",
            event_type="assignment",
        )
    ]

    res = await get_calendar_events(site_id="c1", event_type="assignment")
    assert len(res) == 1
    assert res[0].id == "ev1"


@pytest.mark.asyncio
async def test_get_course_materials_tool(mock_sakai_client):
    """get_course_materials ツールの正常系"""
    mock_sakai_client.get_course_materials.return_value = [
        CourseMaterial(
            id="m1",
            site_id="c1",
            name="lecture01.pdf",
            material_type=MaterialType.FILE,
            is_collection=False,
            url="https://example.edu/lecture01.pdf",
        )
    ]

    res = await get_course_materials(site_id="c1", files_only=True)
    assert len(res) == 1
    assert res[0].id == "m1"
    assert res[0].name == "lecture01.pdf"


@pytest.mark.asyncio
async def test_download_material_tool_policy_blocked(mock_sakai_client, monkeypatch):
    """download_material ツールのポリシー拒否テスト"""
    monkeypatch.setattr(Config, "get_course_policy", lambda _: AIPolicyMode.TEXT_ONLY)
    url = "https://tact.ac.thers.ac.jp/access/content/group/c1/slide.pdf"

    with pytest.raises(PermissionError, match="ダウンロードが禁止されています"):
        await download_material(url=url, save_path="/tmp/slide.pdf")


def test_get_settings_tool(monkeypatch):
    """get_settings ツールの正常系"""
    from src.config import AppConfigData

    mock_data = AppConfigData(sakai_host="tact.ac.thers.ac.jp", request_timeout=45.0)
    monkeypatch.setattr(Config, "load", lambda: mock_data)

    settings = get_settings()
    assert settings["sakai_host"] == "tact.ac.thers.ac.jp"
    assert settings["request_timeout"] == 45.0
    assert "policies" in settings
