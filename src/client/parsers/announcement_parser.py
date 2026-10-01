"""Announcement parser from Sakai /direct/announcement/user.json or site/{siteId}.json."""

from typing import Any

from src.client import endpoints
from src.client.parsers.base import (
    clean_html_text,
    parse_attachments,
    parse_datetime,
)
from src.models import Announcement


def parse_announcements(
    data: dict[str, Any] | list[dict[str, Any]],
    host: str,
    site_names: dict[str, str] | None = None,
    site_tool_pages: dict[str, dict[str, str]] | None = None,
    announcement_id: str | None = None,
    include_details: bool = True,
) -> list[Announcement]:
    """
    /direct/announcement/user.json または site/{siteId}.json のレスポンスをパースし、
    条件に応じた Announcement モデルのリストを生成する。

    Args:
        data: Sakai API の JSON レスポンス ({"announcement_collection": [...]})
        host: Sakai ホスト名 (添付ファイルリンク補正用)
        site_names: site_id -> site_name の対応辞書 (指定時は対象講義に絞り込み)
        site_tool_pages: site_id -> {"announcement": "https://...", ...} のツール URL 辞書
        announcement_id: 特定の 1 件のみを抽出する場合に指定
        include_details: True の場合は本文 (body) や添付資料 (attachments) もパースして格納

    Returns:
        list[Announcement]: 正規化されたお知らせモデル一覧
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("announcement_collection", [])

    announcements: list[Announcement] = []

    for item in collection:
        a_id = str(item.get("announcementId") or item["id"])

        if announcement_id and a_id != announcement_id:
            continue

        site_id = item.get("siteId") or ""
        if site_names is not None and site_id not in site_names:
            continue

        site_title = item.get("siteTitle")
        site_name = site_title or (site_names.get(site_id) if site_names else None) or site_id
        title = item["title"]

        published_at = parse_datetime(item.get("createdOn"))
        created_by = item.get("createdByDisplayName")

        site_url = endpoints.get_site_url(host, site_id) if site_id else None
        tool_url = None
        if site_tool_pages and site_id and site_id in site_tool_pages:
            tool_url = site_tool_pages[site_id].get("announcement")
        url = tool_url or site_url

        if include_details:
            content = clean_html_text(item.get("body")) or None
            attachments = parse_attachments(item.get("attachments"), host)
        else:
            content = None
            attachments = []

        announcements.append(
            Announcement(
                id=a_id,
                title=title,
                content=content,
                published_at=published_at,
                created_by=created_by,
                site_id=site_id,
                site_name=site_name,
                url=url,
                attachments=attachments,
            )
        )

    return announcements
