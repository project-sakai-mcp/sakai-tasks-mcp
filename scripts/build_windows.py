#!/usr/bin/env python3
"""
Windows 用 Embeddable Python 配布パッケージ作成スクリプト
docs/architecture.md 7.1.2 に準拠
"""

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
PACKAGE_DIR = DIST_DIR / "sakai-tasks-mcp-windows"
PYTHON_EMBED_DIR = PACKAGE_DIR / "python-embed"
SITE_PACKAGES_DIR = PYTHON_EMBED_DIR / "Lib" / "site-packages"
SRC_DIR = ROOT_DIR / "src"
RUN_BAT_SRC = ROOT_DIR / "scripts" / "run.bat"
REQUIREMENTS_TXT = ROOT_DIR / "requirements.txt"

PYTHON_VERSION = "3.12.8"
EMBED_ZIP_NAME = f"python-{PYTHON_VERSION}-embed-amd64.zip"
EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{EMBED_ZIP_NAME}"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def download_file(url: str, dest_path: Path) -> Path:
    """指定 URL からファイルをダウンロードする（キャッシュが存在する場合は再利用）。"""
    if dest_path.exists():
        print(f"[build_windows] Using cached: {dest_path}")
        return dest_path

    print(f"[build_windows] Downloading: {url} -> {dest_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


def setup_embeddable_python(dest_dir: Path) -> None:
    """Embeddable Python zip をダウンロードし、dest_dir に展開する。"""
    zip_cache_path = DIST_DIR / EMBED_ZIP_NAME
    download_file(EMBED_URL, zip_cache_path)

    print(f"[build_windows] Extracting {zip_cache_path} -> {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_cache_path, "r") as zf:
        zf.extractall(dest_dir)


def configure_pth(python_embed_dir: Path) -> None:
    """
    python312._pth を設定し、親ディレクトリ (パッケージルート) と Lib/site-packages の読み込み、
    および site の有効化を行う。
    """
    pth_file = python_embed_dir / "python312._pth"
    print(f"[build_windows] Configuring {pth_file}")
    content = "python312.zip\n.\n..\nLib/site-packages\nimport site\n"
    pth_file.write_text(content, encoding="utf-8")

    site_packages = python_embed_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)


def install_dependencies(python_embed_dir: Path, requirements_file: Path) -> None:
    """依存ライブラリを python-embed/Lib/site-packages にインストールする。"""
    if sys.platform != "win32":
        raise RuntimeError("build_windows.py must be run on Windows (win32).")

    site_packages = python_embed_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    python_exe = python_embed_dir / "python.exe"
    get_pip_path = python_embed_dir / "get-pip.py"
    download_file(GET_PIP_URL, get_pip_path)

    print("[build_windows] Installing pip into embeddable Python...")
    subprocess.run(
        [str(python_exe), str(get_pip_path), "--no-warn-script-location"],
        check=True,
    )
    if get_pip_path.exists():
        get_pip_path.unlink()

    print("[build_windows] Installing setuptools and wheel into embeddable Python...")
    subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "setuptools",
            "wheel",
            "--no-warn-script-location",
        ],
        check=True,
    )

    print(f"[build_windows] Installing packages from {requirements_file}...")
    subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_file),
            "--no-warn-script-location",
        ],
        check=True,
    )

    scripts_dir = python_embed_dir / "Scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)


def copy_app_files(package_dir: Path) -> None:
    """アプリケーションソースコード (src/) および起動スクリプト (run.bat) をパッケージに配置する。"""
    dest_src = package_dir / "src"
    print(f"[build_windows] Copying {SRC_DIR} -> {dest_src}")
    if dest_src.exists():
        shutil.rmtree(dest_src)
    shutil.copytree(
        SRC_DIR,
        dest_src,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    dest_run_bat = package_dir / "run.bat"
    print(f"[build_windows] Copying {RUN_BAT_SRC} -> {dest_run_bat}")
    shutil.copy2(RUN_BAT_SRC, dest_run_bat)


def create_zip_archive(package_dir: Path, output_zip: Path) -> Path:
    """パッケージディレクトリを zip アーカイブに圧縮する。"""
    print(f"[build_windows] Creating archive: {output_zip}")
    base_name = str(output_zip.with_suffix(""))
    archive_format = "zip"
    created_path = shutil.make_archive(
        base_name=base_name,
        format=archive_format,
        root_dir=str(package_dir.parent),
        base_dir=package_dir.name,
    )
    return Path(created_path)


def build() -> Path:
    """Windows 配布パッケージ全体をビルドする。"""
    print("=" * 60)
    print("Building Windows Portable Package (sakai-tasks-mcp-windows)")
    print("=" * 60)

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    setup_embeddable_python(PYTHON_EMBED_DIR)
    configure_pth(PYTHON_EMBED_DIR)
    install_dependencies(PYTHON_EMBED_DIR, REQUIREMENTS_TXT)
    copy_app_files(PACKAGE_DIR)

    output_zip = DIST_DIR / "sakai-tasks-mcp-windows.zip"
    archive_path = create_zip_archive(PACKAGE_DIR, output_zip)
    print(f"[build_windows] Successfully built: {archive_path}")
    return archive_path


def main() -> None:
    build()


if __name__ == "__main__":
    main()
