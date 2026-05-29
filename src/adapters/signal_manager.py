from __future__ import annotations

import queue
import tkinter as tk
from collections.abc import Callable


class TkSignalQueue:
    def __init__(self, root: tk.Misc, interval_ms: int = 80) -> None:
        self.root = root
        self.interval_ms = interval_ms
        self._queue: queue.Queue[Callable[[], None]] = queue.Queue()

    def emit(self, callback: Callable[[], None]) -> None:
        self._queue.put(callback)

    def start(self) -> None:
        self._drain()

    def _drain(self) -> None:
        while True:
            try:
                callback = self._queue.get_nowait()
            except queue.Empty:
                break
            callback()
        self.root.after(self.interval_ms, self._drain)
