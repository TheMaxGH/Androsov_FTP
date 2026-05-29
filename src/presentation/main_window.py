from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src.adapters.network_adapter import scan_result_to_row
from src.adapters.signal_manager import TkSignalQueue
from src.core.entities import ServerConfig, TransferProgress
from src.core.use_cases import ManageServerUseCase, PublishPortUseCase, ScanNetworkUseCase
from src.infrastructure.ftp_client import OptimizedFTPClient
from src.infrastructure.network_engine import FastLANScanner
from src.utils.logger import configure_logging


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OptiFTP")
        self.geometry("1120x740")
        self.minsize(960, 640)
        self.configure(bg="#eef2f0")

        self.signal_queue = TkSignalQueue(self)
        self.server_use_case = ManageServerUseCase()
        self.scan_use_case = ScanNetworkUseCase(FastLANScanner())
        self.publish_use_case = PublishPortUseCase()
        self.client = OptimizedFTPClient()

        self.server_root = tk.StringVar(value=str(Path.cwd()))
        self.server_port = tk.StringVar(value="2121")
        self.server_user = tk.StringVar(value="user")
        self.server_password = tk.StringVar(value="password")
        self.server_status = tk.StringVar(value="Сервер остановлен")
        self.server_address = tk.StringVar(value="Адрес появится после запуска")

        self.scan_subnet = tk.StringVar(value=FastLANScanner().default_subnet())
        self.scan_status = tk.StringVar(value="Готово")

        self.client_host = tk.StringVar(value="127.0.0.1")
        self.client_port = tk.StringVar(value="2121")
        self.client_user = tk.StringVar(value="user")
        self.client_password = tk.StringVar(value="password")
        self.local_file = tk.StringVar(value="")
        self.remote_name = tk.StringVar(value="")
        self.transfer_status = tk.StringVar(value="Ожидание")

        self._build_style()
        self._build_ui()
        self.signal_queue.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#eef2f0", foreground="#182522")
        style.configure("TFrame", background="#eef2f0")
        style.configure("Panel.TFrame", background="#f8faf9")
        style.configure("TLabelframe", background="#eef2f0", bordercolor="#cad6d1", relief=tk.SOLID)
        style.configure("TLabelframe.Label", font=("Segoe UI Semibold", 10), background="#eef2f0", foreground="#29423b")
        style.configure("TLabel", background="#eef2f0", foreground="#182522")
        style.configure("Panel.TLabel", background="#f8faf9", foreground="#182522")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20), background="#eef2f0", foreground="#12332b")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), background="#eef2f0", foreground="#52645f")
        style.configure("Status.TLabel", foreground="#14613d", background="#eef2f0", font=("Segoe UI Semibold", 10))
        style.configure("Address.TLabel", foreground="#29423b", background="#f8faf9", font=("Consolas", 10))
        style.configure("TButton", padding=(12, 7), background="#dbe7e2", foreground="#10231e")
        style.map("TButton", background=[("active", "#c9dad3")])
        style.configure("Accent.TButton", background="#27745c", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#1f604c")], foreground=[("active", "#ffffff")])
        style.configure("Danger.TButton", background="#f2d8d4", foreground="#8a1f11")
        style.configure("TNotebook", background="#eef2f0", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab", background=[("selected", "#f8faf9")])
        style.configure("Treeview", rowheight=26, fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10), background="#dbe7e2")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(header, text="OptiFTP", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="единое приложение для FTP-сервера, клиента и поиска узлов в локальной сети",
            style="Subtitle.TLabel",
        ).pack(side=tk.LEFT, padx=14)

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)
        notebook.add(self._server_tab(notebook), text="Сервер")
        notebook.add(self._scanner_tab(notebook), text="Сканер LAN")
        notebook.add(self._client_tab(notebook), text="Клиент")

        log_frame = ttk.LabelFrame(root, text="Журнал событий", padding=10)
        log_frame.pack(fill=tk.BOTH, pady=(10, 0))
        self.log_box = tk.Text(
            log_frame,
            height=7,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#0f1f1b",
            fg="#dce8e4",
            insertbackground="#dce8e4",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=("Consolas", 10),
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

    def _server_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        form = ttk.Frame(frame)
        form.pack(fill=tk.X)

        self._labeled_entry(form, "Папка раздачи", self.server_root, 0, width=66)
        ttk.Button(form, text="Выбрать", command=self._choose_server_root).grid(row=0, column=2, padx=8)
        self._labeled_entry(form, "Порт", self.server_port, 1, width=12)
        self._labeled_entry(form, "Логин", self.server_user, 2, width=24)
        self._labeled_entry(form, "Пароль", self.server_password, 3, width=24, show="*")

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=12)
        ttk.Button(buttons, text="Запустить сервер", style="Accent.TButton", command=self._start_server).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Остановить", style="Danger.TButton", command=self._stop_server).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Пробросить порт UPnP", command=self._open_upnp).pack(side=tk.LEFT)
        ttk.Label(buttons, textvariable=self.server_status, style="Status.TLabel").pack(side=tk.LEFT, padx=16)

        address_box = ttk.LabelFrame(frame, text="Адрес для подключения", padding=10)
        address_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(address_box, textvariable=self.server_address, style="Address.TLabel").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(address_box, text="Скопировать", command=self._copy_server_address).pack(side=tk.RIGHT)

        info = ttk.LabelFrame(frame, text="Как это работает", padding=10)
        info.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(
            info,
            text=(
                "Сервер работает на pyftpdlib: внутри используется асинхронный цикл select/poll, "
                "поэтому множество FTP-сессий обслуживается без отдельного потока на каждое подключение."
            ),
            style="Panel.TLabel",
            wraplength=850,
        ).pack(anchor=tk.W)
        return frame

    def _scanner_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X)
        self._labeled_entry(controls, "Подсеть", self.scan_subnet, 0, width=28)
        ttk.Button(controls, text="Сканировать порты 21/2121", style="Accent.TButton", command=self._scan_network).grid(row=0, column=2, padx=8)
        ttk.Label(controls, textvariable=self.scan_status, style="Status.TLabel").grid(row=0, column=3, sticky=tk.W, padx=8)

        columns = ("host", "port", "latency", "banner")
        self.scan_table = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for column, title, width in (
            ("host", "Хост", 180),
            ("port", "Порт", 80),
            ("latency", "Задержка", 120),
            ("banner", "Ответ сервера", 520),
        ):
            self.scan_table.heading(column, text=title)
            self.scan_table.column(column, width=width, stretch=column == "banner")
        self.scan_table.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.scan_table.bind("<Double-1>", self._use_scanned_host)
        return frame

    def _client_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14)
        form = ttk.Frame(frame)
        form.pack(fill=tk.X)
        self._labeled_entry(form, "Хост", self.client_host, 0, width=24)
        self._labeled_entry(form, "Порт", self.client_port, 0, column_offset=2, width=10)
        self._labeled_entry(form, "Логин", self.client_user, 1, width=24)
        self._labeled_entry(form, "Пароль", self.client_password, 1, column_offset=2, width=24, show="*")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=10)
        ttk.Button(controls, text="Подключиться", style="Accent.TButton", command=self._connect_client).pack(side=tk.LEFT)
        ttk.Button(controls, text="Отключиться", command=self._disconnect_client).pack(side=tk.LEFT, padx=8)
        ttk.Button(controls, text="Обновить список", command=self._refresh_remote).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.transfer_status, style="Status.TLabel").pack(side=tk.LEFT, padx=14)

        body = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(body, text="Файлы на сервере", padding=8)
        right = ttk.LabelFrame(body, text="Передача", padding=8)
        body.add(left, weight=3)
        body.add(right, weight=2)

        self.remote_list = tk.Listbox(left, height=18)
        self.remote_list.pack(fill=tk.BOTH, expand=True)
        self.remote_list.bind("<<ListboxSelect>>", self._remote_selected)

        self._labeled_entry(right, "Локальный файл", self.local_file, 0, width=42)
        ttk.Button(right, text="Выбрать", command=self._choose_local_file).grid(row=0, column=2, padx=8)
        self._labeled_entry(right, "Имя на сервере", self.remote_name, 1, width=42)
        ttk.Button(right, text="Загрузить", command=self._upload).grid(row=2, column=1, sticky=tk.W, pady=10)
        ttk.Button(right, text="Скачать выбранный", command=self._download).grid(row=2, column=1, sticky=tk.E, pady=10)
        self.progress = ttk.Progressbar(right, maximum=100)
        self.progress.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(6, 0))
        right.columnconfigure(1, weight=1)
        return frame

    def _labeled_entry(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row: int,
        column_offset: int = 0,
        width: int = 30,
        show: str | None = None,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=column_offset, sticky=tk.W, pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=width, show=show)
        entry.grid(row=row, column=column_offset + 1, sticky=tk.EW, padx=(8, 0), pady=4)
        parent.columnconfigure(column_offset + 1, weight=1)
        return entry

    def _choose_server_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.server_root.get())
        if selected:
            self.server_root.set(selected)

    def _choose_local_file(self) -> None:
        selected = filedialog.askopenfilename()
        if selected:
            self.local_file.set(selected)
            self.remote_name.set(Path(selected).name)

    def _start_server(self) -> None:
        try:
            config = ServerConfig(
                port=int(self.server_port.get()),
                username=self.server_user.get().strip() or "user",
                password=self.server_password.get(),
                root_path=Path(self.server_root.get()),
            )
            address = self.server_use_case.start(config)
            self.server_status.set("Сервер запущен")
            self.server_address.set(address)
            self._log(f"Сервер запущен: {address}")
        except Exception as exc:
            messagebox.showerror("Ошибка сервера", str(exc))

    def _stop_server(self) -> None:
        self.server_use_case.stop()
        self.server_status.set("Сервер остановлен")
        self._log("Сервер остановлен")

    def _copy_server_address(self) -> None:
        value = self.server_address.get()
        if not value.startswith("ftp://"):
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self._log(f"Адрес скопирован: {value}")

    def _open_upnp(self) -> None:
        port = int(self.server_port.get())

        def worker() -> None:
            ok, msg = self.publish_use_case.execute(port)
            prefix = "UPnP: " if ok else "UPnP недоступен: "
            self.signal_queue.emit(lambda prefix=prefix, msg=msg: self._log(prefix + msg))

        threading.Thread(target=worker, daemon=True).start()

    def _scan_network(self) -> None:
        subnet = self.scan_subnet.get().strip()
        for item in self.scan_table.get_children():
            self.scan_table.delete(item)
        self.scan_status.set("Сканирование...")
        self._log(f"Сканирование {subnet}, порты 21 и 2121")

        def on_result(result) -> None:
            self.signal_queue.emit(lambda result=result: self.scan_table.insert("", tk.END, values=scan_result_to_row(result)))

        def worker() -> None:
            try:
                results = self.scan_use_case.execute(subnet=subnet, on_result=on_result)
                self.signal_queue.emit(lambda: self.scan_status.set(f"Готово: найдено {len(results)}"))
                self.signal_queue.emit(lambda: self._log(f"Сканирование завершено: найдено {len(results)} сервер(ов)"))
            except Exception as exc:
                message = str(exc)
                self.signal_queue.emit(lambda: self.scan_status.set("Ошибка сканирования"))
                self.signal_queue.emit(lambda message=message: messagebox.showerror("Ошибка сканера", message))

        threading.Thread(target=worker, daemon=True).start()

    def _use_scanned_host(self, _event) -> None:
        item_id = self.scan_table.focus()
        if not item_id:
            return
        host, port, *_ = self.scan_table.item(item_id, "values")
        self.client_host.set(host)
        self.client_port.set(port)
        self._log(f"Выбран FTP-узел {host}:{port}")

    def _connect_client(self) -> None:
        try:
            self.client.connect(
                self.client_host.get().strip(),
                int(self.client_port.get()),
                self.client_user.get().strip(),
                self.client_password.get(),
            )
            self.transfer_status.set("Подключено")
            self._log("FTP-клиент подключен")
            self._refresh_remote()
        except Exception as exc:
            messagebox.showerror("Ошибка клиента", str(exc))

    def _disconnect_client(self) -> None:
        self.client.disconnect()
        self.transfer_status.set("Отключено")
        self.remote_list.delete(0, tk.END)
        self._log("FTP-клиент отключен")

    def _refresh_remote(self) -> None:
        try:
            names = self.client.list_dir()
            self.remote_list.delete(0, tk.END)
            for name in names:
                self.remote_list.insert(tk.END, name)
            self._log(f"Список файлов обновлен: {len(names)} элемент(ов)")
        except Exception as exc:
            messagebox.showerror("Ошибка клиента", str(exc))

    def _remote_selected(self, _event) -> None:
        selected = self._selected_remote()
        if selected:
            self.remote_name.set(Path(selected).name)

    def _upload(self) -> None:
        path = Path(self.local_file.get())
        if not path.is_file():
            messagebox.showwarning("Загрузка", "Сначала выберите локальный файл.")
            return
        self.progress["value"] = 0
        self.transfer_status.set("Загрузка...")
        future = self.client.upload_async(path, self.remote_name.get() or path.name, self._on_progress)
        self._watch_future(future, "Загрузка завершена")

    def _download(self) -> None:
        selected = self._selected_remote()
        if not selected:
            messagebox.showwarning("Скачивание", "Сначала выберите файл на сервере.")
            return
        target = filedialog.asksaveasfilename(initialfile=Path(selected).name)
        if not target:
            return
        self.progress["value"] = 0
        self.transfer_status.set("Скачивание...")
        future = self.client.download_async(selected, Path(target), self._on_progress)
        self._watch_future(future, "Скачивание завершено")

    def _watch_future(self, future, success_message: str) -> None:
        def worker() -> None:
            try:
                future.result()
                self.signal_queue.emit(lambda: self.transfer_status.set(success_message))
                self.signal_queue.emit(lambda: self._log(success_message))
                self.signal_queue.emit(self._refresh_remote)
            except Exception as exc:
                message = str(exc)
                self.signal_queue.emit(lambda: self.transfer_status.set("Ошибка передачи"))
                self.signal_queue.emit(lambda message=message: messagebox.showerror("Ошибка передачи", message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, progress: TransferProgress) -> None:
        self.signal_queue.emit(lambda: self.progress.configure(value=progress.percent))
        self.signal_queue.emit(lambda: self.transfer_status.set(f"{progress.filename}: {progress.percent:.0f}%"))

    def _selected_remote(self) -> str | None:
        selection = self.remote_list.curselection()
        if not selection:
            return None
        return self.remote_list.get(selection[0])

    def _log(self, message: str) -> None:
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        try:
            self.client.disconnect()
            self.server_use_case.stop()
        finally:
            self.destroy()


def run_app() -> None:
    configure_logging()
    MainWindow().mainloop()
