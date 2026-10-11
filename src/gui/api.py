"""JS communication bridge module for pywebview."""

from typing import Any
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


class SettingsApi:
    """pywebview (JavaScript) から非同期に呼び出される API クラス"""

    def __init__(self, initial_data: SettingsUIData):
        self._initial_data = initial_data

    def get_initial_data(self) -> dict[str, Any]:
        """設定画面起動時に JS から呼ばれ、SettingsUIData を即時返却 (0ms)"""
        return self._initial_data.model_dump()

    def save_settings(self, data: dict[str, Any]) -> bool:
        """設定変更の入力停止から 300ms 後等に呼ばれ、config.json を更新する"""
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
        return True
