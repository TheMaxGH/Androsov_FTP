# Performance graphs

Графики построены на основе сценариев из [таблицы тестов производительности](PERFORMANCE_TESTS.md). Они показывают покрытие проверок, порядок прогона и целевые ориентиры там, где в тест-плане уже задан числовой порог.

## Покрытие сценариев

```mermaid
pie title Performance test coverage
    "Startup and GUI" : 1
    "Server runtime" : 2
    "LAN scanner" : 1
    "Transfers" : 4
    "Limits and throttling" : 1
    "FTPS" : 1
    "Stability and stress" : 2
```

## Порядок прогона

```mermaid
flowchart LR
    env["Окружение\nОС, Python, сеть, диск"] --> startup["PERF-001\nХолодный старт GUI"]
    env --> server["PERF-002\nСтарт headless-сервера"]
    server --> scan["PERF-003\nLAN-сканирование"]
    server --> small["PERF-004\n100 маленьких файлов"]
    small --> upload["PERF-005\nUpload 100 MB"]
    upload --> download["PERF-006\nDownload 100 MB"]
    download --> big["PERF-007\nФайл 1 GB"]
    big --> parallel["PERF-008\n4-8 клиентов"]
    parallel --> limits["PERF-009\nЛимиты скорости"]
    limits --> ftps["PERF-010\nFTPS overhead"]
    ftps --> longrun["PERF-011\n1-2 часа работы"]
    longrun --> stress["PERF-012\nЛимит подключений"]
    stress --> report["Отчет\nрезультат, статус, замечания"]
```

## Целевые временные ориентиры

```mermaid
xychart-beta
    title "Target time limits"
    x-axis ["PERF-001 GUI start", "PERF-002 server start", "PERF-003 /24 scan"]
    y-axis "Seconds" 0 --> 10
    bar [3, 1, 10]
```

## Матрица transfer-тестов

```mermaid
flowchart TB
    transfer["Transfer performance"]
    transfer --> small["PERF-004\n100 x 64 KB\nfiles/s, latency"]
    transfer --> upload["PERF-005\nUpload 100 MB\nMB/s, CPU, memory"]
    transfer --> download["PERF-006\nDownload 100 MB\nMB/s, checksum"]
    transfer --> big["PERF-007\nUpload/download 1 GB\nmemory stability"]
    transfer --> parallel["PERF-008\n4-8 clients\ntotal throughput"]
    transfer --> ftps["PERF-010\nFTP vs FTPS\nspeed and CPU delta"]
```

## Нагрузка и длительность

```mermaid
quadrantChart
    title Load and duration profile
    x-axis Low client pressure --> High client pressure
    y-axis Short run --> Long run
    quadrant-1 Long stress
    quadrant-2 Long baseline
    quadrant-3 Fast checks
    quadrant-4 Burst load
    PERF-001: [0.10, 0.10]
    PERF-002: [0.15, 0.12]
    PERF-003: [0.25, 0.20]
    PERF-004: [0.35, 0.25]
    PERF-005: [0.45, 0.30]
    PERF-006: [0.45, 0.32]
    PERF-007: [0.55, 0.48]
    PERF-008: [0.82, 0.45]
    PERF-011: [0.50, 0.90]
    PERF-012: [0.92, 0.60]
```

## Что вносить после реального прогона

После замеров добавляйте фактические значения в таблицу результатов и обновляйте графики:

- для startup/scanner: секунды;
- для upload/download: `MB/s`;
- для parallel clients: суммарный `MB/s` и число ошибок;
- для long run: пиковая память и количество зависших сессий;
- для FTPS: процентное отличие от FTP.
