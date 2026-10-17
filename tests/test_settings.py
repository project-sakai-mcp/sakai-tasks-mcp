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


def test_university_presets():
    """UNIVERSITY_PRESETS に指定された大学が含まれ、非対応大学が除外されていることを検証"""
    presets = Config.UNIVERSITY_PRESETS
    assert "名古屋大学" in presets
    assert presets["名古屋大学"] == "tact.ac.thers.ac.jp"
    assert "京都大学" in presets
    assert presets["京都大学"] == "panda.ecs.kyoto-u.ac.jp"
    assert "東京農工大学" in presets
    assert presets["東京農工大学"] == "lms.sirius.tuat.ac.jp"
    assert "東京都立大学" in presets
    assert presets["東京都立大学"] == "kibaco.tmu.ac.jp"

    # Sakaiから移行済みの大学が除外されていることを検証
    assert not any("法政" in name for name in presets)
    assert not any("岡山" in name for name in presets)


def test_get_client_raises_when_host_unconfigured(monkeypatch, tmp_path):
    """ホストが未設定の場合、get_client が RuntimeError を投げることを検証"""
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    with pytest.raises(RuntimeError) as exc_info:
        get_client()

    assert "接続先大学のSakaiのドメインが設定されていません" in str(exc_info.value)
    assert "open_settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_auth_status_returns_unconfigured_message(monkeypatch, tmp_path):
    """ホストが未設定の場合、check_auth_status が未設定メッセージを返すことを検証"""
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    res = await check_auth_status()
    assert res["authenticated"] is False
    assert "接続先大学のSakaiのドメインが設定されていません" in res["message"]


def test_show_settings_window_opens_directly(monkeypatch, tmp_path):
    """ホスト未設定時でも初期ダイアログを経由せず直接設定画面を開くことを検証"""
    from src.gui.settings_window import show_settings_window

    test_config_path = tmp_path / "config.json"
    monkeypatch.setattr(Config, "CONFIG_FILE_PATH", test_config_path)
    monkeypatch.setattr(Config, "SAKAI_HOST", "")

    with patch("src.gui.settings_window.build_settings_ui_data", new_callable=AsyncMock) as mock_build:
        mock_build.return_value = MagicMock()
        with patch("webview.create_window") as mock_create_window:
            with patch("webview.start") as mock_start:
                show_settings_window()
                mock_build.assert_called_once()
                mock_create_window.assert_called_once()
                mock_start.assert_called_once()

