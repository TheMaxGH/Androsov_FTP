from __future__ import annotations

import argparse
from pathlib import Path

from src.core.entities import ClientProfile
from src.infrastructure.config_store import ConfigStore
from src.infrastructure.ftp_client import OptimizedFTPClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vallhala-ftp-client",
        description="Headless FTP/FTPS client commands for automation and SSH sessions.",
    )
    parser.add_argument("--ftp", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("command", choices=("list", "upload", "download"), help="FTP client command")
    parser.add_argument("--config", help="JSON config with client profiles")
    parser.add_argument("--profile", help="Client profile name from --config")
    parser.add_argument("--host", help="FTP host")
    parser.add_argument("--port", type=int, default=2121, help="FTP port")
    parser.add_argument("--user", default="user", help="FTP username")
    parser.add_argument("--password", default="password", help="FTP password")
    parser.add_argument("--protocol", choices=("ftp", "ftps"), default="ftp", help="Transfer protocol")
    parser.add_argument("--remote", default=".", help="Remote path/name")
    parser.add_argument("--local", help="Local path for upload/download")
    return parser


def run_cli_client(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    profile = _profile_from_args(args)
    client = OptimizedFTPClient()
    client.connect(profile.host, profile.port, profile.username, profile.password, protocol=profile.protocol)
    try:
        if args.command == "list":
            for name in client.list_dir(args.remote):
                print(name)
            return

        if not args.local:
            raise SystemExit("--local is required for upload/download")

        local = Path(args.local).expanduser().resolve()
        if args.command == "upload":
            remote = args.remote if args.remote != "." else local.name
            client.upload(local, remote)
            print(f"Uploaded {local} -> {remote}")
        elif args.command == "download":
            client.download(args.remote, local)
            print(f"Downloaded {args.remote} -> {local}")
    finally:
        client.disconnect()


def _profile_from_args(args: argparse.Namespace) -> ClientProfile:
    if args.config:
        config = ConfigStore(Path(args.config)).load()
        profile_name = args.profile or (config.client_profiles[0].name if config.client_profiles else "")
        for profile in config.client_profiles:
            if profile.name == profile_name:
                return profile
        raise SystemExit(f"Client profile not found: {profile_name}")

    if not args.host:
        raise SystemExit("--host is required unless --config/--profile is used")
    return ClientProfile(
        name="quick",
        host=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        protocol=args.protocol,
    )


if __name__ == "__main__":
    run_cli_client()
