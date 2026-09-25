"""Sakai API response parsers package."""

__all__: list[str] = []

try:
    from src.client.parsers.base import (
        clean_html_text,
        parse_attachments,
        parse_datetime,
    )
    __all__.extend(["clean_html_text", "parse_attachments", "parse_datetime"])
except ImportError:
    pass

try:
    from src.client.parsers.course_parser import (
        extract_tool_pages,
        parse_courses,
    )
    __all__.extend(["extract_tool_pages", "parse_courses"])
except ImportError:
    pass

try:
    from src.client.parsers.favorite_parser import (
        parse_favorite_courses,
    )
    __all__.append("parse_favorite_courses")
except ImportError:
    pass

try:
    from src.client.parsers.assignment_parser import (
        parse_assignments,
    )
    __all__.append("parse_assignments")
except ImportError:
    pass

try:
    from src.client.parsers.quiz_parser import (
        parse_quizzes,
    )
    __all__.append("parse_quizzes")
except ImportError:
    pass

try:
    from src.client.parsers.announcement_parser import (
        parse_announcements,
    )
    __all__.append("parse_announcements")
except ImportError:
    pass

try:
    from src.client.parsers.calendar_parser import (
        parse_calendar_events,
    )
    __all__.append("parse_calendar_events")
except ImportError:
    pass

try:
    from src.client.parsers.content_parser import (
        parse_course_contents,
    )
    __all__.append("parse_course_contents")
except ImportError:
    pass
