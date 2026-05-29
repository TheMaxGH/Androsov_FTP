from __future__ import annotations

from collections.abc import Callable

from src.core.entities import ScanResult, ServerConfig
from src.core.entities import ServerRuntimeInfo
from src.infrastructure.network_engine import FastLANScanner, MultiFTPServerManager, OptiFTPServer, UPnPManager


class ScanNetworkUseCase:
    def __init__(self, scanner: FastLANScanner | None = None) -> None:
        self.scanner = scanner or FastLANScanner()

    def execute(
        self,
        subnet: str | None = None,
        ports: tuple[int, ...] = (21, 2121),
        on_result: Callable[[ScanResult], None] | None = None,
    ) -> list[ScanResult]:
        return self.scanner.scan_sync(subnet=subnet, ports=ports, on_result=on_result)


class ManageServerUseCase:
    def __init__(self, server: OptiFTPServer | None = None) -> None:
        self.server = server or OptiFTPServer()

    def start(self, config: ServerConfig) -> str:
        self.server.start(config)
        return self.server.public_address

    def stop(self) -> None:
        self.server.stop()

    def info(self) -> ServerRuntimeInfo:
        return self.server.info()


class ManageServerProfilesUseCase:
    def __init__(self, manager: MultiFTPServerManager | None = None) -> None:
        self.manager = manager or MultiFTPServerManager()

    def start(self, name: str, config: ServerConfig) -> str:
        return self.manager.start(name, config)

    def stop(self, name: str) -> None:
        self.manager.stop(name)

    def stop_all(self) -> None:
        self.manager.stop_all()

    def info(self, name: str) -> ServerRuntimeInfo:
        return self.manager.info(name)


class PublishPortUseCase:
    def __init__(self, upnp: UPnPManager | None = None) -> None:
        self.upnp = upnp or UPnPManager()

    def execute(self, port: int, description: str = "OptiFTP") -> tuple[bool, str]:
        return self.upnp.open_port(port, description=description)
