"""
    initial_cookieはげwebviewの機能を使うのが良いか明示的に再注入するのが良いかという問題と、
    webviewの違いの問題があります。
    なくても動くので一回未実装のまま置いておいてあとで調整する方針を採用しました。
"""
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import webview

from src.config import Config

def authenticate_via_webview(
    host: str = Config.SAKAI_HOST,
    profile_dir: Path = Config.WEBVIEW_DATA_DIR,
    initial_cookies: list[dict[str, Any]] | None = None,
    auto_timeout_seconds: float = Config.WEBVIEW_AUTO_TIMEOUT,
) -> list[dict[str, Any]]:
    """
    WebView を起動して Sakai のログインを行い、
    ログイン成功時の Cookie 一覧を返す。

    Returns:
        list[dict[str, Any]]:
            ログイン成功時は Cookie 一覧。
            ユーザー中断・タイムアウト・取得失敗時は []。
    """

    cookies_result: list[dict[str, Any]] = []

    login_url = f"https://{host}/portal/login"

    def is_login_success(url: str) -> bool:
        """
        Sakai の /portal/login を抜け、
        /portal またはその配下へ遷移したらログイン成功とみなす。
        """
        portal_prefix = f"https://{host}/portal"

        return (
            url.startswith(portal_prefix)
            and not url.startswith(login_url)
        )

    def is_stale_or_idp_error(url: str, title: str) -> bool:
        """
        外部 IdP / Shibboleth 上で認証処理がタイムアウトした
        可能性がある状態を検出する。
        """
        netloc = urlparse(url).netloc

        # Sakai 自身のページなら対象外
        if not netloc or netloc == host:
            return False

        return (
            "/POST/SSO" in url
            or "Stale Request" in title
            or "エラー" in title
        )

    def normalize_cookies(raw_cookies: Any) -> list[dict[str, Any]]:
        """
        pywebview が返す Cookie を、
        cookie_storage.py が扱う list[dict] に変換する。

        pywebview / OS WebView の実際の Cookie 型に応じて
        今後調整する可能性がある。
        """
        result: list[dict[str, Any]] = []

        if raw_cookies is None:
            return result

        for cookie in raw_cookies:
            # SimpleCookie / Morsel 系を想定
            try:
                result.append(
                    {
                        "name": cookie.key,
                        "value": cookie.value,
                        "domain": cookie["domain"],
                        "path": cookie["path"],
                        "httponly": bool(cookie["httponly"]),
                        "secure": bool(cookie["secure"]),
                    }
                )
            except (AttributeError, KeyError, TypeError):
                # 実際の pywebview の Cookie 型が異なる場合は
                # 統合時にここを調整する
                continue

        return result

    def watch_loop(window: webview.Window) -> None:
        nonlocal cookies_result

        started_at = time.monotonic()
        shown = False
        retried_stale = False

        while True:
            time.sleep(0.2)

            elapsed = time.monotonic() - started_at

            try:
                url = window.get_current_url() or ""
            except Exception:
                # ユーザーがウィンドウを閉じた場合など
                return

            try:
                title = window.evaluate_js("document.title") or ""
            except Exception:
                title = ""

            # 1. ログイン成功
            if is_login_success(url):
                try:
                    raw_cookies = window.get_cookies()
                    cookies_result = normalize_cookies(raw_cookies)
                finally:
                    try:
                        window.destroy()
                    except Exception:
                        pass

                return

            # 2. Shibboleth / IdP タイムアウト救済
            if (
                not retried_stale
                and is_stale_or_idp_error(url, title)
            ):
                retried_stale = True

                time.sleep(0.5)

                try:
                    window.load_url(login_url)
                except Exception:
                    return

                continue

            # 3. 自動ログインできなければ画面表示
            if (
                elapsed >= auto_timeout_seconds
                and not shown
            ):
                try:
                    window.show()
                    shown = True
                except Exception:
                    return

            # 4. 最大待機時間
            if elapsed >= Config.AUTH_MAX_TIMEOUT:
                try:
                    window.destroy()
                except Exception:
                    pass

                return

    # WebView プロファイル保存先を準備
    profile_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    window = webview.create_window(
        title="Sakai ログイン",
        url=login_url,
        width=Config.WEBVIEW_WINDOW_WIDTH,
        height=Config.WEBVIEW_WINDOW_HEIGHT,
        hidden=True,
    )

    # TODO:
    # initial_cookies の WebView への明示的な注入は、
    # 使用する OS / WebView backend の Cookie API を確認して実装する。
    #
    # 現状は storage_path + private_mode=False による
    # WebView プロファイルの永続化を利用する。

    webview.start(
        watch_loop,
        window,
        storage_path=str(profile_dir),
        private_mode=False,
    )

    return cookies_result