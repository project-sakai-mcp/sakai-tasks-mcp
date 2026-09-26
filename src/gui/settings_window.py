"""Window launch and lifecycle management module for settings GUI."""

import asyncio
from pathlib import Path
import sys
import webview

from src.config import Config
from src.gui.api import InitialSetupApi, SettingsApi
from src.gui.data_builder import build_settings_ui_data


def show_settings_window() -> None:
    """
    ユーザー詳細設定画面 (WebView GUI) を起動する。
    別プロセス (--settings) からメインスレッドで直接呼び出される。
    起動前にセッション確認および UI データ構築 (SettingsUIData) を同期完了させ、
    設定画面 HTML (settings.html) を即座に完全描画する。
    """
    template_path = Path(__file__).parent / "templates" / "settings.html"

    # 1. UI データの事前構築 (未ログイン時は内部で get_valid_cookies が呼ばれ、必要に応じ WebView ログインが完了)
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
    api.set_window(window)

    # webview.start はメインスレッドで起動 (OS 制約遵守)
    webview.start(storage_path=str(Config.WEBVIEW_DATA_DIR), private_mode=False)


def show_initial_setup_window() -> str | None:
    """
    初回起動時やインストーラ、CLI (--setup) から呼び出される大学プリセット選択ダイアログ。
    """
    template_path = Path(__file__).parent / "templates" / "initial_setup.html"
    config = Config.load()
    api = InitialSetupApi(presets=Config.UNIVERSITY_PRESETS, current_host=config.sakai_host)

    window = webview.create_window(
        title="Sakai Tasks MCP - 初期セットアップ",
        url=template_path.as_uri(),
        js_api=api,
        width=500,
        height=400,
        resizable=False,
    )
    api.set_window(window)

    webview.start(storage_path=str(Config.WEBVIEW_DATA_DIR), private_mode=False)

    if api.selected_host:
        config.sakai_host = api.selected_host
        Config.save(config)
        return api.selected_host
    return None
