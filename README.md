# VALLHALA FTP

**VALLHALA FTP** - быстрый и надёжный FTP/FTPS клиент-сервер для локального обмена файлами, учебного проекта и серверных машин без GUI.

## Быстрая навигация

- [Быстрый старт](docs/QUICK_START.md)
- [Legacy server mode для SSH/серверной машины](docs/LEGACY_SERVER.md)
- [CLI FTP-клиент: list/upload/download](docs/CLI_CLIENT.md)
- [Production notes: порты, несколько серверов, firewall](docs/PRODUCTION.md)
- [Архитектура проекта](docs/ARCHITECTURE.md)
- [Сравнение с FileZilla, WinSCP, IIS FTP и vsftpd](docs/COMPARISON.md)
- [Сетевой движок](src/infrastructure/network_engine.py)
- [PySide6 GUI](src/gui/main_window.py)
- [QSS тема](src/ui/dark_carbon.qss)

## Возможности

- Запуск нескольких FTP-серверов из GUI в одном окне.
- Профили серверов в общем JSON-конфиге `vallhala.servers.json`.
- Несколько пользователей на сервер, индивидуальные права и папки.
- Anonymous read-only режим для простой раздачи файлов.
- FTP и FTPS: TLS включается явно через GUI или CLI.
- Цветной live-статус: остановлен, запускается, запущен, ошибка.
- LAN-сканер портов `21` и `2121` без блокировки интерфейса.
- Drag & Drop прямо в локальный проводник для постановки файлов в очередь загрузки.
- CLI-клиент и legacy/headless сервер для SSH и автоматизации.
- UPnP-проброс порта, если роутер и окружение это поддерживают.

## Запуск GUI

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Запуск сервера без GUI

Быстрый режим:

```powershell
python main.py --legacy-server --host 0.0.0.0 --port 2121 --root "D:\Share" --user user --password password
```

Профиль из общего конфига:

```powershell
python main.py --legacy-server --config vallhala.servers.json --server Public
```

## CLI FTP-клиент

```powershell
python main.py --ftp list --host 127.0.0.1 --port 2121 --user user --password password
python main.py --ftp upload --host 127.0.0.1 --local "D:\file.txt" --remote file.txt
python main.py --ftp download --host 127.0.0.1 --remote file.txt --local "D:\Downloads\file.txt"
python main.py --ftp list --config vallhala.servers.json --profile local
```

## Пример JSON-конфига

```json
{
  "servers": [
    {
      "name": "Public",
      "host": "0.0.0.0",
      "port": 2121,
      "root_path": "D:/Share",
      "protocol": "ftp",
      "allow_anonymous": true,
      "passive_ports": [60000, 60100],
      "users": [
        {
          "username": "user",
          "password": "password",
          "root_path": "",
          "permissions": "elradfmwMT",
          "enabled": true
        }
      ],
      "limits": {
        "max_connections": 128,
        "max_connections_per_ip": 8,
        "upload_limit_kbps": 0,
        "download_limit_kbps": 0
      },
      "ip_filter": {
        "allow": [],
        "deny": []
      }
    }
  ],
  "client_profiles": [
    {
      "name": "local",
      "host": "127.0.0.1",
      "port": 2121,
      "username": "user",
      "password": "password",
      "protocol": "ftp"
    }
  ]
}
```

## Сборка EXE

```powershell
python -m pip install pyinstaller
python build_script.py
```

## Тесты

```powershell
python -m unittest discover -v
```

## Безопасность

Обычный FTP передает логин и пароль без шифрования. Для production-сценариев включайте FTPS, используйте сильные пароли, ограничивайте папку раздачи, IP-фильтр и firewall.
