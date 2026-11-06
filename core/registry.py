"""Работа с реестром с автоматическим резервированием исходных значений."""
import winreg

from . import state

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE
DWORD = winreg.REG_DWORD
SZ = winreg.REG_SZ

_HIVE_NAMES = {HKCU: "HKCU", HKLM: "HKLM"}
_HIVES = {v: k for k, v in _HIVE_NAMES.items()}
_FLAGS = winreg.KEY_WOW64_64KEY


def _key_id(hive, path, name):
    return f"{_HIVE_NAMES[hive]}\\{path}::{name}"


def get(hive, path, name):
    """Возвращает значение или None, если параметра нет."""
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | _FLAGS) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def get_with_type(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | _FLAGS) as key:
            return winreg.QueryValueEx(key, name)
    except OSError:
        return None, None


def _raw_set(hive, path, name, kind, value):
    with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE | _FLAGS) as key:
        if kind == DWORD:
            value = int(value) & 0xFFFFFFFF
        elif kind in (SZ, winreg.REG_EXPAND_SZ):
            value = str(value)
        winreg.SetValueEx(key, name, 0, kind, value)


def _raw_delete(hive, path, name):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE | _FLAGS) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def backup(hive, path, name):
    """Запоминает текущее значение перед первым изменением."""
    value, kind = get_with_type(hive, path, name)
    if isinstance(value, bytes):
        value = value.hex()
        kind = -kind  # пометка «бинарные данные в hex»
    state.remember("registry", _key_id(hive, path, name), {"kind": kind, "value": value})


def set(hive, path, name, kind, value):
    backup(hive, path, name)
    _raw_set(hive, path, name, kind, value)


def delete(hive, path, name):
    backup(hive, path, name)
    _raw_delete(hive, path, name)


def restore(hive, path, name, fallback_kind=None, fallback=None):
    """
    Возвращает исходное значение из резервной копии.
    Если копии нет — применяет fallback (None = удалить параметр).
    Возвращает фактически восстановленное значение (для журнала).
    """
    kid = _key_id(hive, path, name)
    saved = state.lookup("registry", kid)
    if saved is not None:
        kind, value = saved["kind"], saved["value"]
        if value is None:
            _raw_delete(hive, path, name)
        elif kind is not None and kind < 0:
            _raw_set(hive, path, name, -kind, bytes.fromhex(value))
        else:
            _raw_set(hive, path, name, kind, value)
        state.forget("registry", kid)
        return value
    if fallback is None:
        _raw_delete(hive, path, name)
    else:
        _raw_set(hive, path, name, fallback_kind, fallback)
    return fallback


def delete_tree(hive, path):
    """Рекурсивно удаляет ключ реестра."""
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS | _FLAGS) as key:
            while True:
                try:
                    sub = winreg.EnumKey(key, 0)
                except OSError:
                    break
                delete_tree(hive, path + "\\" + sub)
        winreg.DeleteKeyEx(hive, path, _FLAGS, 0)
    except OSError:
        pass


def key_exists(hive, path):
    try:
        winreg.CloseKey(winreg.OpenKey(hive, path, 0, winreg.KEY_READ | _FLAGS))
        return True
    except OSError:
        return False


def subkeys(hive, path):
    result = []
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | _FLAGS) as key:
            i = 0
            while True:
                try:
                    result.append(winreg.EnumKey(key, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return result

