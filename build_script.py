from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_with_pyinstaller() -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "VALLHALA-FTP",
        "--icon",
        str(ROOT / "src" / "ui" / "assets" / "vallhala_ftp_icon.ico"),
        "--add-data",
        f"{ROOT / 'src' / 'ui'};src/ui",
        str(ROOT / "main.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


if __name__ == "__main__":
    build_with_pyinstaller()
