"""Tests for models and policy filtering of unread messages and forums."""

import pytest

from src.config import AIPolicyMode, Config
from src.models import (
    CourseDashboard,
    UnreadForumMessage,
)
from src.policy import (
    filter_dashboard,
    filter_unread_forum_messages,
)


def test_unread_forum_message_model():
    msg = UnreadForumMessage(
        site_id="site_1",
        site_name="講義1",
        unread_messages_count=2,
        unread_forums_count=5,
        message_url="https://tact.ac.thers.ac.jp/portal/directtool/m1",
        forum_url="https://tact.ac.thers.ac.jp/portal/directtool/f1",
        site_url="https://tact.ac.thers.ac.jp/portal/site/site_1",
    )
    assert msg.site_id == "site_1"
    assert msg.site_name == "講義1"
    assert msg.unread_messages_count == 2
    assert msg.unread_forums_count == 5
    assert msg.message_url == "https://tact.ac.thers.ac.jp/portal/directtool/m1"
    assert msg.forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/f1"


def test_filter_unread_forum_messages(monkeypatch):
    items = [
        UnreadForumMessage(site_id="allowed_site", site_name="OK Course", unread_messages_count=1),
        UnreadForumMessage(site_id="blocked_site", site_name="NG Course", unread_messages_count=3),
    ]

    def mock_get_course_policy(site_id: str) -> AIPolicyMode:
        if site_id == "blocked_site":
            return AIPolicyMode.BLOCKED
        return AIPolicyMode.ALLOW_ALL

    monkeypatch.setattr(Config, "get_course_policy", mock_get_course_policy)

    filtered = filter_unread_forum_messages(items)
    assert len(filtered) == 1
    assert filtered[0].site_id == "allowed_site"
    assert filtered[0].unread_messages_count == 1


def test_filter_dashboard_preserves_unread_info(monkeypatch):
    monkeypatch.setattr(Config, "get_course_policy", lambda site_id: AIPolicyMode.ALLOW_ALL)

    dashboard = CourseDashboard(
        site_id="site_1",
        site_name="講義1",
        unread_messages_count=4,
        unread_forums_count=8,
        message_url="https://tact.ac.thers.ac.jp/portal/directtool/m1",
        forum_url="https://tact.ac.thers.ac.jp/portal/directtool/f1",
    )

    filtered = filter_dashboard(dashboard)
    assert filtered.site_id == "site_1"
    assert filtered.unread_messages_count == 4
    assert filtered.unread_forums_count == 8
    assert filtered.message_url == "https://tact.ac.thers.ac.jp/portal/directtool/m1"
    assert filtered.forum_url == "https://tact.ac.thers.ac.jp/portal/directtool/f1"
