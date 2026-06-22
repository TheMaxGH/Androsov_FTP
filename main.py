from __future__ import annotations

import sys

from src.cli_client import run_cli_client
from src.gui.main_window import run_app
from src.legacy_server import run_legacy_server


HELP = """VALLHALA FTP

Запуск GUI:
  python main.py

CLI-клиент:
  python main.py --ftp list --host 127.0.0.1 --port 2121
  python main.py --ftp upload --host 127.0.0.1 --local "D:\\file.txt"
  python main.py --ftp download --host 127.0.0.1 --remote file.txt --local "D:\\file.txt"

Headless сервер:
  python main.py --legacy-server --host 0.0.0.0 --port 2121 --root "D:\\Share"

Важно: --quiet работает только вместе с --ftp или --legacy-server.
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        run_app()
        return 0
    if "--help" in argv or "-h" in argv:
        print(HELP)
        return 0
    if "--legacy-server" in argv:
        run_legacy_server(argv)
        return 0
    if "--ftp" in argv:
        run_cli_client(argv)
        return 0
    print("Ошибка: неизвестный режим запуска.\n")
    print(HELP)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
