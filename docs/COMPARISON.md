# Сравнение с конкурентами

## Таблица для диплома

| Критерий | VALLHALA FTP | FileZilla Client/Server | WinSCP | IIS FTP / vsftpd |
|---|---|---|---|---|
| Архитектура | All-in-One GUI + CLI + headless server | Клиент и сервер существуют отдельно | В первую очередь клиент и автоматизация | Серверная роль/демон |
| Порог входа | Запуск сервера в GUI за пару минут | Требуется отдельная настройка сервера | Удобен как клиент, сервер не предоставляет | Требует администрирования ОС |
| Несколько серверов | Несколько профилей в GUI и CLI config | Серверная часть ориентирована на службу | Не является FTP-сервером | Можно через несколько инстансов/конфигов |
| Пользователи | Несколько пользователей, права, anonymous read-only | Пользователи, группы, TLS, логи | Site profiles, credential workflow | Пользователи ОС или конфиг демона |
| LAN discovery | Встроенный asyncio scanner 21/2121 | Обычно ручной ввод адреса | Обычно ручной ввод адреса | Нет GUI discovery |
| CLI/automation | `--legacy-server` и `--ftp` команды | Отдельные инструменты | Сильная сторона WinSCP: scripting/automation | Сервисные команды ОС |
| FTPS | Есть режим FTPS через pyftpdlib TLS handler | Поддерживается | Поддерживается как клиент | Поддерживается в зависимости от сервера |
| UX | Современный русский GUI, статусы и быстрые сценарии | Много настроек, интерфейс перегружен для новичка | Сильный клиентский UX | Нет единого desktop UX |

## Вывод

VALLHALA FTP не пытается заменить все протоколы WinSCP или всю зрелость FileZilla Server. Цель проекта другая: дать учебно-практическое приложение, где клиент, сервер, LAN-discovery, UPnP, GUI и CLI работают как единая система с низким порогом входа.

Сценарии для практической проверки этих отличий вынесены в [сравнительные тесты с аналогами](COMPETITIVE_TESTS.md).

## Источники для сравнения

- WinSCP feature index: https://winscp.net/eng/docs/feature_index
- WinSCP introduction: https://winscp.net/eng/docs/introduction
- FileZilla Server features: https://filezillapro.com/docs/server/features/filezilla-server-features/
