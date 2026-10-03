"""Favorite courses parser from Sakai /portal/favorites/list JSON."""

from typing import Any

from src.client import endpoints
from src.models import CourseSite


def parse_favorite_courses(
    data: dict[str, Any] | list[Any],
    host: str,
) -> list[CourseSite]:
    """
    /portal/favorites/list の JSON レスポンスからお気に入り講義一覧を抽出する。

    Args:
        data: /portal/favorites/list のレスポンス (例: {"favoriteSiteIds": [...]})
        host: Sakai ホスト名 (講義 URL 生成用)

    Returns:
        list[CourseSite]: お気に入り講義モデル (is_favorite=True) のリスト
    """
    if not data:
        return []

    if isinstance(data, list):
        raw_ids = data
    elif isinstance(data, dict):
        raw_ids = data.get("favoriteSiteIds", [])
    else:
        return []

    courses: list[CourseSite] = []
    seen_ids: set[str] = set()

    for item in raw_ids:
        if not isinstance(item, str):
            continue
        site_id = item.strip()
        if not site_id or site_id.startswith("~"):
            # マイワークスペースは除外
            continue

        if site_id in seen_ids:
            continue
        seen_ids.add(site_id)

        site_url = endpoints.get_site_url(host, site_id)
        courses.append(
            CourseSite(
                id=site_id,
                name=site_id,
                is_favorite=True,
                site_url=site_url,
            )
        )

    return courses
