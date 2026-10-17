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
    UnreadForumMessage,
)

MASKED_INSTRUCTION_TEXT = "[Instructions hidden by course policy (SCHEDULE_ONLY)]"
MASKED_ANNOUNCEMENT_TEXT = "[Content hidden by course policy (SCHEDULE_ONLY)]"


def filter_courses(courses: list[CourseSite]) -> list[CourseSite]:
    """Filter out BLOCKED courses."""
    return [c for c in courses if Config.get_course_policy(c.id) != AIPolicyMode.BLOCKED]


def filter_tasks(tasks: list[SakaiTask]) -> list[SakaiTask]:
    """Filter and mask tasks according to course policies."""
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
            # Mask download URLs of attachments (set to None)
            masked_attachments = [
                att.model_copy(update={"url": None}) for att in task.attachments
            ]
            result.append(task.model_copy(update={"attachments": masked_attachments}))
        else:  # ALLOW_ALL
            result.append(task)
    return result


def filter_announcements(announcements: list[Announcement]) -> list[Announcement]:
    """Filter and mask announcements according to course policies."""
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
            # Mask download URLs of attachments (set to None)
            masked_attachments = [
                att.model_copy(update={"url": None}) for att in item.attachments
            ]
            result.append(item.model_copy(update={"attachments": masked_attachments}))
        else:  # ALLOW_ALL
            result.append(item)
    return result


def filter_calendar_events(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """Filter and mask calendar events according to course policies."""
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
    """Filter and mask course materials according to course policies."""
    policy = Config.get_course_policy(site_id)
    if policy == AIPolicyMode.BLOCKED:
        raise ValueError(f"Specified course '{site_id}' does not exist or is unavailable.")
    elif policy == AIPolicyMode.SCHEDULE_ONLY:
        return []
    elif policy == AIPolicyMode.TEXT_ONLY:
        # Strip download URLs to only provide metadata (filenames, etc.)
        return [m.model_copy(update={"url": None}) for m in materials]
    return materials


def filter_unread_forum_messages(
    items: list[UnreadForumMessage],
) -> list[UnreadForumMessage]:
    """Filter unread messages and forum items according to course policies."""
    return [
        item for item in items
        if Config.get_course_policy(item.site_id) != AIPolicyMode.BLOCKED
    ]


def filter_dashboard(dashboard: CourseDashboard) -> CourseDashboard:
    """Apply policy masking to a course dashboard in bulk."""
    policy = Config.get_course_policy(dashboard.site_id)
    if policy == AIPolicyMode.BLOCKED:
        raise ValueError(f"Course '{dashboard.site_id}' does not exist or access is restricted.")

    return CourseDashboard(
        site_id=dashboard.site_id,
        site_name=dashboard.site_name,
        assignments=filter_tasks(dashboard.assignments),
        quizzes=filter_tasks(dashboard.quizzes),
        announcements=filter_announcements(dashboard.announcements),
        materials=filter_course_materials(dashboard.materials, dashboard.site_id),
        unread_messages_count=dashboard.unread_messages_count,
        unread_forums_count=dashboard.unread_forums_count,
        message_url=dashboard.message_url,
        forum_url=dashboard.forum_url,
    )



_SAKAI_RESOURCE_PATTERN = re.compile(r"^/access/content/(?:group|attachment)/([^/]+)/")


def check_download_allowed_by_url(url: str) -> None:
    """
    Extract course site_id from URL path and raise PermissionError if download is not allowed by policy.
    Unconfigured courses default to TEXT_ONLY (DL prohibited) to ensure Secure by Default.
    """
    path = urlparse(url).path
    match = _SAKAI_RESOURCE_PATTERN.match(path)

    if not match:
        raise PermissionError(f"Download restricted because the target course could not be identified from URL '{url}'.")

    site_id = match.group(1)
    policy = Config.get_course_policy(site_id)

    if policy == AIPolicyMode.BLOCKED:
        raise PermissionError(f"Access to the specified resource '{url}' is denied.")
    elif policy in (AIPolicyMode.SCHEDULE_ONLY, AIPolicyMode.TEXT_ONLY):
        raise PermissionError(
            f"Downloading files from course '{site_id}' is prohibited under the current policy ({policy.value})."
        )
