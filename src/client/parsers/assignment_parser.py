"""Assignment parser from Sakai /direct/assignment/my.json."""

from typing import Any

from src.client import endpoints
from src.client.parsers.base import (
    clean_html_text,
    parse_attachments,
    parse_datetime,
)
from src.models import SakaiTask, TaskStatus, TaskType


def parse_assignments(
    data: dict[str, Any] | list[dict[str, Any]],
    host: str,
    site_names: dict[str, str] | None = None,
    site_tool_pages: dict[str, dict[str, str]] | None = None,
    assignment_id: str | None = None,
    include_details: bool = True,
) -> list[SakaiTask]:
    """
    /direct/assignment/my.json のレスポンスをパースし、
    条件に応じた SakaiTask のリストを生成する。

    Args:
        data: Sakai API の JSON レスポンス ({"assignment_collection": [...]})
        host: Sakai ホスト名 (リンク補正用)
        site_names: site_id -> site_name の対応辞書 (講義名マッピング兼、対象講義の絞り込み用)
        site_tool_pages: site_id -> {"assignment": "https://...", ...} のツール URL 辞書
        assignment_id: 特定の 1 課題のみを抽出する場合に指定
        include_details: True の場合は指示文 (instructions) や添付資料 (attachments) もパースして格納

    Returns:
        list[SakaiTask]: 正規化された課題タスク一覧 (task_type=TaskType.ASSIGNMENT)
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("assignment_collection", [])

    tasks: list[SakaiTask] = []

    for item in collection:
        a_id = str(item["id"])
        if assignment_id and a_id != assignment_id:
            continue

        site_id = item["context"]
        if site_names is not None and site_id not in site_names:
            continue

        site_name = (site_names.get(site_id) if site_names else None) or item.get("siteTitle") or site_id
        title = item["title"]

        due_date = parse_datetime(item.get("dueTime"))
        open_date = parse_datetime(item.get("openTime"))
        close_date = parse_datetime(item.get("closeTime"))

        # 提出判定
        raw_status = str(item.get("status", "")).upper()
        submissions = item.get("submissions") or []
        is_submitted = raw_status == "SUBMITTED" or len(submissions) > 0

        # status
        if is_submitted:
            status = TaskStatus.SUBMITTED
        elif raw_status == "CLOSED":
            status = TaskStatus.CLOSED
        else:
            status = TaskStatus.OPEN

        site_url = endpoints.get_site_url(host, site_id)
        tool_url = None
        if site_tool_pages and site_id in site_tool_pages:
            tool_url = site_tool_pages[site_id].get("assignment")
        url = tool_url or site_url

        if include_details:
            instructions = clean_html_text(item.get("instructions")) or None
            attachments = parse_attachments(item.get("attachments"), host)
            raw_points = item.get("maxGradePoint")
            if raw_points is not None and raw_points != "":
                max_points = float(raw_points)
            else:
                max_points = None
        else:
            instructions = None
            attachments = []
            max_points = None

        tasks.append(
            SakaiTask(
                id=a_id,
                title=title,
                task_type=TaskType.ASSIGNMENT,
                site_id=site_id,
                site_name=site_name,
                due_date=due_date,
                open_date=open_date,
                close_date=close_date,
                is_submitted=is_submitted,
                status=status,
                url=url,
                site_url=site_url,
                instructions=instructions,
                attachments=attachments,
                max_points=max_points,
                time_limit_seconds=None,
            )
        )

    return tasks
