# Структура проекта VALLHALA FTP

```text
FTP CLIENT/
├── src/
│   ├── core/
│   │   ├── entities.py        ServerConfig, UserAccount, ClientProfile
│   │   └── use_cases.py       сценарии сканирования и управления сервером
│   ├── infrastructure/
│   │   ├── network_engine.py  FTP/FTPS сервер, multi-server manager, LAN scanner, UPnP
│   │   ├── ftp_client.py      FTP/FTPS клиент с буферизацией
│   │   └── config_store.py    JSON-конфиг GUI/CLI
│   ├── gui/
│   │   └── main_window.py     PySide6 GUI
│   ├── ui/
│   │   ├── dark_carbon.qss    тема интерфейса
│   │   └── assets/            иконки
│   ├── legacy_server.py       запуск сервера без GUI
│   └── cli_client.py          CLI list/upload/download
├── docs/
│   ├── QUICK_START.md
│   ├── LEGACY_SERVER.md
│   ├── CLI_CLIENT.md
│   ├── PRODUCTION.md
│   ├── ARCHITECTURE.md
│   └── COMPARISON.md
├── tests/
├── main.py
├── build_script.py
├── requirements.txt
└── README.md
```

Главная идея: GUI, CLI и legacy server используют одни и те же доменные модели и один JSON-конфиг. Это снижает дублирование и делает поведение одинаковым в desktop- и server-сценариях.
