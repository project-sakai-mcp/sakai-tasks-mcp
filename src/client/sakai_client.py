import asyncio
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse
import httpx

try:
    from src.config import Config
except ImportError:
    class Config:  # type: ignore
        SAKAI_HOST: str = "tact.ac.thers.ac.jp"
        REQUEST_TIMEOUT: float = 15.0
        CACHE_TTL: float = 300.0
        DEFAULT_ANNOUNCEMENT_LIMIT: int = 7
        DEFAULT_DEADLINE_DAYS: int = 30

try:
    from src.auth import get_valid_cookies
except (ImportError, Exception):
    async def get_valid_cookies(force_refresh: bool = False, host: str | None = None) -> dict[str, str]:  # type: ignore
        return {}

from src.client import endpoints

try:
    from src.client.parsers.favorite_parser import parse_favorite_courses
except ImportError:
    def parse_favorite_courses(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("favorite_parser is not implemented yet")

try:
    from src.client.parsers.course_parser import parse_courses
except ImportError:
    def parse_courses(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("course_parser is not implemented yet")

try:
    from src.client.parsers.assignment_parser import parse_assignments
except ImportError:
    def parse_assignments(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("assignment_parser is not implemented yet")

try:
    from src.client.parsers.quiz_parser import parse_quizzes
except ImportError:
    def parse_quizzes(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("quiz_parser is not implemented yet")

try:
    from src.client.parsers.announcement_parser import parse_announcements
except ImportError:
    def parse_announcements(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("announcement_parser is not implemented yet")

try:
    from src.client.parsers.calendar_parser import parse_calendar_events
except ImportError:
    def parse_calendar_events(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("calendar_parser is not implemented yet")

try:
    from src.client.parsers.content_parser import parse_course_contents
except ImportError:
    def parse_course_contents(*args: Any, **kwargs: Any) -> list[Any]:  # type: ignore
        raise NotImplementedError("content_parser is not implemented yet")

from src.models import (
    Announcement,
    CalendarEvent,
    CourseDashboard,
    CourseMaterial,
    CourseSite,
    SakaiTask,
)

logger = logging.getLogger(__name__)


class SakaiClient:
    """
    Sakai LMS との非同期通信およびデータモデル変換を統括するクライアント。
    """

    def __init__(
        self,
        host: str = Config.SAKAI_HOST,
        timeout: float = Config.REQUEST_TIMEOUT,
        cache_ttl: float = Config.CACHE_TTL,
    ):
        """
        Args:
            host: Sakai ホスト名 (デフォルト: Config.SAKAI_HOST)
            timeout: HTTP リクエストのタイムアウト秒数 (デフォルト: Config.REQUEST_TIMEOUT)
            cache_ttl: 講義一覧・ツール情報のインメモリキャッシュ有効秒数 (デフォルト: Config.CACHE_TTL)
        """
        self.host = host
        self.timeout = timeout
        self.cache_ttl = cache_ttl

        self._http_client: httpx.AsyncClient | None = None
        self._client_lock: asyncio.Lock | None = None

        # 通信中リクエストの多重防止・合流機構 (Singleflight: cache_key -> asyncio.Future)
        self._inflight_requests: dict[str, asyncio.Future] = {}
        self._inflight_lock: asyncio.Lock | None = None

        # レスポンス TTL キャッシュ (cache_key -> (data, cached_at_monotonic))
        self._response_cache: dict[str, tuple[Any, float]] = {}
        self._cache_lock: asyncio.Lock | None = None

    def _get_client_lock(self) -> asyncio.Lock:
        if self._client_lock is None:
            self._client_lock = asyncio.Lock()
        return self._client_lock

    def _get_inflight_lock(self) -> asyncio.Lock:
        if self._inflight_lock is None:
            self._inflight_lock = asyncio.Lock()
        return self._inflight_lock

    def _get_cache_lock(self) -> asyncio.Lock:
        if self._cache_lock is None:
            self._cache_lock = asyncio.Lock()
        return self._cache_lock

    async def __aenter__(self) -> "SakaiClient":
        await self.open()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def open(self) -> None:
        """非同期 HTTP クライアントセッションを開始する (排他制御付き)。"""
        if self._http_client is None or self._http_client.is_closed:
            async with self._get_client_lock():
                if self._http_client is None or self._http_client.is_closed:
                    self._http_client = httpx.AsyncClient(
                        timeout=httpx.Timeout(self.timeout),
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/128.0.0.0 Safari/537.36"
                            ),
                            "Accept": "application/json, text/html, */*",
                        },
                        follow_redirects=True,
                    )

    async def close(self) -> None:
        """非同期 HTTP クライアントセッションを安全に終了する。"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ==========================================================================
    # 内部通信 & セッション管理メソッド
    # ==========================================================================

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        SessionManager から取得した Cookie を注入して HTTP リクエストを実行する。
        セッション失効を検知した場合は自動で再認証を行い、1 回のみ自動リトライする。
        """
        await self.open()
        assert self._http_client is not None

        url = f"https://{self.host}{endpoint}"
        cookies = await get_valid_cookies(host=self.host)

        resp = await self._http_client.request(
            method,
            url,
            params=params,
            headers=headers,
            cookies=cookies,
        )

        # セッション切れ検知 (401 または ログイン画面へのリダイレクト等。403 は権限不足のため除外)
        if self._is_session_expired(resp):
            # 強制再認証を実行
            cookies = await get_valid_cookies(force_refresh=True, host=self.host)
            resp = await self._http_client.request(
                method,
                url,
                params=params,
                headers=headers,
                cookies=cookies,
            )

        resp.raise_for_status()
        return resp

    def _is_session_expired(self, resp: httpx.Response) -> bool:
        """レスポンスからセッション失効を判定する (403はツール権限不足等のため失効とは見なさない)。"""
        if resp.status_code == 401:
            return True
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type and (
            "/portal/login" in str(resp.url) or "login" in resp.text[:500].lower()
        ):
            return True
        return False

    async def _fetch(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        ttl: float = 0.0,
        as_json: bool = True,
        default: Any = None,
    ) -> Any:
        """
        API / Portal との通信を行い、レスポンス（JSON または テキスト）を返却する。
        同一エンドポイントへの多重通信防止およびインメモリキャッシュを内部で自動処理する。
        通信エラー時に default が指定されている場合は、標準エラー出力に詳細を記録した上で default 値にフォールバックする。
        """
        param_key = tuple(sorted(params.items())) if params else ()
        cache_key = f"{'JSON' if as_json else 'TEXT'}:{method}:{endpoint}:{param_key}"
        now = time.monotonic()

        # 1. キャッシュの確認 (有効期限内なら即返却)
        if ttl > 0:
            async with self._get_cache_lock():
                if cache_key in self._response_cache:
                    data, cached_at = self._response_cache[cache_key]
                    if now - cached_at < ttl:
                        return data

        # 2. 通信中リクエストの多重防止 (先行タスクの完了をロック外で待機)
        async with self._get_inflight_lock():
            if cache_key in self._inflight_requests:
                fut = self._inflight_requests[cache_key]
                is_leader = False
            else:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                self._inflight_requests[cache_key] = fut
                is_leader = True

        if not is_leader:
            return await fut

        # 3. 実際の HTTP 通信を実行
        try:
            resp = await self._request(method, endpoint, params=params)
            result = resp.json() if as_json else resp.text

            # キャッシュ保存
            if ttl > 0:
                async with self._get_cache_lock():
                    self._response_cache[cache_key] = (result, time.monotonic())

            if not fut.done():
                fut.set_result(result)
            return result
        except httpx.HTTPStatusError as e:
            if default is not None:
                logger.warning(
                    f"Sakai API HTTP error: {method} {endpoint} (params={params}) -> HTTP {e.response.status_code}. "
                    f"Falling back to default value."
                )
                if not fut.done():
                    fut.set_result(default)
                return default
            if not fut.done():
                fut.set_exception(e)
            raise
        except BaseException as e:
            if default is not None and isinstance(e, Exception):
                logger.warning(
                    f"Sakai API communication error: {method} {endpoint} (params={params}) -> {e}. "
                    f"Falling back to default value."
                )
                if not fut.done():
                    fut.set_result(default)
                return default
            if not fut.done():
                fut.set_exception(e)
            raise
        finally:
            async with self._get_inflight_lock():
                self._inflight_requests.pop(cache_key, None)
            if fut.done() and not fut.cancelled():
                try:
                    fut.exception()
                except BaseException:
                    pass

    async def _get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        ttl: float = 0.0,
        default: Any = None,
    ) -> dict[str, Any]:
        """JSON レスポンスを取得する。"""
        return await self._fetch("GET", endpoint, params=params, ttl=ttl, as_json=True, default=default)

    async def _get_text(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        ttl: float = 0.0,
        default: Any = None,
    ) -> str:
        """HTML / テキストレスポンスを取得する。"""
        return await self._fetch("GET", endpoint, params=params, ttl=ttl, as_json=False, default=default)

    async def _get_all_courses_cached(self, force_refresh: bool = False) -> list[CourseSite]:
        """
        全講義一覧（お気に入りフラグ & tool_pages 付き）を取得する。
        """
        ttl = 0.0 if force_refresh else self.cache_ttl
        portal_task = self._get_text(endpoints.PORTAL, ttl=ttl)
        sites_task = self._get_json(endpoints.SITE_LIST, ttl=ttl)
        portal_html, sites_json = await asyncio.gather(portal_task, sites_task)

        fav_courses = parse_favorite_courses(portal_html, self.host)
        fav_site_ids = {c.id for c in fav_courses}

        return parse_courses(sites_json, self.host, favorite_site_ids=fav_site_ids)

    async def _resolve_site_context(
        self,
        site_id: str | None = None,
        favorites_only: bool = True,
    ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """
        指定条件に応じた (site_names, site_tool_pages) のマッピング辞書を解決する。
        お気に入り講義が 0 件の場合は、自動的に全講義を対象にフォールバックする。
        """
        courses = await self._get_all_courses_cached()

        if site_id:
            target_courses = [c for c in courses if c.id == site_id]
            if target_courses:
                site_names = {c.id: c.name for c in target_courses}
                site_tool_pages = {c.id: c.tool_pages for c in target_courses}
            else:
                site_names = {site_id: site_id}
                site_tool_pages = {}
            return site_names, site_tool_pages
        elif favorites_only:
            favs = [c for c in courses if c.is_favorite]
            # お気に入り未設定時のフォールバック
            target_courses = favs if len(favs) > 0 else courses
        else:
            target_courses = courses

        site_names = {c.id: c.name for c in target_courses}
        site_tool_pages = {c.id: c.tool_pages for c in target_courses}
        return site_names, site_tool_pages

    # ==========================================================================
    # 公開データ取得メソッド
    # ==========================================================================

    async def get_courses(self, favorites_only: bool = True) -> list[CourseSite]:
        """
        履修・所属している講義サイト一覧を取得する。

        Args:
            favorites_only: True の場合はお気に入り登録講義のみ、False の場合は全講義を返却 (デフォルト: True)

        Returns:
            list[CourseSite]: 講義サイトモデル一覧
        """
        courses = await self._get_all_courses_cached()
        if favorites_only:
            favs = [c for c in courses if c.is_favorite]
            return favs if len(favs) > 0 else courses
        return courses

    async def get_assignments(
        self,
        site_id: str | None = None,
        favorites_only: bool = True,
        assignment_id: str | None = None,
        include_details: bool = True,
    ) -> list[SakaiTask]:
        """
        課題一覧または個別課題詳細を取得する。

        Args:
            site_id: 特定講義で絞り込む場合のサイト ID (未指定時は対象全講義)
            favorites_only: True の場合はお気に入り講義の課題のみ取得 (デフォルト: True)
            assignment_id: 特定の 1 課題のみを取得する場合の課題 ID
            include_details: True の場合は指示文・添付ファイル詳細を含める (デフォルト: True)

        Returns:
            list[SakaiTask]: 課題タスクモデル一覧 (task_type=TaskType.ASSIGNMENT)
        """
        site_names, site_tool_pages = await self._resolve_site_context(site_id, favorites_only)
        data = await self._get_json(endpoints.ASSIGNMENT_MY)
        return parse_assignments(
            data=data,
            host=self.host,
            site_names=site_names,
            site_tool_pages=site_tool_pages,
            assignment_id=assignment_id,
            include_details=include_details,
        )

    async def get_quizzes(
        self,
        site_id: str | None = None,
        favorites_only: bool = True,
    ) -> list[SakaiTask]:
        """
        小テスト・クイズ一覧を取得する。対象講義の SAMIGO API を並行取得して統合する。

        Args:
            site_id: 特定講義で絞り込む場合のサイト ID (未指定時は対象全講義)
            favorites_only: True の場合はお気に入り講義のテストのみ取得 (デフォルト: True)

        Returns:
            list[SakaiTask]: テスト・クイズタスクモデル一覧 (task_type=TaskType.QUIZ)
        """
        site_names, site_tool_pages = await self._resolve_site_context(site_id, favorites_only)
        sem = asyncio.Semaphore(5)

        async def fetch_one(s_id: str, s_name: str, t_pages: dict[str, str]) -> list[SakaiTask]:
            async with sem:
                endpoint = endpoints.sam_pub_context(s_id)
                tool_page = t_pages.get("quiz")
                data = await self._get_json(endpoint, default={})
                return parse_quizzes(data, s_id, self.host, s_name, tool_page)

        tasks = [
            fetch_one(s_id, s_name, site_tool_pages.get(s_id, {}))
            for s_id, s_name in site_names.items()
        ]
        results = await asyncio.gather(*tasks)
        return [task for sublist in results for task in sublist]

    async def get_announcements(
        self,
        site_id: str | None = None,
        favorites_only: bool = True,
        announcement_id: str | None = None,
        n: int = Config.DEFAULT_ANNOUNCEMENT_LIMIT,
        include_details: bool = True,
    ) -> list[Announcement]:
        """
        お知らせ一覧または個別お知らせ詳細を取得する。

        Args:
            site_id: 特定講義で絞り込む場合のサイト ID (未指定時は全講義)
            favorites_only: True の場合はお気に入り講義のお知らせのみ取得 (デフォルト: True)
            announcement_id: 特定の 1 件のみを取得する場合のお知らせ ID
            n: 取得件数 (デフォルト: Config.DEFAULT_ANNOUNCEMENT_LIMIT)
            include_details: True の場合は本文・添付ファイル詳細を含める (デフォルト: True)

        Returns:
            list[Announcement]: お知らせモデル一覧
        """
        site_names, site_tool_pages = await self._resolve_site_context(site_id, favorites_only)
        fetch_limit = max(n * 5, 50) if favorites_only and not site_id else n
        endpoint = endpoints.ANNOUNCEMENT_USER if not site_id else endpoints.announcement_site(site_id)
        data = await self._get_json(endpoint, params={"n": fetch_limit}, default={})
        announcements = parse_announcements(
            data=data,
            host=self.host,
            site_names=site_names,
            site_tool_pages=site_tool_pages,
            announcement_id=announcement_id,
            include_details=include_details,
        )
        return announcements[:n]

    async def get_calendar_events(
        self,
        site_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        event_type: str | None = None,
    ) -> list[CalendarEvent]:
        """
        カレンダー予定一覧を取得する。

        Args:
            site_id: 特定講義で絞り込む場合のサイト ID (未指定時は全講義)
            start_date: 期間絞り込みの開始日時
            end_date: 期間絞り込みの終了日時
            event_type: イベント種別による絞り込み ("Assignment", "Quiz" 等)

        Returns:
            list[CalendarEvent]: カレンダーイベント一覧
        """
        site_names, site_tool_pages = await self._resolve_site_context(site_id, favorites_only=False)
        endpoint = endpoints.CALENDAR_MY if not site_id else endpoints.calendar_site(site_id)
        data = await self._get_json(endpoint, default={})
        events = parse_calendar_events(
            data=data,
            host=self.host,
            site_names=site_names,
            site_tool_pages=site_tool_pages,
            event_type=event_type,
        )
        if start_date:
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            else:
                start_date = start_date.astimezone(timezone.utc)
            events = [e for e in events if e.start_time and e.start_time >= start_date]
        if end_date:
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            else:
                end_date = end_date.astimezone(timezone.utc)
            events = [e for e in events if e.start_time and e.start_time <= end_date]
        return events

    async def get_course_materials(
        self,
        site_id: str,
        files_only: bool = False,
    ) -> list[CourseMaterial]:
        """
        指定講義の授業資料・配布ファイル一覧を取得する。

        Args:
            site_id: 講義サイト ID (必須)
            files_only: True の場合はフォルダ項目を除外し、ファイルのみ返却 (デフォルト: False)

        Returns:
            list[CourseMaterial]: 講義資料・配布ファイル一覧
        """
        courses = await self._get_all_courses_cached()
        course = next((c for c in courses if c.id == site_id), None)
        site_name = course.name if course else None
        tool_page = course.tool_pages.get("resource") if course else None

        endpoint = endpoints.content_site(site_id)
        data = await self._get_json(endpoint, default={})
        return parse_course_contents(
            data=data,
            site_id=site_id,
            host=self.host,
            site_name=site_name,
            resource_tool_page_url=tool_page,
            files_only=files_only,
        )

    async def get_upcoming_deadlines(
        self,
        days: int = Config.DEFAULT_DEADLINE_DAYS,
        favorites_only: bool = True,
    ) -> list[SakaiTask]:
        """
        直近 N 日以内に締切のある未提出課題および小テストを統合し、締切日時昇順でソートして取得する。
        ユーザーから「直近の課題を教えて」と尋ねられた際に最適な統合メソッド。

        Args:
            days: 何日後までの締切を対象とするか (デフォルト: Config.DEFAULT_DEADLINE_DAYS)
            favorites_only: True の場合はお気に入り講義のみ対象 (デフォルト: True)

        Returns:
            list[SakaiTask]: 締切昇順でソートされた未提出タスク一覧
        """
        now = datetime.now(timezone.utc)
        limit_date = now + timedelta(days=days)

        assignments_task = self.get_assignments(favorites_only=favorites_only, include_details=False)
        quizzes_task = self.get_quizzes(favorites_only=favorites_only)
        assignments, quizzes = await asyncio.gather(assignments_task, quizzes_task)

        all_tasks = assignments + quizzes
        upcoming: list[SakaiTask] = []
        for t in all_tasks:
            if t.is_submitted:
                continue
            if t.due_date is not None:
                if now <= t.due_date <= limit_date:
                    upcoming.append(t)

        upcoming.sort(key=lambda x: x.due_date or datetime.max.replace(tzinfo=timezone.utc))
        return upcoming

    async def get_course_dashboard(
        self,
        site_id: str,
    ) -> CourseDashboard:
        """
        指定講義の総合状況（課題・小テスト・直近お知らせ・授業資料）を並行一括取得してサマリーを生成する。

        Args:
            site_id: 講義サイト ID (必須)

        Returns:
            CourseDashboard: 講義名および各データの総合サマリーモデル
        """
        site_names, _ = await self._resolve_site_context(site_id, favorites_only=False)
        site_name = site_names.get(site_id, "名称未設定講義")

        assignments_task = self.get_assignments(site_id=site_id)
        quizzes_task = self.get_quizzes(site_id=site_id)
        announcements_task = self.get_announcements(site_id=site_id, n=5)
        materials_task = self.get_course_materials(site_id=site_id)

        assignments, quizzes, announcements, materials = await asyncio.gather(
            assignments_task,
            quizzes_task,
            announcements_task,
            materials_task,
        )

        return CourseDashboard(
            site_id=site_id,
            site_name=site_name,
            assignments=assignments,
            quizzes=quizzes,
            announcements=announcements,
            materials=materials,
        )

    async def download_material(
        self,
        url: str,
        save_path: str,
    ) -> str:
        """
        Sakai 内の授業資料や課題添付ファイルをローカルにダウンロード保存する。
        FastMCP の stdio (JSON-RPC) 通信で安全に扱えるよう、保存先パスとファイルサイズ情報を返却する。

        Args:
            url: Sakai 相対パス (/access/content/...) または 完全修飾 URL
            save_path: 保存先のローカルファイルパス (必須)

        Returns:
            str: ダウンロード完了メッセージ (保存先絶対パス、サイズ等)
        """
        parsed = urlparse(url)
        path = parsed.path if parsed.path.startswith("/") else f"/{parsed.path}"
        endpoint = f"{path}?{parsed.query}" if parsed.query else path

        resp = await self._request("GET", endpoint)
        content = resp.content

        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

        return f"ファイルが正常に保存されました: {p.resolve()} ({len(content)} バイト)"
