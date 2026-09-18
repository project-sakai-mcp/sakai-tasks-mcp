from enum import Enum
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class TaskType(str, Enum):
    """タスク種別"""
    ASSIGNMENT = "assignment"  # 通常の提出課題 (/direct/assignment)
    QUIZ = "quiz"              # 小テスト・オンラインテスト (/direct/sam_pub)


class TaskStatus(str, Enum):
    """タスクの進行状態"""
    OPEN = "open"              # 受付中 (未提出)
    SUBMITTED = "submitted"    # 提出済み
    CLOSED = "closed"          # 締切終了


class MaterialType(str, Enum):
    """授業資料アイテム種別"""
    FILE = "file"              # ダウンロード可能なファイル
    FOLDER = "folder"          # フォルダ (コレクション)


class BaseModelConfig(BaseModel):
    """全モデル共通の基底クラス (防御的パースと日時シリアライズ設定)"""
    model_config = ConfigDict(
        extra="ignore",            # 未知のフィールドを無視して安全にパース
        populate_by_name=True,    # エイリアス名での代入を許容
        use_enum_values=True      # JSON 出力時に Enum 値 (文字列) を直接出力
    )

# AI が各フィールドの意味を正確に解釈できるよう Field(description="...") を付与

class Attachment(BaseModelConfig):
    """課題やお知らせに添付されたファイル情報"""
    id: str = Field(description="添付ファイル ID")
    name: str = Field(description="ファイル名 (拡張子含む)")
    url: str | None = Field(default=None, description="ダウンロード用 URL (TEXT_ONLY / SCHEDULE_ONLY 時は None にマスク)")
    size_bytes: int | None = Field(default=None, description="ファイルサイズ (バイト単位)")
    content_type: str | None = Field(default=None, description="MIME タイプ (例: application/pdf)")


class CourseSite(BaseModelConfig):
    """履修・所属している講義サイト情報"""
    id: str = Field(description="講義サイト ID (例: 2024_01_1234567)")
    name: str = Field(description="講義名 / サイトタイトル")
    is_favorite: bool = Field(default=False, description="トップバーにお気に入り登録されているか")
    site_url: str | None = Field(default=None, description="Sakai ポータル上の講義トップページ URL")
    tool_pages: dict[str, str] = Field(
        default_factory=dict,
        description="講義内の各ツールへの直通 URL マッピング (例: {'assignment': '...', 'quiz': '...', 'resource': '...'})"
    )
    description: str | None = Field(default=None, description="講義の説明文 / シラバス概要")


class SakaiTask(BaseModelConfig):
    """
    課題および小テストを共通フォーマットで表現する統合タスクモデル。
    AI アシスタントが締切管理や課題解答を行うための中心エンティティ。
    """
    id: str = Field(description="タスク一意 ID (課題 ID または テスト公開 ID)")
    title: str = Field(description="課題 / テストのタイトル")
    task_type: TaskType = Field(description="タスク種別 (assignment / quiz)")
    site_id: str = Field(description="所属する講義サイト ID")
    site_name: str = Field(description="所属する講義名")
    due_date: datetime | None = Field(default=None, description="締切日時 (UTC/JST タイムゾーン付き)")
    open_date: datetime | None = Field(default=None, description="受付開始日時")
    close_date: datetime | None = Field(default=None, description="最終受付終了日時 (遅延提出締切等)")
    is_submitted: bool = Field(default=False, description="提出済みフラグ (※小テストは Sakai SAMIGO API の制約上、学生別の受験完了フラグが取得できないため原則未受験判定となります)")
    status: TaskStatus = Field(default=TaskStatus.OPEN, description="タスク進行状態 (open / submitted / closed)")
    url: str | None = Field(default=None, description="Sakai 上の課題/テスト直通 Web 画面 URL")
    site_url: str | None = Field(default=None, description="所属講義トップページ URL")
    instructions: str | None = Field(default=None, description="課題の指示文 / テストの説明 (HTML 除去済みテキスト)")
    attachments: list[Attachment] = Field(default_factory=list, description="課題に付属する添付ファイル一覧")
    max_points: float | None = Field(default=None, description="満点配点 (設定されている場合)")
    time_limit_seconds: int | None = Field(default=None, description="制限時間秒数 (小テスト等の場合)")


class Announcement(BaseModelConfig):
    """講義またはシステムからのお知らせ・連絡事項"""
    id: str = Field(description="お知らせ ID")
    title: str = Field(description="お知らせタイトル")
    content: str | None = Field(default=None, description="お知らせ本文 (HTML 除去済みテキスト)")
    published_at: datetime | None = Field(default=None, description="公開日時")
    created_by: str | None = Field(default=None, description="発信者名 (教員名等)")
    site_id: str = Field(description="所属する講義サイト ID")
    site_name: str = Field(description="所属する講義名")
    url: str | None = Field(default=None, description="Sakai 上のお知らせ直通 Web 画面 URL")
    attachments: list[Attachment] = Field(default_factory=list, description="お知らせに添付されたファイル一覧")


class CalendarEvent(BaseModelConfig):
    """カレンダーに登録されたスケジュール・講義イベント"""
    id: str = Field(description="カレンダーイベント ID")
    title: str = Field(description="イベントタイトル")
    description: str | None = Field(default=None, description="イベント説明")
    start_time: datetime | None = Field(default=None, description="開始日時")
    end_time: datetime | None = Field(default=None, description="終了日時")
    event_type: str | None = Field(default=None, description="イベント種別 (例: Assignment, Quiz, Academic Calendar)")
    site_id: str | None = Field(default=None, description="所属する講義サイト ID (全学共通行事・祝日等の場合は None)")
    site_name: str | None = Field(default=None, description="所属する講義名")
    url: str | None = Field(default=None, description="Sakai 上のカレンダー直通 URL")


class CourseMaterial(BaseModelConfig):
    """講義サイト内の授業資料・配布ファイル・フォルダ情報"""
    id: str = Field(description="リソース ID (相対パス形式 /group/site_id/...)")
    name: str = Field(description="ファイル名またはフォルダ名")
    material_type: MaterialType = Field(default=MaterialType.FILE, description="資料種別 (file / folder)")
    is_collection: bool = Field(default=False, description="フォルダ (コレクション) であるか")
    url: str | None = Field(default=None, description="ダウンロード URL (Cookie 認証必須)")
    size_bytes: int | None = Field(default=None, description="ファイルサイズ (バイト単位)")
    modified_at: datetime | None = Field(default=None, description="最終更新日時")
    path: str | None = Field(default=None, description="フォルダ階層パス (例: /第1回講義資料/スライド.pdf)")
    mime_type: str | None = Field(default=None, description="MIME タイプ")
    site_id: str = Field(description="所属する講義サイト ID")
    site_name: str | None = Field(default=None, description="所属する講義名")


class CourseDashboard(BaseModelConfig):
    """特定講義の状況を一括集約した総合サマリーモデル"""
    site_id: str = Field(description="講義サイト ID")
    site_name: str = Field(description="講義名")
    assignments: list[SakaiTask] = Field(default_factory=list, description="未提出・提出済みの課題一覧")
    quizzes: list[SakaiTask] = Field(default_factory=list, description="小テスト・オンラインテスト一覧")
    announcements: list[Announcement] = Field(default_factory=list, description="直近のお知らせ一覧")
    materials: list[CourseMaterial] = Field(default_factory=list, description="授業資料・配布ファイル一覧")
