"""Quiz / Assessment parser from Sakai SAMIGO /direct/sam_pub/context/{siteId}.json."""

from datetime import datetime, timezone
from typing import Any

from src.client import endpoints
from src.client.parsers.base import parse_datetime
from src.models import SakaiTask, TaskStatus, TaskType


def parse_quizzes(
    data: dict[str, Any] | list[dict[str, Any]],
    site_id: str,
    host: str,
    site_name: str | None = None,
    tool_page_url: str | None = None,
) -> list[SakaiTask]:
    """
    /direct/sam_pub/context/{siteId}.json のレスポンスをパースし、
    SakaiTask (task_type=TaskType.QUIZ) のリストに変換する。

    Args:
        data: SAMIGO API の JSON レスポンス ({"sam_pub_collection": [...]})
        site_id: 講義サイト ID
        host: Sakai ホスト名
        site_name: 講義名 (省略時は None)
        tool_page_url: テスト・クイズツールの Page URL

    Returns:
        list[SakaiTask]: 正規化されたテスト・クイズタスク一覧
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("sam_pub_collection", [])

    tasks: list[SakaiTask] = []
    now = datetime.now(timezone.utc)

    for item in collection:
        # 非公開・下書き (status == "0") は除外
        raw_status = str(item.get("status", "1"))
        if raw_status == "0":
            continue

        q_id = item["publishedAssessmentId"]
        q_id_str = str(q_id)
        title = item["title"]

        open_date = parse_datetime(item.get("startDate"))
        due_date = parse_datetime(item.get("dueDate"))
        close_date = parse_datetime(item.get("retractDate"))

        time_limit = item.get("timeLimit")
        time_limit_seconds = int(time_limit) if time_limit is not None else None

        site_url = endpoints.get_site_url(host, site_id)
        url = tool_page_url or site_url

        # 締切判定
        if close_date and close_date < now:
            status = TaskStatus.CLOSED
        elif due_date and due_date < now:
            status = TaskStatus.CLOSED
        else:
            status = TaskStatus.OPEN

        tasks.append(
            SakaiTask(
                id=q_id_str,
                title=title,
                task_type=TaskType.QUIZ,
                site_id=site_id,
                site_name=site_name or site_id,
                due_date=due_date,
                open_date=open_date,
                close_date=close_date,
                is_submitted=False,
                status=status,
                url=url,
                site_url=site_url,
                instructions=None,
                attachments=[],
                max_points=None,
                time_limit_seconds=time_limit_seconds,
            )
        )

    return tasks
