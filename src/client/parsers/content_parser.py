"""Course content / materials parser from Sakai /direct/content/site/{siteId}.json."""

import urllib.parse
from typing import Any

from src.client import endpoints
from src.client.parsers.base import parse_datetime
from src.models import CourseMaterial, MaterialType


def parse_course_contents(
    data: dict[str, Any] | list[dict[str, Any]],
    site_id: str,
    host: str,
    site_name: str | None = None,
    resource_tool_page_url: str | None = None,
    files_only: bool = False,
) -> list[CourseMaterial]:
    """
    /direct/content/site/{siteId}.json のレスポンスをパースし、
    CourseMaterial モデルのリストに変換する。
    Sakai バージョンによって {"content_collection": [...]} の辞書形式、
    または [...] の直接配列形式の双方が返るため両構造に自動対応する。

    Args:
        data: Sakai API の JSON レスポンス (辞書または配列)
        site_id: 講義サイト ID
        host: Sakai ホスト名 (ダウンロード URL 補正用)
        site_name: 講義名 (省略時は None)
        resource_tool_page_url: 講義の「授業資料（リソース）」ツール直通 Page URL
        files_only: True の場合はフォルダ項目を除外し、ダウンロード可能なファイルのみを返却

    Returns:
        list[CourseMaterial]: 正規化された講義資料・配布ファイル一覧
    """
    if isinstance(data, list):
        collection = data
    else:
        collection = data.get("content_collection", [])

    materials: list[CourseMaterial] = []
    root_entity = f"/group/{site_id}/"

    for item in collection:
        entity_id = item.get("entityId", "")
        # ルートフォルダ項目は除外
        if entity_id == root_entity:
            continue

        raw_type = item.get("type", "")
        is_folder = raw_type == "collection"

        if is_folder and files_only:
            continue

        material_type = MaterialType.FOLDER if is_folder else MaterialType.FILE
        is_collection = is_folder

        raw_title = item.get("title") or ""
        name = urllib.parse.unquote(str(raw_title))

        raw_url = item.get("url") or ""
        if is_folder:
            url = resource_tool_page_url or endpoints.get_site_url(host, site_id)
            size_bytes = None
        else:
            if raw_url.startswith("http://") or raw_url.startswith("https://"):
                url = raw_url
            elif raw_url:
                endpoint = raw_url if raw_url.startswith("/") else f"/{raw_url}"
                url = f"https://{host}{endpoint}"
            else:
                url = None

            raw_size = item.get("size")
            size_bytes = int(float(raw_size)) if raw_size is not None and raw_size != "" else None

        container = item.get("container") or ""
        if container.startswith(root_entity):
            path = container[len(root_entity):]
        else:
            path = container or None

        modified_at = parse_datetime(item.get("modifiedDate"))
        mime_type = item.get("mimeType")
        mat_id = str(entity_id or url or name)

        materials.append(
            CourseMaterial(
                id=mat_id,
                name=name,
                material_type=material_type,
                is_collection=is_collection,
                url=url,
                size_bytes=size_bytes,
                modified_at=modified_at,
                path=path,
                mime_type=mime_type,
                site_id=site_id,
                site_name=site_name,
            )
        )

    return materials
