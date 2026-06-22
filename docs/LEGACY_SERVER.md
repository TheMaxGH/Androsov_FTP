# Legacy server mode

Legacy mode нужен для серверной машины без GUI: Windows Server, Linux-хост, VPS или машина, доступная только по SSH.

## Быстрый запуск

```powershell
python main.py --legacy-server --host 0.0.0.0 --port 2121 --root "D:\Share" --user user --password password
```

CLI-сервер показывает параметры в виде панели и подсвечивает события: запуск, вход пользователей, ошибки и остановку. Для компактного логирования используйте `--quiet`.

Linux/macOS:

```bash
python main.py --legacy-server --host 0.0.0.0 --port 2121 --root /srv/ftp --user user --password password
```

## Запуск из JSON-конфига

Тот же `vallhala.servers.json`, который использует GUI, можно использовать на сервере:

```powershell
python main.py --legacy-server --config vallhala.servers.json --server Public
```

Если `--server` не указан, будет выбран первый профиль из `servers`.

## Параметры быстрого режима

| Параметр | Назначение | По умолчанию |
|---|---|---|
| `--host` | IP-адрес для bind | `0.0.0.0` |
| `--port` | FTP-порт | `2121` |
| `--root` | Папка раздачи | текущая папка |
| `--user` | Имя пользователя | `user` |
| `--password` | Пароль | `password` |
| `--anonymous` | Разрешить read-only anonymous | выключено |
| `--passive-from` | Начало passive range | `60000` |
| `--passive-to` | Конец passive range | `60100` |
| `--tls` | Включить FTPS | выключено |
| `--certfile` | TLS-сертификат | пусто |
| `--keyfile` | TLS-ключ | пусто |
| `--quiet` | Компактные логи без визуальной панели | выключено |

## Несколько серверов

Можно запускать несколько серверов, если у каждого уникальная пара `IP:port`:

```powershell
python main.py --legacy-server --port 2121 --root "D:\Share1"
python main.py --legacy-server --port 2122 --root "D:\Share2"
```

В GUI это делается через вкладку **Серверы**: добавьте несколько профилей и запустите нужные.

## Остановка

Нажмите `Ctrl+C` в терминале. GUI останавливает все запущенные серверы при закрытии приложения.

## Безопасность

- Не используйте пароль `password` в реальной сети.
- Anonymous всегда read-only.
- Для доступа из интернета настройте firewall и passive range.
- Для production включайте FTPS.
