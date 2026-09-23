# ==============================================================================
# 静的エンドポイント (パス定数)
# ==============================================================================

PORTAL = "/portal"                                      # トップページ (お気に入り講義の DOM 抽出用)
PORTAL_LOGIN = "/portal/login"                          # SSO ログイン画面

SESSION_CURRENT = "/direct/session/current.json"        # セッション有効性確認 & 有効期限延長
SITE_LIST = "/direct/site.json?_limit=0"                # 履修講義一覧 (全件取得のため _limit=0 を指定)
ASSIGNMENT_MY = "/direct/assignment/my.json?_limit=0"    # 履修中全講義の課題一覧 (全件取得のため _limit=0 を指定)
CALENDAR_MY = "/direct/calendar/my.json"                # カレンダー予定・イベント一覧
ANNOUNCEMENT_USER = "/direct/announcement/user.json"    # 全講義のお知らせ一覧 (?d=日数)

ATTACHMENT_ACCESS_PREFIX = "/access/content/attachment" # 添付ファイルダウンロード用 URL プレフィックス


# ==============================================================================
# 動的エンドポイント (講義IDや課題IDを埋め込む関数)
# ==============================================================================

def assignment_site(site_id: str) -> str:
    """指定講義の課題一覧 (/direct/assignment/site/{site_id}.json?_limit=0)"""
    return f"/direct/assignment/site/{site_id}.json?_limit=0"

def assignment_item(assignment_id: str) -> str:
    """特定課題の詳細情報・指示文・添付資料 (/direct/assignment/item/{assignment_id}.json)"""
    return f"/direct/assignment/item/{assignment_id}.json"

def sam_pub_context(site_id: str) -> str:
    """指定講義のテスト・クイズ一覧 (/direct/sam_pub/context/{site_id}.json)"""
    return f"/direct/sam_pub/context/{site_id}.json"

def sam_pub_item(published_assessment_id: str) -> str:
    """個別クイズの詳細メタデータ (/direct/sam_pub/{published_assessment_id}.json)"""
    return f"/direct/sam_pub/{published_assessment_id}.json"

def announcement_site(site_id: str) -> str:
    """指定講義のお知らせ一覧・添付資料 (/direct/announcement/site/{site_id}.json)"""
    return f"/direct/announcement/site/{site_id}.json"

def calendar_site(site_id: str) -> str:
    """指定講義のカレンダー予定一覧 (/direct/calendar/site/{site_id}.json)"""
    return f"/direct/calendar/site/{site_id}.json"

def content_site(site_id: str) -> str:
    """指定講義の配布資料・ファイル一覧 (/direct/content/site/{site_id}.json)"""
    return f"/direct/content/site/{site_id}.json"


# ==============================================================================
# Web 画面 URL 生成ヘルパー
# ==============================================================================

def get_site_url(host: str, site_id: str) -> str:
    """講義トップページ URL (https://<host>/portal/site/{site_id})"""
    return f"https://{host}/portal/site/{site_id}"
