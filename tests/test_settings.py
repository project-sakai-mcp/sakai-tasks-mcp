"""Unit tests for settings and initial setup flows."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.config import AppConfigData, Config
from src.server import get_client, check_auth_status


def test_config_default_host_is_empty():
    """デフォルトの sakai_host が空文字であることを検証"""
    data = AppConfigData()
    assert data.sakai_host == ""


def test_get_client_raises_when_host_unconfigured(monkeypatch, tmp_path):
    """ホストが未設定の場合、get_client が RuntimeError を投げることを検証"""
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    with pytest.raises(RuntimeError) as exc_info:
        get_client()

    assert "Sakai の接続先大学が設定されていません" in str(exc_info.value)
    assert "open_settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_auth_status_returns_unconfigured_message(monkeypatch, tmp_path):
    """ホストが未設定の場合、check_auth_status が未設定メッセージを返すことを検証"""
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    res = await check_auth_status()
    assert res["authenticated"] is False
    assert "Sakai の接続先大学が設定されていません" in res["message"]


def test_show_settings_window_opens_initial_setup_first_if_unconfigured(monkeypatch, tmp_path):
    """ホスト未設定時に show_settings_window がまず初期設定を開くことを検証"""
    from src.gui.settings_window import show_settings_window

    test_config_path = tmp_path / "config.json"
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", test_config_path)
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    # 初期設定でキャンセルされた場合
    with patch("src.gui.settings_window.show_initial_setup_window", return_value=None) as mock_setup:
        with patch("src.gui.settings_window.build_settings_ui_data") as mock_build:
            show_settings_window()
            mock_setup.assert_called_once()
            # キャンセルされたので講義一覧取得には進まない
            mock_build.assert_not_called()

    # 初期設定で大学が選ばれた場合
    def select_host():
        # 設定を保存するシミュレーション
        Config.save(AppConfigData(sakai_host="panda.ecs.kyoto-u.ac.jp"))
        return "panda.ecs.kyoto-u.ac.jp"

    with patch("src.gui.settings_window.show_initial_setup_window", side_effect=select_host) as mock_setup:
        with patch("src.gui.settings_window.build_settings_ui_data", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = MagicMock()
            with patch("webview.create_window") as mock_create_window:
                with patch("webview.start") as mock_start:
                    show_settings_window()
                    mock_setup.assert_called_once()
                    mock_build.assert_called_once()
                    mock_create_window.assert_called_once()
                    mock_start.assert_called_once()
