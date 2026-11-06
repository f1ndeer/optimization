"""
Системные функции: мониторинг ОЗУ и диска, управление обоями (OLED Black с возвратом),
управление службами Windows, очистка кэша/мусора и запуск системных инструментов.
"""
import ctypes
from ctypes import wintypes
import os
import platform
import shutil
import struct
import subprocess
import winreg

from . import registry as reg
from . import state
from .registry import HKCU, HKLM, DWORD, SZ
from .utils import BACKUP_DIR, LOGS_DIR, run_hidden, run_powershell


# ==================== СТАТИСТИКА ПАМЯТИ, ДИСКА И СИСТЕМЫ ====================

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_ram_info():
    """Возвращает словарь с информацией об ОЗУ (в ГБ, МБ и процентах)."""
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_gb = stat.ullTotalPhys / (1024 ** 3)
    avail_gb = stat.ullAvailPhys / (1024 ** 3)
    used_gb = total_gb - avail_gb
    return {
        "load_percent": int(stat.dwMemoryLoad),
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "avail_gb": round(avail_gb, 1),
        "avail_mb": round(stat.ullAvailPhys / (1024 ** 2), 1),
    }


def get_disk_free_gb(drive=None):
    drive = drive or os.environ.get("SystemDrive", "C:") + "\\"
    try:
        usage = shutil.disk_usage(drive)
        return round(usage.free / (1024 ** 3), 1), round(usage.total / (1024 ** 3), 1)
    except Exception:
        return 0.0, 0.0


def get_system_summary():
    """Краткая сводка об ОС и процессоре для информационной панели."""
    cpu_name = reg.get(HKLM, r"HARDWARE\Description\System\CentralProcessor\0", "ProcessorNameString")
    if not cpu_name:
        cpu_name = platform.processor() or "Процессор x64"
    os_name = reg.get(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName") or "Windows"
    display_ver = reg.get(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion") or ""
    build = reg.get(HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuild") or ""
    try:
        if build and int(build) >= 22000 and "Windows 10" in os_name:
            os_name = os_name.replace("Windows 10", "Windows 11")
    except Exception:
        pass
    os_full = f"{os_name} {display_ver} (Build {build})".strip()
    return {
        "cpu": cpu_name.strip(),
        "os": os_full,
    }


# ==================== ЧЁРНЫЕ ОБОИ (OLED BLACK) С ВОЗВРАТОМ ====================

SPI_GETDESKWALLPAPER = 0x0073
SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02
COLOR_DESKTOP = 1

_BLACK_BMP_PATH = os.path.join(BACKUP_DIR, "oled_black_wallpaper.bmp")


def _ensure_black_bmp():
    """Создаёт минимальный 16x16 чисто чёрный BMP-файл для мгновенной установки обоев."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.isfile(_BLACK_BMP_PATH):
        return _BLACK_BMP_PATH
    width, height = 16, 16
    row_bytes = width * 3  # 48 байт (кратно 4)
    pixel_data_size = row_bytes * height
    file_size = 14 + 40 + pixel_data_size
    bmp_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        40, width, height, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0
    )
    pixels = b"\x00" * pixel_data_size
    with open(_BLACK_BMP_PATH, "wb") as f:
        f.write(bmp_header + dib_header + pixels)
    return _BLACK_BMP_PATH


def _get_current_wallpaper_path():
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 512, buf, 0)
    path = buf.value.strip()
    if not path:
        path = reg.get(HKCU, r"Control Panel\Desktop", "Wallpaper") or ""
    return path


def _set_desktop_rgb(r, g, b):
    try:
        color_ref = (int(r) & 0xFF) | ((int(g) & 0xFF) << 8) | ((int(b) & 0xFF) << 16)
        elems = (ctypes.c_int * 1)(COLOR_DESKTOP)
        colors = (wintypes.DWORD * 1)(color_ref)
        ctypes.windll.user32.SetSysColors(1, elems, colors)
    except Exception:
        pass


def is_black_wallpaper():
    """Проверяет, активен ли сейчас режим чёрных обоев OLED Black."""
    wp_state = state.get("wallpaper")
    if isinstance(wp_state, dict) and wp_state.get("active"):
        return True
    cur = _get_current_wallpaper_path()
    if cur and os.path.normcase(os.path.abspath(cur)) == os.path.normcase(os.path.abspath(_BLACK_BMP_PATH)):
        return True
    return False


def has_saved_wallpaper():
    """Есть ли сохранённая резервная копия пользовательских обоев."""
    wp_state = state.get("wallpaper")
    return isinstance(wp_state, dict) and bool(wp_state.get("saved"))


def set_black_wallpaper():
    """
    Переключает рабочий стол на чисто чёрный цвет (#000000).
    Перед этим сохраняет оригинальный файл обоев, стиль и цвет фона в backup/state.json
    (копирует и сам файл картинки в backup/, чтобы он не потерялся).
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        current_path = _get_current_wallpaper_path()
        black_bmp = _ensure_black_bmp()

        wp_state = state.get("wallpaper")
        is_already_black = (
            current_path
            and os.path.normcase(os.path.abspath(current_path)) == os.path.normcase(os.path.abspath(black_bmp))
        )

        # Сохраняем исходные обои только если сейчас не включён наш же чёрный фон
        if not is_already_black and not (isinstance(wp_state, dict) and wp_state.get("saved")):
            copied_file = ""
            if current_path and os.path.isfile(current_path):
                ext = os.path.splitext(current_path)[1] or ".jpg"
                copied_file = os.path.join(BACKUP_DIR, "original_wallpaper" + ext)
                try:
                    shutil.copy2(current_path, copied_file)
                except Exception:
                    copied_file = ""

            wp_state = {
                "saved": True,
                "active": True,
                "original_path": current_path,
                "backup_file": copied_file,
                "style": reg.get(HKCU, r"Control Panel\Desktop", "WallpaperStyle") or "10",
                "tile": reg.get(HKCU, r"Control Panel\Desktop", "TileWallpaper") or "0",
                "background": reg.get(HKCU, r"Control Panel\Colors", "Background") or "0 0 0",
            }
            state.set_value("wallpaper", wp_state)
        elif isinstance(wp_state, dict):
            wp_state["active"] = True
            state.set_value("wallpaper", wp_state)

        # Записываем чёрный цвет фона и применяем чёрный BMP через WinAPI
        reg._raw_set(HKCU, r"Control Panel\Colors", "Background", SZ, "0 0 0")
        reg._raw_set(HKCU, r"Control Panel\Desktop", "Wallpaper", SZ, black_bmp)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, black_bmp, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
        )
        _set_desktop_rgb(0, 0, 0)
        return True, "Установлены чисто чёрные обои (OLED Black #000000). Прежние обои сохранены в резервную копию."
    except Exception as e:
        return False, f"Не удалось установить чёрные обои: {e}"


def restore_wallpaper():
    """Восстанавливает прежние обои пользователя из резервной копии в backup/state.json."""
    try:
        wp_state = state.get("wallpaper")
        if not isinstance(wp_state, dict) or not wp_state.get("saved"):
            # Пробуем найти TranscodedWallpaper Windows, если бэкапа не было
            transcoded = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Themes\TranscodedWallpaper")
            if os.path.isfile(transcoded):
                ctypes.windll.user32.SystemParametersInfoW(
                    SPI_SETDESKWALLPAPER, 0, transcoded, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
                )
                return True, "Восстановлены обои из кэша темы Windows (TranscodedWallpaper)."
            return False, "Резервная копия прежних обоев не найдена (обои не менялись через программу)."

        orig_path = wp_state.get("original_path") or ""
        backup_file = wp_state.get("backup_file") or ""
        style = wp_state.get("style") or "10"
        tile = wp_state.get("tile") or "0"
        bg = wp_state.get("background") or "0 0 0"

        target_path = orig_path if (orig_path and os.path.isfile(orig_path)) else backup_file

        reg._raw_set(HKCU, r"Control Panel\Desktop", "WallpaperStyle", SZ, str(style))
        reg._raw_set(HKCU, r"Control Panel\Desktop", "TileWallpaper", SZ, str(tile))
        reg._raw_set(HKCU, r"Control Panel\Colors", "Background", SZ, str(bg))

        parts = str(bg).split()
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            _set_desktop_rgb(int(parts[0]), int(parts[1]), int(parts[2]))

        if target_path and os.path.isfile(target_path):
            reg._raw_set(HKCU, r"Control Panel\Desktop", "Wallpaper", SZ, target_path)
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, target_path, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
            )
            msg = f"Прежние обои успешно возвращены ({os.path.basename(orig_path or target_path)})."
        else:
            reg._raw_set(HKCU, r"Control Panel\Desktop", "Wallpaper", SZ, "")
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, "", SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
            )
            msg = "Восстановлен исходный цвет фона рабочего стола."

        wp_state["active"] = False
        state.set_value("wallpaper", wp_state)
        return True, msg
    except Exception as e:
        return False, f"Ошибка восстановления обоев: {e}"


# ==================== УПРАВЛЕНИЕ СЛУЖБАМИ WINDOWS ====================

def get_service_status(service_name):
    """Возвращает 'RUNNING', 'STOPPED' или 'UNKNOWN'."""
    res = run_hidden(["sc", "query", service_name], timeout=15)
    out = res.stdout.upper()
    if "RUNNING" in out:
        return "RUNNING"
    if "STOPPED" in out:
        return "STOPPED"
    return "UNKNOWN"


def manage_service(service_name, action):
    """
    action: 'stop' или 'start'.
    При остановке запоминает службу в state.json (stopped_services),
    чтобы при нажатии «Восстановить» включить её обратно даже после перезапуска программы.
    """
    status_before = get_service_status(service_name)
    if status_before == "UNKNOWN":
        return False, f"Служба {service_name} отсутствует в этой редакции Windows — пропущена"

    stopped_list = state.get("stopped_services")

    if action == "stop":
        if status_before == "STOPPED":
            return True, f"Служба {service_name} уже остановлена"
        res = run_hidden(["net", "stop", service_name, "/y"], timeout=60)
        if res.returncode == 0 or get_service_status(service_name) == "STOPPED":
            if service_name not in stopped_list:
                stopped_list.append(service_name)
                state.save()
            return True, f"Остановлена служба: {service_name}"
        return False, f"Не удалось остановить {service_name} (защищена системой)"

    elif action == "start":
        if status_before == "RUNNING":
            if service_name in stopped_list:
                stopped_list.remove(service_name)
                state.save()
            return True, f"Служба {service_name} уже работает"
        res = run_hidden(["net", "start", service_name], timeout=60)
        if res.returncode == 0 or get_service_status(service_name) == "RUNNING":
            if service_name in stopped_list:
                stopped_list.remove(service_name)
                state.save()
            return True, f"Запущена служба: {service_name}"
        return False, f"Не удалось запустить {service_name} (отключена или запускается по событию)"

    return False, "Неизвестное действие"


# ==================== ОЧИСТКА МУСОРА, КЭША И ОЗУ ====================

def _env(name, default=""):
    return os.environ.get(name, default)


def _clean_folders(folders, file_pred=None):
    """Удаляет содержимое папок. Возвращает (количество_объектов, освобождено_МБ)."""
    deleted = 0
    freed_bytes = 0
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            entries = os.listdir(folder)
        except Exception:
            continue
        for entry in entries:
            if file_pred and not file_pred(entry):
                continue
            full_path = os.path.join(folder, entry)
            try:
                if os.path.isfile(full_path) or os.path.islink(full_path):
                    size = os.path.getsize(full_path)
                    os.unlink(full_path)
                    deleted += 1
                    freed_bytes += size
                elif os.path.isdir(full_path) and file_pred is None:
                    dir_size = 0
                    for root, _, files in os.walk(full_path):
                        for f in files:
                            try:
                                dir_size += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass
                    shutil.rmtree(full_path)
                    deleted += 1
                    freed_bytes += dir_size
            except Exception:
                pass
    return deleted, round(freed_bytes / (1024 * 1024), 2)


def clean_temp_files():
    """Очищает папки Temp пользователя и системы (Prefetch не трогается)."""
    return _clean_folders([
        _env("TEMP"),
        os.path.join(_env("SystemRoot", r"C:\Windows"), "Temp"),
    ])


def clean_shader_cache():
    """Очищает кэш шейдеров DirectX / NVIDIA / AMD / Intel."""
    local = _env("LOCALAPPDATA")
    appdata = _env("APPDATA")
    return _clean_folders([
        os.path.join(local, "D3DSCache"),
        os.path.join(local, "NVIDIA", "DXCache"),
        os.path.join(local, "NVIDIA", "GLCache"),
        os.path.join(appdata, "NVIDIA", "ComputeCache"),
        os.path.join(local, "AMD", "DxCache"),
        os.path.join(local, "AMD", "DxcCache"),
        os.path.join(local, "AMD", "VkCache"),
        os.path.join(local, "Intel", "ShaderCache"),
    ])


def clean_windows_update_cache():
    """Удаляет скачанные пакеты обновлений из SoftwareDistribution\\Download."""
    run_hidden(["net", "stop", "wuauserv", "/y"], timeout=45)
    run_hidden(["net", "stop", "bits", "/y"], timeout=45)
    result = _clean_folders([os.path.join(_env("SystemRoot", r"C:\Windows"), "SoftwareDistribution", "Download")])
    run_hidden(["net", "start", "bits"], timeout=45)
    run_hidden(["net", "start", "wuauserv"], timeout=45)
    return result


def clean_crash_dumps():
    """Удаляет дампы памяти и отчёты об ошибках Windows Error Reporting (WER)."""
    root = _env("SystemRoot", r"C:\Windows")
    pd = _env("ProgramData", r"C:\ProgramData")
    local = _env("LOCALAPPDATA")
    return _clean_folders([
        os.path.join(root, "Minidump"),
        os.path.join(root, "LiveKernelReports"),
        os.path.join(local, "CrashDumps"),
        os.path.join(pd, "Microsoft", "Windows", "WER", "ReportArchive"),
        os.path.join(pd, "Microsoft", "Windows", "WER", "ReportQueue"),
        os.path.join(local, "Microsoft", "Windows", "WER", "ReportArchive"),
        os.path.join(local, "Microsoft", "Windows", "WER", "ReportQueue"),
    ])


def clean_browser_cache():
    """Очищает ТОЛЬКО файловый кэш браузеров (пароли, куки и история НЕ затрагиваются)."""
    local = _env("LOCALAPPDATA")
    folders = [
        os.path.join(local, r"Google\Chrome\User Data\Default\Cache\Cache_Data"),
        os.path.join(local, r"Google\Chrome\User Data\Default\Code Cache\js"),
        os.path.join(local, r"Google\Chrome\User Data\Default\GPUCache"),
        os.path.join(local, r"Microsoft\Edge\User Data\Default\Cache\Cache_Data"),
        os.path.join(local, r"Microsoft\Edge\User Data\Default\Code Cache\js"),
        os.path.join(local, r"Microsoft\Edge\User Data\Default\GPUCache"),
        os.path.join(local, r"BraveSoftware\Brave-Browser\User Data\Default\Cache\Cache_Data"),
        os.path.join(local, r"Yandex\YandexBrowser\User Data\Default\Cache\Cache_Data"),
        os.path.join(local, r"Opera Software\Opera Stable\Cache\Cache_Data"),
        os.path.join(local, r"Opera Software\Opera GX Stable\Cache\Cache_Data"),
    ]
    return _clean_folders(folders)


def clean_logs_and_thumbs():
    """Очищает системные лог-файлы CBS/DISM и повреждённый кэш эскизов Проводника (thumbcache)."""
    root = _env("SystemRoot", r"C:\Windows")
    local = _env("LOCALAPPDATA")
    c1, m1 = _clean_folders([
        os.path.join(root, "Logs", "CBS"),
        os.path.join(root, "Logs", "DISM"),
        os.path.join(root, "Logs", "MoSetup"),
    ])
    explorer_dir = os.path.join(local, "Microsoft", "Windows", "Explorer")
    c2, m2 = _clean_folders([explorer_dir], file_pred=lambda name: name.lower().startswith("thumbcache_"))
    return c1 + c2, round(m1 + m2, 2)


def empty_recycle_bin():
    """Очищает корзину на всех дисках без лишних окон."""
    SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI, SHERB_NOSOUND = 0x1, 0x2, 0x4
    try:
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        )
        return res == 0 or (res & 0xFFFFFFFF) == 0x8000FFFF
    except Exception:
        return False


def flush_dns_cache():
    """Очищает кэш резолвера DNS."""
    return run_hidden(["ipconfig", "/flushdns"], timeout=20).returncode == 0


def reset_network_stack():
    """Полный сброс Winsock, TCP/IP и прокси-настроек."""
    r1 = run_hidden(["netsh", "winsock", "reset"], timeout=60)
    r2 = run_hidden(["netsh", "int", "ip", "reset"], timeout=60)
    run_hidden(["netsh", "winhttp", "reset", "proxy"], timeout=30)
    return r1.returncode == 0, r2.returncode == 0


def create_restore_point(description="WinOptimizer Pro Backup"):
    """Создаёт точку восстановления системы Windows."""
    ps = (
        "$ErrorActionPreference='Stop';"
        "try { Enable-ComputerRestore -Drive \"$env:SystemDrive\\\" } catch {};"
        "New-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' "
        "-Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null;"
        f"Checkpoint-Computer -Description '{description}' -RestorePointType MODIFY_SETTINGS;"
        "Write-Output 'OK'"
    )
    res = run_powershell(ps, timeout=300)
    if res.returncode == 0 and "OK" in res.stdout:
        return True, "Точка восстановления системы успешно создана."
    err = (res.stderr or res.stdout).strip().splitlines()
    return False, "Не удалось создать точку восстановления: " + (err[0] if err else "служба восстановления отключена")


def optimize_ram_workingset():
    """Выгружает неактивные страницы памяти процессов (EmptyWorkingSet)."""
    before_mb = get_ram_info()["avail_mb"]

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    arr = (wintypes.DWORD * 4096)()
    cb = ctypes.sizeof(arr)
    bytes_returned = wintypes.DWORD()

    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]

    optimized_count = 0
    if psapi.EnumProcesses(ctypes.byref(arr), cb, ctypes.byref(bytes_returned)):
        count = int(bytes_returned.value / ctypes.sizeof(wintypes.DWORD))
        for i in range(count):
            pid = arr[i]
            if pid == 0:
                continue
            h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
            if h_process:
                try:
                    if psapi.EmptyWorkingSet(h_process):
                        optimized_count += 1
                except Exception:
                    pass
                finally:
                    kernel32.CloseHandle(h_process)

    after_mb = get_ram_info()["avail_mb"]
    freed_mb = max(0.0, round(after_mb - before_mb, 1))
    return optimized_count, freed_mb


def restart_explorer():
    """Перезапускает Проводник Windows (explorer.exe), чтобы мгновенно применить твики интерфейса."""
    try:
        run_hidden(["taskkill", "/f", "/im", "explorer.exe"], timeout=15)
        subprocess.Popen(["explorer.exe"])
        return True
    except Exception:
        return False


def generate_battery_report():
    """Генерирует HTML-отчёт о состоянии аккумулятора ноутбука и открывает его."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    report_path = os.path.join(LOGS_DIR, "battery_report.html")
    res = run_hidden(["powercfg", "/batteryreport", "/output", report_path], timeout=30)
    if res.returncode == 0 and os.path.isfile(report_path):
        open_system_tool(report_path)
        return True, f"Отчёт о батарее сохранён и открыт: {report_path}"
    return False, "Аккумулятор не обнаружен (доступно только на ноутбуках/ИБП)."


def open_hosts_file():
    """Открывает системный файл hosts в Блокноте от имени администратора."""
    hosts_path = os.path.join(_env("SystemRoot", r"C:\Windows"), r"System32\drivers\etc\hosts")
    try:
        subprocess.Popen(["notepad.exe", hosts_path])
        return True
    except Exception:
        return False


def run_sfc_scan():
    """Запускает проверку целостности системных файлов sfc /scannow в отдельном окне консоли."""
    try:
        subprocess.Popen(["cmd.exe", "/k", "title Проверка целостности Windows (SFC) & sfc /scannow"])
        return True
    except Exception:
        return False


def run_dism_restore():
    """Запускает восстановление образа системы DISM в отдельном окне консоли."""
    try:
        subprocess.Popen([
            "cmd.exe", "/k",
            "title Восстановление образа Windows (DISM) & DISM.exe /Online /Cleanup-image /Restorehealth"
        ])
        return True
    except Exception:
        return False


def open_system_tool(cmd):
    """Открывает встроенную системную программу, оснастку (.msc/.cpl), раздел Параметров (ms-settings:) или папку."""
    if not cmd:
        return False
    try:
        if cmd == "special:hosts":
            return open_hosts_file()
        if cmd == "special:sfc":
            return run_sfc_scan()
        if cmd == "special:dism":
            return run_dism_restore()
        if cmd == "special:battery":
            ok, _ = generate_battery_report()
            return ok
        if cmd.startswith("shell:") or cmd.startswith("ms-settings:") or cmd.endswith(":"):
            os.startfile(cmd)
            return True
        try:
            os.startfile(cmd)
            return True
        except Exception:
            subprocess.Popen(cmd, shell=True)
            return True
    except Exception:
        return False
