"""
Постоянное хранилище состояния (backup/state.json).

Здесь сохраняются ИСХОДНЫЕ значения всего, что программа меняет:
параметры реестра, типы запуска служб, обои, остановленные службы.
Благодаря этому откат возвращает именно ваши настройки, а не «средние по больнице»,
и работает даже после перезапуска программы или перезагрузки ПК.
"""
import json
import os
import threading

from .utils import BACKUP_DIR

STATE_PATH = os.path.join(BACKUP_DIR, "state.json")
_lock = threading.Lock()
_state = None

_DEFAULT = {
    "registry": {},        # "HIVE\\path::name" -> {"kind": int, "value": ... | None}
    "service_start": {},   # имя службы -> исходный тип запуска (auto/delayed-auto/demand/disabled)
    "stopped_services": [],
    "wallpaper": None,     # сведения об исходных обоях
    "commands": {},        # исходные значения для твиков-команд (powercfg и т.п.)
}


def _load():
    global _state
    if _state is None:
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                _state = json.load(f)
        except Exception:
            _state = {}
        for k, v in _DEFAULT.items():
            _state.setdefault(k, json.loads(json.dumps(v)))
    return _state


def save():
    with _lock:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_load(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_PATH)


def get(section):
    return _load()[section]


def set_value(section, value):
    _load()[section] = value
    save()


def remember(section, key, value):
    """Запоминает исходное значение, только если оно ещё не сохранено (первое изменение)."""
    data = _load()[section]
    if key not in data:
        data[key] = value
        save()
        return True
    return False


def forget(section, key):
    data = _load()[section]
    if key in data:
        del data[key]
        save()


def lookup(section, key, default=None):
    return _load()[section].get(key, default)

