"""JS communication bridge module for pywebview."""

from typing import Any
import webview
from src.config import AIPolicyMode, AppConfigData, Config
from src.gui.data_builder import SettingsUIData


class SettingsApi:
    """pywebview (JavaScript) から非同期に呼び出される API クラス"""

    def __init__(self, initial_data: SettingsUIData):
        self._initial_data = initial_data
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """バインドされた Window インスタンスを保持する"""
        self._window = window

    def get_initial_data(self) -> dict[str, Any]:
        """設定画面起動時に JS から呼ばれ、SettingsUIData を即時返却 (0ms)"""
        return self._initial_data.model_dump()

    def save_settings(self, data: dict[str, Any]) -> bool:
        """ユーザーが「保存」をクリックした際に呼ばれ、config.json を更新してウィンドウを閉じる"""
        # JS から渡された courses 配列を policies 辞書 (site_id -> AIPolicyMode) にマッピング変換
        policies = {}
        for c in data.get("courses", []):
            if "id" in c and "current_policy" in c:
                policies[c["id"]] = AIPolicyMode(c["current_policy"])

        app_config = AppConfigData(
            sakai_host=data.get("sakai_host", Config.SAKAI_HOST),
            policies=policies,
            default_deadline_days=int(data.get("default_deadline_days", Config.DEFAULT_DEADLINE_DAYS)),
            default_announcement_limit=int(data.get("default_announcement_limit", Config.DEFAULT_ANNOUNCEMENT_LIMIT)),
            request_timeout=float(data.get("request_timeout", Config.REQUEST_TIMEOUT)),
            cache_ttl=float(data.get("cache_ttl", Config.CACHE_TTL)),
        )
        Config.save(app_config)
        if self._window:
            self._window.destroy()
        return True

    def close_window(self) -> None:
        """ウィンドウを閉じる (キャンセル用)"""
        if self._window:
            self._window.destroy()

    def cancel(self) -> None:
        """ウィンドウを閉じる (キャンセル用エイリアス)"""
        self.close_window()


class InitialSetupApi:
    """初回大学プリセット選択ダイアログ用 JS API クラス"""

    def __init__(self, presets: dict[str, str], current_host: str):
        self._presets = presets
        self._current_host = current_host
        self.selected_host: str | None = None
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        """バインドされた Window インスタンスを保持する"""
        self._window = window

    def get_presets(self) -> dict[str, Any]:
        """大学プリセット一覧と現在のホスト名を返却"""
        return {
            "presets": self._presets,
            "current_host": self._current_host,
        }

    def select_host(self, host: str) -> bool:
        """大学ドメインを選択・入力して保存"""
        self.selected_host = host.strip()
        if self._window:
            self._window.destroy()
        return True

    def close_window(self) -> None:
        """ウィンドウを閉じる (キャンセル用)"""
        if self._window:
            self._window.destroy()

    def cancel(self) -> None:
        """ウィンドウを閉じる (キャンセル用エイリアス)"""
        self.close_window()
