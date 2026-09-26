"""UI data builder module for Sakai settings."""

import asyncio
from typing import TYPE_CHECKING
from pydantic import BaseModel
from src.config import AIPolicyMode, Config

if TYPE_CHECKING:
    from src.client.sakai_client import SakaiClient


class CourseSettingItem(BaseModel):
    """設定表に 1 行として並ぶ講義データ"""
    id: str                          # 講義サイト ID (例: "2024_01_AI101")
    title: str                       # 講義名 (例: "人工知能基礎 (2024前期)")
    is_favorite: bool                # お気に入り講義フラグ (★判定用)
    current_policy: AIPolicyMode     # 現在設定されているポリシー (デフォルト: TEXT_ONLY)


class SettingsUIData(BaseModel):
    """設定画面の初期描画に必要な全データ"""
    sakai_host: str                  # 現在の Sakai ホスト名
    presets: dict[str, str]          # 大学ドメインプリセット一覧
    default_deadline_days: int       # 直近締切の取得対象日数 (デフォルト 30)
    default_announcement_limit: int  # お知らせ取得の最大件数 (デフォルト 7)
    courses: list[CourseSettingItem] # 講義一覧 (お気に入り優先順)


async def build_settings_ui_data(client: "SakaiClient | None" = None) -> SettingsUIData:
    """
    Sakai から全講義一覧を取得し、既存の config.json とマージして
    UI 用データ (SettingsUIData) を構築する。
    """
    # 1. 講義一覧とお気に入り情報を SakaiClient から取得 (未ログインなら自動ログイン)
    if client is not None:
        courses = await client.get_courses(favorites_only=False)
    else:
        from src.client.sakai_client import SakaiClient
        async with SakaiClient() as c:
            courses = await c.get_courses(favorites_only=False)

    # 2. 現在の config.json をロード
    config = Config.load()

    # 3. 講義データと既存ポリシーをマージ (お気に入り講義を先頭にソート)
    course_items = []
    sorted_courses = sorted(courses, key=lambda c: (not c.is_favorite, c.name))
    for c in sorted_courses:
        # 未設定時は Config.DEFAULT_POLICY (TEXT_ONLY: 強) を適用
        policy = config.policies.get(c.id, Config.DEFAULT_POLICY)
        course_items.append(
            CourseSettingItem(
                id=c.id,
                title=c.name,
                is_favorite=c.is_favorite,
                current_policy=policy,
            )
        )

    return SettingsUIData(
        sakai_host=config.sakai_host,
        presets=Config.UNIVERSITY_PRESETS,
        default_deadline_days=config.default_deadline_days,
        default_announcement_limit=config.default_announcement_limit,
        courses=course_items,
    )
