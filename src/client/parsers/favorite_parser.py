"""Favorite courses parser from Sakai portal HTML."""

import re
from bs4 import BeautifulSoup

from src.client import endpoints
from src.models import CourseSite

SITE_HREF_PATTERN = re.compile(r"/portal/site-?[a-z]*/([^/]+)")


def parse_favorite_courses(html_content: str, host: str) -> list[CourseSite]:
    """
    /portal の HTML から「お気に入り」登録されている講義一覧を抽出する。

    Args:
        html_content: /portal から取得した HTML 文字列
        host: Sakai ホスト名 (講義 URL 生成用)

    Returns:
        list[CourseSite]: お気に入り講義モデル (is_favorite=True) のリスト
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    entries = soup.find_all(class_="fav-sites-entry")

    courses: list[CourseSite] = []
    seen_ids: set[str] = set()

    for entry in entries:
        a_tag = entry.find("a")
        if not a_tag:
            continue

        href = a_tag.get("href", "")
        m = SITE_HREF_PATTERN.search(href)
        if not m:
            continue

        site_id = m.group(1)
        if site_id.startswith("~"):
            # マイワークスペースは除外
            continue

        if site_id in seen_ids:
            continue
        seen_ids.add(site_id)

        # 講義名の抽出: span タグの title / テキスト、または a タグの title / テキスト
        span = entry.find("span")
        name = ""
        if span:
            name = span.get("title") or span.get_text(strip=True)
        if not name:
            name = a_tag.get("title") or a_tag.get_text(strip=True)

        site_url = endpoints.get_site_url(host, site_id)
        courses.append(
            CourseSite(
                id=site_id,
                name=name,
                is_favorite=True,
                site_url=site_url,
            )
        )

    return courses
