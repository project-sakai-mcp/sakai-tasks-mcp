from typing import Any

import httpx

from src.config import Config


async def is_session_valid(
    cookies: dict[str, str],
    host: str = Config.SAKAI_HOST,
    timeout: float = Config.SESSION_CHECK_TIMEOUT,
) -> bool:
    """
    Cookie を用いて Sakai の現在セッションを確認し、
    ログイン済みなら True を返す。
    """
    info = await get_session_info(
        cookies,
        host=host,
        timeout=timeout,
    )
    return info is not None


async def get_session_info(
    cookies: dict[str, str],
    host: str = Config.SAKAI_HOST,
    timeout: float = Config.SESSION_CHECK_TIMEOUT,
) -> dict[str, Any] | None:
    """
    Sakai の /direct/session/current.json にアクセスし、
    有効なセッション情報を返す。

    未ログイン・通信エラー・タイムアウト時は None。
    """
    url = f"https://{host}/direct/session/current.json"

    try:
        async with httpx.AsyncClient(
            cookies=cookies,
            timeout=timeout,
        ) as client:
            response = await client.get(url)

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return None

        user_eid = data.get("userEid")

        if not isinstance(user_eid, str):
            return None

        if not user_eid:
            return None

        return data

    except (
        httpx.RequestError,
        httpx.HTTPStatusError,
        ValueError,
    ):
        return None