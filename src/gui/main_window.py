from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFileIconProvider,
    QFileSystemModel,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.core.entities import (
    AppConfig,
    IPFilter,
    READ_ONLY_PERMISSIONS,
    READ_WRITE_PERMISSIONS,
    ServerConfig,
    ServerLimits,
    TransferProgress,
    UserAccount,
)
from src.core.use_cases import PublishPortUseCase, ScanNetworkUseCase
from src.infrastructure.config_store import ConfigStore, default_app_config
from src.infrastructure.ftp_client import OptimizedFTPClient
from src.infrastructure.network_engine import FastLANScanner, MultiFTPServerManager
from src.utils.logger import configure_logging


class FileDropTreeView(QTreeView):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeView.DragDropMode.DropOnly)
        self.setProperty("dragActive", False)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self._set_active(False)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _set_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)


class ScanWorker(QObject):
    found = Signal(str, int, str, str)
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, subnet: str) -> None:
        super().__init__()
        self.subnet = subnet

    def run(self) -> None:
        try:
            count = 0

            def on_result(result) -> None:
                nonlocal count
                count += 1
                self.found.emit(result.host, result.port, f"{result.latency_ms:.1f} ms", result.banner or "порт открыт")

            ScanNetworkUseCase(FastLANScanner()).execute(subnet=self.subnet, on_result=on_result)
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))


class RemoteListWorker(QObject):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, client: OptimizedFTPClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.loaded.emit(self.client.list_dir())
        except Exception as exc:
            self.failed.emit(str(exc))


class TransferWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, client: OptimizedFTPClient, mode: str, local_path: Path, remote_name: str) -> None:
        super().__init__()
        self.client = client
        self.mode = mode
        self.local_path = local_path
        self.remote_name = remote_name

    def run(self) -> None:
        try:
            def on_progress(progress: TransferProgress) -> None:
                self.progress.emit(progress.filename, int(progress.percent))

            if self.mode == "upload":
                self.client.upload(self.local_path, self.remote_name, on_progress)
                self.finished.emit(f"Загрузка завершена: {self.remote_name}")
            else:
                self.client.download(self.remote_name, self.local_path, on_progress)
                self.finished.emit(f"Скачивание завершено: {self.local_path.name}")
        except Exception as exc:
            self.failed.emit(str(exc))


class UPnPWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, port: int) -> None:
        super().__init__()
        self.port = port

    def run(self) -> None:
        ok, message = PublishPortUseCase().execute(self.port)
        self.finished.emit(ok, message)


class ModernFTPGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VALLHALA FTP")
        self.setMinimumSize(QSize(1180, 760))
        self.resize(1360, 850)
        icon_path = _asset_path("vallhala_ftp_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.config_store = ConfigStore()
        try:
            self.app_config = self.config_store.load()
        except Exception:
            self.app_config = default_app_config()
        self.server_manager = MultiFTPServerManager(self._log)
        self.client = OptimizedFTPClient()
        self.transfer_queue: deque[tuple[str, Path, str]] = deque()
        self.active_transfer_thread: QThread | None = None
        self.active_transfer_worker: TransferWorker | None = None
        self._worker_threads: list[QThread] = []
        self._worker_refs: list[QObject] = []
        self.icon_provider = QFileIconProvider()
        self.remote_model = QStandardItemModel()
        self.remote_model.setHorizontalHeaderLabels(["Имя", "Тип"])

        self._build_ui()
        self._refresh_profile_table()
        self._load_profile_to_form(0)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh_server_runtime)
        self.status_timer.start(1000)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)
        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_transfer_tab(), "Проводник")
        self.tabs.addTab(self._build_server_tab(), "Серверы")
        self.tabs.addTab(self._build_scanner_tab(), "LAN-сканер")
        root.addWidget(self.tabs, 1)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(74)
        root.addWidget(self.log_view)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        icon = QLabel()
        icon.setObjectName("AppIconLabel")
        icon.setFixedSize(54, 54)
        icon_path = _asset_path("vallhala_ftp_icon.png")
        if icon_path.exists():
            icon.setPixmap(QPixmap(str(icon_path)).scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(icon)

        title_box = QVBoxLayout()
        title = QLabel("VALLHALA FTP")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Быстрый и надёжный клиент/сервер FTP")
        subtitle.setObjectName("SubtitleLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.status_metric = self._metric("Статус", "Готово", "StatusPill")
        self.queue_metric = self._metric("Очередь", "0", "QueuePill")
        layout.addWidget(self.status_metric)
        layout.addWidget(self.queue_metric)
        return frame

    def _metric(self, title: str, value: str, object_name: str) -> QWidget:
        box = QFrame()
        box.setObjectName(object_name)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 8, 14, 8)
        label = QLabel(title)
        label.setObjectName("MetricTitle")
        metric = QLabel(value)
        metric.setObjectName("MetricValue")
        layout.addWidget(label)
        layout.addWidget(metric)
        if title == "Статус":
            self.status_label = metric
        if title == "Очередь":
            self.queue_label = metric
        return box

    def _build_transfer_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setObjectName("SidebarScroll")
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setFixedWidth(390)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)

        connection = QGroupBox("FTP-подключение")
        connection.setObjectName("SoftCard")
        connection_layout = QGridLayout(connection)
        connection_layout.setContentsMargins(16, 20, 16, 16)
        self.host_edit = QLineEdit("127.0.0.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(2121)
        self.user_edit = QLineEdit("user")
        self.password_edit = QLineEdit("password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_protocol_combo = QComboBox()
        self.client_protocol_combo.addItems(["ftp", "ftps"])
        connect_btn = QPushButton("Подключиться")
        connect_btn.setObjectName("PrimaryButton")
        disconnect_btn = QPushButton("Отключиться")
        refresh_btn = QPushButton("Обновить удаленный список")
        connect_btn.clicked.connect(self._connect_client)
        disconnect_btn.clicked.connect(self._disconnect_client)
        refresh_btn.clicked.connect(self._load_remote_async)
        fields = (
            ("Хост", self.host_edit),
            ("Порт", self.port_spin),
            ("Логин", self.user_edit),
            ("Пароль", self.password_edit),
            ("Протокол", self.client_protocol_combo),
        )
        for row, (label, widget) in enumerate(fields):
            connection_layout.addWidget(QLabel(label), row, 0)
            connection_layout.addWidget(widget, row, 1)
        connection_layout.addWidget(connect_btn, 5, 0, 1, 2)
        connection_layout.addWidget(disconnect_btn, 6, 0, 1, 2)
        connection_layout.addWidget(refresh_btn, 7, 0, 1, 2)
        sidebar_layout.addWidget(connection)

        actions = QFrame()
        actions.setObjectName("ActionPanel")
        actions_layout = QVBoxLayout(actions)
        buttons_row = QHBoxLayout()
        upload_btn = QPushButton("Загрузить")
        upload_btn.setObjectName("PurpleButton")
        download_btn = QPushButton("Скачать")
        upload_btn.clicked.connect(self._upload_selected_local)
        download_btn.clicked.connect(self._download_selected_remote)
        buttons_row.addWidget(upload_btn)
        buttons_row.addWidget(download_btn)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        actions_layout.addLayout(buttons_row)
        actions_layout.addWidget(self.progress)
        sidebar_layout.addWidget(actions)
        sidebar_layout.addStretch(1)
        sidebar_scroll.setWidget(sidebar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_local_explorer())
        splitter.addWidget(self._build_remote_explorer())
        splitter.setSizes([500, 270])
        layout.addWidget(sidebar_scroll)
        layout.addWidget(splitter, 1)
        return page

    def _build_local_explorer(self) -> QGroupBox:
        group = QGroupBox("Локальный диск")
        group.setObjectName("ExplorerCard")
        layout = QVBoxLayout(group)
        hint = QLabel("Перетащите файлы прямо в проводник, чтобы добавить их в очередь загрузки")
        hint.setObjectName("ExplorerHint")
        layout.addWidget(hint)
        self.local_model = QFileSystemModel(self)
        self.local_model.setRootPath(QDir.rootPath())
        self.local_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self.local_tree = FileDropTreeView()
        self.local_tree.files_dropped.connect(self._enqueue_dropped_files)
        self.local_tree.setModel(self.local_model)
        self.local_tree.setRootIndex(self.local_model.index(str(Path.home())))
        self.local_tree.setSortingEnabled(True)
        self.local_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.local_tree.setAlternatingRowColors(True)
        self.local_tree.header().setStretchLastSection(False)
        self.local_tree.header().resizeSection(0, 280)
        layout.addWidget(self.local_tree)
        return group

    def _build_remote_explorer(self) -> QGroupBox:
        group = QGroupBox("Удаленный сервер")
        group.setObjectName("ExplorerCard")
        layout = QVBoxLayout(group)
        self.remote_view = QTreeView()
        self.remote_view.setModel(self.remote_model)
        self.remote_view.setAlternatingRowColors(True)
        self.remote_view.header().resizeSection(0, 360)
        layout.addWidget(self.remote_view)
        return group

    def _build_server_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        left = QGroupBox("Профили")
        left.setObjectName("SoftCard")
        left_layout = QVBoxLayout(left)
        self.profile_table = QTableWidget(0, 3)
        self.profile_table.setHorizontalHeaderLabels(["Имя", "Порт", "Статус"])
        self.profile_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.profile_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.profile_table.itemSelectionChanged.connect(self._profile_selection_changed)
        self.profile_table.verticalHeader().setVisible(False)
        self.profile_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.profile_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.profile_table, 1)
        profile_buttons = QHBoxLayout()
        add_profile = QPushButton("Добавить")
        remove_profile = QPushButton("Удалить")
        add_profile.clicked.connect(self._add_profile)
        remove_profile.clicked.connect(self._remove_profile)
        profile_buttons.addWidget(add_profile)
        profile_buttons.addWidget(remove_profile)
        left_layout.addLayout(profile_buttons)
        left.setMinimumWidth(300)
        left.setMaximumWidth(360)

        right_scroll = QScrollArea()
        right_scroll.setObjectName("ServerScroll")
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 8, 0)
        right_layout.setSpacing(12)

        self.runtime_card = QFrame()
        self.runtime_card.setObjectName("RuntimeCard")
        runtime_layout = QHBoxLayout(self.runtime_card)
        runtime_layout.setContentsMargins(18, 12, 18, 12)
        runtime_layout.setSpacing(18)
        runtime_text = QVBoxLayout()
        runtime_text.setSpacing(4)
        self.runtime_status = QLabel("Остановлен")
        self.runtime_status.setObjectName("RuntimeStatus")
        self.runtime_address = QLabel("Адрес появится после запуска")
        self.runtime_address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.runtime_address.setWordWrap(True)
        self.runtime_sessions = QLabel("Сессии: 0")
        self.runtime_uptime = QLabel("Uptime: 00:00:00")
        runtime_caption = QLabel("Состояние")
        runtime_caption.setObjectName("HelperText")
        runtime_text.addWidget(runtime_caption)
        runtime_text.addWidget(self.runtime_status)
        runtime_layout.addLayout(runtime_text)
        runtime_layout.addWidget(self.runtime_address, 1)
        runtime_layout.addWidget(self.runtime_sessions)
        runtime_layout.addWidget(self.runtime_uptime)
        right_layout.addWidget(self.runtime_card)

        settings = QGroupBox("Настройки выбранного сервера")
        settings.setObjectName("SoftCard")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(18, 20, 18, 18)
        settings_layout.setSpacing(10)
        self.server_name_edit = QLineEdit("Default")
        self.server_host_edit = QLineEdit("0.0.0.0")
        self.server_root_edit = QLineEdit(str(Path.cwd()))
        browse_btn = QPushButton("Выбрать папку")
        browse_btn.clicked.connect(self._choose_server_root)
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setRange(1, 65535)
        self.server_port_spin.setValue(2121)
        self.passive_from_spin = QSpinBox()
        self.passive_from_spin.setRange(1, 65535)
        self.passive_from_spin.setValue(60000)
        self.passive_to_spin = QSpinBox()
        self.passive_to_spin.setRange(1, 65535)
        self.passive_to_spin.setValue(60100)
        self.server_protocol_combo = QComboBox()
        self.server_protocol_combo.addItems(["ftp", "ftps"])
        self.anonymous_check = QCheckBox("Разрешить anonymous read-only")
        self.certfile_edit = QLineEdit()
        self.keyfile_edit = QLineEdit()
        cert_btn = QPushButton("Сертификат")
        key_btn = QPushButton("Ключ")
        cert_btn.clicked.connect(lambda: self._choose_file(self.certfile_edit, "TLS-сертификат"))
        key_btn.clicked.connect(lambda: self._choose_file(self.keyfile_edit, "TLS-ключ"))
        self.max_conn_spin = QSpinBox()
        self.max_conn_spin.setRange(1, 10000)
        self.max_conn_spin.setValue(128)
        self.max_ip_spin = QSpinBox()
        self.max_ip_spin.setRange(1, 10000)
        self.max_ip_spin.setValue(8)
        self.upload_limit_spin = QSpinBox()
        self.upload_limit_spin.setRange(0, 1000000)
        self.download_limit_spin = QSpinBox()
        self.download_limit_spin.setRange(0, 1000000)
        self.allow_ip_edit = QLineEdit()
        self.deny_ip_edit = QLineEdit()

        for widget in (
            self.server_name_edit,
            self.server_host_edit,
            self.server_root_edit,
            self.certfile_edit,
            self.keyfile_edit,
            self.allow_ip_edit,
            self.deny_ip_edit,
        ):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(_field("Имя", self.server_name_edit), 2)
        top_row.addWidget(_field("Bind IP", self.server_host_edit), 1)
        top_row.addWidget(_field("Порт", self.server_port_spin), 1)
        settings_layout.addLayout(top_row)

        root_row = QHBoxLayout()
        root_row.setSpacing(10)
        root_row.addWidget(_field("Папка раздачи", self.server_root_edit), 1)
        root_row.addWidget(browse_btn)
        settings_layout.addLayout(root_row)

        protocol_row = QHBoxLayout()
        protocol_row.setSpacing(10)
        protocol_row.addWidget(_field("Протокол", self.server_protocol_combo), 1)
        protocol_row.addWidget(_field("Passive from", self.passive_from_spin), 1)
        protocol_row.addWidget(_field("Passive to", self.passive_to_spin), 1)
        protocol_row.addWidget(self.anonymous_check, 2)
        settings_layout.addLayout(protocol_row)

        tls_row = QHBoxLayout()
        tls_row.setSpacing(10)
        tls_row.addWidget(_field("TLS-сертификат", self.certfile_edit), 1)
        tls_row.addWidget(cert_btn)
        tls_row.addWidget(_field("TLS-ключ", self.keyfile_edit), 1)
        tls_row.addWidget(key_btn)
        settings_layout.addLayout(tls_row)

        limits_row = QHBoxLayout()
        limits_row.setSpacing(10)
        limits_row.addWidget(_field("Max conn", self.max_conn_spin), 1)
        limits_row.addWidget(_field("Max per IP", self.max_ip_spin), 1)
        limits_row.addWidget(_field("Upload KB/s", self.upload_limit_spin), 1)
        limits_row.addWidget(_field("Download KB/s", self.download_limit_spin), 1)
        settings_layout.addLayout(limits_row)

        ip_row = QHBoxLayout()
        ip_row.setSpacing(10)
        ip_row.addWidget(_field("Allow IP", self.allow_ip_edit), 1)
        ip_row.addWidget(_field("Deny IP", self.deny_ip_edit), 1)
        settings_layout.addLayout(ip_row)
        right_layout.addWidget(settings)

        users = QGroupBox("Пользователи")
        users.setObjectName("SoftCard")
        users_layout = QVBoxLayout(users)
        self.users_table = QTableWidget(0, 5)
        self.users_table.setHorizontalHeaderLabels(["Вкл", "Логин", "Пароль", "Папка", "Права"])
        self.users_table.setMinimumHeight(150)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        users_layout.addWidget(self.users_table)
        user_buttons = QHBoxLayout()
        add_user = QPushButton("Добавить пользователя")
        remove_user = QPushButton("Удалить пользователя")
        add_user.clicked.connect(self._add_user_row)
        remove_user.clicked.connect(self._remove_user_row)
        user_buttons.addWidget(add_user)
        user_buttons.addWidget(remove_user)
        users_layout.addLayout(user_buttons)
        right_layout.addWidget(users)

        actions = QHBoxLayout()
        self.save_profile_btn = QPushButton("Сохранить профиль")
        self.save_profile_btn.clicked.connect(self._save_current_profile)
        self.start_server_btn = QPushButton("Запустить")
        self.start_server_btn.setObjectName("PrimaryButton")
        self.stop_server_btn = QPushButton("Остановить")
        self.stop_server_btn.setObjectName("DangerButton")
        self.upnp_btn = QPushButton("Пробросить UPnP")
        self.start_server_btn.clicked.connect(self._start_selected_server)
        self.stop_server_btn.clicked.connect(self._stop_selected_server)
        self.upnp_btn.clicked.connect(self._open_upnp)
        actions.addWidget(self.save_profile_btn)
        actions.addStretch(1)
        actions.addWidget(self.start_server_btn)
        actions.addWidget(self.stop_server_btn)
        actions.addWidget(self.upnp_btn)
        right_layout.addLayout(actions)
        right_layout.addStretch(1)

        layout.addWidget(left)
        right_scroll.setWidget(right)
        layout.addWidget(right_scroll, 1)
        return page

    def _build_scanner_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        controls = QHBoxLayout()
        self.subnet_edit = QLineEdit(FastLANScanner().default_subnet())
        scan_btn = QPushButton("Сканировать 21/2121")
        scan_btn.setObjectName("PrimaryButton")
        scan_btn.clicked.connect(self._scan_async)
        controls.addWidget(QLabel("Подсеть"))
        controls.addWidget(self.subnet_edit, 1)
        controls.addWidget(scan_btn)
        layout.addLayout(controls)
        self.scan_model = QStandardItemModel()
        self.scan_model.setHorizontalHeaderLabels(["Хост", "Порт", "Задержка", "Ответ"])
        self.scan_view = QTreeView()
        self.scan_view.setModel(self.scan_model)
        self.scan_view.setAlternatingRowColors(True)
        self.scan_view.doubleClicked.connect(self._use_scanned_host)
        layout.addWidget(self.scan_view, 1)
        return page

    def _selected_profile_index(self) -> int:
        row = self.profile_table.currentRow()
        return row if 0 <= row < len(self.app_config.servers) else 0

    def _selected_profile(self) -> ServerConfig:
        if not self.app_config.servers:
            self.app_config.servers.append(default_app_config().servers[0])
        return self.app_config.servers[self._selected_profile_index()]

    def _refresh_profile_table(self) -> None:
        selected = max(0, self.profile_table.currentRow())
        self.profile_table.setRowCount(len(self.app_config.servers))
        for row, server in enumerate(self.app_config.servers):
            info = self.server_manager.info(server.name)
            for col, value in enumerate((server.name, str(server.port), info.status)):
                item = QTableWidgetItem(value)
                if col == 2:
                    item.setData(Qt.ItemDataRole.UserRole, info.status)
                self.profile_table.setItem(row, col, item)
        if self.app_config.servers:
            self.profile_table.selectRow(min(selected, len(self.app_config.servers) - 1))
        self._refresh_server_runtime()

    def _profile_selection_changed(self) -> None:
        self._load_profile_to_form(self._selected_profile_index())

    def _load_profile_to_form(self, index: int) -> None:
        if not self.app_config.servers:
            return
        server = self.app_config.servers[index]
        self.server_name_edit.setText(server.name)
        self.server_host_edit.setText(server.host)
        self.server_root_edit.setText(str(server.root_path))
        self.server_port_spin.setValue(server.port)
        self.passive_from_spin.setValue(server.passive_ports[0])
        self.passive_to_spin.setValue(server.passive_ports[1])
        self.server_protocol_combo.setCurrentText(server.protocol)
        self.anonymous_check.setChecked(server.allow_anonymous)
        self.certfile_edit.setText(str(server.certfile or ""))
        self.keyfile_edit.setText(str(server.keyfile or ""))
        self.max_conn_spin.setValue(server.limits.max_connections)
        self.max_ip_spin.setValue(server.limits.max_connections_per_ip)
        self.upload_limit_spin.setValue(server.limits.upload_limit_kbps)
        self.download_limit_spin.setValue(server.limits.download_limit_kbps)
        self.allow_ip_edit.setText(", ".join(server.ip_filter.allow))
        self.deny_ip_edit.setText(", ".join(server.ip_filter.deny))
        self._load_users(server.users)
        self._refresh_server_runtime()

    def _load_users(self, users: list[UserAccount]) -> None:
        self.users_table.setRowCount(0)
        for user in users:
            self._add_user_row(user)

    def _add_profile(self) -> None:
        base_port = 2121 + len(self.app_config.servers)
        self.app_config.servers.append(ServerConfig(name=f"Server {len(self.app_config.servers) + 1}", port=base_port))
        self._persist_config()
        self._refresh_profile_table()
        self.profile_table.selectRow(len(self.app_config.servers) - 1)

    def _remove_profile(self) -> None:
        index = self._selected_profile_index()
        if not self.app_config.servers:
            return
        name = self.app_config.servers[index].name
        if name in self.server_manager.running():
            self._error("Удаление профиля", "Сначала остановите сервер.")
            return
        self.app_config.servers.pop(index)
        if not self.app_config.servers:
            self.app_config.servers.append(default_app_config().servers[0])
        self._persist_config()
        self._refresh_profile_table()

    def _add_user_row(self, user: UserAccount | None = None) -> None:
        user = user or UserAccount(username=f"user{self.users_table.rowCount() + 1}", password="password")
        row = self.users_table.rowCount()
        self.users_table.insertRow(row)
        enabled = QTableWidgetItem()
        enabled.setCheckState(Qt.CheckState.Checked if user.enabled else Qt.CheckState.Unchecked)
        self.users_table.setItem(row, 0, enabled)
        self.users_table.setItem(row, 1, QTableWidgetItem(user.username))
        self.users_table.setItem(row, 2, QTableWidgetItem(user.password))
        self.users_table.setItem(row, 3, QTableWidgetItem(str(user.root_path or "")))
        rights = QComboBox()
        rights.addItems(["Чтение и запись", "Только чтение"])
        rights.setCurrentText("Только чтение" if user.permissions == READ_ONLY_PERMISSIONS else "Чтение и запись")
        self.users_table.setCellWidget(row, 4, rights)

    def _remove_user_row(self) -> None:
        row = self.users_table.currentRow()
        if row >= 0:
            self.users_table.removeRow(row)

    def _collect_profile_from_form(self) -> ServerConfig:
        users: list[UserAccount] = []
        for row in range(self.users_table.rowCount()):
            enabled_item = self.users_table.item(row, 0)
            username = self._table_text(row, 1).strip()
            password = self._table_text(row, 2)
            root_text = self._table_text(row, 3).strip()
            rights_widget = self.users_table.cellWidget(row, 4)
            rights_text = rights_widget.currentText() if isinstance(rights_widget, QComboBox) else "Чтение и запись"
            if username:
                users.append(
                    UserAccount(
                        username=username,
                        password=password,
                        root_path=Path(root_text) if root_text else None,
                        permissions=READ_ONLY_PERMISSIONS if rights_text == "Только чтение" else READ_WRITE_PERMISSIONS,
                        enabled=enabled_item.checkState() == Qt.CheckState.Checked if enabled_item else True,
                    )
                )
        return ServerConfig(
            name=self.server_name_edit.text().strip() or "Default",
            host=self.server_host_edit.text().strip() or "0.0.0.0",
            port=self.server_port_spin.value(),
            root_path=Path(self.server_root_edit.text().strip() or "."),
            allow_anonymous=self.anonymous_check.isChecked(),
            passive_ports=(self.passive_from_spin.value(), self.passive_to_spin.value()),
            protocol=self.server_protocol_combo.currentText(),
            certfile=Path(self.certfile_edit.text()) if self.certfile_edit.text().strip() else None,
            keyfile=Path(self.keyfile_edit.text()) if self.keyfile_edit.text().strip() else None,
            users=users or [UserAccount()],
            limits=ServerLimits(
                max_connections=self.max_conn_spin.value(),
                max_connections_per_ip=self.max_ip_spin.value(),
                upload_limit_kbps=self.upload_limit_spin.value(),
                download_limit_kbps=self.download_limit_spin.value(),
            ),
            ip_filter=IPFilter(allow=_split_csv(self.allow_ip_edit.text()), deny=_split_csv(self.deny_ip_edit.text())),
        )

    def _save_current_profile(self) -> None:
        index = self._selected_profile_index()
        old_name = self.app_config.servers[index].name
        if old_name in self.server_manager.running():
            self._error("Сохранение профиля", "Остановите сервер перед изменением настроек.")
            return
        self.app_config.servers[index] = self._collect_profile_from_form()
        self._persist_config()
        self._refresh_profile_table()
        self._log("Профиль сохранен")

    def _start_selected_server(self) -> None:
        index = self._selected_profile_index()
        config = self._collect_profile_from_form()
        self.app_config.servers[index] = config
        self._persist_config()
        try:
            self._set_profile_editing(False)
            self.runtime_status.setText("Запускается")
            address = self.server_manager.start(config.name, config)
            self._log(f"Сервер запущен: {address}")
            self._set_status("Сервер запущен")
        except Exception as exc:
            self.runtime_status.setText("Ошибка")
            self._error("Ошибка сервера", str(exc))
        finally:
            self._refresh_profile_table()

    def _stop_selected_server(self) -> None:
        profile = self._selected_profile()
        self.server_manager.stop(profile.name)
        self._log(f"Сервер остановлен: {profile.name}")
        self._set_status("Готово")
        self._refresh_profile_table()

    def _refresh_server_runtime(self) -> None:
        if not hasattr(self, "runtime_status") or not self.app_config.servers:
            return
        profile = self._selected_profile()
        info = self.server_manager.info(profile.name)
        self.runtime_status.setText(info.status)
        self.runtime_status.setProperty("state", info.status)
        self.runtime_status.style().unpolish(self.runtime_status)
        self.runtime_status.style().polish(self.runtime_status)
        self.runtime_address.setText(info.error or info.address or "Адрес появится после запуска")
        self.runtime_sessions.setText(f"Сессии: {info.active_sessions}")
        self.runtime_uptime.setText(f"Uptime: {_format_seconds(info.uptime_seconds)}")
        running = info.status == "Запущен"
        self.start_server_btn.setEnabled(not running)
        self.stop_server_btn.setEnabled(running)
        self.upnp_btn.setEnabled(running)
        self._set_profile_editing(not running)
        for row, server in enumerate(self.app_config.servers):
            table_info = self.server_manager.info(server.name)
            item = self.profile_table.item(row, 2)
            if item:
                item.setText(table_info.status)

    def _set_profile_editing(self, enabled: bool) -> None:
        for widget in (
            self.server_name_edit,
            self.server_host_edit,
            self.server_root_edit,
            self.server_port_spin,
            self.passive_from_spin,
            self.passive_to_spin,
            self.server_protocol_combo,
            self.anonymous_check,
            self.certfile_edit,
            self.keyfile_edit,
            self.max_conn_spin,
            self.max_ip_spin,
            self.upload_limit_spin,
            self.download_limit_spin,
            self.allow_ip_edit,
            self.deny_ip_edit,
            self.users_table,
            self.save_profile_btn,
        ):
            widget.setEnabled(enabled)

    def _persist_config(self) -> None:
        try:
            self.config_store.save(self.app_config)
        except Exception as exc:
            self._log(f"Не удалось сохранить config: {exc}")

    def _connect_client(self) -> None:
        try:
            self.client.connect(
                self.host_edit.text().strip(),
                self.port_spin.value(),
                self.user_edit.text().strip(),
                self.password_edit.text(),
                protocol=self.client_protocol_combo.currentText(),
            )
            self._set_status("Подключено")
            self._log("FTP-клиент подключен")
            self._load_remote_async()
        except Exception as exc:
            self._error("Ошибка подключения", str(exc))

    def _disconnect_client(self) -> None:
        self.client.disconnect()
        self.remote_model.removeRows(0, self.remote_model.rowCount())
        self._set_status("Отключено")
        self._log("FTP-клиент отключен")

    def _load_remote_async(self) -> None:
        if not self.client.connected:
            self._log("Сначала подключитесь к FTP-серверу")
            return
        worker = RemoteListWorker(self.client)
        thread = self._run_worker(worker)
        worker.loaded.connect(self._remote_loaded)
        worker.failed.connect(lambda msg: self._error("Ошибка списка файлов", msg))
        worker.loaded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.start()

    def _remote_loaded(self, names: list[str]) -> None:
        self.remote_model.removeRows(0, self.remote_model.rowCount())
        file_icon = self.icon_provider.icon(QFileIconProvider.IconType.File)
        for name in names:
            self.remote_model.appendRow([QStandardItem(file_icon, str(name)), QStandardItem("файл")])
        self._log(f"Удаленный список обновлен: {len(names)} элемент(ов)")

    def _upload_selected_local(self) -> None:
        path = self._selected_local_path()
        if not path or not path.is_file():
            self._error("Загрузка", "Выберите локальный файл.")
            return
        self._enqueue_transfer("upload", path, path.name)

    def _download_selected_remote(self) -> None:
        remote_name = self._selected_remote_name()
        if not remote_name:
            self._error("Скачивание", "Выберите файл на удаленном сервере.")
            return
        target, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", str(Path.home() / Path(remote_name).name))
        if target:
            self._enqueue_transfer("download", Path(target), remote_name)

    def _enqueue_dropped_files(self, paths: list[str]) -> None:
        added = 0
        for raw_path in paths:
            path = Path(raw_path)
            if path.is_file():
                self._enqueue_transfer("upload", path, path.name, autostart=False)
                added += 1
        self._update_queue_metric()
        self._log(f"Добавлено файлов в очередь: {added}")
        self._start_next_transfer()

    def _enqueue_transfer(self, mode: str, local_path: Path, remote_name: str, autostart: bool = True) -> None:
        if not self.client.connected:
            self._error("Передача", "Сначала подключитесь к FTP-серверу.")
            return
        self.transfer_queue.append((mode, local_path, remote_name))
        self._update_queue_metric()
        if autostart:
            self._start_next_transfer()

    def _start_next_transfer(self) -> None:
        if self.active_transfer_thread or not self.transfer_queue:
            return
        mode, local_path, remote_name = self.transfer_queue.popleft()
        self._update_queue_metric()
        worker = TransferWorker(self.client, mode, local_path, remote_name)
        thread = QThread(self)
        self.active_transfer_thread = thread
        self.active_transfer_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._transfer_progress)
        worker.finished.connect(self._transfer_finished)
        worker.failed.connect(lambda msg: self._transfer_failed(msg))
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_active_transfer)
        thread.start()
        self._set_status("Передача")

    def _transfer_progress(self, filename: str, percent: int) -> None:
        self.progress.setValue(percent)
        self._set_status(f"{filename}: {percent}%")

    def _transfer_finished(self, message: str) -> None:
        self.progress.setValue(100)
        self._log(message)
        self._load_remote_async()

    def _transfer_failed(self, message: str) -> None:
        self._error("Ошибка передачи", message)

    def _clear_active_transfer(self) -> None:
        self.active_transfer_thread = None
        self.active_transfer_worker = None
        self._set_status("Готово")
        self._start_next_transfer()

    def _open_upnp(self) -> None:
        worker = UPnPWorker(self.server_port_spin.value())
        thread = self._run_worker(worker)
        worker.finished.connect(lambda ok, message: self._log(("UPnP: " if ok else "UPnP недоступен: ") + message))
        worker.finished.connect(thread.quit)
        thread.start()

    def _choose_server_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Папка FTP-сервера", self.server_root_edit.text())
        if directory:
            self.server_root_edit.setText(directory)

    def _choose_file(self, target: QLineEdit, title: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, str(Path.cwd()))
        if path:
            target.setText(path)

    def _scan_async(self) -> None:
        self.scan_model.removeRows(0, self.scan_model.rowCount())
        self._set_status("Сканирование")
        worker = ScanWorker(self.subnet_edit.text().strip())
        thread = self._run_worker(worker)
        worker.found.connect(self._add_scan_result)
        worker.finished.connect(lambda count: self._scan_finished(count))
        worker.failed.connect(lambda msg: self._error("Ошибка сканера", msg))
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.start()

    def _add_scan_result(self, host: str, port: int, latency: str, banner: str) -> None:
        icon = self.icon_provider.icon(QFileIconProvider.IconType.Computer)
        self.scan_model.appendRow([QStandardItem(icon, host), QStandardItem(str(port)), QStandardItem(latency), QStandardItem(banner)])

    def _scan_finished(self, count: int) -> None:
        self._set_status("Готово")
        self._log(f"Сканирование завершено: найдено {count} сервер(ов)")

    def _use_scanned_host(self, index: QModelIndex) -> None:
        row = index.row()
        host = self.scan_model.item(row, 0).text()
        port = int(self.scan_model.item(row, 1).text())
        self.host_edit.setText(host)
        self.port_spin.setValue(port)
        self.tabs.setCurrentIndex(0)
        self._log(f"Выбран FTP-узел {host}:{port}")

    def _run_worker(self, worker: QObject) -> QThread:
        thread = QThread(self)
        self._worker_threads.append(thread)
        self._worker_refs.append(worker)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda thread=thread: self._worker_threads.remove(thread) if thread in self._worker_threads else None)
        thread.finished.connect(lambda worker=worker: self._worker_refs.remove(worker) if worker in self._worker_refs else None)
        return thread

    def _selected_local_path(self) -> Path | None:
        index = self.local_tree.currentIndex()
        if not index.isValid():
            return None
        return Path(self.local_model.filePath(index))

    def _selected_remote_name(self) -> str | None:
        index = self.remote_view.currentIndex()
        if not index.isValid():
            return None
        return self.remote_model.item(index.row(), 0).text()

    def _table_text(self, row: int, column: int) -> str:
        item = self.users_table.item(row, column)
        return item.text() if item else ""

    def _set_status(self, value: str) -> None:
        self.status_label.setText(value)

    def _update_queue_metric(self) -> None:
        self.queue_label.setText(str(len(self.transfer_queue)))

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _error(self, title: str, message: str) -> None:
        self._set_status("Ошибка")
        self._log(f"{title}: {message}")
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        self.server_manager.stop_all()
        self.client.disconnect()
        super().closeEvent(event)


def _asset_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "ui" / "assets" / name


def _field(label: str, widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    caption = QLabel(label)
    caption.setObjectName("FieldCaption")
    layout.addWidget(caption)
    layout.addWidget(widget)
    return box


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _format_seconds(value: float) -> str:
    total = int(value)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def run_app() -> None:
    configure_logging()
    app = QApplication(sys.argv)
    qss_path = Path(__file__).resolve().parents[1] / "ui" / "dark_carbon.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    window = ModernFTPGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
