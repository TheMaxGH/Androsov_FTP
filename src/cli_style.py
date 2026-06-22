from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.entities import TransferProgress


for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class Style:
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    blue = "\033[38;5;39m"
    purple = "\033[38;5;141m"
    green = "\033[38;5;83m"
    yellow = "\033[38;5;221m"
    red = "\033[38;5;203m"
    gray = "\033[38;5;245m"


def color(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"{code}{text}{Style.reset}"


def title(text: str) -> None:
    print()
    print(color("VALLHALA FTP", Style.bold + Style.purple))
    print(color(text, Style.gray))
    print(color("─" * min(_width(), 88), Style.blue))


def panel(lines: list[tuple[str, str]], heading: str | None = None) -> None:
    width = min(_width(), 88)
    if heading:
        print(color(heading, Style.bold + Style.blue))
    key_width = max((len(key) for key, _value in lines), default=0)
    for key, value in lines:
        print(f"  {color(key.ljust(key_width), Style.gray)}  {value}")
    print(color("─" * width, Style.dim + Style.gray))


def success(message: str) -> None:
    print(color(f"OK  {message}", Style.green))


def warning(message: str) -> None:
    print(color(f"WARN  {message}", Style.yellow))


def error(message: str) -> None:
    print(color(f"ERROR  {message}", Style.red), file=sys.stderr)


def table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        warning("Список пуст.")
        return
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    separator = "  ".join("─" * width for width in widths)
    print("  ".join(color(header.ljust(widths[index]), Style.bold) for index, header in enumerate(headers)))
    print(color(separator, Style.dim + Style.gray))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


@dataclass
class ProgressPrinter:
    label: str
    total: int = 0

    def __post_init__(self) -> None:
        self.started = time.perf_counter()
        self.last_percent = -1
        self.last_render = 0.0

    def update(self, progress: TransferProgress) -> None:
        now = time.perf_counter()
        percent = int(progress.percent)
        if percent == self.last_percent and now - self.last_render < 0.08:
            return
        self.last_percent = percent
        self.last_render = now
        self.total = progress.total
        self._render(progress.transferred, progress.total, percent, final=False)

    def done(self, transferred: int | None = None) -> None:
        total = transferred or self.total
        self._render(total, total, 100, final=True)
        print()

    def _render(self, transferred: int, total: int, percent: int, final: bool) -> None:
        columns = max(18, min(34, _width() - 52))
        filled = columns if final else int(columns * percent / 100)
        bar = "█" * filled + "░" * (columns - filled)
        elapsed = max(time.perf_counter() - self.started, 0.001)
        speed = transferred / elapsed
        total_text = _format_size(total) if total else "?"
        line = (
            f"\r{color(self.label, Style.blue)} "
            f"[{color(bar, Style.purple)}] "
            f"{percent:3d}%  {_format_size(transferred)}/{total_text}  {_format_size(speed)}/s"
        )
        print(line[: max(_width() - 1, 20)], end="", flush=True)


def file_rows(names: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for index, name in enumerate(names, start=1):
        suffix = Path(name).suffix.lower() or "-"
        rows.append([str(index), name, suffix])
    return rows


def _format_size(value: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _width() -> int:
    return shutil.get_terminal_size((96, 24)).columns
