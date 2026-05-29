import sys

from src.gui.main_window import run_app
from src.cli_client import run_cli_client
from src.legacy_server import run_legacy_server


if __name__ == "__main__":
    if "--legacy-server" in sys.argv:
        run_legacy_server(sys.argv[1:])
    elif "--ftp" in sys.argv:
        run_cli_client(sys.argv[1:])
    else:
        run_app()
