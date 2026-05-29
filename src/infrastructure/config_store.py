from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.entities import (
    AppConfig,
    ClientProfile,
    IPFilter,
    READ_ONLY_PERMISSIONS,
    READ_WRITE_PERMISSIONS,
    ServerConfig,
    ServerLimits,
    UserAccount,
)


def default_config_path() -> Path:
    return Path.cwd() / "vallhala.servers.json"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or default_config_path())

    def load(self) -> AppConfig:
        if not self.path.exists():
            return default_app_config()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return app_config_from_dict(payload)

    def save(self, config: AppConfig) -> None:
        self.path.write_text(
            json.dumps(app_config_to_dict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def default_app_config() -> AppConfig:
    server = ServerConfig(
        name="Default",
        users=[UserAccount("user", "password", permissions=READ_WRITE_PERMISSIONS)],
    )
    client = ClientProfile(name="local", host="127.0.0.1", port=2121, username="user", password="password")
    return AppConfig(servers=[server], client_profiles=[client])


def app_config_from_dict(payload: dict[str, Any]) -> AppConfig:
    servers = [server_from_dict(item) for item in payload.get("servers", [])]
    clients = [client_from_dict(item) for item in payload.get("client_profiles", [])]
    return AppConfig(servers=servers or default_app_config().servers, client_profiles=clients)


def app_config_to_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "servers": [server_to_dict(server) for server in config.servers],
        "client_profiles": [client_to_dict(client) for client in config.client_profiles],
    }


def server_from_dict(item: dict[str, Any]) -> ServerConfig:
    passive = item.get("passive_ports", [60000, 60100])
    users = [user_from_dict(user) for user in item.get("users", [])]
    limits = item.get("limits", {})
    ip_filter = item.get("ip_filter", {})
    return ServerConfig(
        name=str(item.get("name", "Default")),
        host=str(item.get("host", "0.0.0.0")),
        port=int(item.get("port", 2121)),
        root_path=Path(item.get("root_path", ".")),
        allow_anonymous=bool(item.get("allow_anonymous", False)),
        passive_ports=(int(passive[0]), int(passive[1])),
        protocol=str(item.get("protocol", "ftp")).lower(),
        certfile=_optional_path(item.get("certfile")),
        keyfile=_optional_path(item.get("keyfile")),
        users=users or [UserAccount()],
        limits=ServerLimits(
            max_connections=int(limits.get("max_connections", 128)),
            max_connections_per_ip=int(limits.get("max_connections_per_ip", 8)),
            upload_limit_kbps=int(limits.get("upload_limit_kbps", 0)),
            download_limit_kbps=int(limits.get("download_limit_kbps", 0)),
        ),
        ip_filter=IPFilter(
            allow=[str(value) for value in ip_filter.get("allow", [])],
            deny=[str(value) for value in ip_filter.get("deny", [])],
        ),
    )


def server_to_dict(server: ServerConfig) -> dict[str, Any]:
    return {
        "name": server.name,
        "host": server.host,
        "port": server.port,
        "root_path": str(server.root_path),
        "protocol": server.protocol,
        "certfile": str(server.certfile) if server.certfile else "",
        "keyfile": str(server.keyfile) if server.keyfile else "",
        "allow_anonymous": server.allow_anonymous,
        "passive_ports": [server.passive_ports[0], server.passive_ports[1]],
        "users": [user_to_dict(user) for user in server.users],
        "limits": {
            "max_connections": server.limits.max_connections,
            "max_connections_per_ip": server.limits.max_connections_per_ip,
            "upload_limit_kbps": server.limits.upload_limit_kbps,
            "download_limit_kbps": server.limits.download_limit_kbps,
        },
        "ip_filter": {
            "allow": server.ip_filter.allow,
            "deny": server.ip_filter.deny,
        },
    }


def user_from_dict(item: dict[str, Any]) -> UserAccount:
    preset = str(item.get("permission_preset", "")).lower()
    permissions = str(item.get("permissions") or (READ_ONLY_PERMISSIONS if preset == "read_only" else READ_WRITE_PERMISSIONS))
    return UserAccount(
        username=str(item.get("username", "user")),
        password=str(item.get("password", "password")),
        root_path=_optional_path(item.get("root_path")),
        permissions=permissions,
        enabled=bool(item.get("enabled", True)),
    )


def user_to_dict(user: UserAccount) -> dict[str, Any]:
    return {
        "username": user.username,
        "password": user.password,
        "root_path": str(user.root_path) if user.root_path else "",
        "permissions": user.permissions,
        "enabled": user.enabled,
    }


def client_from_dict(item: dict[str, Any]) -> ClientProfile:
    return ClientProfile(
        name=str(item.get("name", "local")),
        host=str(item.get("host", "127.0.0.1")),
        port=int(item.get("port", 2121)),
        username=str(item.get("username", "user")),
        password=str(item.get("password", "password")),
        protocol=str(item.get("protocol", "ftp")).lower(),
    )


def client_to_dict(client: ClientProfile) -> dict[str, Any]:
    return {
        "name": client.name,
        "host": client.host,
        "port": client.port,
        "username": client.username,
        "password": client.password,
        "protocol": client.protocol,
    }


def _optional_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value))
