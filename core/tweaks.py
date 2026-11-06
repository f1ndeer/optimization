"""
Все твики системы.

REG_TWEAKS — твики, которые сводятся к записи в реестр.
Формат строки: (куст, путь, параметр, тип, оптимальное_значение, значение_по_умолчанию)
«По умолчанию» используется ТОЛЬКО если нет резервной копии исходного значения
(None = удалить параметр, Windows вернётся к встроенному стандарту).

SPECIAL_TWEAKS — твики, которым нужна логика (powercfg, вычисления, несколько интерфейсов).
"""
import re

from . import registry as reg
from . import state
from .registry import HKCU, HKLM, DWORD, SZ
from .utils import run_hidden
from .system import get_ram_info

_MM = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
_MM_GAMES = _MM + r"\Tasks\Games"
_CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_TCP = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
_FS = r"SYSTEM\CurrentControlSet\Control\FileSystem"
_CAM = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"

REG_TWEAKS = {
    # ======================= ИГРЫ И FPS =======================
    "game_dvr": [
        (HKCU, r"System\GameConfigStore", "GameDVR_Enabled", DWORD, 0, 1),
        (HKCU, r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", DWORD, 0, 1),
        (HKCU, r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", DWORD, 0, None),
        (HKCU, r"Software\Microsoft\GameBar", "ShowStartupPanel", DWORD, 0, None),
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", DWORD, 0, None),
    ],
    "mmcss_gaming": [
        (HKLM, _MM, "SystemResponsiveness", DWORD, 0, 20),
        (HKLM, _MM_GAMES, "GPU Priority", DWORD, 8, 8),
        (HKLM, _MM_GAMES, "Priority", DWORD, 6, 2),
        (HKLM, _MM_GAMES, "Scheduling Category", SZ, "High", "Medium"),
        (HKLM, _MM_GAMES, "SFIO Priority", SZ, "High", "Normal"),
        (HKLM, _MM_GAMES, "Background Only", SZ, "False", "False"),
        (HKLM, _MM_GAMES, "Clock Rate", DWORD, 10000, 10000),
    ],
    "game_mode": [
        (HKCU, r"Software\Microsoft\GameBar", "AutoGameModeEnabled", DWORD, 1, None),
        (HKCU, r"Software\Microsoft\GameBar", "AllowAutoGameMode", DWORD, 1, None),
    ],
    "win32_priority": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", DWORD, 0x26, 2),
    ],
    "power_throttling": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", DWORD, 1, None),
    ],
    "windowed_opt": [
        (HKCU, r"Software\Microsoft\DirectX\UserGpuPreferences", "DirectXUserGlobalSettings", SZ, "SwapEffectUpgradeEnable=1;", None),
    ],
    "fullscreen_opt": [
        (HKCU, r"System\GameConfigStore", "GameDVR_FSEBehavior", DWORD, 2, None),
        (HKCU, r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", DWORD, 1, 0),
        (HKCU, r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", DWORD, 1, 0),
    ],
    "hags": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", DWORD, 2, None),
    ],
    "mpo_disable": [
        (HKLM, r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", DWORD, 5, None),
    ],
    "fth_disable": [
        (HKLM, r"SOFTWARE\Microsoft\FTH", "Enabled", DWORD, 0, 1),
    ],
    "mouse_accel": [
        (HKCU, r"Control Panel\Mouse", "MouseSpeed", SZ, "0", "1"),
        (HKCU, r"Control Panel\Mouse", "MouseThreshold1", SZ, "0", "6"),
        (HKCU, r"Control Panel\Mouse", "MouseThreshold2", SZ, "0", "10"),
    ],
    "keyboard_response": [
        (HKCU, r"Control Panel\Keyboard", "KeyboardDelay", SZ, "0", "1"),
        (HKCU, r"Control Panel\Keyboard", "KeyboardSpeed", SZ, "31", "31"),
    ],
    "sticky_keys": [
        (HKCU, r"Control Panel\Accessibility\StickyKeys", "Flags", SZ, "506", "510"),
        (HKCU, r"Control Panel\Accessibility\ToggleKeys", "Flags", SZ, "58", "62"),
        (HKCU, r"Control Panel\Accessibility\Keyboard Response", "Flags", SZ, "122", "126"),
    ],
    "global_timer_resolution": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", DWORD, 1, None),
    ],

    # ======================= СЕТЬ =======================
    "network_throttling": [
        (HKLM, _MM, "NetworkThrottlingIndex", DWORD, 0xFFFFFFFF, 10),
    ],
    "dns_priority": [
        (HKLM, r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", "LocalPriority", DWORD, 4, 499),
        (HKLM, r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", "HostsPriority", DWORD, 5, 500),
        (HKLM, r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", "DnsPriority", DWORD, 6, 2000),
        (HKLM, r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", "NetbtPriority", DWORD, 7, 2001),
    ],
    "delivery_optimization": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", DWORD, 0, None),
    ],
    "tcp_params": [
        (HKLM, _TCP, "DefaultTTL", DWORD, 64, None),
        (HKLM, _TCP, "TcpTimedWaitDelay", DWORD, 30, None),
        (HKLM, _TCP, "MaxUserPort", DWORD, 65534, None),
    ],
    "llmnr_disable": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", DWORD, 0, None),
    ],

    # ======================= СИСТЕМА =======================
    "startup_delay": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", "StartupDelayInMSec", DWORD, 0, None),
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", "WaitForIdleState", DWORD, 0, None),
    ],
    "ntfs_last_access": [
        (HKLM, _FS, "NtfsDisableLastAccessUpdate", DWORD, 0x80000001, 0x80000002),
    ],
    "ntfs_8dot3": [
        (HKLM, _FS, "NtfsDisable8dot3NameCreation", DWORD, 1, 2),
    ],
    "fast_shutdown": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", SZ, "2000", "5000"),
    ],
    "hung_apps": [
        (HKCU, r"Control Panel\Desktop", "HungAppTimeout", SZ, "2000", None),
        (HKCU, r"Control Panel\Desktop", "WaitToKillAppTimeout", SZ, "5000", None),
    ],
    "paging_executive": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "DisablePagingExecutive", DWORD, 1, 0),
    ],
    "update_no_reboot": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoRebootWithLoggedOnUsers", DWORD, 1, None),
    ],
    "auto_maintenance": [
        (HKLM, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance", "MaintenanceDisabled", DWORD, 1, None),
    ],
    "fast_startup": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", DWORD, 0, 1),
    ],
    "error_reporting": [
        (HKLM, r"SOFTWARE\Microsoft\Windows\Windows Error Reporting", "Disabled", DWORD, 1, None),
    ],
    "remote_assistance": [
        (HKLM, r"SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", DWORD, 0, 1),
    ],

    # ======================= ПРИВАТНОСТЬ И ФОН =======================
    "telemetry": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", DWORD, 0, None),
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "DoNotShowFeedbackNotifications", DWORD, 1, None),
        (HKCU, r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", DWORD, 0, None),
    ],
    "advertising_id": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", DWORD, 0, 1),
    ],
    "tailored_experiences": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Privacy", "TailoredExperiencesWithDiagnosticDataEnabled", DWORD, 0, 1),
    ],
    "activity_history": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", DWORD, 0, None),
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", DWORD, 0, None),
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", DWORD, 0, None),
    ],
    "suggestions_ads": [
        (HKCU, _CDM, "SystemPaneSuggestionsEnabled", DWORD, 0, 1),
        (HKCU, _CDM, "SilentInstalledAppsEnabled", DWORD, 0, 1),
        (HKCU, _CDM, "SoftLandingEnabled", DWORD, 0, 1),
        (HKCU, _CDM, "RotatingLockScreenOverlayEnabled", DWORD, 0, 1),
        (HKCU, _CDM, "SubscribedContent-338387Enabled", DWORD, 0, 1),
        (HKCU, _CDM, "SubscribedContent-338388Enabled", DWORD, 0, 1),
        (HKCU, _CDM, "SubscribedContent-338389Enabled", DWORD, 0, 1),
        (HKCU, _CDM, "SubscribedContent-353694Enabled", DWORD, 0, 1),
    ],
    "start_tracking": [
        (HKCU, _ADV, "Start_TrackProgs", DWORD, 0, None),
    ],
    "input_personalization": [
        (HKCU, r"Software\Microsoft\InputPersonalization", "RestrictImplicitInkCollection", DWORD, 1, None),
        (HKCU, r"Software\Microsoft\InputPersonalization", "RestrictImplicitTextCollection", DWORD, 1, None),
        (HKCU, r"Software\Microsoft\Personalization\Settings", "AcceptedPrivacyPolicy", DWORD, 0, None),
    ],
    "bing_search": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", DWORD, 0, None),
        (HKCU, r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", DWORD, 1, None),
    ],
    "cortana": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", DWORD, 0, None),
    ],
    "copilot": [
        (HKCU, r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", DWORD, 1, None),
        (HKCU, _ADV, "ShowCopilotButton", DWORD, 0, None),
    ],
    "widgets": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", DWORD, 0, None),
    ],
    "edge_background": [
        (HKLM, r"SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", DWORD, 0, None),
        (HKLM, r"SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", DWORD, 0, None),
    ],
    "background_apps": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", DWORD, 1, None),
    ],
    "location": [
        (HKLM, _CAM + r"\location", "Value", SZ, "Deny", "Allow"),
    ],

    # ======================= ИНТЕРФЕЙС =======================
    "menu_delay": [
        (HKCU, r"Control Panel\Desktop", "MenuShowDelay", SZ, "0", "400"),
    ],
    "mouse_hover": [
        (HKCU, r"Control Panel\Mouse", "MouseHoverTime", SZ, "10", "400"),
    ],
    "disable_transparency": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", DWORD, 0, 1),
    ],
    "disable_animations": [
        (HKCU, r"Control Panel\Desktop\WindowMetrics", "MinAnimate", SZ, "0", "1"),
        (HKCU, _ADV, "TaskbarAnimations", DWORD, 0, 1),
    ],
    "dark_theme": [
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", DWORD, 0, 1),
        (HKCU, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "SystemUsesLightTheme", DWORD, 0, 1),
    ],
    "show_extensions": [
        (HKCU, _ADV, "HideFileExt", DWORD, 0, 1),
    ],
    "explorer_this_pc": [
        (HKCU, _ADV, "LaunchTo", DWORD, 1, None),
    ],
    "aero_shake": [
        (HKCU, _ADV, "DisallowShaking", DWORD, 1, None),
    ],
    "taskbar_end_task": [
        (HKCU, _ADV + r"\TaskbarDeveloperSettings", "TaskbarEndTask", DWORD, 1, None),
    ],
    "sync_provider_ads": [
        (HKCU, _ADV, "ShowSyncProviderNotifications", DWORD, 0, 1),
    ],
}

# ---------------------------------------------------------------------------
#                          Специальные твики
# ---------------------------------------------------------------------------

_POWER_HIGH = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
_POWER_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
_POWER_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
_USB_SUB = "2a737441-1930-4402-8d77-b2bebba308a3"
_USB_SET = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
_GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_TCP_IFACES = _TCP + r"\Interfaces"
_CLASSIC_MENU = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"


def _active_scheme():
    m = _GUID_RE.search(run_hidden(["powercfg", "/getactivescheme"], 15).stdout)
    return m.group(0).lower() if m else None


def _tcp_interfaces():
    result = []
    for sub in reg.subkeys(HKLM, _TCP_IFACES):
        path = _TCP_IFACES + "\\" + sub
        ip = reg.get(HKLM, path, "DhcpIPAddress") or reg.get(HKLM, path, "IPAddress")
        if isinstance(ip, list):
            ip = ip[0] if ip else ""
        if ip and ip != "0.0.0.0":
            result.append(path)
    return result


def _usb_suspend_value():
    out = run_hidden(["powercfg", "/q", "scheme_current", _USB_SUB, _USB_SET], 15).stdout
    values = re.findall(r"0x([0-9a-fA-F]{8})", out)
    return int(values[-2], 16) if len(values) >= 2 else None


def _svchost_target_kb():
    return int(get_ram_info()["total_gb"] * 1024 * 1024) + 1024


class _Special:
    """Описание специального твика: три функции."""
    def __init__(self, check, apply, restore):
        self.check, self.apply, self.restore = check, apply, restore


# --- Схема питания ---
def _power_check():
    s = _active_scheme()
    return s in (_POWER_HIGH, _POWER_ULTIMATE) or (s is not None and s == state.lookup("commands", "power_plan_new"))


def _power_apply():
    state.remember("commands", "power_plan", _active_scheme())
    res = run_hidden(["powercfg", "/setactive", _POWER_HIGH], 20)
    if res.returncode != 0:
        dup = run_hidden(["powercfg", "-duplicatescheme", _POWER_HIGH], 20)
        m = _GUID_RE.search(dup.stdout)
        if m:
            state.remember("commands", "power_plan_new", m.group(0).lower())
            res = run_hidden(["powercfg", "/setactive", m.group(0)], 20)
    if res.returncode != 0:
        return False, ["не удалось переключить схему питания"]
    for setting in ("CPMINCORES", "PROCTHROTTLEMIN"):
        run_hidden(["powercfg", "-setacvalueindex", "scheme_current", "sub_processor", setting, "100"])
    run_hidden(["powercfg", "/setactive", "scheme_current"])
    return True, ["схема «Высокая производительность»", "парковка ядер = выкл", "мин. состояние ЦП = 100%"]


def _power_restore():
    guid = state.lookup("commands", "power_plan") or _POWER_BALANCED
    ok = run_hidden(["powercfg", "/setactive", guid], 20).returncode == 0
    state.forget("commands", "power_plan")
    return ok, [f"возвращена исходная схема питания ({guid})"]


# --- USB Selective Suspend ---
def _usb_check():
    return _usb_suspend_value() == 0


def _usb_apply():
    state.remember("commands", "usb_suspend", _usb_suspend_value())
    run_hidden(["powercfg", "-setacvalueindex", "scheme_current", _USB_SUB, _USB_SET, "0"])
    run_hidden(["powercfg", "/setactive", "scheme_current"])
    return True, ["Временное отключение USB-порта = выкл (питание от сети)"]


def _usb_restore():
    val = state.lookup("commands", "usb_suspend")
    val = 1 if val is None else val
    run_hidden(["powercfg", "-setacvalueindex", "scheme_current", _USB_SUB, _USB_SET, str(val)])
    run_hidden(["powercfg", "/setactive", "scheme_current"])
    state.forget("commands", "usb_suspend")
    return True, [f"Временное отключение USB-порта = {'вкл' if val else 'выкл'}"]


# --- Гибернация ---
def _hib_check():
    return reg.get(HKLM, r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled") == 0


def _hib_apply():
    state.remember("commands", "hibernation", reg.get(HKLM, r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled"))
    ok = run_hidden(["powercfg", "-h", "off"]).returncode == 0
    return ok, ["powercfg -h off — hiberfil.sys удалён"] if ok else ["не удалось отключить гибернацию"]


def _hib_restore():
    was = state.lookup("commands", "hibernation")
    state.forget("commands", "hibernation")
    if was == 0:
        return True, ["гибернация была выключена изначально — оставлена выключенной"]
    ok = run_hidden(["powercfg", "-h", "on"]).returncode == 0
    return ok, ["powercfg -h on — гибернация включена"]


# --- Алгоритм Нейгла ---
def _nagle_check():
    ifaces = _tcp_interfaces()
    return bool(ifaces) and all(
        reg.get(HKLM, p, "TcpAckFrequency") == 1 and reg.get(HKLM, p, "TCPNoDelay") == 1 for p in ifaces
    )


def _nagle_apply():
    ifaces = _tcp_interfaces()
    if not ifaces:
        return False, ["не найдено активных сетевых интерфейсов"]
    for p in ifaces:
        reg.set(HKLM, p, "TcpAckFrequency", DWORD, 1)
        reg.set(HKLM, p, "TCPNoDelay", DWORD, 1)
    return True, [f"TcpAckFrequency = 1, TCPNoDelay = 1 ({len(ifaces)} интерфейсов)"]


def _nagle_restore():
    ifaces = _tcp_interfaces()
    for p in ifaces:
        reg.restore(HKLM, p, "TcpAckFrequency")
        reg.restore(HKLM, p, "TCPNoDelay")
    return True, [f"TcpAckFrequency / TCPNoDelay восстановлены ({len(ifaces)} интерфейсов)"]


# --- Классическое контекстное меню Windows 11 ---
def _menu_check():
    return reg.key_exists(HKCU, _CLASSIC_MENU + r"\InprocServer32")


def _menu_apply():
    reg._raw_set(HKCU, _CLASSIC_MENU + r"\InprocServer32", "", SZ, "")
    return True, ["создан ключ CLSID {86ca1aa0…}\\InprocServer32 — классическое меню"]


def _menu_restore():
    reg.delete_tree(HKCU, _CLASSIC_MENU)
    return True, ["ключ CLSID {86ca1aa0…} удалён — меню Windows 11 по умолчанию"]


# --- Объединение процессов svchost ---
_SVC = r"SYSTEM\CurrentControlSet\Control"


def _svc_check():
    v = reg.get(HKLM, _SVC, "SvcHostSplitThresholdInKB")
    return v is not None and int(v) >= _svchost_target_kb() - 2048


def _svc_apply():
    kb = _svchost_target_kb()
    reg.set(HKLM, _SVC, "SvcHostSplitThresholdInKB", DWORD, kb)
    return True, [f"SvcHostSplitThresholdInKB = {kb} (≈ объём ОЗУ)"]


def _svc_restore():
    v = reg.restore(HKLM, _SVC, "SvcHostSplitThresholdInKB", DWORD, 0x380000)
    return True, [f"SvcHostSplitThresholdInKB = {v}"]


SPECIAL_TWEAKS = {
    "power_plan": _Special(_power_check, _power_apply, _power_restore),
    "usb_suspend": _Special(_usb_check, _usb_apply, _usb_restore),
    "disable_hibernation": _Special(_hib_check, _hib_apply, _hib_restore),
    "nagle": _Special(_nagle_check, _nagle_apply, _nagle_restore),
    "classic_menu": _Special(_menu_check, _menu_apply, _menu_restore),
    "svchost_split": _Special(_svc_check, _svc_apply, _svc_restore),
}


# ---------------------------------------------------------------------------
#                               Публичный API
# ---------------------------------------------------------------------------

def _fmt(kind, value):
    if value is None:
        return "по умолчанию Windows (удалено)"
    if kind == DWORD and isinstance(value, int) and value > 0xFFFF:
        return "0x%X" % (value & 0xFFFFFFFF)
    return str(value)


def known_ids():
    return set(REG_TWEAKS) | set(SPECIAL_TWEAKS)


def is_applied(tweak_id):
    try:
        if tweak_id in REG_TWEAKS:
            for hive, path, name, kind, opt, _ in REG_TWEAKS[tweak_id]:
                cur = reg.get(hive, path, name)
                if cur is None:
                    return False
                if kind == DWORD:
                    if int(cur) & 0xFFFFFFFF != int(opt) & 0xFFFFFFFF:
                        return False
                elif str(cur) != str(opt):
                    return False
            return True
        if tweak_id in SPECIAL_TWEAKS:
            return bool(SPECIAL_TWEAKS[tweak_id].check())
    except Exception:
        return False
    return False


def apply(tweak_id):
    """Применяет твик. Возвращает (успех, текст_для_журнала)."""
    try:
        if tweak_id in REG_TWEAKS:
            changes = []
            for hive, path, name, kind, opt, _ in REG_TWEAKS[tweak_id]:
                reg.set(hive, path, name, kind, opt)
                changes.append(f"{name} = {_fmt(kind, opt)}")
            return True, "; ".join(changes)
        if tweak_id in SPECIAL_TWEAKS:
            ok, changes = SPECIAL_TWEAKS[tweak_id].apply()
            return ok, "; ".join(changes)
    except PermissionError:
        return False, "нет доступа к реестру (нужны права администратора)"
    except Exception as e:
        return False, f"ошибка: {e}"
    return False, "неизвестный твик"


def restore(tweak_id):
    """Возвращает исходное значение (из резервной копии) или стандарт Windows."""
    try:
        if tweak_id in REG_TWEAKS:
            changes = []
            for hive, path, name, kind, _opt, default in REG_TWEAKS[tweak_id]:
                value = reg.restore(hive, path, name, kind, default)
                changes.append(f"{name} = {_fmt(kind, value)}")
            return True, "; ".join(changes)
        if tweak_id in SPECIAL_TWEAKS:
            ok, changes = SPECIAL_TWEAKS[tweak_id].restore()
            return ok, "; ".join(changes)
    except PermissionError:
        return False, "нет доступа к реестру"
    except Exception as e:
        return False, f"ошибка: {e}"
    return False, "неизвестный твик"

