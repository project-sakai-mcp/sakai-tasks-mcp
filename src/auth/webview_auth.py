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
    host: str | None = None,
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
    host = host or Config.SAKAI_HOST
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
        """
        result: list[dict[str, Any]] = []

        if raw_cookies is None:
            return result

        items = raw_cookies if isinstance(raw_cookies, list) else [raw_cookies]
        for item in items:
            # 1. http.cookies.SimpleCookie (辞書ライク: {name: Morsel})
            if hasattr(item, "items") and callable(getattr(item, "items")):
                for name, morsel in item.items():
                    try:
                        result.append(
                            {
                                "name": name,
                                "value": morsel.value if hasattr(morsel, "value") else str(morsel),
                                "domain": morsel["domain"] if hasattr(morsel, "__getitem__") and "domain" in morsel else "",
                                "path": morsel["path"] if hasattr(morsel, "__getitem__") and "path" in morsel else "/",
                                "httponly": bool(morsel["httponly"]) if hasattr(morsel, "__getitem__") and "httponly" in morsel else False,
                                "secure": bool(morsel["secure"]) if hasattr(morsel, "__getitem__") and "secure" in morsel else False,
                            }
                        )
                    except Exception:
                        continue
            # 2. Morsel 単体の場合
            elif hasattr(item, "key") and hasattr(item, "value"):
                try:
                    result.append(
                        {
                            "name": item.key,
                            "value": item.value,
                            "domain": item["domain"] if hasattr(item, "__getitem__") and "domain" in item else "",
                            "path": item["path"] if hasattr(item, "__getitem__") and "path" in item else "/",
                            "httponly": bool(item["httponly"]) if hasattr(item, "__getitem__") and "httponly" in item else False,
                            "secure": bool(item["secure"]) if hasattr(item, "__getitem__") and "secure" in item else False,
                        }
                    )
                except Exception:
                    continue
            # 3. dict の場合
            elif isinstance(item, dict):
                result.append(
                    {
                        "name": item.get("name", ""),
                        "value": item.get("value", ""),
                        "domain": item.get("domain", ""),
                        "path": item.get("path", "/"),
                        "httponly": bool(item.get("httponly", False)),
                        "secure": bool(item.get("secure", False)),
                    }
                )

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