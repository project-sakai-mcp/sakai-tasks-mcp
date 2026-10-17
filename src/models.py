from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TaskType(str, Enum):
    """Task type"""
    ASSIGNMENT = "assignment"  # Standard assignment (/direct/assignment)
    QUIZ = "quiz"              # Quiz or assessment (/direct/sam_pub)


class TaskStatus(str, Enum):
    """Task progress status"""
    OPEN = "open"              # Open / pending submission
    SUBMITTED = "submitted"    # Submitted
    CLOSED = "closed"          # Closed / deadline passed


class MaterialType(str, Enum):
    """Course material item type"""
    FILE = "file"              # Downloadable file
    FOLDER = "folder"          # Folder (collection)


class BaseModelConfig(BaseModel):
    """Base class for all models with defensive parsing and datetime serialization settings."""
    model_config = ConfigDict(
        extra="ignore",            # Ignore unknown fields for safe parsing
        populate_by_name=True,    # Allow assignment by alias name
        use_enum_values=True      # Output enum values (strings) directly in JSON serialization
    )

# Field(description="...") attached so AI can accurately understand each field schema


class Attachment(BaseModelConfig):
    """Attachment file information for assignments or announcements."""
    id: str = Field(description="Attachment ID")
    name: str = Field(description="Filename including extension")
    url: str | None = Field(default=None, description="Download URL (masked to None under TEXT_ONLY / SCHEDULE_ONLY)")
    size_bytes: int | None = Field(default=None, description="File size in bytes")
    content_type: str | None = Field(default=None, description="MIME type (e.g., application/pdf)")


class CourseSite(BaseModelConfig):
    """Enrolled or joined course site information."""
    id: str = Field(description="Course site ID (e.g., 2024_01_1234567)")
    name: str = Field(description="Course name")
    is_favorite: bool = Field(default=False, description="Whether the course is bookmarked in the top bar favorites")
    site_url: str | None = Field(default=None, description="Course top page URL")
    tool_pages: dict[str, str] = Field(
        default_factory=dict,
        description="Direct URL mapping for tools within the course (e.g., {'assignment': '...', 'quiz': '...', 'resource': '...'})"
    )
    description: str | None = Field(default=None, description="Course description / syllabus overview")


class SakaiTask(BaseModelConfig):
    """
    Unified task model representing both assignments and quizzes in a common format.
    Core entity used by AI assistant for deadline tracking and task handling.
    """
    id: str = Field(description="Unique task ID (assignment ID or published assessment ID)")
    title: str = Field(description="Assignment / quiz title")
    task_type: TaskType = Field(description="Task type (assignment / quiz)")
    site_id: str = Field(description="Course site ID")
    site_name: str = Field(description="Course name")
    due_date: datetime | None = Field(default=None, description="Due date and time (with UTC/JST timezone)")
    open_date: datetime | None = Field(default=None, description="Opening date and time")
    close_date: datetime | None = Field(default=None, description="Final closing date and time (late submission deadline, etc.)")
    is_submitted: bool = Field(default=False, description="Submission flag (Note: Quizzes are marked unsubmitted by default due to Sakai SAMIGO API constraints preventing per-student completion checks)")
    status: TaskStatus = Field(default=TaskStatus.OPEN, description="Task progress status (open / submitted / closed)")
    url: str | None = Field(default=None, description="Web URL")
    site_url: str | None = Field(default=None, description="Course top page URL")
    instructions: str | None = Field(default=None, description="Task instructions / quiz description (HTML stripped)")
    attachments: list[Attachment] = Field(default_factory=list, description="List of attachments accompanying the task")
    max_points: float | None = Field(default=None, description="Maximum points/score (if configured)")
    time_limit_seconds: int | None = Field(default=None, description="Time limit in seconds (for quizzes, etc.)")


class Announcement(BaseModelConfig):
    """Course or system announcement / notice."""
    id: str = Field(description="Announcement ID")
    title: str = Field(description="Announcement title")
    content: str | None = Field(default=None, description="Announcement body content (HTML stripped)")
    published_at: datetime | None = Field(default=None, description="Publication date and time")
    created_by: str | None = Field(default=None, description="Author name (instructor, etc.)")
    site_id: str = Field(description="Course site ID")
    site_name: str = Field(description="Course name")
    url: str | None = Field(default=None, description="Web URL")
    attachments: list[Attachment] = Field(default_factory=list, description="List of files attached to the announcement")


class CalendarEvent(BaseModelConfig):
    """Schedule or event registered in the calendar."""
    id: str = Field(description="Calendar event ID")
    title: str = Field(description="Event title")
    description: str | None = Field(default=None, description="Event description")
    start_time: datetime | None = Field(default=None, description="Start date and time")
    end_time: datetime | None = Field(default=None, description="End date and time")
    event_type: str | None = Field(default=None, description="Event type (e.g., Assignment, Quiz, Academic Calendar)")
    site_id: str | None = Field(default=None, description="Course site ID (None for university-wide events or holidays)")
    site_name: str | None = Field(default=None, description="Course name")
    url: str | None = Field(default=None, description="Calendar URL")


class CourseMaterial(BaseModelConfig):
    """Course material, distributed file, or folder information in the course site."""
    id: str = Field(description="Resource ID (relative path format /group/site_id/...)")
    name: str = Field(description="Filename or folder name")
    material_type: MaterialType = Field(default=MaterialType.FILE, description="Material item type (file / folder)")
    is_collection: bool = Field(default=False, description="Whether the item is a folder (collection)")
    url: str | None = Field(default=None, description="Download URL (requires cookie authentication)")
    size_bytes: int | None = Field(default=None, description="File size in bytes")
    modified_at: datetime | None = Field(default=None, description="Last modified date and time")
    path: str | None = Field(default=None, description="Folder path hierarchy (e.g., /Lecture01/slides.pdf)")
    mime_type: str | None = Field(default=None, description="MIME type")
    site_id: str = Field(description="Course site ID")
    site_name: str | None = Field(default=None, description="Course name")


class UnreadForumMessage(BaseModelConfig):
    """Unread count information for course Messages and Forum tools."""
    site_id: str = Field(description="Course site ID")
    site_name: str = Field(description="Course name")
    unread_messages_count: int = Field(default=0, description="Number of unread messages")
    unread_forums_count: int = Field(default=0, description="Number of unread forum posts")
    message_url: str | None = Field(default=None, description="Messages tool URL")
    forum_url: str | None = Field(default=None, description="Forums tool URL")
    site_url: str | None = Field(default=None, description="Course top page URL")


class CourseDashboard(BaseModelConfig):
    """Consolidated summary model aggregating status for a specific course."""
    site_id: str = Field(description="Course site ID")
    site_name: str = Field(description="Course name")
    assignments: list[SakaiTask] = Field(default_factory=list, description="List of unsubmitted and submitted assignments")
    quizzes: list[SakaiTask] = Field(default_factory=list, description="List of quizzes and online tests")
    announcements: list[Announcement] = Field(default_factory=list, description="List of recent announcements")
    materials: list[CourseMaterial] = Field(default_factory=list, description="List of course materials and distributed files")
    unread_messages_count: int = Field(default=0, description="Number of unread messages")
    unread_forums_count: int = Field(default=0, description="Number of unread forum posts")
    message_url: str | None = Field(default=None, description="Messages tool URL")
    forum_url: str | None = Field(default=None, description="Forums tool URL")

