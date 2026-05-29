# Архитектура

Проект разделен по Clean Architecture: GUI и CLI не создают FTP-сервер напрямую, а работают через модели, use cases и инфраструктурный слой.

```text
FTP CLIENT/
├── src/
│   ├── core/                 доменные модели и use cases
│   ├── infrastructure/       pyftpdlib, FTP client, LAN scanner, config store
│   ├── gui/                  PySide6 интерфейс
│   ├── ui/                   QSS, иконки, ресурсы
│   ├── legacy_server.py      headless FTP/FTPS server
│   └── cli_client.py         headless FTP/FTPS client
├── docs/                     документация и материалы для диплома
├── tests/                    unit/integration tests
├── main.py                   точка входа
└── requirements.txt
```

## Основные сущности

- `ServerConfig` - профиль FTP/FTPS-сервера.
- `UserAccount` - пользователь, пароль, папка и права.
- `ServerLimits` - лимиты соединений и скорости.
- `IPFilter` - allow/deny list.
- `ClientProfile` - профиль подключения CLI-клиента.
- `AppConfig` - общий JSON-конфиг GUI и CLI.

## Сетевой слой

`OptiFTPServer` использует `pyftpdlib`. Библиотека обслуживает подключения асинхронно через select/poll, поэтому сервер не создает отдельный поток на каждого клиента.

`MultiFTPServerManager` держит несколько `OptiFTPServer` в одном процессе. Каждый сервер должен иметь уникальный `host:port`.

`FastLANScanner` использует `asyncio` и короткие таймауты, чтобы быстро проверять подсеть без блокировки GUI.

## GUI

PySide6-интерфейс состоит из трех вкладок:

- **Проводник** - FTP-клиент, локальный диск, удаленный список, очередь передач.
- **Серверы** - менеджер серверных профилей, пользователи, FTPS, anonymous, лимиты.
- **LAN-сканер** - поиск FTP-узлов в локальной сети.

## CLI

- `python main.py --legacy-server` запускает сервер без GUI.
- `python main.py --ftp list/upload/download` запускает клиентские операции.
- Оба режима умеют читать общий `vallhala.servers.json`.
