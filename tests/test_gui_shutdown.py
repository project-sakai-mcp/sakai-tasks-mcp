"""Exercise real pywebview API replies with a controllable GUI substitute."""

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from webview.event import Event
from webview.util import js_bridge_call

from src.config import AIPolicyMode, AppConfigData
from src.gui import settings_window
from src.gui.data_builder import SettingsUIData


@pytest.mark.parametrize("screen,action", [
    (screen, action)
    for screen in ("setup", "settings")
    for action in ("submit", "close_window", "cancel", "native_close", "save_error")
    if (screen, action) != ("setup", "save_error")
])
def test_close_waits_for_api_response(screen, action, monkeypatch, tmp_path):
    response_started = threading.Event()
    release_response = threading.Event()
    destroyed = threading.Event()
    order = []
    bridge_threads = []
    scripts = []
    alive_at_destroy = []
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")
    monkeypatch.setattr(settings_window.Config, "CONFIG_FILE_PATH", config_path)
    monkeypatch.setattr(settings_window.Config, "load", lambda: AppConfigData(sakai_host="example.edu"))
    save = Mock(side_effect=OSError("test save failure") if action == "save_error" else None)
    monkeypatch.setattr(settings_window.Config, "save", save)
    ui_data = SettingsUIData(
        sakai_host="example.edu", presets={}, default_deadline_days=30,
        default_announcement_limit=7, courses=[],
    )
    monkeypatch.setattr(settings_window, "build_settings_ui_data", AsyncMock(return_value=ui_data))

    class Window:
        _functions = {}

        def __init__(self):
            self.events = SimpleNamespace(closed=Event(self))

        def evaluate_js(self, script):
            bridge_threads.append(threading.current_thread())
            scripts.append(script)
            order.append("reply-start")
            response_started.set()
            if not release_response.wait(3):
                raise RuntimeError("test did not release the API reply")
            order.append("reply-finished")

        def destroy(self):
            alive_at_destroy.append(any(t.is_alive() for t in bridge_threads))
            order.append("destroy")
            self.events.closed.set()
            destroyed.set()

    window = Window()

    def create_window(**kwargs):
        window._js_api = kwargs["js_api"]
        return window

    def start(func=None, args=None, **kwargs):
        watcher = threading.Thread(target=func, args=args, daemon=True) if func else None
        if watcher:
            watcher.start()
        try:
            if action == "native_close":
                window.events.closed.set()
                if watcher:
                    watcher.join(2)
                    assert not watcher.is_alive(), "native close left the watcher running"
                assert not destroyed.is_set()
                return

            if action in ("submit", "save_error"):
                if screen == "setup":
                    method, params = "select_host", [" https://example.edu/path "]
                else:
                    method, params = "save_settings", [{
                        "sakai_host": " https://example.edu/path ",
                        "default_deadline_days": 14,
                        "default_announcement_limit": 3,
                        "courses": [{"id": "course-1", "current_policy": "text_only"}],
                    }]
            else:
                method, params = action, []
            js_bridge_call(window, method, params, "test-request")
            assert response_started.wait(2)
            # Hold longer than the old 0.1-second Timer: a slow reply must remain safe.
            assert not destroyed.wait(0.2), "closed before the JS reply completed"
            if screen == "settings" and action == "submit":
                save.assert_called_once()
            if screen == "setup":
                save.assert_not_called()

            release_response.set()
            for thread in bridge_threads:
                thread.join(2)
                assert not thread.is_alive()

            if action == "save_error":
                assert "isError: true" in scripts[0]
                assert not window._js_api.close_event.is_set()
                assert not destroyed.is_set()
                window.events.closed.set()
            else:
                assert destroyed.wait(2)
                assert alive_at_destroy == [False]
                assert order == ["reply-start", "reply-finished", "destroy"]
            if watcher:
                watcher.join(2)
                assert not watcher.is_alive()
        finally:
            release_response.set()
            window.events.closed.set()
            for thread in bridge_threads:
                thread.join(2)
            if watcher:
                watcher.join(2)

    monkeypatch.setattr(settings_window.webview, "create_window", create_window)
    monkeypatch.setattr(settings_window.webview, "start", start)
    if screen == "setup":
        result = settings_window.show_initial_setup_window()
        assert result == ("example.edu" if action == "submit" else None)
    else:
        settings_window.show_settings_window()

    if action == "submit":
        save.assert_called_once()
        saved = save.call_args.args[0]
        assert saved.sakai_host == "example.edu"
        if screen == "settings":
            assert saved.default_deadline_days == 14
            assert saved.default_announcement_limit == 3
            assert saved.policies == {"course-1": AIPolicyMode.TEXT_ONLY}
    elif action != "save_error":
        save.assert_not_called()
