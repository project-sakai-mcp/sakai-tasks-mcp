"""FastMCP server implementation for Sakai Tasks MCP."""

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any

# Ensure project root is in sys.path for direct script execution
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp.server.fastmcp import FastMCP

from src.client import SakaiClient
from src.auth import cookie_storage, session_checker
from src.client.parsers.base import parse_datetime
from src.config import Config
from src.models import (
    Announcement,
    CalendarEvent,
    CourseDashboard,
    CourseMaterial,
    CourseSite,
    SakaiTask,
)
from src.policy import (
    check_download_allowed_by_url,
    filter_announcements,
    filter_calendar_events,
    filter_course_materials,
    filter_courses,
    filter_dashboard,
    filter_tasks,
)

mcp = FastMCP("sakai-tasks-mcp")

_client: SakaiClient | None = None


def get_client() -> SakaiClient:
    """SakaiClient インスタンスを取得する。"""
    global _client
    if _client is None or _client.host != Config.SAKAI_HOST:
        _client = SakaiClient(host=Config.SAKAI_HOST, timeout=Config.REQUEST_TIMEOUT, cache_ttl=Config.CACHE_TTL)
    return _client


@mcp.tool()
async def list_courses(favorites_only: bool = True) -> list[CourseSite]:
    """
    履修・所属している講義サイト一覧を取得します。
    学生が登録している講義の一覧や講義 ID を確認する際に使用してください。

    Args:
        favorites_only: True の場合はお気に入り（ピン留め）登録講義のみ取得します。未設定時は自動的に全講義にフォールバックします。
    """
    client = get_client()
    courses = await client.get_courses(favorites_only=favorites_only)
    return filter_courses(courses)


@mcp.tool()
async def get_assignments(
    site_id: str | None = None,
    assignment_id: str | None = None,
    favorites_only: bool = True,
    include_details: bool = True,
) -> list[SakaiTask]:
    """
    提出課題の一覧または個別課題の詳細を取得します。

    Args:
        site_id: 特定の講義で絞り込む場合の講義サイト ID。
        assignment_id: 特定の 1 課題のみを取得する場合の課題 ID。
        favorites_only: True の場合はお気に入り講義の課題のみ取得します。
        include_details: True の場合は課題の指示文 (instructions) や添付ファイル情報も含めます。
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
    小テスト・オンラインテスト・クイズの一覧を取得します。

    Args:
        site_id: 特定の講義で絞り込む場合の講義サイト ID。
        favorites_only: True の場合はお気に入り講義のテストのみ取得します。
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
    直近 N 日以内に締切のある未提出課題および小テストを統合し、締切日時昇順でソートして取得します。
    学生が「今週の課題はある？」「直近の締切を教えて」などと尋ねてきた場合の第一選択ツールです。

    Args:
        days: 何日先までの締切を対象とするか。未指定時は設定のデフォルト日数 (通常30日) が適用されます。
        favorites_only: True の場合はお気に入り講義のみを対象とします。
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
    講義またはシステムからのお知らせ・連絡事項一覧または個別詳細を取得します。

    Args:
        site_id: 特定講義で絞り込む場合の講義サイト ID。
        announcement_id: 特定の 1 件のみを取得する場合のお知らせ ID。
        n: 取得件数上限。未指定時は設定のデフォルト件数 (通常7件) が適用されます。
        favorites_only: True の場合はお気に入り講義のお知らせのみ取得します。
        include_details: True の場合は本文 (body) や添付資料も含めます。
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
    カレンダーに登録されたスケジュール・イベント・課題締切予定一覧を取得します。

    Args:
        site_id: 特定講義で絞り込む場合の講義サイト ID。
        start_date: 期間開始日時 (ISO 8601 形式の文字列、例: "2024-10-01T00:00:00Z")。
        end_date: 期間終了日時 (ISO 8601 形式の文字列)。
        event_type: イベント種別による絞り込み ("Assignment", "Quiz" 等)。
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
    指定講義の授業資料・配布ファイル・フォルダ一覧を取得します。

    Args:
        site_id: 講義サイト ID (必須)。
        files_only: True の場合はフォルダ項目を除外し、ファイルのみ返却します。
    """
    client = get_client()
    materials = await client.get_course_materials(site_id=site_id, files_only=files_only)
    return filter_course_materials(materials, site_id)


@mcp.tool()
async def get_course_dashboard(
    site_id: str,
) -> CourseDashboard:
    """
    指定講義の総合状況（課題・小テスト・直近お知らせ・授業資料）を並行一括取得してサマリーを返します。
    ユーザーから「この講義の状況を全部教えて」と求められた場合の最適ツールです。

    Args:
        site_id: 講義サイト ID (必須)。
    """
    client = get_client()
    dashboard = await client.get_course_dashboard(site_id=site_id)
    return filter_dashboard(dashboard)


@mcp.tool()
async def download_material(
    url: str,
    save_path: str,
) -> str:
    """
    講義資料や課題添付ファイルを指定のローカルパスにダウンロード保存します。
    講義の AI 利用ポリシーが ALLOW_ALL の場合のみダウンロード可能です。

    Args:
        url: ダウンロード対象の Sakai 相対パス (/access/content/...) または完全修飾 URL。
        save_path: 保存先のローカルファイル絶対パス。
    """
    check_download_allowed_by_url(url)
    client = get_client()
    return await client.download_material(url=url, save_path=save_path)


@mcp.tool()
def open_settings() -> str:
    """
    ユーザー設定画面 (GUI) を別プロセスでポップアップ起動します。
    stdio 通信をブロックしないため、設定画面を開いたまま AI との対話を継続できます。
    """
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--settings"]
    else:
        cmd = [sys.executable, sys.argv[0], "--settings"]

    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return "ユーザー設定画面を開きました。設定保存後は自動的に最新設定が反映されます。"


@mcp.tool()
def get_settings() -> dict[str, Any]:
    """
    現在の設定一覧（Sakai 接続ホスト名、講義別 AI 利用ポリシー等）を取得します。
    講義ポリシーによる制限理由の確認や、ユーザーへの設定変更案内時に利用します。
    """
    config_data = Config.load()
    return config_data.model_dump()


@mcp.tool()
async def check_auth_status() -> dict[str, Any]:
    """
    現在の Sakai ログインセッションの有効性を確認します。
    未ログインまたはセッション失効時はその旨を返却し、画面の強制表示は行いません。
    """
    cookies = cookie_storage.load_sakai_cookies(host=Config.SAKAI_HOST)
    if not cookies:
        return {
            "authenticated": False,
            "message": "未ログインです。設定画面または認証を実行してください。",
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
        "message": "セッションが切れています。再ログインが必要です。",
    }


def main():
    """
    MCP サーバープロセスのメインエントリポイント。
    CLI 引数の処理、設定の初期解決、GUI 起動制御、stdio サーバー実行を管理する。
    """
    parser = argparse.ArgumentParser(description="Sakai Tasks MCP Server")
    parser.add_argument("--host", type=str, help="Sakai LMS のホスト名 (例: tact.ac.thers.ac.jp)")
    parser.add_argument("--settings", action="store_true", help="ユーザー設定 GUI 画面を起動する")
    parser.add_argument("--setup", action="store_true", help="初回大学プリセット選択ダイアログを起動する")
    parser.add_argument("--login", action="store_true", help="WebView ログイン画面を別プロセスのメインスレッドで実行して Cookie を保存する")
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

    # 3. --setup 引数指定時: 初回大学プリセット選択ダイアログを起動して終了
    if args.setup:
        from src.gui.settings_window import show_initial_setup_window
        show_initial_setup_window()
        sys.exit(0)

    # 4. 通常起動時: Config を安全に初期化 (stdio タイムアウト防止のためブロッキング GUI は出さない)
    Config.init(cli_host=args.host)

    # 5. stdio 通信で FastMCP サーバーを開始
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
