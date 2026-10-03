"""Sakai API response parsers package."""

from src.client.parsers.announcement_parser import parse_announcements
from src.client.parsers.assignment_parser import parse_assignments
from src.client.parsers.base import (
    clean_html_text,
    parse_attachments,
    parse_datetime,
)
from src.client.parsers.calendar_parser import parse_calendar_events
from src.client.parsers.content_parser import parse_course_contents
from src.client.parsers.course_parser import (
    extract_tool_pages,
    parse_courses,
)
from src.client.parsers.favorite_parser import parse_favorite_courses
from src.client.parsers.quiz_parser import parse_quizzes

__all__ = [
    "clean_html_text",
    "parse_attachments",
    "parse_datetime",
    "extract_tool_pages",
    "parse_courses",
    "parse_favorite_courses",
    "parse_assignments",
    "parse_quizzes",
    "parse_announcements",
    "parse_calendar_events",
    "parse_course_contents",
]
