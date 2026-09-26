import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any
from platformdirs import user_data_dir
from pydantic import BaseModel, Field


# ==============================================================================
# 講義別 AI 利用ポリシー定義
# ==============================================================================

class AIPolicyMode(str, Enum):
    """講義ごとの AI アシスタント利用権限ポリシー"""
    ALLOW_ALL = "allow_all"          # 全て (完全アクセス: 資料DL・課題指示文・締切)
    TEXT_ONLY = "text_only"          # 強   (ファイルDL禁止 / テキスト対話・指示文許可)
    SCHEDULE_ONLY = "schedule_only"  # 弱   (締切・予定のみ / 指示文・本文・資料マスク)
    BLOCKED = "blocked"              # 無効 (完全除外 / 講義の存在を隠蔽)


# ==============================================================================
# ユーザー設定データモデル (AppConfigData)
# ==============================================================================

class AppConfigData(BaseModel):
    """config.json に保存・復元されるスキーマ定義"""
    sakai_host: str = "tact.ac.thers.ac.jp"
    policies: dict[str, AIPolicyMode] = Field(default_factory=dict)
    default_deadline_days: int = 30
    default_announcement_limit: int = 7
    request_timeout: float = 15.0
    cache_ttl: float = 300.0


# ==============================================================================
# 設定・定数公開クラス (Config)
# ==============================================================================

class Config:
    """
    アプリケーション全体の設定・定数を一元公開するクラス。
    各モジュールは `from src.config import Config` でインポートして利用する。
    """

    # 1. 不変のシステム定数 & パス (platformdirs 利用)
    APP_DATA_DIR: Path = Path(user_data_dir("sakai-tasks-mcp", appauthor=False))
    CONFIG_FILE_PATH: Path = APP_DATA_DIR / "config.json"
    SESSION_FILE_PATH: Path = APP_DATA_DIR / "session.enc"
    WEBVIEW_DATA_DIR: Path = APP_DATA_DIR / "webview_profile"

    AUTH_COOLDOWN_SECONDS: float = 3.0       # 認証失敗・キャンセル直後の連打防止クールダウン (秒)
    SESSION_CHECK_TIMEOUT: float = 5.0       # セッション確認 API タイムアウト (秒)
    WEBVIEW_AUTO_TIMEOUT: float = 5.0        # WebView 自動素通り猶予秒数 (秒)
    AUTH_MAX_TIMEOUT: float = 300.0          # WebView ログイン待機最大タイムアウト (秒)
    WEBVIEW_WINDOW_WIDTH: int = 800          # ウィンドウ横幅 (px)
    WEBVIEW_WINDOW_HEIGHT: int = 600         # ウィンドウ高さ (px)

    DEFAULT_POLICY: AIPolicyMode = AIPolicyMode.TEXT_ONLY  # デフォルトポリシー (強: ファイルDL禁止)

    UNIVERSITY_PRESETS: dict[str, str] = {
        "名古屋大学 (TACT)": "tact.ac.thers.ac.jp",
        "京都大学 (PandA)": "panda.ecs.kyoto-u.ac.jp",
        "岡山大学 (Moodle/Sakai)": "sakai.okayama-u.ac.jp",
        "法政大学 (学習支援システム)": "hoppii.hosei.ac.jp",
    }

    # 2. 動的ユーザー設定値 (実行中に随時同期される)
    SAKAI_HOST: str = "tact.ac.thers.ac.jp"
    DEFAULT_DEADLINE_DAYS: int = 30
    DEFAULT_ANNOUNCEMENT_LIMIT: int = 7
    REQUEST_TIMEOUT: float = 15.0
    CACHE_TTL: float = 300.0
    POLICIES: dict[str, AIPolicyMode] = {}

    # 3. 内部状態 (mtime ベースの自動再読込用)
    _last_loaded_mtime: float = 0.0

    # 4. ライフサイクル & 実行中リロード・保存メソッド
    @classmethod
    def apply_data(cls, data: AppConfigData) -> None:
        """AppConfigData をクラス変数に一括反映する"""
        cls.SAKAI_HOST = data.sakai_host
        cls.POLICIES = data.policies
        cls.DEFAULT_DEADLINE_DAYS = data.default_deadline_days
        cls.DEFAULT_ANNOUNCEMENT_LIMIT = data.default_announcement_limit
        cls.REQUEST_TIMEOUT = data.request_timeout
        cls.CACHE_TTL = data.cache_ttl

    @classmethod
    def check_and_reload(cls) -> None:
        """config.json が外部 (別プロセス等) で更新されていれば自動再読込する"""
        if cls.CONFIG_FILE_PATH.exists():
            try:
                current_mtime = cls.CONFIG_FILE_PATH.stat().st_mtime
                if current_mtime > cls._last_loaded_mtime:
                    cls.load()
            except Exception:
                pass

    @classmethod
    def init(cls, cli_host: str | None = None) -> None:
        """
        サーバー起動時に main() から 1 回呼び出し、設定を初期化・確定する。
        stdio タイムアウトを防止するためブロッキング GUI は起動せず、
        1. CLI引数 -> 2. 環境変数 -> 3. config.json -> 4. デフォルト の優先度で確定する。
        """
        data = cls.load()
        if cli_host:
            data.sakai_host = cli_host
        elif env_host := os.environ.get("SAKAI_HOST"):
            data.sakai_host = env_host

        if not cls.CONFIG_FILE_PATH.exists():
            # 初回起動時: config.json を生成
            cls.save(data)

        cls.apply_data(data)

    @classmethod
    def load(cls) -> AppConfigData:
        """config.json をディスクから読み込み、クラス変数も最新化して返す (実行中随時呼び出し可能)"""
        if not cls.CONFIG_FILE_PATH.exists():
            data = AppConfigData()
        else:
            try:
                with open(cls.CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = AppConfigData.model_validate_json(f.read())
                cls._last_loaded_mtime = cls.CONFIG_FILE_PATH.stat().st_mtime
            except Exception:
                data = AppConfigData()

        cls.apply_data(data)
        return data

    @classmethod
    def save(cls, data: AppConfigData | None = None) -> None:
        """設定を config.json に書き込み、即座にクラス変数を同期する (実行中随時呼び出し可能)"""
        cls.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if data is None:
            data = AppConfigData(
                sakai_host=cls.SAKAI_HOST,
                policies=cls.POLICIES,
                default_deadline_days=cls.DEFAULT_DEADLINE_DAYS,
                default_announcement_limit=cls.DEFAULT_ANNOUNCEMENT_LIMIT,
                request_timeout=cls.REQUEST_TIMEOUT,
                cache_ttl=cls.CACHE_TTL,
            )
        with open(cls.CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json(indent=2))
        if cls.CONFIG_FILE_PATH.exists():
            cls._last_loaded_mtime = cls.CONFIG_FILE_PATH.stat().st_mtime
        cls.apply_data(data)

    @classmethod
    def get_course_policy(cls, site_id: str) -> AIPolicyMode:
        """
        指定された講義サイトの AI 利用ポリシーを取得する。
        別プロセス (open_settings) による変更を即時反映するため、呼び出し時に mtime チェックを行う。
        未設定時はデフォルト (TEXT_ONLY: 強)。
        """
        cls.check_and_reload()
        return cls.POLICIES.get(site_id, cls.DEFAULT_POLICY)
