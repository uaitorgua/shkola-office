"""Перевірка оновлень: https://uait.org.ua/ofis/version.json (портативний EXE: новий файл підміняє поточний, програма перезапускається).

Якщо на сайті версія новіша — програма вимагає оновитись (ui/update_check.py).
Встановлення з Microsoft Store (MSIX у WindowsApps) оновлюється через Store, інше — новим EXE з сайту.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import urllib.request

from . import __version__

log = logging.getLogger(__name__)
BASE = os.environ.get("OFIS_UPDATE_BASE", "https://uait.org.ua/ofis/")   # змінна — лише для локальних тестів
VERSION_URL = BASE + "version.json"
STORE_URL = ""


def parse(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse(remote) > parse(local)


def is_store_install() -> bool:
    return "\\windowsapps\\" in sys.executable.lower()


def _get(url: str, timeout: float, limit: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "OfisShkola/" + __version__})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 – лише https uait.org.ua
        return r.read(limit)


def check(timeout: float = 6) -> dict | None:
    """Повертає version.json, якщо є новіша версія; інакше (або без мережі) None."""
    if is_store_install():          # Microsoft Store оновлює сам; сайт може випереджати сертифікацію
        return None
    try:
        d = json.loads(_get(VERSION_URL, timeout, 100_000).decode("utf-8"))
        setup = str(d.get("setup", ""))
        if not re.fullmatch(r"OfisShkola-\d+\.\d+\.\d+(\.\d+)?\.exe", setup):
            return None
        return d if is_newer(d.get("version", "0")) else None
    except Exception as e:  # noqa: BLE001
        log.info("Оновлення: сайт недоступний (%s)", e)
        return None


def download(info: dict, progress=None) -> str:
    """Завантажує новий EXE у %TEMP% і звіряє md5. Повертає шлях."""
    name = info["setup"]
    path = os.path.join(tempfile.gettempdir(), name)
    req = urllib.request.Request(BASE + name, headers={"User-Agent": "OfisShkola/" + __version__})
    md5 = hashlib.md5()
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as fh:  # noqa: S310
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            fh.write(chunk)
            md5.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    want = (info.get("md5") or {}).get(name)
    if want and md5.hexdigest() != want:
        os.remove(path)
        raise IOError("Завантажений файл пошкоджено (md5 не збігається)")
    return path


def install_portable(new_exe: str) -> None:
    """Підміняє запущений EXE новим після виходу програми й запускає оновлену версію."""
    import subprocess
    cur = sys.executable
    bat = os.path.join(tempfile.gettempdir(), "ofis_shkola_update.bat")
    with open(bat, "w", encoding="utf-8") as fh:
        fh.write(f'''@echo off
chcp 65001 >nul
:w
timeout /t 1 /nobreak >nul
tasklist /fi "PID eq {os.getpid()}" | find "{os.getpid()}" >nul && goto w
move /y "{new_exe}" "{cur}" >nul || (start "" "{BASE}" & exit /b 1)
start "" "{cur}"
del "%~f0"
''')
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000, close_fds=True)
