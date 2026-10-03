"""Course sites parser from Sakai /direct/site.json."""

from typing import Any

from src.client import endpoints
from src.client.parsers.base import clean_html_text
from src.models import CourseSite


def extract_tool_pages(site_pages: list[dict[str, Any]] | None) -> dict[str, str]:
    """
    sitePages 配列から主要ツール (課題, お知らせ, 資料, テスト) の Page URL 辞書を抽出する。

    Returns:
        dict[str, str]: {"assignment": "https://...", "announcement": "...", "resource": "...", "quiz": "..."}
    """
    if not site_pages:
        return {}

    tool_pages: dict[str, str] = {}
    for page in site_pages:
        title = page.get("title", "")
        url = page.get("url", "")
        if not title or not url:
            continue

        title_lower = title.lower()
        if "assignment" not in tool_pages and ("課題" in title or "assignment" in title_lower):
            tool_pages["assignment"] = url
        elif "announcement" not in tool_pages and ("お知らせ" in title or "連絡" in title or "announcement" in title_lower):
            tool_pages["announcement"] = url
        elif "resource" not in tool_pages and ("授業資料" in title or "リソース" in title or "資料" in title or "resource" in title_lower):
            tool_pages["resource"] = url
        elif "quiz" not in tool_pages and ("テスト" in title or "クイズ" in title or "quiz" in title_lower or "samigo" in title_lower or "assessment" in title_lower):
            tool_pages["quiz"] = url

    return tool_pages


def parse_courses(
    data: dict[str, Any] | list[dict[str, Any]],
    host: str,
    favorite_site_ids: set[str] | None = None,
) -> list[CourseSite]:
    """
    /direct/site.json のレスポンスをパースし、講義サイトモデルのリストに変換する。
    各講義の sitePages からツール Page URL 辞書 (tool_pages) も自動抽出して格納する。

    Args:
        data: /direct/site.json の JSON レスポンス ({"site_collection": [...]})
        host: Sakai ホスト名 (講義 URL 補正用)
        favorite_site_ids: お気に入り登録されているサイト ID の集合 (is_favorite 判定用)

    Returns:
        list[CourseSite]: 正規化された講義サイト一覧 (tool_pages 含む)
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("site_collection", [])

    fav_ids = favorite_site_ids or set()
    courses: list[CourseSite] = []

    for site in collection:
        site_id = site.get("id", "")
        if not site_id or site_id.startswith("~") or site.get("type") == "myworkspace":
            continue

        name = site["title"]
        description = clean_html_text(site.get("description")) or None
        site_url = endpoints.get_site_url(host, site_id)
        is_favorite = site_id in fav_ids
        tool_pages = extract_tool_pages(site.get("sitePages"))

        courses.append(
            CourseSite(
                id=site_id,
                name=name,
                is_favorite=is_favorite,
                site_url=site_url,
                tool_pages=tool_pages,
                description=description,
            )
        )

    return courses
