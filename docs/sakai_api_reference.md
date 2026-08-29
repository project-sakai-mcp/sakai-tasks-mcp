# Sakai Direct REST API リファレンス & 実装ガイド

本書は、Sakai LMS の EntityBroker Direct REST API の仕様、主要エンドポイント、データ構造、および `sakai-tasks-mcp` 実装時における重要な留意点をまとめた技術リファレンスです。

---

## 1. Sakai Direct REST API 共通仕様

Sakai は **EntityBroker** と呼ばれるフレームワークを通じて RESTful API を提供しています。

### 基本 URL 構造
* エンドポイントは通常 `/direct/{entity_prefix}` で構成されます。
* 出力形式は URL 末尾に拡張子（通常 `.json`）を付与するか、`Accept: application/json` ヘッダーを指定します。
  * 例: `https://<sakai-host>/direct/site.json`
  * 例: `https://<sakai-host>/direct/assignment/site/{siteId}.json`

### レスポンスフォーマットの規則性
* **コレクション（一覧）API**:
  * 常に `{ "{entity_name}_collection": [ ... ] }` という形式のオブジェクトでラップされて返されます。
  * 例: `site.json` -> `{"site_collection": [...]}`
  * 例: `assignment/site/{siteId}.json` -> `{"assignment_collection": [...]}`
  * 例: `sam_pub/context/{siteId}.json` -> `{"sam_pub_collection": [...]}`
* **単一エンティティ（詳細）API**:
  * エンティティオブジェクトそのものが直接返されます。

### 共通クエリパラメータ (Pagination & Filtering)
EntityBroker は Ruby on Rails 風のパラメータ規約をサポートしています。

| パラメータ | 型 | 説明 | 例 |
| :--- | :--- | :--- | :--- |
| `_start` | int | 取得開始位置 (0-indexed) | `_start=0` |
| `_limit` | int | 最大取得件数 (0 は全件またはサーバー上限) | `_limit=50` |
| `_page` | int | ページ番号 (0-indexed) | `_page=1` |
| `_perpage` | int | 1ページあたりの件数 | `_perpage=20` |
| `_order` / `_sort` | string | ソート順（フィールド名 + `_asc` / `_desc` / `_reverse`） | `_order=dueTime_desc` |
| `_validateSession` | boolean | セッションが有効かを明示的にチェック | `_validateSession=true` |
| `no-cache` | flag | キャッシュヘッダをバイパス | `no-cache` |

### HTTP ステータスコード
* `200 OK`: リクエスト成功・データ返却
* `401 UNAUTHORIZED`: 認証が必要（未ログインまたはセッション失効）
* `403 FORBIDDEN`: 権限不足（ログイン済みだがアクセス権がない）
* `404 NOT FOUND`: 存在しないエンティティまたは無効な URL / ツールが無効
* `500 INTERNAL SERVER ERROR`: サーバー内部エラー

---

## 2. 主要エンティティ & エンドポイント詳細

### 2.1 講義・サイト (`/site`)

ユーザーが所属している講義やプロジェクトサイトの情報を扱います。

* **一覧取得**: `GET /direct/site.json`
  * ログインユーザーがアクセス可能なすべてのサイト一覧を取得。
* **サイト詳細**: `GET /direct/site/{siteId}.json`
* **サイト内ツール一覧**: `GET /direct/site/{siteId}/pages.json`
  * 当該サイトでどのツール（課題、テスト、お知らせ等）が有効になっているかを確認可能。

#### 主要データ構造 (`site_collection` 内の要素)
```json
{
  "id": "2024_01_12345",
  "title": "人工知能概論 (春学期)",
  "description": "...",
  "type": "course",
  "published": true,
  "owner": "user123",
  "modifiedDate": 1712000000000
}
```

---

### 2.2 課題 (`/assignment`)

Sakai の「課題」ツールのデータを扱います。

* **全サイトの課題一覧**: `GET /direct/assignment/my.json`
  * ユーザーの全受講講義の課題を一括取得。
* **指定サイトの課題一覧**: `GET /direct/assignment/site/{siteId}.json`
  * 指定講義の課題一覧を取得。
* **課題詳細**: `GET /direct/assignment/item/{assignmentId}.json`
* **ディープリンク**: `GET /direct/assignment/deepLink/{assignmentRef}`

#### 主要データ構造 (`assignment_collection` 内の要素)
```json
{
  "id": "assignment-uuid-1234",
  "title": "第3回復習レポート",
  "context": "2024_01_12345",
  "instructions": "<p>講義資料の第3章を読み...</p>",
  "status": "OPEN",
  "draft": false,
  "submissionType": "ATTACHMENTS_ONLY",
  "openTime": { "epochSecond": 1712000000, "nano": 0 },
  "dueTime": { "epochSecond": 1712600000, "nano": 0 },
  "closeTime": { "epochSecond": 1712600000, "nano": 0 },
  "dropDeadTime": { "epochSecond": 1712600000, "nano": 0 },
  "openTimeString": "2024-04-01 09:00:00",
  "dueTimeString": "2024-04-08 23:59:59",
  "maxGradePoint": "100",
  "gradeScale": "Points",
  "submissions": []
}
```

---

### 2.3 テスト・小テスト (`/sam_pub` - SAMIGO)

Sakai の「テスト・クイズ」ツールのデータを扱います。

* **指定サイトの公開テスト一覧**: `GET /direct/sam_pub/context/{siteId}.json`
* **テスト詳細**: `GET /direct/sam_pub/{publishedAssessmentId}.json`

#### 主要データ構造 (`sam_pub_collection` 内の要素)
```json
{
  "publishedAssessmentId": 123456,
  "title": "第2回確認小テスト",
  "startDate": 1712000000000,
  "dueDate": 1712600000000,
  "retractDate": 1712600000000,
  "timeLimit": 1800,
  "status": "1"
}
```

---

### 2.4 お知らせ (`/announcement`)

講義やシステムのお知らせを扱います。

* **ユーザーの全お知らせ一覧**: `GET /direct/announcement/user.json`
* **指定サイトのお知らせ一覧**: `GET /direct/announcement/site/{siteId}.json`
* **今日のお知らせ**: `GET /direct/announcement/motd.json`
* **パラメータ**:
  * `n`: 最大取得件数 (例: `?n=20`)
  * `d`: 過去取得日数 (例: `?d=30` で過去30日分)

#### 主要データ構造 (`announcement_collection` 内の要素)
```json
{
  "announcementId": "annc-uuid-1234",
  "id": "annc-uuid-1234",
  "title": "次回講義の教室変更について",
  "body": "<p>来週の講義は情報棟第1講義室で行います。</p>",
  "createdByDisplayName": "担当教員",
  "createdOn": 1712000000000,
  "siteId": "2024_01_12345",
  "siteTitle": "人工知能概論",
  "attachments": []
}
```

---

### 2.5 カレンダー・日程 (`/calendar`)

講義日程や提出締切などのスケジュールを扱います。

* **ユーザーの全カレンダーイベント**: `GET /direct/calendar/my.json`
* **指定サイトのカレンダーイベント**: `GET /direct/calendar/site/{siteId}.json`
* **パラメータ**:
  * `firstDate`: 検索開始日 (`yyyy-MM-dd`)
  * `lastDate`: 検索終了日 (`yyyy-MM-dd`)

#### 主要データ構造 (`calendar_collection` 内の要素)
```json
{
  "eventId": "cal-uuid-1234",
  "title": "課題提出締切: 第3回レポート",
  "siteId": "2024_01_12345",
  "siteName": "人工知能概論",
  "firstTime": { "time": 1712600000000 },
  "duration": 3600000,
  "type": "Assignment",
  "assignmentId": "assignment-uuid-1234"
}
```

---

### 2.6 セッション & ユーザー (`/session`, `/user`)

認証確認・セッション寿命の監視に不可欠なエンドポイントです。

* **現在のセッション情報確認**: `GET /direct/session/current.json`
* **タイムアウトをリフレッシュしない確認**: `GET /direct/session/current/norefresh.json` (または `?auto=true`)
* **現在のユーザー情報**: `GET /direct/user/current.json`

#### セッション (`/session/current.json`) レスポンス構造
```json
{
  "id": "c7a8b9d0-...",
  "userId": "internal-user-uuid",
  "userEid": "student_account_id",
  "active": true,
  "creationTime": 1712000000000,
  "lastAccessedTime": 1712005000000,
  "maxInactiveInterval": 7200
}
```

#### ユーザー (`/user/current.json`) レスポンス構造
```json
{
  "id": "internal-user-uuid",
  "eid": "student_account_id",
  "displayName": "名古屋 太郎",
  "email": "taro@example.ac.jp"
}
```

---

### 2.7 教材・リソース (`/content`)

講義資料や配布ファイルの取得に使用できます。

* **指定サイトのリソース一覧**: `GET /direct/content/site/{siteId}.json`
* **マイワークスペースのリソース**: `GET /direct/content/my.json`

---

## 3. 実装上の最重要注意点 & Comfortable Sakai の知見

### 3.1 日時フィールドのフォーマット不統一（最重要！）
Sakai の各ツール（課題、テスト、お知らせ、カレンダー）は開発時期や内部アーキテクチャが異なるため、日時の表現形式がバラバラです。

| エンティティ | 日時フィールド例 | 形式 | 単位 / 構造 |
| :--- | :--- | :--- | :--- |
| **課題 (Assignment)** | `dueTime`, `closeTime` | `Instant` オブジェクト | `{ "epochSecond": 1712600000, "nano": 0 }` (秒) |
| **テスト (SAMIGO)** | `startDate`, `dueDate` | 数値 (long) | `1712600000000` (**ミリ秒**) |
| **お知らせ (Announcement)** | `createdOn` | 数値 (long) / Date | `1712600000000` (**ミリ秒**) |
| **カレンダー (Calendar)** | `firstTime` | Time オブジェクト | `{ "time": 1712600000000 }` (**ミリ秒**) |
| **サイト (Site)** | `modifiedDate` | 数値 (long) | `1712600000000` (**ミリ秒**) |

> [!WARNING]
> **ミリ秒と秒の混在に厳重注意！**
> Python の `datetime.fromtimestamp()` に渡す際、Assignment の `epochSecond` はそのまま使えますが、SAMIGO や Announcement、Calendar のタイムスタンプは `1000` で割って秒に変換する必要があります。

### 3.2 ID フィールドの名前の揺れ
| エンティティ | ID フィールド名 |
| :--- | :--- |
| **サイト (Site)** | `id` (例: `"2024_01_12345"`) |
| **課題 (Assignment)** | `id` (例: `"c8b1..."`) |
| **テスト (SAMIGO)** | `publishedAssessmentId` (例: `12345` ※数値型) |
| **お知らせ (Announcement)** | `announcementId` または `id` |
| **カレンダー (Calendar)** | `eventId` |

### 3.3 課題・小テストの一括取得 vs サイト別取得の使い分け
* `/direct/assignment/my.json` は全履修科目の課題を一括取得できるため高速です。
* 一方、テスト・小テスト (`sam_pub`) は `/direct/sam_pub/context/{siteId}.json` のように **サイトごとの取得しか提供されていません**。
* そのため、統合タスクリストを作成する場合は以下のフローが効率的です：
  1. `GET /direct/site.json` で履修中サイト一覧を取得
  2. `GET /direct/assignment/my.json` で課題を一括取得
  3. 各サイトに対して並行（`asyncio.gather`）で `GET /direct/sam_pub/context/{siteId}.json` を取得してマージ

### 3.4 セッション監視と `norefresh` の活用
* 定期的なヘルスチェックやツール実行前のセッション確認には `GET /direct/session/current/norefresh.json` (または `?auto=true`) を使用します。
* これにより、無駄にセッション有効期限を延ばしすぎることなく、現在のセッション状態（ログイン中か失効中か）を安全に確認できます。

---

## 4. Python (Pydantic) データモデル設計の推奨例

Python クライアント側で統一して扱うためのモデル設計案です。

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TaskType(str, Enum):
    ASSIGNMENT = "assignment"
    QUIZ = "quiz"
    EVENT = "event"

class TaskStatus(str, Enum):
    OPEN = "open"
    SUBMITTED = "submitted"
    CLOSED = "closed"
    DRAFT = "draft"

class SakaiTask(BaseModel):
    id: str = Field(..., description="タスクの一意な識別子 (UUIDまたはID文字列)")
    title: str = Field(..., description="課題・小テストのタイトル")
    site_id: str = Field(..., description="講義サイトID")
    site_name: Optional[str] = Field(None, description="講義名")
    task_type: TaskType = Field(..., description="タスクの種類 (assignment/quiz/event)")
    due_date: Optional[datetime] = Field(None, description="締切日時 (UTCまたはローカル時刻)")
    close_date: Optional[datetime] = Field(None, description="最終受付日時")
    instructions: Optional[str] = Field(None, description="課題指示文・詳細")
    is_submitted: bool = Field(default=False, description="提出済みかどうか")
    max_points: Optional[float] = Field(None, description="配点")
    url: Optional[str] = Field(None, description="Web上のSakai該当ページURL")
```

---

## 5. 参考資料
* Sakai 公式 EntityBroker ドキュメント (`../sakai-lms-api-docs/`)
* [Comfortable Sakai (kyoto-u/comfortable-sakai)](https://github.com/kyoto-u/comfortable-sakai)
