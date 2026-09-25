import html
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from src.models import Attachment


def parse_datetime(raw: Any) -> datetime | None:
    """
    Sakai API の多様な日時形式 (秒オブジェクト, ミリ秒数値, 秒数値, ISO文字列) を判定し、
    統一された datetime オブジェクト (UTC aware) に変換する。

    Args:
        raw: Sakai API から返される生の日時データ
             (例: {'epochSecond': 1712000000}, 1712000000000, "2026-08-31T00:00:00Z" 等)

    Returns:
        datetime | None: パースされた datetime (パース不能または None の場合は None)
    """
    if raw is None or raw == "":
        return None

    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)

    # 1. 辞書形式: {'epochSecond': 1712000000, 'nano': 0}
    if isinstance(raw, dict):
        if "epochSecond" in raw:
            try:
                sec = float(raw["epochSecond"])
                nano = float(raw.get("nano") or 0.0)
                return datetime.fromtimestamp(sec + nano / 1e9, tz=timezone.utc)
            except (ValueError, TypeError, OverflowError, OSError):
                return None
        return None

    # 2. 数値 (秒またはミリ秒)
    if isinstance(raw, (int, float)):
        try:
            val = float(raw)
            # 10^11 以上の場合はミリ秒数値と判定 (10^11 ms ≒ 1973年)
            if abs(val) >= 1e11:
                return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
            else:
                return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError, OSError):
            return None

    # 3. 文字列形式 (数値文字列, 8桁日付, ISO 8601)
    if isinstance(raw, str):
        raw_str = raw.strip()
        if not raw_str:
            return None

        # 8桁日付文字列 (例: "20240401")
        if len(raw_str) == 8 and raw_str.isdigit():
            try:
                dt = datetime.strptime(raw_str, "%Y%m%d")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        # 数値文字列の判定
        try:
            val = float(raw_str)
            if abs(val) >= 1e11:
                return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
            else:
                return datetime.fromtimestamp(val, tz=timezone.utc)
        except (ValueError, OverflowError):
            pass

        # ISO 8601 文字列 (例: "2026-08-31T00:00:00Z", "2024-10-15T23:59:00+09:00")
        try:
            iso_str = raw_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            pass

    return None


def clean_html_text(raw_html: str | None) -> str:
    """
    リッチエディタ等の生 HTML 文字列からタグを除去・整形し、AI や人間が読みやすい
    クリーンなプレーンテキストに変換する。

    Args:
        raw_html: 生 HTML 文字列 (指示文や連絡事項本文)

    Returns:
        str: サニタイズ・整形済みのプレーンテキスト
    """
    if raw_html is None:
        return ""

    if not isinstance(raw_html, str):
        raw_html = str(raw_html)

    if not raw_html.strip():
        return ""

    # 1. スクリプト・スタイルタグとその中身を除去
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", "", raw_html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", "", text)

    # 2. HTML コメントを除去
    text = re.sub(r"(?s)<!--.*?-->", "", text)

    # 3. 改行系タグの置換
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6]|table|blockquote|pre)>", "\n", text)

    # 4. 残りの HTML タグを除去
    text = re.sub(r"<[^>]+>", "", text)

    # 5. HTML 実体参照のデコード (&nbsp;, &lt;, &gt;, &amp; 等)
    text = html.unescape(text)

    # 6. 特殊空白文字の正規化
    text = text.replace("\xa0", " ")

    # 各行の末尾空白を除去
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)

    # 7. 3行以上の連続する空行を2行（段落区切り）に圧縮
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 8. 前後の余分な空白を除去
    return text.strip()


def parse_attachments(
    raw_attachments: list[dict[str, Any]] | None,
    host: str
) -> list[Attachment]:
    """
    Sakai API から返される添付ファイル情報リストを正規化し、Attachment モデルのリストに変換する。
    相対パス (例: /access/content/...) を完全修飾 URL に補正し、日本語ファイル名をデコードする。

    Args:
        raw_attachments: 生の添付ファイル辞書リスト
        host: Sakai ホスト名 (例: tact.ac.thers.ac.jp)

    Returns:
        list[Attachment]: 正規化された添付ファイル一覧
    """
    if not raw_attachments or not isinstance(raw_attachments, list):
        return []

    clean_host = host.removeprefix("https://").removeprefix("http://").rstrip("/")

    attachments: list[Attachment] = []
    for item in raw_attachments:
        if not isinstance(item, dict):
            continue

        raw_url = item.get("url") or ""
        if raw_url:
            if raw_url.startswith("http://") or raw_url.startswith("https://"):
                full_url = raw_url
            else:
                endpoint = raw_url if raw_url.startswith("/") else f"/{raw_url}"
                full_url = f"https://{clean_host}{endpoint}"
        else:
            full_url = None

        # ファイル名 (URL エンコードされている場合をデコード)
        raw_name = item.get("name")
        if raw_name:
            name = urllib.parse.unquote(str(raw_name))
        elif full_url:
            path = urllib.parse.urlparse(full_url).path
            last_segment = path.rstrip("/").split("/")[-1] if "/" in path else ""
            name = urllib.parse.unquote(last_segment) if last_segment else "attachment"
        else:
            name = "attachment"

        # 添付ファイル ID
        att_id = str(item.get("id") or full_url or name)

        # ファイルサイズ (0 バイトファイルも許容)
        raw_size = item.get("size")
        size_bytes: int | None = None
        if raw_size is not None:
            try:
                size_bytes = int(float(raw_size))
            except (ValueError, TypeError):
                size_bytes = None

        # MIME タイプ
        raw_type = item.get("mimeType") or item.get("type")
        content_type = str(raw_type) if raw_type is not None else None

        attachments.append(
            Attachment(
                id=att_id,
                name=name,
                url=full_url,
                size_bytes=size_bytes,
                content_type=content_type,
            )
        )

    return attachments
