"""Общие утилиты: пути, конфиг, права администратора, скрытый запуск команд."""
import ctypes
import json
import os
import subprocess
import sys

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
BACKUP_DIR = os.path.join(APP_DIR, "backup")
LOGS_DIR = os.path.join(APP_DIR, "logs")

CREATE_NO_WINDOW = 0x08000000


def _load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def load_config():
    """Собирает конфиг из config.json (UI/настройки) и файлов в data/."""
    cfg = _load_json(os.path.join(APP_DIR, "config.json"), {}) or {}
    for name in ("services", "tweaks", "articles", "tools"):
        loaded = _load_json(os.path.join(DATA_DIR, f"{name}.json"), None)
        if loaded:
            cfg[name] = loaded
        else:
            cfg.setdefault(name, [])
    return cfg


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


def run_hidden(cmd, timeout=120):
    """Выполняет команду без окна консоли. Возвращает CompletedProcess (никогда не бросает исключений)."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore",
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 1, "", "timeout")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def run_powershell(script, timeout=300):
    return run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)

