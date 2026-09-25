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

    # 1. 辞書形式: {'epochSecond': 1712000000, 'nano': 0} または {'time': 1712600000000}
    if isinstance(raw, dict):
        if "epochSecond" in raw:
            try:
                sec = float(raw["epochSecond"])
                nano = float(raw.get("nano", 0))
                return datetime.fromtimestamp(sec + nano / 1e9, tz=timezone.utc)
            except (ValueError, TypeError, OverflowError, OSError):
                return None
        if "time" in raw:
            return parse_datetime(raw["time"])
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

    # 1. 改行系タグの置換
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])>", "\n", text)

    # 2. 残りの HTML タグを除去
    text = re.sub(r"<[^>]+>", "", text)

    # 3. HTML 実体参照のデコード (&nbsp;, &lt;, &gt;, &amp; 等)
    text = html.unescape(text)

    # 4. 特殊空白文字の正規化
    text = text.replace("\xa0", " ")

    # 各行の末尾空白を除去
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)

    # 5. 3行以上の連続する空行を2行（段落区切り）に圧縮
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 6. 前後の余分な空白を除去
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
    if not raw_attachments:
        return []

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
                full_url = f"https://{host}{endpoint}"
        else:
            full_url = None

        # ファイル名 (name または title、なければ URL パスから取得)
        raw_name = item.get("name") or item.get("title") or ""
        if raw_name:
            name = urllib.parse.unquote(str(raw_name))
        elif full_url:
            path = urllib.parse.urlparse(full_url).path
            last_segment = path.rstrip("/").split("/")[-1] if "/" in path else ""
            name = urllib.parse.unquote(last_segment) if last_segment else "attachment"
        else:
            name = "attachment"

        # ID
        raw_id = item.get("id") or item.get("attachmentId")
        if raw_id:
            att_id = str(raw_id)
        elif full_url:
            att_id = full_url
        else:
            att_id = name

        # サイズ (int 換算)
        raw_size = item.get("size") or item.get("size_bytes")
        size_bytes: int | None = None
        if raw_size is not None:
            try:
                size_bytes = int(float(raw_size))
            except (ValueError, TypeError):
                size_bytes = None

        # MIME タイプ
        content_type = (
            item.get("type")
            or item.get("contentType")
            or item.get("mimeType")
            or item.get("content_type")
        )
        if content_type is not None:
            content_type = str(content_type)

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
