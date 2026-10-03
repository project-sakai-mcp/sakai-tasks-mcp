#!/usr/bin/env python3
"""
macOS 用 python-build-standalone 配布パッケージ作成スクリプト
docs/architecture.md 7.1.3 に準拠
"""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
PACKAGE_DIR = DIST_DIR / "sakai-tasks-mcp-macos"
PYTHON_DIR = PACKAGE_DIR / "python"
SITE_PACKAGES_DIR = PYTHON_DIR / "lib" / "python3.12" / "site-packages"
SRC_DIR = ROOT_DIR / "src"
RUN_SH_SRC = ROOT_DIR / "scripts" / "run.sh"
REQUIREMENTS_TXT = ROOT_DIR / "requirements.txt"

STANDALONE_RELEASE_TAG = "20241016"
STANDALONE_PYTHON_VERSION = "3.12.7"
DEFAULT_ARCH = "aarch64"  # Apple Silicon (M1/M2/M3/M4)


def get_standalone_url(arch: str) -> tuple[str, str]:
    """アーキテクチャに応じたダウンロード URL とアーカイブファイル名を返却する。"""
    tar_name = (
        f"cpython-{STANDALONE_PYTHON_VERSION}+{STANDALONE_RELEASE_TAG}-"
        f"{arch}-apple-darwin-install_only.tar.gz"
    )
    url = (
        f"https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{STANDALONE_RELEASE_TAG}/{tar_name}"
    )
    return url, tar_name


def download_file(url: str, dest_path: Path) -> Path:
    """指定 URL からファイルをダウンロードする（キャッシュが存在する場合は再利用）。"""
    if dest_path.exists():
        print(f"[build_macos] Using cached: {dest_path}")
        return dest_path

    print(f"[build_macos] Downloading: {url} -> {dest_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


def setup_standalone_python(dest_dir: Path, arch: str) -> None:
    """python-build-standalone をダウンロードし、dest_dir 配下に展開する。"""
    url, tar_name = get_standalone_url(arch)
    tar_cache_path = DIST_DIR / tar_name
    download_file(url, tar_cache_path)

    print(f"[build_macos] Extracting {tar_cache_path} -> {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_cache_path, "r:gz") as tf:
        tf.extractall(dest_dir)


def install_dependencies(python_dir: Path, requirements_file: Path) -> None:
    """依存ライブラリを python/lib/python3.12/site-packages にインストールする。"""
    if sys.platform != "darwin":
        raise RuntimeError("build_macos.py must be run on macOS (darwin).")

    site_packages = python_dir / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    python_bin = python_dir / "bin" / "python3"
    print(f"[build_macos] Installing packages using standalone python into {site_packages}...")
    subprocess.run(
        [
            str(python_bin),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_file),
        ],
        check=True,
    )


def copy_app_files(package_dir: Path) -> None:
    """アプリケーションソースコード (src/) および起動スクリプト (run.sh) をパッケージに配置する。"""
    dest_src = package_dir / "src"
    print(f"[build_macos] Copying {SRC_DIR} -> {dest_src}")
    if dest_src.exists():
        shutil.rmtree(dest_src)
    shutil.copytree(
        SRC_DIR,
        dest_src,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    dest_run_sh = package_dir / "run.sh"
    print(f"[build_macos] Copying {RUN_SH_SRC} -> {dest_run_sh}")
    shutil.copy2(RUN_SH_SRC, dest_run_sh)

    # 実行権限を付与 (chmod +x)
    dest_run_sh.chmod(0o755)


def create_tar_archive(package_dir: Path, output_tar: Path) -> Path:
    """パッケージディレクトリを .tar.gz アーカイブに圧縮する。"""
    print(f"[build_macos] Creating archive: {output_tar}")
    base_name = str(output_tar).removesuffix(".tar.gz")
    created_path = shutil.make_archive(
        base_name=base_name,
        format="gztar",
        root_dir=str(package_dir.parent),
        base_dir=package_dir.name,
    )
    return Path(created_path)


def build(arch: str = DEFAULT_ARCH) -> Path:
    """macOS 配布パッケージ全体をビルドする。"""
    print("=" * 60)
    print(f"Building macOS Standalone Package (sakai-tasks-mcp-macos, arch={arch})")
    print("=" * 60)

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    setup_standalone_python(PACKAGE_DIR, arch)
    install_dependencies(PYTHON_DIR, REQUIREMENTS_TXT)
    copy_app_files(PACKAGE_DIR)

    output_tar = DIST_DIR / "sakai-tasks-mcp-macos.tar.gz"
    archive_path = create_tar_archive(PACKAGE_DIR, output_tar)
    print(f"[build_macos] Successfully built: {archive_path}")
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build macOS portable package for sakai-tasks-mcp")
    parser.add_argument(
        "--arch",
        choices=["aarch64", "x86_64"],
        default=DEFAULT_ARCH,
        help="Target architecture (default: aarch64)",
    )
    args = parser.parse_args()
    build(arch=args.arch)


if __name__ == "__main__":
    main()
