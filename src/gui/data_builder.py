"""UI data builder module for Sakai settings."""

import logging

from pydantic import BaseModel

from src.client.sakai_client import SakaiClient
from src.config import AIPolicyMode, Config

logger = logging.getLogger(__name__)


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
    request_timeout: float = 30.0    # 通信タイムアウト秒数 (デフォルト 30.0)
    courses: list[CourseSettingItem] # 講義一覧 (お気に入り優先順)


async def build_settings_ui_data() -> SettingsUIData:
    """
    Sakai から全講義一覧を取得し、既存の config.json とマージして
    UI 用データ (SettingsUIData) を構築する。
    sakai_host が未設定の場合や接続エラー時は空の講義一覧で安全に返却する。
    """
    # 1. 現在の config.json をロード
    config = Config.load()

    # 2. ホスト設定がある場合のみ講義一覧取得を試みる (未設定時・失敗時は空のまま安全に続行)
    courses = []
    if config.sakai_host:
        try:
            async with SakaiClient() as client:
                courses = await client.get_courses(favorites_only=False)
        except Exception as e:
            logger.warning(
                "講義一覧の取得をスキップしました (ドメイン未設定、接続エラー、または認証失敗): %s",
                e,
            )

    # 3. 講義データと既存ポリシーをマージ (お気に入り講義を先頭にソート)
    sorted_courses = sorted(courses, key=lambda c: (not c.is_favorite, c.name))
    course_items = [
        CourseSettingItem(
            id=c.id,
            title=c.name,
            is_favorite=c.is_favorite,
            current_policy=config.policies.get(c.id, Config.DEFAULT_POLICY),
        )
        for c in sorted_courses
    ]

    return SettingsUIData(
        sakai_host=config.sakai_host,
        presets=Config.UNIVERSITY_PRESETS,
        default_deadline_days=config.default_deadline_days,
        default_announcement_limit=config.default_announcement_limit,
        request_timeout=config.request_timeout,
        courses=course_items,
    )
