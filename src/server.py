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

SERVER_INSTRUCTIONS = """
大学 LMS「Sakai (TACT)」から課題・小テスト・お知らせ・講義資料を安全に取得・管理するための MCP サーバーです。

【1. Sakai LMS の特異な仕様と大学運用の前提知識】
- 「お気に入り (Favorites)」＝「システムが自動設定した今学期の履修中講義」:
  大学の Sakai では過去数年分の履修履歴が残りますが、Sakai システムによって「今学期・今年度の履修中講義」が自動的にお気に入り（★）に登録されます。
  したがって、【お気に入り ＝ 現在履修している講義の完全なリスト】であり、学生の手動登録漏れ等はありません。
  ユーザーから「秋1期」「今年度」「月曜の講義」等の学期・条件指定があった場合でも、すべてお気に入りの中に網羅されています。それらを理由に `favorites_only` を False にしてはいけません（False にすると数十件の無関係な過去講義が混入します）。引数は指定せず省略するか、デフォルトの True のまま呼び出してください。
- テスト (SAMIGO) の仕様:
  小テストは Sakai の API 仕様上、全科目一括取得ができません (講義別取得のみ)。また、学生権限の API では提出済みかどうかのフラグが返らない制約があります。

【2. ツールの使用順序・標準ワークフロー】
特定講義の情報を調べるツール (`get_course_dashboard`, `get_course_materials` 等) は内部識別子である `site_id` (例: "n_2026_1000195") が必須です。
ユーザーから「講義名」で指定された場合は、必ず以下の順序で実行してください：
  Step 1 (講義IDの特定):
    まず `list_courses` を引数なし（デフォルト True）で呼び出し、講義名に対応する `site_id` を特定する。(※勝手に ID を推測・捏造しないこと)
  Step 2 (講義情報の取得):
    特定した `site_id` を用いて、目的のツール (`get_course_dashboard`, `get_course_materials` 等) を呼び出す。
    ※複数講義を調べる場合は、特定した複数の `site_id` に対して Step 2 のツールを 1 ターンで並列呼び出しする。

【3. 講義の絞り込みに関する鉄則（原則として絞り込み禁止）】
- 「お気に入り講義はすべて対象とする」のが大原則:
  `list_courses`（デフォルト True）が返す講義はすべて「今学期の履修中講義」です（せいぜい十数件程度）。
  ユーザーが「秋1期」「秋2期」「今学期」などと言った場合でも、AI側で「これは秋1期、これは秋2期」と講義を勝手に選別・除外してはいけません（セメスター開講科目などの漏れや誤判定を防ぐため）。
  取得できたお気に入り講義はすべて今学期の対象として扱い、一括・並列でチェックしてください。
- 講義の絞り込みを許可する唯一のケース:
  1. ユーザーから「アルゴリズム１」「確率統計」のように、具体的な【講義名・科目名】が指定された場合
  2. ユーザーから「月曜の講義だけ」「〇〇を除いて」と明示的な限定・除外指示があった場合
  ※ 上記以外（学期名、クォーター名、「履修講義すべて」など）では一切絞り込まず、取得できた全講義を対象としてください。
- 外部スクリプト（Python, PowerShell, Bash等）による絞り込みの禁止:
  講義の特定・絞り込みのためだけに外部コードやスクリプトを作成・実行してはいけません。例外は、ユーザーから「過去数年分の全履歴」を求められてデータ件数が膨大（数百件規模）な場合や、数値の統計・集計計算が必要な場合のみに限られます。

【4. 集約ツールの優先と重複呼び出しの防止】
本サーバーには「集約ツール」と「個別ツール」があります。不要な重複取得（同じ情報の二重取得）を避けるため、以下の指針に従ってください。
- 直近の課題・小テスト確認:
  個別ツール (`get_assignments`, `get_quizzes`, `get_calendar_events`) を個別に呼ぶのではなく、統合・締切ソート済みの集約ツール `get_upcoming_deadlines` を第一選択としてください。
- 特定講義の総合確認:
  課題・テスト・お知らせ・資料を一度に把握したい場合は、個別ツールを乱用せず、集約ツール `get_course_dashboard` を 1 回呼び出してください。個別ツールは「資料一覧だけ見たい」「お知らせだけ見たい」といった単一目的の場合のみ使用します。

【5. 並列呼び出し・バッチ処理の指針】
- 本サーバーは内部で完全非同期 (asyncio)・Singleflight (同一リクエスト合流)・TTL キャッシュを備えており、高並行処理に最適化されています。
- 複数講義のダッシュボード比較、複数科目のお知らせ確認、複数ファイルのダウンロード (`download_material`) 等を行う際は、外部 Python スクリプトを作成せず、本 MCP ツールを 1 ターンで並列（複数同時）に呼び出してください。サーバー側で安全かつ高速に並行処理されます。

【6. 設定変更 & 認証仕様】
- 講義資料ファイルや添付ファイルのダウンロードは、講義ごとの AI ポリシーが ALLOW_ALL の場合のみ許可されます。ユーザーからポリシー変更や接続先ドメイン変更を求められた場合は、設定画面起動ツール `open_settings` を案内してください。
- 認証セッションの有効性は `check_auth_status` で確認できます。
- セッション切れ（未ログイン）の場合、データ取得時にサーバーが自動的に別プロセスでログイン画面 (WebView) を起動して再認証を行います。AI 側でログイン用の別ツールを呼ぶ必要はありません。
"""

mcp = FastMCP("sakai-tasks-mcp", instructions=SERVER_INSTRUCTIONS.strip())

_client: SakaiClient | None = None


def get_client() -> SakaiClient:
    """SakaiClient インスタンスを取得する。"""
    global _client
    Config.check_and_reload()
    if not Config.SAKAI_HOST or not Config.CONFIG_FILE_PATH.exists():
        raise RuntimeError(
            "接続先大学のSakaiのドメインが設定されていません。ツール `open_settings` を実行して接続先大学を設定してください。"
        )

    if _client is None or _client.host != Config.SAKAI_HOST:
        _client = SakaiClient(host=Config.SAKAI_HOST, timeout=Config.REQUEST_TIMEOUT, cache_ttl=Config.CACHE_TTL)
    return _client


@mcp.tool()
async def list_courses(
    favorites_only: bool = True,
    summary_only: bool = True,
) -> list[CourseSite]:
    """
    履修・所属している講義サイト一覧を取得します。
    学生が登録している講義の一覧や講義 ID を確認する際に使用してください。

    Args:
        favorites_only: 【重要】通常は引数を指定せず省略してください（デフォルト True）。
            Sakai システムにより「今学期履修中の講義」が自動的にお気に入りに登録されているため、
            「秋1期」「今年度」などの指定がある場合でも False にする必要はありません（お気に入りに全件網羅されています）。
            False を指定できるのは、「過去の修得済み講義」「全履歴」を参照したいと明示された場合、
            またはお気に入り一覧に対象講義が見つからなかった場合の再検索時のみです。
        summary_only: デフォルト True。True の場合は id, name, is_favorite の基本情報のみを軽量に返します。講義名と講義idの対応を知るときは値を指定せずデフォルトのまま使うことで詳細を省き、コンテキストを抑えられる。
            シラバス概要 (description) やサイト URL 等の全詳細情報が必要な場合のみ False を指定します。
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
    提出課題の一覧または個別課題の詳細を取得します。

    Args:
        site_id: 特定の講義で絞り込む場合の講義サイト ID。
        assignment_id: 特定の 1 課題のみを取得する場合の課題 ID。
        favorites_only: 原則としてデフォルトの True のまま（または指定を省略して）呼び出してください。ユーザーから「全講義の課題」「過去の課題も含めて」と明示された場合のみ False を指定します。
        include_details: True の場合は課題の指示文 (instructions) や添付ファイル情報も含めます。

    ※ 講義全体の課題・テスト・連絡・資料をまとめて確認したい場合は、個別ツールではなく `get_course_dashboard` を使用してください。
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
        favorites_only: 原則としてデフォルトの True のまま（または指定を省略して）呼び出してください。ユーザーから明示的に指示された場合のみ False を指定します。

    ※ 講義全体の課題・テスト・連絡・資料をまとめて確認したい場合は、個別ツールではなく `get_course_dashboard` を使用してください。
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
        favorites_only: 原則としてデフォルトの True のまま（または指定を省略して）呼び出してください。ユーザーから明示的に指示された場合のみ False を指定します。
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
        favorites_only: 原則としてデフォルトの True のまま（または指定を省略して）呼び出してください。ユーザーから明示的に指示された場合のみ False を指定します。
        include_details: True の場合は本文 (body) や添付資料も含めます。

    ※ 複数講義のお知らせを横断チェックする場合は、講義ごとに本ツールを並列（複数同時）に呼び出してください。
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

    ※ 複数講義の資料一覧を調べる場合は、各講義の site_id に対して本ツールを並列（複数同時）に呼び出してください。
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

    ※ 複数講義の状況を一括比較・確認する場合は、各講義の site_id に対して本ツールを並列（複数同時）に呼び出してください。
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

    ※ 複数ファイルを保存する場合は、スクリプトを作成せず本ツールを並列（複数同時）に呼び出してください。サーバー側で安全に並行ダウンロードされます。
    """
    check_download_allowed_by_url(url)
    client = get_client()
    return await client.download_material(url=url, save_path=save_path)


@mcp.tool()
def open_settings() -> str:
    """
    ユーザー設定画面 (GUI) を別プロセスでポップアップ起動します。
    stdio 通信をブロックしないため、設定画面を開いたまま AI との対話を継続できます。
    設定画面では（Sakai 接続ホスト名、講義別 AI 利用ポリシー等）を設定できます。
    接続先ホスト名(ドメイン)が未設定の場合、接続祭ホスト名のみを設定できる初期設定ウィンドウが起動します。
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
    Config.check_and_reload()
    if not Config.SAKAI_HOST or not Config.CONFIG_FILE_PATH.exists():
        return {
            "authenticated": False,
            "message": "接続先大学のSakaiのドメインが設定されていません。ツール `open_settings` を実行して接続先大学を設定してください。",
        }

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
