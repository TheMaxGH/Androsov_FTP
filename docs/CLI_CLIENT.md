# CLI FTP-клиент

CLI-клиент нужен для автоматизации, SSH-сессий и скриптов.

## Команды

```powershell
python main.py --ftp list --host 127.0.0.1 --port 2121 --user user --password password
python main.py --ftp upload --host 127.0.0.1 --local "D:\file.txt" --remote file.txt
python main.py --ftp download --host 127.0.0.1 --remote file.txt --local "D:\Downloads\file.txt"
```

## Профили из JSON-конфига

```powershell
python main.py --ftp list --config vallhala.servers.json --profile local
python main.py --ftp upload --config vallhala.servers.json --profile local --local "D:\file.txt" --remote file.txt
```

Профили берутся из секции `client_profiles`.

## FTPS

```powershell
python main.py --ftp list --host 127.0.0.1 --port 2121 --protocol ftps --user user --password password
```

FTPS-клиент использует `ftplib.FTP_TLS` и переключает data-channel в защищенный режим через `PROT P`.
