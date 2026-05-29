from __future__ import annotations

from pathlib import Path

from src.core.entities import FileItem


class LocalStorage:
    def list_dir(self, path: Path) -> list[FileItem]:
        result: list[FileItem] = []
        for item in sorted(Path(path).iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            stat = item.stat()
            result.append(FileItem(item.name, stat.st_size, item.is_dir(), stat.st_mtime))
        return result
