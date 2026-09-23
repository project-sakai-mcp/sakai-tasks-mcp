import json
from pathlib import Path
from typing import Any

import keyring
from cryptography.fernet import Fernet, InvalidToken

from src.config import Config


_KEYRING_SERVICE = "sakai-tasks-mcp"
_KEYRING_USERNAME = "fernet_key"


def _get_or_create_fernet_key() -> bytes:
    """
    OS のセキュアストアから Fernet 鍵を取得する。
    鍵が存在しない場合は新規生成して保存する。
    """
    stored_key = keyring.get_password(
        _KEYRING_SERVICE,
        _KEYRING_USERNAME,
    )

    if stored_key is not None:
        return stored_key.encode("utf-8")

    key = Fernet.generate_key()

    keyring.set_password(
        _KEYRING_SERVICE,
        _KEYRING_USERNAME,
        key.decode("utf-8"),
    )

    return key


def save_all_cookies(
    cookies: list[dict[str, Any]],
    file_path: Path = Config.SESSION_FILE_PATH,
) -> None:
    """
    WebView から取得した全ドメインの Cookie リストを JSON 化し、
    Fernet で暗号化して保存する。

    保存先の親ディレクトリが存在しない場合は自動生成する。
    """
    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    key = _get_or_create_fernet_key()
    fernet = Fernet(key)

    json_bytes = json.dumps(
        cookies,
        ensure_ascii=False,
    ).encode("utf-8")

    encrypted = fernet.encrypt(json_bytes)

    file_path.write_bytes(encrypted)


def load_all_cookies(
    file_path: Path = Config.SESSION_FILE_PATH,
) -> list[dict[str, Any]] | None:
    """
    暗号化 Cookie ファイルを復号し、
    WebView 再注入用の Cookie リストとして返す。

    ファイルが存在しない場合、復号に失敗した場合、
    JSON が破損している場合は None を返す。
    """
    if not file_path.exists():
        return None

    try:
        key = _get_or_create_fernet_key()
        fernet = Fernet(key)

        encrypted = file_path.read_bytes()
        decrypted = fernet.decrypt(encrypted)

        data = json.loads(decrypted.decode("utf-8"))

        if not isinstance(data, list):
            return None

        if not all(isinstance(cookie, dict) for cookie in data):
            return None

        return data

    except (
        InvalidToken,
        json.JSONDecodeError,
        UnicodeDecodeError,
        OSError,
    ):
        return None


def load_sakai_cookies(
    host: str = Config.SAKAI_HOST,
    file_path: Path = Config.SESSION_FILE_PATH,
) -> dict[str, str] | None:
    """
    保存済み Cookie のうち Sakai ホストに適用されるものだけを抽出し、
    httpx.AsyncClient 用の {name: value} 形式で返す。
    """
    cookies = load_all_cookies(file_path)

    if cookies is None:
        return None

    normalized_host = host.lower().rstrip(".")

    sakai_cookies: dict[str, str] = {}

    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")

        if not isinstance(name, str):
            continue

        if not isinstance(value, str):
            continue

        if not isinstance(domain, str):
            continue

        normalized_domain = domain.lower().lstrip(".").rstrip(".")

        if (
            normalized_host == normalized_domain
            or normalized_host.endswith("." + normalized_domain)
        ):
            sakai_cookies[name] = value

    return sakai_cookies


def delete_cookies(
    file_path: Path = Config.SESSION_FILE_PATH,
) -> None:
    """
    保存済みの暗号化 Cookie ファイルを削除する。

    ファイルが存在しない場合もエラーにしない。
    """
    file_path.unlink(missing_ok=True)