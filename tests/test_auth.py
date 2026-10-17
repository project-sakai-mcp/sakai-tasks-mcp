"""Unit tests for webview authentication and URL update pause duration detection."""

from unittest.mock import MagicMock, patch

from src.auth.webview_auth import authenticate_via_webview


class TimeController:
    """time.monotonic() の進行をシミュレートするヘルパー"""
    def __init__(self, start: float = 100.0, step: float = 0.2):
        self.current = start
        self.step = step

    def monotonic(self) -> float:
        val = self.current
        self.current += self.step
        return val


def test_url_pause_triggers_window_show():
    """URL が pause_duration_seconds 以上静止した場合に window.show() が呼ばれることを検証"""
    mock_window = MagicMock()
    show_called_at_url = None

    def on_show():
        nonlocal show_called_at_url
        show_called_at_url = mock_window.get_current_url()

    mock_window.show.side_effect = on_show

    # タイムライン:
    # 1. login_url からスタート
    # 2. https://idp.example.ac.jp/login に遷移 (URL変化)
    # 3. 1.5 秒以上同じ URL で静止 -> show() が呼ばれる
    # 4. ユーザーがログインして https://tact.ac.thers.ac.jp/portal に遷移 -> 成功終了
    urls = (
        ["https://tact.ac.thers.ac.jp/portal/login"] * 2
        + ["https://idp.example.ac.jp/login"] * 10  # 10 * 0.2s = 2.0s 静止
        + ["https://tact.ac.thers.ac.jp/portal"] * 2
    )

    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(urls):
            u = urls[url_idx]
            url_idx += 1
            return u
        return urls[-1]

    mock_window.get_current_url.side_effect = get_url
    mock_window.evaluate_js.return_value = "Login Page"
    mock_window.get_cookies.return_value = [{"name": "JSESSIONID", "value": "test_session", "domain": "tact.ac.thers.ac.jp"}]

    time_ctrl = TimeController(start=100.0, step=0.2)

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(
                        host="tact.ac.thers.ac.jp",
                        pause_duration_seconds=1.5,
                    )

    assert mock_window.show.call_count == 1
    assert show_called_at_url == "https://idp.example.ac.jp/login"
    assert mock_window.destroy.call_count == 1
    assert len(cookies) == 1
    assert cookies[0]["name"] == "JSESSIONID"


def test_url_continuous_updates_prevent_window_show():
    """多段リダイレクト等で URL が変化し続けている間は window.show() が呼ばれないことを検証"""
    mock_window = MagicMock()

    # 各ステップで異なる URL に遷移し続ける（素通り中）
    redirect_urls = [
        "https://tact.ac.thers.ac.jp/portal/login",
        "https://idp.example.ac.jp/auth/step1",
        "https://login.microsoftonline.com/oauth2/authorize?req=1",
        "https://login.microsoftonline.com/oauth2/authorize?req=2",
        "https://idp.example.ac.jp/auth/step2",
        "https://tact.ac.thers.ac.jp/portal",  # ログイン完了
    ]

    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(redirect_urls):
            u = redirect_urls[url_idx]
            url_idx += 1
            return u
        return redirect_urls[-1]

    mock_window.get_current_url.side_effect = get_url
    mock_window.evaluate_js.return_value = ""
    mock_window.get_cookies.return_value = [{"name": "SakaiSession", "value": "success", "domain": "tact.ac.thers.ac.jp"}]

    # 各ステップ 0.5 秒進む（pause_duration 1.5 秒未満で遷移し続ける）
    time_ctrl = TimeController(start=100.0, step=0.5)

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(
                        host="tact.ac.thers.ac.jp",
                        pause_duration_seconds=1.5,
                    )

    # 画面を表示せずに自動素通りで完了したことを検証
    assert mock_window.show.call_count == 0
    assert mock_window.destroy.call_count == 1
    assert len(cookies) == 1
    assert cookies[0]["name"] == "SakaiSession"


def test_login_success_immediate():
    """初回から /portal に到達していた場合、直ちに終了し window.show() は呼ばれないことを検証"""
    mock_window = MagicMock()
    mock_window.get_current_url.return_value = "https://tact.ac.thers.ac.jp/portal/site/123"
    mock_window.get_cookies.return_value = [{"name": "session", "value": "abc"}]

    time_ctrl = TimeController()

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert mock_window.show.call_count == 0
    assert mock_window.destroy.call_count == 1
    assert len(cookies) == 1


def test_user_closes_window_returns_empty():
    """ユーザーがウィンドウを閉じて例外が発生した場合、空リストが返ることを検証"""
    mock_window = MagicMock()
    mock_window.get_current_url.side_effect = Exception("Window destroyed by user")

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert cookies == []


def test_user_closes_window_via_closed_event_returns_empty():
    """ユーザーが[✕]で閉じて events.closed がセットされた場合、即座に空リストが返ることを検証"""
    mock_window = MagicMock()
    mock_window.events.closed.is_set.return_value = True

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert cookies == []


def test_temporary_none_or_empty_url_during_redirect_continues():
    """リダイレクトの合間に一時的に URL が None や空文字になっても中断せず、最終ポータル到達で成功することを検証"""
    mock_window = MagicMock()
    mock_window.events.closed.is_set.return_value = False

    # 1. ログイン画面
    # 2. 静止して表示
    # 3. 認証後のリダイレクトの隙間で一時的に None / ""
    # 4. ポータルに着地
    urls = (
        ["https://tact.ac.thers.ac.jp/portal/login"] * 2
        + ["https://idp.example.ac.jp/login"] * 3
        + [None, "", "https://tact.ac.thers.ac.jp/portal"]
    )
    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(urls):
            u = urls[url_idx]
            url_idx += 1
            return u
        return urls[-1]

    mock_window.get_current_url.side_effect = get_url
    mock_window.evaluate_js.return_value = "Login"
    mock_window.get_cookies.return_value = [{"name": "JSESSIONID", "value": "redirected_session"}]

    time_ctrl = TimeController(start=100.0, step=1.0)

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp", pause_duration_seconds=1.5)

    assert len(cookies) == 1
    assert cookies[0]["name"] == "JSESSIONID"
    assert mock_window.show.call_count == 1




def test_stale_or_idp_error_recovery():
    """IdP Stale Request 発生時に window.load_url(login_url) が呼ばれリトライされることを検証"""
    mock_window = MagicMock()

    urls = [
        "https://tact.ac.thers.ac.jp/portal/login",
        "https://idp.example.ac.jp/POST/SSO",  # Stale エラー
        "https://idp.example.ac.jp/POST/SSO",
        "https://tact.ac.thers.ac.jp/portal",  # リトライ後成功
    ]
    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(urls):
            u = urls[url_idx]
            url_idx += 1
            return u
        return urls[-1]

    mock_window.get_current_url.side_effect = get_url
    mock_window.evaluate_js.return_value = "Stale Request"
    mock_window.get_cookies.return_value = [{"name": "reloaded_session", "value": "yes"}]

    time_ctrl = TimeController()

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert mock_window.load_url.call_count == 1
    assert "https://tact.ac.thers.ac.jp/portal/login" in mock_window.load_url.call_args[0][0]
    assert len(cookies) == 1


def test_cookie_normalization_types():
    """SimpleCookie, Morsel, dict 形式の Cookie が正しく規格化されることを検証"""
    from http.cookies import SimpleCookie

    sc = SimpleCookie()
    sc["session1"] = "val1"
    sc["session1"]["domain"] = "example.com"
    sc["session1"]["path"] = "/"
    sc["session1"]["httponly"] = True
    sc["session1"]["secure"] = True

    mock_window = MagicMock()
    mock_window.get_current_url.return_value = "https://tact.ac.thers.ac.jp/portal"
    # 異なる形式が混在したリスト
    mock_window.get_cookies.return_value = [
        sc,
        {"name": "dict_cookie", "value": "val2", "domain": "example.com", "path": "/path"},
    ]

    time_ctrl = TimeController()

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert len(cookies) == 2
    c1 = next(c for c in cookies if c["name"] == "session1")
    assert c1["value"] == "val1"
    assert c1["httponly"] is True
    assert c1["secure"] is True

    c2 = next(c for c in cookies if c["name"] == "dict_cookie")
    assert c2["value"] == "val2"
    assert c2["path"] == "/path"


def test_empty_url_does_not_trigger_window_show():
    """URL が初期化中などで空文字のまま経過しても window.show() はトリガーされないことを検証"""
    mock_window = MagicMock()
    mock_window.get_cookies.return_value = []

    # 最初の数イテレーションは URL が ""、その後 portal に着地
    urls = ["", "", "", "https://tact.ac.thers.ac.jp/portal"]
    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(urls):
            u = urls[url_idx]
            url_idx += 1
            return u
        return urls[-1]

    mock_window.get_current_url.side_effect = get_url
    time_ctrl = TimeController(start=100.0, step=1.0)  # 1秒ずつ進む

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    authenticate_via_webview(host="tact.ac.thers.ac.jp", pause_duration_seconds=1.5)

    assert mock_window.show.call_count == 0
    assert mock_window.destroy.call_count == 1


def test_auto_timeout_seconds_compatibility():
    """互換パラメータ auto_timeout_seconds が渡された場合でもそれが pause_limit として機能することを検証"""
    mock_window = MagicMock()
    mock_window.get_cookies.return_value = []

    urls = (
        ["https://idp.example.ac.jp/login"] * 5
        + ["https://tact.ac.thers.ac.jp/portal"]
    )
    url_idx = 0

    def get_url():
        nonlocal url_idx
        if url_idx < len(urls):
            u = urls[url_idx]
            url_idx += 1
            return u
        return urls[-1]

    mock_window.get_current_url.side_effect = get_url
    time_ctrl = TimeController(start=100.0, step=0.5)

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=time_ctrl.monotonic):
                    # auto_timeout_seconds=2.0 を明示指定
                    authenticate_via_webview(host="tact.ac.thers.ac.jp", auto_timeout_seconds=2.0)

    assert mock_window.show.call_count == 1


def test_auth_max_timeout_destroys_window():
    """最大待機時間 (AUTH_MAX_TIMEOUT) を超過した場合は window.destroy() して終了することを検証"""
    mock_window = MagicMock()
    mock_window.get_current_url.return_value = "https://idp.example.ac.jp/login"

    # AUTH_MAX_TIMEOUT (300秒) を超えるようにジャンプ
    call_count = 0

    def mock_monotonic():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return 100.0
        return 500.0  # 300秒超過

    with patch("webview.create_window", return_value=mock_window):
        with patch("webview.start") as mock_start:
            def run_watch_loop(func, window, **kwargs):
                func(window)

            mock_start.side_effect = run_watch_loop
            with patch("time.sleep"):
                with patch("time.monotonic", side_effect=mock_monotonic):
                    cookies = authenticate_via_webview(host="tact.ac.thers.ac.jp")

    assert mock_window.destroy.call_count == 1
    assert cookies == []

