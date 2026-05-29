from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.core.entities import READ_WRITE_PERMISSIONS, ServerConfig, UserAccount
from src.infrastructure.config_store import ConfigStore
from src.infrastructure.network_engine import OptiFTPServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vallhala-ftp-legacy-server",
        description="Headless FTP/FTPS server mode for SSH/server machines.",
    )
    parser.add_argument("--legacy-server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--config", help="JSON config with server profiles")
    parser.add_argument("--server", help="Server profile name from --config")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address, default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=2121, help="FTP port, default: 2121")
    parser.add_argument("--root", default=".", help="Shared directory, default: current directory")
    parser.add_argument("--user", default="user", help="FTP username for quick mode")
    parser.add_argument("--password", default="password", help="FTP password for quick mode")
    parser.add_argument("--anonymous", action="store_true", help="Allow read-only anonymous access")
    parser.add_argument("--passive-from", type=int, default=60000, help="First passive port")
    parser.add_argument("--passive-to", type=int, default=60100, help="Last passive port")
    parser.add_argument("--tls", action="store_true", help="Enable FTPS")
    parser.add_argument("--certfile", help="TLS certificate path for FTPS")
    parser.add_argument("--keyfile", help="TLS private key path for FTPS")
    return parser


def run_legacy_server(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    config = _config_from_args(args)
    server = OptiFTPServer(lambda message: logging.info(message))

    logging.info("Starting VALLHALA FTP legacy server")
    logging.info("Profile: %s", config.name)
    logging.info("Bind: %s:%s", config.host, config.port)
    logging.info("Root: %s", Path(config.root_path).expanduser().resolve())
    logging.info("Protocol: %s", config.protocol.upper())
    logging.info("Anonymous: %s", "enabled read-only" if config.allow_anonymous else "disabled")
    logging.info("Users: %s", ", ".join(user.username for user in config.normalized_users()))
    logging.info("Stop: Ctrl+C")
    try:
        server.start(config)
        while True:
            import time

            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Stopping server...")
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


if __name__ == "__main__":
    run_legacy_server()
