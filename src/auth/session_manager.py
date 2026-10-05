import asyncio
import logging
import os
from pathlib import Path
import sys
import time

from src.config import Config
from src.auth import cookie_storage, session_checker

logger = logging.getLogger(__name__)


SESSION_CACHE_TTL: float = 300.0  # 5分

_auth_lock: asyncio.Lock | None = None

# host -> Sakai用Cookie
_cached_sakai_cookies: dict[str, dict[str, str]] = {}

# host -> 最後に認証成功した時刻
_last_auth_success_times: dict[str, float] = {}

# host -> 最後に認証失敗した時刻
_last_auth_error_times: dict[str, float] = {}


def _get_auth_lock() -> asyncio.Lock:
    """
    認証処理用の asyncio.Lock を遅延生成して返す。
    """
    global _auth_lock

    if _auth_lock is None:
        _auth_lock = asyncio.Lock()

    return _auth_lock


async def get_valid_cookies(
    force_refresh: bool = False,
    host: str | None = None,
) -> dict[str, str]:
    """
    有効な Sakai Cookie を取得する。

    通常時:
        1. 有効なインメモリキャッシュがあれば即返す
        2. 保存済み Cookie を読み込む
        3. Sakai に問い合わせて有効性を確認する
        4. 無効なら別プロセスで WebView 認証を行う
        5. 新しい Cookie を読み込み、キャッシュして返す

    force_refresh=True:
        保存済みセッションやキャッシュを使わず、
        WebView による再認証を行う。

    Raises:
        RuntimeError:
            認証キャンセル、WebView 認証失敗、
            または Cookie を取得できなかった場合。
    """

    global _cached_sakai_cookies
    global _last_auth_success_times
    global _last_auth_error_times
    host = host or Config.SAKAI_HOST
    # --------------------------------------------------
    # 1. Fast Path
    # --------------------------------------------------

    now = time.monotonic()

    if not force_refresh and host in _cached_sakai_cookies:
        last_success = _last_auth_success_times.get(host, 0.0)

        if now - last_success < SESSION_CACHE_TTL:
            return _cached_sakai_cookies[host]

    # --------------------------------------------------
    # 2. 認証処理は同時に1タスクだけ
    # --------------------------------------------------

    async with _get_auth_lock():
        now = time.monotonic()

        # ----------------------------------------------
        # 認証失敗直後なら WebView の連続起動を防ぐ
        # ----------------------------------------------

        last_error = _last_auth_error_times.get(host, 0.0)

        if (
            now - last_error
            < Config.AUTH_COOLDOWN_SECONDS
        ):
            raise RuntimeError(
                "直前のログイン認証がキャンセルまたは失敗したため、"
                "クールダウン中です。"
            )

        # ----------------------------------------------
        # Double-Checked Locking
        #
        # Lock待機中に別タスクが認証を完了した可能性があるので
        # もう一度キャッシュを見る
        # ----------------------------------------------

        if not force_refresh and host in _cached_sakai_cookies:
            last_success = _last_auth_success_times.get(
                host,
                0.0,
            )

            if now - last_success < SESSION_CACHE_TTL:
                return _cached_sakai_cookies[host]

        # --------------------------------------------------
        # 3. 保存済み Cookie を確認
        # --------------------------------------------------

        if not force_refresh:
            cookies = cookie_storage.load_sakai_cookies(
                host=host,
            )

            if cookies:
                valid = await session_checker.is_session_valid(
                    cookies,
                    host=host,
                )

                if valid:
                    _cached_sakai_cookies[host] = cookies
                    _last_auth_success_times[host] = (
                        time.monotonic()
                    )

                    return cookies

        # --------------------------------------------------
        # 4. Cookieがない / 無効 / 強制更新
        #    → WebViewログインを別プロセスで実行
        # --------------------------------------------------

        server_script = Path(__file__).resolve().parent.parent / "server.py"
        project_root = server_script.parent.parent

        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(project_root)
        )
        embed_dll = project_root / "python-embed" / "python312.dll"
        if embed_dll.exists():
            env["PYTHONNET_PYDLL"] = str(embed_dll)
            env["PYTHONHOME"] = str(embed_dll.parent)

        if getattr(sys, "frozen", False):
            # PyInstaller等で単一バイナリ化されている場合
            cmd = [
                sys.executable,
                "--login",
                "--host",
                host,
            ]
        else:
            # Pythonスクリプトとして実行している場合
            cmd = [
                sys.executable,
                str(server_script),
                "--login",
                "--host",
                host,
            ]

        logger.info("Starting WebView login subprocess: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_root),
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await proc.communicate()
        returncode = proc.returncode

        # --------------------------------------------------
        # 5. WebView認証失敗
        # --------------------------------------------------

        if returncode != 0:
            _last_auth_error_times[host] = time.monotonic()
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
            error_detail = stderr_text or stdout_text or "ログインウィンドウが閉じられたか、認証に失敗しました。"

            logger.error(
                "WebView login subprocess failed with code %s.\nSTDERR: %s\nSTDOUT: %s",
                returncode,
                stderr_text,
                stdout_text,
            )

            raise RuntimeError(
                f"WebViewログイン認証に失敗しました (終了コード: {returncode})。\n"
                f"詳細: {error_detail}"
            )

        logger.info("WebView login subprocess completed successfully.")

        # --------------------------------------------------
        # 6. 子プロセスが保存した新しい Cookie を読み込む
        # --------------------------------------------------

        cookies = cookie_storage.load_sakai_cookies(
            host=host,
        )

        if not cookies:
            _last_auth_error_times[host] = time.monotonic()

            raise RuntimeError(
                "Sakai のセッション Cookie を取得できませんでした。"
            )

        # --------------------------------------------------
        # 7. キャッシュ更新
        # --------------------------------------------------

        _cached_sakai_cookies[host] = cookies
        _last_auth_success_times[host] = time.monotonic()

        # 前回失敗情報があれば消しておく
        _last_auth_error_times.pop(host, None)

        return cookies


async def refresh_session(
    host: str | None = None,
) -> dict[str, str]:
    """
    保存済み Cookie やキャッシュを使わず、
    WebView で強制的に再認証する。
    """
    host = host or Config.SAKAI_HOST
    return await get_valid_cookies(
        force_refresh=True,
        host=host,
    )


def clear_session(
    host: str | None = None,
) -> None:
    """
    インメモリ Cookie キャッシュと、
    保存済み session.enc を削除する。
    """

    global _cached_sakai_cookies
    global _last_auth_success_times
    global _last_auth_error_times

    if host is not None:
        _cached_sakai_cookies.pop(host, None)
        _last_auth_success_times.pop(host, None)
        _last_auth_error_times.pop(host, None)

    else:
        _cached_sakai_cookies.clear()
        _last_auth_success_times.clear()
        _last_auth_error_times.clear()

    cookie_storage.delete_cookies()