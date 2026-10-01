"""Calendar events parser from Sakai /direct/calendar/my.json or site/{siteId}.json."""

from datetime import timedelta
from typing import Any

from src.client import endpoints
from src.client.parsers.base import clean_html_text, parse_datetime
from src.models import CalendarEvent


def parse_calendar_events(
    data: dict[str, Any] | list[dict[str, Any]],
    host: str,
    site_names: dict[str, str] | None = None,
    site_tool_pages: dict[str, dict[str, str]] | None = None,
    event_type: str | None = None,
) -> list[CalendarEvent]:
    """
    /direct/calendar/my.json または site/{siteId}.json のレスポンスをパースし、
    CalendarEvent モデルのリストを生成する。

    Args:
        data: Sakai API の JSON レスポンス ({"calendar_collection": [...]})
        host: Sakai ホスト名 (リンク補正用)
        site_names: site_id -> site_name の対応辞書 (指定時は対象講義に絞り込み)
        site_tool_pages: site_id -> {"assignment": "https://...", ...} のツール URL 辞書
        event_type: イベント種別による絞り込み ("Assignment", "Quiz" 等)

    Returns:
        list[CalendarEvent]: 正規化されたカレンダーイベント一覧
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("calendar_collection", [])

    events: list[CalendarEvent] = []

    for item in collection:
        e_id = str(item.get("eventId") or item.get("id") or "")
        if not e_id:
            continue

        raw_type = item.get("type")
        if event_type:
            if not raw_type or raw_type.lower() != event_type.lower():
                continue

        site_id = item.get("siteId")
        if site_names is not None and site_id and site_id not in site_names:
            continue

        site_name = (site_names.get(site_id) if site_names and site_id else None) or item.get("siteName")
        title = item["title"]
        description = clean_html_text(item.get("description")) or None

        first_time = item.get("firstTime")
        if isinstance(first_time, dict):
            raw_time = first_time.get("time")
        else:
            raw_time = first_time
        start_time = parse_datetime(raw_time)

        duration = item.get("duration")
        if start_time and duration is not None:
            end_time = start_time + timedelta(milliseconds=float(duration))
        else:
            end_time = None

        site_url = endpoints.get_site_url(host, site_id) if site_id else None
        tool_url = None
        if site_tool_pages and site_id and site_id in site_tool_pages:
            pages = site_tool_pages[site_id]
            if raw_type and raw_type.lower() == "assignment":
                tool_url = pages.get("assignment")
            else:
                tool_url = pages.get("calendar") or pages.get("schedule")
        url = tool_url or site_url or item.get("entityURL")

        events.append(
            CalendarEvent(
                id=e_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                event_type=raw_type,
                site_id=site_id,
                site_name=site_name,
                url=url,
            )
        )

    return events
