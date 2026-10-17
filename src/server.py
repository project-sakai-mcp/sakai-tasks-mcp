"""FastMCP server implementation for Sakai Tasks MCP."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path for direct script execution
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp.server.fastmcp import FastMCP

from src.auth import cookie_storage, session_checker
from src.client import SakaiClient
from src.client.parsers.base import parse_datetime
from src.config import Config
from src.models import (
    Announcement,
    CalendarEvent,
    CourseDashboard,
    CourseMaterial,
    CourseSite,
    SakaiTask,
    UnreadForumMessage,
)
from src.policy import (
    check_download_allowed_by_url,
    filter_announcements,
    filter_calendar_events,
    filter_course_materials,
    filter_courses,
    filter_dashboard,
    filter_tasks,
    filter_unread_forum_messages,
)

SERVER_INSTRUCTIONS = """
MCP server for retrieving assignments, quizzes, announcements, and course materials from the university Sakai LMS (e.g., TACT).

[1. Courses & Favorites]
- Sakai automatically stars the current semester's enrolled courses as Favorites, so Favorites = the complete list of currently enrolled courses.
  Terms like "Fall Q1", "this academic year", or "Monday lectures" are already covered. Do NOT set `favorites_only` to False for such reasons (it pulls in dozens of irrelevant past courses); omit it.
- Quizzes (SAMIGO) cannot be retrieved in bulk across courses (per-course only), and student-level access returns no submission status.

[2. Workflow]
Course-specific tools (`get_course_dashboard`, `get_course_materials`, etc.) require `site_id` (e.g., "n_2026_1000195").
When the user gives a course name, first call `list_courses` (no arguments) to find the `site_id`. Never guess IDs. Then call the target tool; for multiple courses, call it in parallel in a single turn.

[3. Course Filtering]
- By default, target ALL courses returned by `list_courses` (usually 10-15). Do not filter by term/quarter names or "this semester".
- Filter only when the user names a specific course/subject, or explicitly asks to limit/exclude (e.g., "only Monday lectures", "excluding XX").
- Do not write external scripts (Python, PowerShell, Bash, etc.) just to identify or filter courses. Exceptions: multi-year historical data (hundreds of items) or numerical aggregation.

[4. Prefer Aggregation Tools]
- Upcoming assignments/quizzes: use `get_upcoming_deadlines` instead of `get_assignments`, `get_quizzes`, `get_calendar_events`.
- Overview of one course: use `get_course_dashboard` once instead of several individual tools. Use individual tools only for single-purpose queries.
- Unread private messages/forums (not covered by `get_announcements`): use `get_unread_messages_and_forums`.

[5. Parallel Calls]
The server is async with request deduplication and caching. For multiple courses or files (`download_material`), call tools concurrently in a single turn instead of writing scripts.

[6. Settings & Authentication]
- Downloads are allowed only when the course AI policy is ALLOW_ALL. To change policies or the connection domain, run `open_settings`.
- Use `check_auth_status` to check the session. Expired sessions trigger an automatic login window during data retrieval; no login tool call is needed.
"""

mcp = FastMCP("sakai-tasks-mcp", instructions=SERVER_INSTRUCTIONS.strip())

_client: SakaiClient | None = None


def get_client() -> SakaiClient:
    """Get or initialize the SakaiClient instance."""
    global _client
    Config.check_and_reload()
    if not Config.SAKAI_HOST or not Config.CONFIG_FILE_PATH.exists():
        raise RuntimeError(
            "The target university Sakai domain is not configured. Please run the `open_settings` tool to configure the university domain."
        )

    if _client is None or _client.host != Config.SAKAI_HOST:
        _client = SakaiClient(host=Config.SAKAI_HOST, timeout=Config.REQUEST_TIMEOUT)
    return _client


@mcp.tool()
async def list_courses(
    favorites_only: bool = True,
    summary_only: bool = True,
) -> list[CourseSite]:
    """
    Retrieve the list of enrolled/joined course sites.
    Use this to check the courses a student is enrolled in or to look up course IDs.

    Args:
        favorites_only: Usually omit (default True covers all current-semester courses, even when terms like "Fall Q1" are mentioned).
            Set to False only for "past completed courses"/"full history", or when a course was not found in favorites.
        summary_only: When True, returns only id, name, is_favorite (saves tokens for name-to-ID lookup).
            Set to False only when details such as the syllabus description or site URL are needed.
    """
    client = get_client()
    courses = await client.get_courses(favorites_only=favorites_only)
    filtered = filter_courses(courses)

    if summary_only:
        return [
            CourseSite(
                id=c.id,
                name=c.name,
                is_favorite=c.is_favorite,
            )
            for c in filtered
        ]
    return filtered


@mcp.tool()
async def get_assignments(
    site_id: str | None = None,
    assignment_id: str | None = None,
    favorites_only: bool = True,
    include_details: bool = True,
) -> list[SakaiTask]:
    """
    Retrieve a list of assignments or details of an individual assignment.

    Args:
        site_id: Course site ID to filter by.
        assignment_id: Retrieve a single assignment.
        favorites_only: Leave as default True. Set to False only when explicitly requested (e.g., "all courses", "past assignments").
        include_details: Include instructions and attachment info.
    """
    client = get_client()
    tasks = await client.get_assignments(
        site_id=site_id,
        favorites_only=favorites_only,
        assignment_id=assignment_id,
        include_details=include_details,
    )
    return filter_tasks(tasks)


@mcp.tool()
async def get_quizzes(
    site_id: str | None = None,
    favorites_only: bool = True,
) -> list[SakaiTask]:
    """
    Retrieve a list of quizzes, online tests, and assessments.

    Args:
        site_id: Course site ID to filter by.
        favorites_only: Leave as default True unless explicitly instructed.
    """
    client = get_client()
    tasks = await client.get_quizzes(site_id=site_id, favorites_only=favorites_only)
    return filter_tasks(tasks)


@mcp.tool()
async def get_upcoming_deadlines(
    days: int | None = None,
    favorites_only: bool = True,
) -> list[SakaiTask]:
    """
    Retrieve unsubmitted assignments and quizzes due within the next N days, sorted by due date.
    Primary tool for "Any assignments this week?" or "What are my upcoming deadlines?".

    Args:
        days: Days ahead to look. Defaults to the configured value (usually 30).
        favorites_only: Leave as default True unless explicitly instructed.
    """
    client = get_client()
    target_days = days if days is not None else Config.DEFAULT_DEADLINE_DAYS
    tasks = await client.get_upcoming_deadlines(days=target_days, favorites_only=favorites_only)
    return filter_tasks(tasks)


@mcp.tool()
async def get_announcements(
    site_id: str | None = None,
    announcement_id: str | None = None,
    n: int | None = None,
    favorites_only: bool = True,
    include_details: bool = True,
) -> list[Announcement]:
    """
    Retrieve course or system announcements/notices, or details of a specific announcement.

    Args:
        site_id: Course site ID to filter by.
        announcement_id: Retrieve a single announcement.
        n: Maximum number of announcements. Defaults to the configured limit (usually 7).
        favorites_only: Leave as default True unless explicitly instructed.
        include_details: Include full body text and attachments.
    """
    client = get_client()
    limit = n if n is not None else Config.DEFAULT_ANNOUNCEMENT_LIMIT
    announcements = await client.get_announcements(
        site_id=site_id,
        favorites_only=favorites_only,
        announcement_id=announcement_id,
        n=limit,
        include_details=include_details,
    )
    return filter_announcements(announcements)


@mcp.tool()
async def get_calendar_events(
    site_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    event_type: str | None = None,
) -> list[CalendarEvent]:
    """
    Retrieve schedules, events, and assignment due dates registered in the calendar.

    Args:
        site_id: Course site ID to filter by.
        start_date: ISO 8601 start date/time (e.g., "2024-10-01T00:00:00Z").
        end_date: ISO 8601 end date/time.
        event_type: Event type filter ("Assignment", "Quiz", etc.).
    """
    client = get_client()
    dt_start = parse_datetime(start_date) if start_date else None
    dt_end = parse_datetime(end_date) if end_date else None
    events = await client.get_calendar_events(
        site_id=site_id,
        start_date=dt_start,
        end_date=dt_end,
        event_type=event_type,
    )
    return filter_calendar_events(events)


@mcp.tool()
async def get_course_materials(
    site_id: str,
    files_only: bool = False,
) -> list[CourseMaterial]:
    """
    Retrieve course materials, distributed files, and folders for the specified course.

    Args:
        site_id: Course site ID.
        files_only: When True, excludes folder items.
    """
    client = get_client()
    materials = await client.get_course_materials(site_id=site_id, files_only=files_only)
    return filter_course_materials(materials, site_id)


@mcp.tool()
async def get_course_dashboard(
    site_id: str,
) -> CourseDashboard:
    """
    Retrieve a course summary (assignments, quizzes, recent announcements, materials) in a single call.
    Best when the user asks "Tell me everything about this course".

    Args:
        site_id: Course site ID.
    """
    client = get_client()
    dashboard = await client.get_course_dashboard(site_id=site_id)
    return filter_dashboard(dashboard)


@mcp.tool()
async def get_unread_messages_and_forums(
    site_id: str | None = None,
    favorites_only: bool = True,
) -> list[UnreadForumMessage]:
    """
    Retrieve unread counts and Web URLs for course Messages and Forums (not delivered via Announcements).

    Args:
        site_id: Course site ID to filter by a specific course.
        favorites_only: Leave as default True.
    """
    client = get_client()
    items = await client.get_unread_forum_messages(site_id=site_id, favorites_only=favorites_only)
    return filter_unread_forum_messages(items)


@mcp.tool()
async def download_material(
    url: str,
    save_path: str,
) -> str:
    """
    Download and save course materials or assignment attachments to the specified local path.
    Downloads are permitted only when the course's AI policy is ALLOW_ALL.

    Args:
        url: Sakai relative path (/access/content/...) or fully qualified URL to download.
        save_path: Absolute local file path where the file should be saved.
    """
    check_download_allowed_by_url(url)
    client = get_client()
    return await client.download_material(url=url, save_path=save_path)


@mcp.tool()
def open_settings() -> str:
    """
    Open the user settings window (GUI) in a separate popup process.
    Does not block stdio communication, allowing conversation with AI to continue while the settings window is open.
    Allows configuring Sakai connection host, course AI policies, etc.
    If the connection host is unconfigured, an initial setup window will be launched.
    """
    # 自身のスクリプト絶対パスとプロジェクトルートを取得
    server_script = Path(__file__).resolve()
    project_root = server_script.parent.parent

    # 子プロセスへ渡す環境変数を設定
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{project_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(project_root)
    )
    # Windows かつ Embeddable Python の場合のフォールバック
    embed_dll = project_root / "python-embed" / "python312.dll"
    if embed_dll.exists():
        env["PYTHONNET_PYDLL"] = str(embed_dll)
        env["PYTHONHOME"] = str(embed_dll.parent)

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--settings"]
    else:
        cmd = [sys.executable, str(server_script), "--settings"]

    subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return "User settings window opened. Saved settings will be automatically applied."


@mcp.tool()
def get_settings() -> dict[str, Any]:
    """
    Retrieve current settings (Sakai connection host, per-course AI policies, etc.).
    Useful for checking policy restriction reasons or guiding the user on settings changes.
    """
    config_data = Config.load()
    return config_data.model_dump()


@mcp.tool()
async def check_auth_status() -> dict[str, Any]:
    """
    Check the validity of the current Sakai login session.
    Returns status information without forcing a login window if unauthenticated or expired.
    """
    Config.check_and_reload()
    if not Config.SAKAI_HOST or not Config.CONFIG_FILE_PATH.exists():
        return {
            "authenticated": False,
            "message": "The target university Sakai domain is not configured. Please run the `open_settings` tool to configure the university domain.",
        }

    cookies = cookie_storage.load_sakai_cookies(host=Config.SAKAI_HOST)
    if not cookies:
        return {
            "authenticated": False,
            "message": "Not logged in. Please open the settings window or perform authentication.",
        }

    info = await session_checker.get_session_info(cookies, host=Config.SAKAI_HOST)
    if info and info.get("userEid"):
        return {
            "authenticated": True,
            "user_eid": info.get("userEid"),
            "session_info": info,
        }
    return {
        "authenticated": False,
        "message": "Session has expired. Re-login is required.",
    }


def main():
    """
    MCP server process main entry point.
    Handles CLI argument parsing, initial configuration resolution, GUI startup, and stdio server execution.
    """
    parser = argparse.ArgumentParser(description="Sakai Tasks MCP Server")
    parser.add_argument("--host", type=str, help="Host name of the Sakai LMS (e.g., tact.ac.thers.ac.jp)")
    parser.add_argument("--settings", action="store_true", help="Launch the user settings GUI window")
    parser.add_argument("--login", action="store_true", help="Run the WebView login window on the main thread of a separate process and save cookies")
    args = parser.parse_args()

    # 1. --login 引数指定時: メインスレッドで WebView ログインを実行して終了 (OS制約遵守)
    if args.login:
        from src.auth.webview_auth import authenticate_via_webview
        target_host = args.host or Config.SAKAI_HOST
        cookies = authenticate_via_webview(host=target_host)
        if not cookies:
            sys.exit(1)
        cookie_storage.save_all_cookies(cookies)
        sys.exit(0)

    # 2. --settings 引数指定時: 設定画面 GUI を起動して終了
    if args.settings:
        from src.gui.settings_window import show_settings_window
        show_settings_window()
        sys.exit(0)

    # 4. 通常起動時: Config を安全に初期化 (stdio タイムアウト防止のためブロッキング GUI は出さない)
    Config.init(cli_host=args.host)

    # 5. stdio 通信で FastMCP サーバーを開始
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
