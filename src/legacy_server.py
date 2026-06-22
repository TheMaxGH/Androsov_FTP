from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.cli_style import color, error, panel, success, title, warning, Style
from src.core.entities import READ_WRITE_PERMISSIONS, ServerConfig, UserAccount
from src.infrastructure.config_store import ConfigStore
from src.infrastructure.network_engine import OptiFTPServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vallhala-ftp-legacy-server",
        description="Headless FTP/FTPS server mode for SSH/server machines.",
    )
    parser.add_argument("--legacy-server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--config", "-config", help="JSON config with server profiles")
    parser.add_argument("--server", "-server", help="Server profile name from --config")
    parser.add_argument("--host", "-host", default="0.0.0.0", help="Bind address, default: 0.0.0.0")
    parser.add_argument("--port", "-port", type=int, default=2121, help="FTP port, default: 2121")
    parser.add_argument("--root", "-root", default=".", help="Shared directory, default: current directory")
    parser.add_argument("--user", "-user", default="user", help="FTP username for quick mode")
    parser.add_argument("--password", "-password", default="password", help="FTP password for quick mode")
    parser.add_argument("--anonymous", "-anonymous", action="store_true", help="Allow read-only anonymous access")
    parser.add_argument("--passive-from", "-passive-from", type=int, default=60000, help="First passive port")
    parser.add_argument("--passive-to", "-passive-to", type=int, default=60100, help="Last passive port")
    parser.add_argument("--tls", "-tls", action="store_true", help="Enable FTPS")
    parser.add_argument("--certfile", "-certfile", help="TLS certificate path for FTPS")
    parser.add_argument("--keyfile", "-keyfile", help="TLS private key path for FTPS")
    parser.add_argument("--quiet", "-quiet", action="store_true", help="Use compact log output")
    return parser


def run_legacy_server(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s" if not args.quiet else "%(asctime)s [%(levelname)s] %(message)s")

    config = _config_from_args(args)
    server = OptiFTPServer(lambda message: _server_event(message, args.quiet))

    if args.quiet:
        logging.info("Starting VALLHALA FTP legacy server")
        logging.info("Profile: %s", config.name)
        logging.info("Bind: %s:%s", config.host, config.port)
    else:
        title("Legacy server")
        panel(
            [
                ("Профиль", config.name),
                ("Bind", f"{config.host}:{config.port}"),
                ("Папка", str(Path(config.root_path).expanduser().resolve())),
                ("Протокол", config.protocol.upper()),
                ("Anonymous", "read-only включен" if config.allow_anonymous else "выключен"),
                ("Пользователи", ", ".join(user.username for user in config.normalized_users())),
                ("Остановка", "Ctrl+C"),
            ],
            "Параметры сервера",
        )
    try:
        server.start(config)
        if not args.quiet:
            success(f"Сервер запущен: {server.public_address}")
            warning("Оставьте это окно открытым. Для остановки нажмите Ctrl+C.")
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        if args.quiet:
            logging.info("Stopping server...")
        else:
            warning("Остановка сервера...")
    except Exception as exc:
        error(str(exc))
        raise SystemExit(1) from exc
    finally:
        server.stop()


def _config_from_args(args: argparse.Namespace) -> ServerConfig:
    if args.config:
        config = ConfigStore(Path(args.config)).load()
        profile_name = args.server or (config.servers[0].name if config.servers else "")
        for server in config.servers:
            if server.name == profile_name:
                return server
        raise SystemExit(f"Server profile not found: {profile_name}")

    return ServerConfig(
        name="quick",
        host=args.host,
        port=args.port,
        root_path=Path(args.root),
        allow_anonymous=args.anonymous,
        passive_ports=(args.passive_from, args.passive_to),
        protocol="ftps" if args.tls else "ftp",
        certfile=Path(args.certfile) if args.certfile else None,
        keyfile=Path(args.keyfile) if args.keyfile else None,
        users=[UserAccount(args.user, args.password, permissions=READ_WRITE_PERMISSIONS)],
    )


def _server_event(message: str, quiet: bool) -> None:
    if quiet:
        logging.info(message)
        return
    if "ошибка" in message.lower() or "failed" in message.lower():
        logging.info(color(f"ERROR  {message}", Style.red))
    elif "останов" in message.lower() or "closed" in message.lower():
        logging.info(color(f"STOP   {message}", Style.yellow))
    elif "запущ" in message.lower() or "opened" in message.lower() or "вошел" in message.lower():
        logging.info(color(f"INFO   {message}", Style.green))
    else:
        logging.info(color(f"INFO   {message}", Style.gray))


if __name__ == "__main__":
    run_legacy_server()
