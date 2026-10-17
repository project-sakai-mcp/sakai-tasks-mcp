"""Sakai /api/users/me/forums parser."""

from typing import Any

from src.models import UnreadForumMessage


def _ensure_absolute_url(url: str | None, host: str) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    path = url if url.startswith("/") else f"/{url}"
    return f"https://{host}{path}"


def parse_unread_forum_messages(
    data: Any,
    host: str,
) -> list[UnreadForumMessage]:
    """
    Sakai の /api/users/me/forums レスポンスをパースして未読メッセージ・フォーラム情報一覧を生成する。

    トップレベルが list の場合と、{"forums": [...]} の辞書形式の両方に対応。
    """
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("forums", [])
    else:
        return []

    results: list[UnreadForumMessage] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        site_id = item.get("siteId")
        if not site_id:
            continue

        site_title = item.get("siteTitle") or ""
        message_count = int(item.get("messageCount") or 0)
        forum_count = int(item.get("forumCount") or 0)

        message_url = _ensure_absolute_url(item.get("messageUrl"), host)
        forum_url = _ensure_absolute_url(item.get("forumUrl"), host)
        site_url = _ensure_absolute_url(item.get("siteUrl"), host)

        results.append(
            UnreadForumMessage(
                site_id=site_id,
                site_name=site_title,
                unread_messages_count=message_count,
                unread_forums_count=forum_count,
                message_url=message_url,
                forum_url=forum_url,
                site_url=site_url,
            )
        )

    return results
