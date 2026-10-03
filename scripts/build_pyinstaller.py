#!/usr/bin/env python3
"""
PyInstaller による単一実行可能ファイル作成スクリプト
docs/architecture.md 7.1.4 に準拠
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = ROOT_DIR / "src" / "server.py"
TEMPLATES_DIR = ROOT_DIR / "src" / "gui" / "templates"


def get_pyinstaller_command() -> list[str]:
    """PyInstaller の実行コマンド引数リストを構築する。"""
    add_data_sep = ";" if sys.platform == "win32" else ":"
    add_data_arg = f"src/gui/templates{add_data_sep}templates"

    pyinstaller_bin = shutil.which("pyinstaller")
    cmd_prefix = [pyinstaller_bin] if pyinstaller_bin else [sys.executable, "-m", "PyInstaller"]

    cmd = cmd_prefix + [
        "--onefile",
        "--name",
        "sakai-tasks-mcp",
        "--add-data",
        add_data_arg,
        "--hidden-import",
        "pywebview.platforms.winforms",
        "--hidden-import",
        "clr",
        str(SERVER_SCRIPT.relative_to(ROOT_DIR)),
    ]
    return cmd


def build() -> None:
    """PyInstaller を実行して単一バイナリをビルドする。"""
    cmd = get_pyinstaller_command()
    print(f"[build_pyinstaller] Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)


def main() -> None:
    build()


if __name__ == "__main__":
    main()
