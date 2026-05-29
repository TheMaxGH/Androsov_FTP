from __future__ import annotations

from src.core.entities import ScanResult


def scan_result_to_row(result: ScanResult) -> tuple[str, str, str, str]:
    return (
        result.host,
        str(result.port),
        f"{result.latency_ms:.1f} ms",
        result.banner or "порт открыт",
    )
