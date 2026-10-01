"""Course-specific AI assistant policy filtering and data masking."""

import re
from urllib.parse import urlparse

from src.config import AIPolicyMode, Config
from src.models import (
    Announcement,
    CalendarEvent,
    CourseDashboard,
    CourseMaterial,
    CourseSite,
    SakaiTask,
)

MASKED_INSTRUCTION_TEXT = "[講義ポリシー (SCHEDULE_ONLY) により指示文は非表示です]"
MASKED_ANNOUNCEMENT_TEXT = "[講義ポリシー (SCHEDULE_ONLY) により本文は非表示です]"


def filter_courses(courses: list[CourseSite]) -> list[CourseSite]:
    """BLOCKED の講義を除外して返す。"""
    return [c for c in courses if Config.get_course_policy(c.id) != AIPolicyMode.BLOCKED]


def filter_tasks(tasks: list[SakaiTask]) -> list[SakaiTask]:
    """ポリシーに応じてタスクを除外・マスキングして返す。"""
    result: list[SakaiTask] = []
    for task in tasks:
        policy = Config.get_course_policy(task.site_id)
        if policy == AIPolicyMode.BLOCKED:
            continue
        elif policy == AIPolicyMode.SCHEDULE_ONLY:
            result.append(
                task.model_copy(
                    update={
                        "instructions": MASKED_INSTRUCTION_TEXT,
                        "attachments": [],
                        "max_points": None,
                    }
                )
            )
        elif policy == AIPolicyMode.TEXT_ONLY:
            # 添付ファイルのダウンロード URL のみ消去 (None にマスク)
            masked_attachments = [
                att.model_copy(update={"url": None}) for att in task.attachments
            ]
            result.append(task.model_copy(update={"attachments": masked_attachments}))
        else:  # ALLOW_ALL
            result.append(task)
    return result


def filter_announcements(announcements: list[Announcement]) -> list[Announcement]:
    """ポリシーに応じてお知らせを除外・マスキングして返す。"""
    result: list[Announcement] = []
    for item in announcements:
        policy = Config.get_course_policy(item.site_id)
        if policy == AIPolicyMode.BLOCKED:
            continue
        elif policy == AIPolicyMode.SCHEDULE_ONLY:
            result.append(
                item.model_copy(
                    update={
                        "content": MASKED_ANNOUNCEMENT_TEXT,
                        "attachments": [],
                    }
                )
            )
        elif policy == AIPolicyMode.TEXT_ONLY:
            # 添付ファイルのダウンロード URL のみ消去 (None にマスク)
            masked_attachments = [
                att.model_copy(update={"url": None}) for att in item.attachments
            ]
            result.append(item.model_copy(update={"attachments": masked_attachments}))
        else:  # ALLOW_ALL
            result.append(item)
    return result


def filter_calendar_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """ポリシーに応じてカレンダーイベントを除外・マスキングして返す。"""
    result: list[CalendarEvent] = []
    for ev in events:
        if ev.site_id:
            policy = Config.get_course_policy(ev.site_id)
        else:
            policy = AIPolicyMode.ALLOW_ALL

        if policy == AIPolicyMode.BLOCKED:
            continue
        elif policy == AIPolicyMode.SCHEDULE_ONLY:
            result.append(ev.model_copy(update={"description": None}))
        else:  # TEXT_ONLY, ALLOW_ALL
            result.append(ev)
    return result


def filter_course_materials(materials: list[CourseMaterial], site_id: str) -> list[CourseMaterial]:
    """ポリシーに応じて授業資料一覧を除外・マスキングして返す。"""
    policy = Config.get_course_policy(site_id)
    if policy == AIPolicyMode.BLOCKED:
        raise ValueError(f"指定講義 '{site_id}' は存在しないか利用できません。")
    elif policy == AIPolicyMode.SCHEDULE_ONLY:
        return []
    elif policy == AIPolicyMode.TEXT_ONLY:
        # ダウンロード URL のみ消去して一覧メタデータ（ファイル名等）のみ提供
        return [m.model_copy(update={"url": None}) for m in materials]
    return materials


def filter_dashboard(dashboard: CourseDashboard) -> CourseDashboard:
    """指定講義のダッシュボードにポリシーマスキングを一括適用する。"""
    policy = Config.get_course_policy(dashboard.site_id)
    if policy == AIPolicyMode.BLOCKED:
        raise ValueError(f"講義 '{dashboard.site_id}' は存在しないか、アクセスが制限されています。")

    return CourseDashboard(
        site_id=dashboard.site_id,
        site_name=dashboard.site_name,
        assignments=filter_tasks(dashboard.assignments),
        quizzes=filter_tasks(dashboard.quizzes),
        announcements=filter_announcements(dashboard.announcements),
        materials=filter_course_materials(dashboard.materials, dashboard.site_id),
    )


_SAKAI_RESOURCE_PATTERN = re.compile(r"^/access/content/(?:group|attachment)/([^/]+)/")


def check_download_allowed_by_url(url: str) -> None:
    """
    URL パスから講義 site_id を正規表現で特定し、ポリシーで許可されていない場合は例外を送出する。
    未設定講義 (Config.POLICIES 未登録) の場合も Config.get_course_policy() により
    自動的にデフォルト (TEXT_ONLY: 強 / DL禁止) が適用されるため、Secure by Default が完全に担保される。
    """
    path = urlparse(url).path
    match = _SAKAI_RESOURCE_PATTERN.match(path)

    if not match:
        # Sakai の講義リソース形式でない場合は安全側に倒して拒否
        raise PermissionError(f"URL '{url}' から対象講義を特定できないため、ダウンロードを制限しました。")

    site_id = match.group(1)
    policy = Config.get_course_policy(site_id)

    if policy == AIPolicyMode.BLOCKED:
        raise PermissionError(f"指定されたリソース '{url}' にはアクセスできません。")
    elif policy in (AIPolicyMode.SCHEDULE_ONLY, AIPolicyMode.TEXT_ONLY):
        raise PermissionError(
            f"講義 '{site_id}' は現在のポリシー ({policy.value}) によりファイルのダウンロードが禁止されています。"
        )
