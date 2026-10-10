"""Window launch and lifecycle management module for settings GUI."""

import asyncio
from pathlib import Path
import sys
import webview

from src.config import Config
from src.gui.api import SettingsApi
from src.gui.data_builder import build_settings_ui_data


def show_settings_window() -> None:
    """
    ユーザー詳細設定画面 (WebView GUI) を起動する。
    別プロセス (--settings) からメインスレッドで直接呼び出される。
    Sakai ホスト未設定時は講義一覧取得をスキップして起動し、
    設定変更は自動保存され、ユーザーはOS標準の[✕]ボタンでウィンドウを閉じる。
    """
    template_path = Path(__file__).parent / "templates" / "settings.html"

    # 1. UI データの事前構築 (未設定時は空の講義一覧が返る)
    try:
        ui_data = asyncio.run(build_settings_ui_data())
    except Exception as e:
        print(f"設定データの読み込みに失敗しました: {e}", file=sys.stderr)
        return

    # 2. JS 通信ブリッジを初期化
    api = SettingsApi(initial_data=ui_data)

    # 3. 設定画面ウィンドウをメインスレッドで直接生成して起動
    window = webview.create_window(
        title="Sakai Tasks MCP 設定",
        url=template_path.as_uri(),
        js_api=api,
        width=Config.WEBVIEW_WINDOW_WIDTH,
        height=Config.WEBVIEW_WINDOW_HEIGHT,
        resizable=True,
    )

    # 4. webview.start はメインスレッドで起動 (OS ネイティブの[✕]ボタンで終了)
    webview.start(
        storage_path=str(Config.WEBVIEW_DATA_DIR),
        private_mode=False,
    )