"""Tests for config atomic save and GUI settings lifecycle."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.config import AIPolicyMode, AppConfigData, Config
from src.gui import settings_window
from src.gui.api import SettingsApi
from src.gui.data_builder import CourseSettingItem, SettingsUIData


def test_config_atomic_save(tmp_path, monkeypatch):
    """Config.save() がアトミックに書き込みを行い、一時ファイルが残留しないことを検証"""
    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"
    tmp_file = config_dir / "config.json.tmp"

    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)

    data = AppConfigData(
        sakai_host="tact.ac.thers.ac.jp",
        policies={"course_1": AIPolicyMode.ALLOW_ALL},
        default_deadline_days=14,
        default_announcement_limit=5,
        request_timeout=20.0,
    )

    Config.save(data)

    # 1. 目的のファイルが存在し、内容が一致する
    assert config_file.exists()
    assert not tmp_file.exists(), "一時ファイル .tmp が残存してはいけない"

    with open(config_file, encoding="utf-8") as f:
        saved_dict = json.load(f)
    assert saved_dict["sakai_host"] == "tact.ac.thers.ac.jp"
    assert saved_dict["policies"]["course_1"] == "allow_all"
    assert saved_dict["default_deadline_days"] == 14

    # 2. クラス変数が同期されている
    assert Config.SAKAI_HOST == "tact.ac.thers.ac.jp"
    assert Config.POLICIES["course_1"] == AIPolicyMode.ALLOW_ALL


def test_config_atomic_save_preserves_old_file_on_error(tmp_path, monkeypatch):
    """書き込み・置換エラー時に既存の config.json が破損・消失しないことを検証"""
    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"

    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)

    # 初期データを書き込み
    initial_data = AppConfigData(sakai_host="original.domain.ac.jp")
    Config.save(initial_data)
    assert config_file.read_text(encoding="utf-8").find("original.domain.ac.jp") != -1

    # os.replace が失敗する状況をシミュレート
    def fail_replace(src, dst):
        raise OSError("Simulated disk error during replace")

    monkeypatch.setattr("os.replace", fail_replace)

    with pytest.raises(OSError):
        Config.save(AppConfigData(sakai_host="new.domain.ac.jp"))

    # 既存のファイルが無傷で残っていること
    assert config_file.exists()
    assert "original.domain.ac.jp" in config_file.read_text(encoding="utf-8")


def test_settings_api_save_settings(tmp_path, monkeypatch):
    """SettingsApi.save_settings() が正しく Config を更新して True を返すことを検証"""
    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)

    ui_data = SettingsUIData(
        sakai_host="",
        presets={"名大": "tact.ac.thers.ac.jp"},
        default_deadline_days=30,
        default_announcement_limit=7,
        courses=[
            CourseSettingItem(
                id="c1",
                title="数学",
                is_favorite=True,
                current_policy=AIPolicyMode.TEXT_ONLY,
            )
        ],
    )
    api = SettingsApi(initial_data=ui_data)

    payload = {
        "sakai_host": " https://tact.ac.thers.ac.jp/portal ",
        "default_deadline_days": 15,
        "default_announcement_limit": 10,
        "request_timeout": 25.0,
        "courses": [
            {"id": "c1", "current_policy": "allow_all"}
        ]
    }

    result = api.save_settings(payload)
    assert result is True

    # 保存された設定値の検証
    loaded = Config.load()
    assert loaded.sakai_host == "tact.ac.thers.ac.jp"
    assert loaded.default_deadline_days == 15
    assert loaded.default_announcement_limit == 10
    assert loaded.policies["c1"] == AIPolicyMode.ALLOW_ALL


@pytest.mark.asyncio
async def test_data_builder_skips_sakai_when_host_unconfigured(monkeypatch, tmp_path):
    """sakai_host が未設定の場合、SakaiClient の呼び出しをスキップして courses=[] を返すことを検証"""
    from src.gui.data_builder import build_settings_ui_data

    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    # Config を空ホストで保存
    Config.save(AppConfigData(sakai_host=""))

    with patch("src.gui.data_builder.SakaiClient") as mock_client:
        ui_data = await build_settings_ui_data()
        # SakaiClient がインスタンス化されないこと
        mock_client.assert_not_called()
        assert ui_data.sakai_host == ""
        assert ui_data.courses == []


def test_show_settings_window_simplified_start(monkeypatch, tmp_path):
    """show_settings_window が webview.start() を直接呼び出し OS ネイティブ終了に委ねることを検証"""
    config_dir = tmp_path / "app_data"
    config_file = config_dir / "config.json"
    monkeypatch.setattr(Config, "APP_DATA_DIR", config_dir)
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", config_file)

    ui_data = SettingsUIData(
        sakai_host="",
        presets={},
        default_deadline_days=30,
        default_announcement_limit=7,
        courses=[],
    )

    with patch("src.gui.settings_window.build_settings_ui_data", AsyncMock(return_value=ui_data)):
        with patch("webview.create_window") as mock_create_window:
            with patch("webview.start") as mock_start:
                settings_window.show_settings_window()
                mock_create_window.assert_called_once()
                mock_start.assert_called_once_with(
                    storage_path=str(Config.WEBVIEW_DATA_DIR),
                    private_mode=False,
                )
