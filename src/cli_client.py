from __future__ import annotations

import argparse
from pathlib import Path

from src.cli_style import ProgressPrinter, error, file_rows, panel, success, table, title
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
    parser.add_argument("--config", "-config", help="JSON config with client profiles")
    parser.add_argument("--profile", "-profile", help="Client profile name from --config")
    parser.add_argument("--host", "-host", help="FTP host")
    parser.add_argument("--port", "-port", type=int, default=2121, help="FTP port")
    parser.add_argument("--user", "-user", default="user", help="FTP username")
    parser.add_argument("--password", "-password", default="password", help="FTP password")
    parser.add_argument("--protocol", "-protocol", choices=("ftp", "ftps"), default="ftp", help="Transfer protocol")
    parser.add_argument("--remote", "-remote", default=".", help="Remote path/name")
    parser.add_argument("--local", "-local", help="Local path for upload/download")
    parser.add_argument("--quiet", "-quiet", action="store_true", help="Print only command results")
    return parser


def run_cli_client(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        profile = _profile_from_args(args)
        client = OptimizedFTPClient()
        if not args.quiet:
            title("CLI-клиент")
            panel(
                [
                    ("Профиль", profile.name),
                    ("Сервер", f"{profile.protocol}://{profile.host}:{profile.port}"),
                    ("Пользователь", profile.username),
                    ("Команда", args.command),
                ],
                "Подключение",
            )

        client.connect(profile.host, profile.port, profile.username, profile.password, protocol=profile.protocol)
        try:
            if args.command == "list":
                names = client.list_dir(args.remote)
                if args.quiet:
                    for name in names:
                        print(name)
                else:
                    table(["#", "Имя", "Тип"], file_rows(names))
                    success(f"Найдено элементов: {len(names)}")
                return

            if not args.local:
                raise SystemExit("--local is required for upload/download")

            local = Path(args.local).expanduser().resolve()
            if args.command == "upload":
                remote = args.remote if args.remote != "." else local.name
                progress = ProgressPrinter("Upload", local.stat().st_size)
                client.upload(local, remote, None if args.quiet else progress.update)
                if args.quiet:
                    print(f"Uploaded {local} -> {remote}")
                else:
                    progress.done(local.stat().st_size)
                    success(f"Загружено: {local} -> {remote}")
            elif args.command == "download":
                progress = ProgressPrinter("Download")
                client.download(args.remote, local, None if args.quiet else progress.update)
                if args.quiet:
                    print(f"Downloaded {args.remote} -> {local}")
                else:
                    progress.done(local.stat().st_size if local.exists() else None)
                    success(f"Скачано: {args.remote} -> {local}")
        finally:
            client.disconnect()
    except SystemExit:
        raise
    except Exception as exc:
        error(str(exc))
        raise SystemExit(1) from exc


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
