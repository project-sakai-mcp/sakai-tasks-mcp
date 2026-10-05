"""JS communication bridge module for pywebview."""

import threading
from typing import Any
import webview
from src.config import AIPolicyMode, AppConfigData, Config
from src.gui.data_builder import SettingsUIData


def _sanitize_host(host: str) -> str:
    """ホスト名からプロトコルやパスを除去して正規化する"""
    clean_host = host.strip()
    if clean_host.startswith("https://"):
        clean_host = clean_host[len("https://"):]
    elif clean_host.startswith("http://"):
        clean_host = clean_host[len("http://"):]
    return clean_host.split("/")[0].strip()


class _CloseRequestApi:
    """API の JS 返答が完了するまで GUI ループを維持するための終了通知。"""

    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self.close_event = threading.Event()
        self._close_request_thread: threading.Thread | None = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window
        # タイトルバーから閉じた場合も、終了監視スレッドを残さない。
        window.events.closed += self.close_event.set

    def _request_close(self) -> None:
        self._close_request_thread = threading.current_thread()
        self.close_event.set()

    def close_window(self) -> None:
        """API の返答完了後に閉じるよう通知する (キャンセル用)。"""
        self._request_close()

    def cancel(self) -> None:
        """キャンセル用エイリアス。"""
        self.close_window()


class SettingsApi(_CloseRequestApi):
    """pywebview (JavaScript) から非同期に呼び出される API クラス"""

    def __init__(self, initial_data: SettingsUIData):
        super().__init__()
        self._initial_data = initial_data

    def get_initial_data(self) -> dict[str, Any]:
        """設定画面起動時に JS から呼ばれ、SettingsUIData を即時返却 (0ms)"""
        return self._initial_data.model_dump()

    def save_settings(self, data: dict[str, Any]) -> bool:
        """ユーザーが「保存」をクリックした際に呼ばれ、config.json を更新し、返答完了後の閉鎖を要求する"""
        policies = {}
        for c in data.get("courses", []):
            if "id" in c and "current_policy" in c:
                policies[c["id"]] = AIPolicyMode(c["current_policy"])

        raw_host = str(data.get("sakai_host", ""))
        sakai_host = _sanitize_host(raw_host) or Config.SAKAI_HOST

        app_config = AppConfigData(
            sakai_host=sakai_host,
            policies=policies,
            default_deadline_days=int(data.get("default_deadline_days") or Config.DEFAULT_DEADLINE_DAYS),
            default_announcement_limit=int(data.get("default_announcement_limit") or Config.DEFAULT_ANNOUNCEMENT_LIMIT),
            request_timeout=float(data.get("request_timeout") or Config.REQUEST_TIMEOUT),
            cache_ttl=float(data.get("cache_ttl") or Config.CACHE_TTL),
        )
        Config.save(app_config)
        self._request_close()
        return True


class InitialSetupApi(_CloseRequestApi):
    """初回大学プリセット選択ダイアログ用 JS API クラス"""

    def __init__(self, presets: dict[str, str], current_host: str):
        super().__init__()
        self._presets = presets
        self._current_host = current_host
        self.selected_host: str | None = None

    def get_presets(self) -> dict[str, Any]:
        """大学プリセット一覧と現在のホスト名を返却"""
        return {
            "presets": self._presets,
            "current_host": self._current_host,
        }

    def select_host(self, host: str) -> bool:
        """大学ドメインを選択し、返答完了後の閉鎖を要求する。"""
        self.selected_host = _sanitize_host(host)
        self._request_close()
        return True
