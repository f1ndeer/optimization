use crate::registry::{self as reg, Hive, RegVal};
use crate::state;
use crate::system::{get_ram_info, run_hidden};

pub struct RegRule {
    pub hive: Hive,
    pub path: &'static str,
    pub name: &'static str,
    pub opt: RegVal,
    pub default: Option<RegVal>,
}

const MM: &str = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile";
const MM_GAMES: &str = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games";
const CDM: &str = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager";
const ADV: &str = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced";
const TCP: &str = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters";
const FS: &str = r"SYSTEM\CurrentControlSet\Control\FileSystem";

pub fn get_reg_rules(id: &str) -> Option<&'static [RegRule]> {
    use Hive::{Hkcu, Hklm};
    use RegVal::{Dword, Sz};

    match id {
        // ======================= ИГРЫ И FPS =======================
        "game_dvr" => Some(&[
            RegRule { hive: Hkcu, path: r"System\GameConfigStore", name: "GameDVR_Enabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR", name: "AppCaptureEnabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\GameBar", name: "UseNexusForGameBarEnabled", opt: Dword(0), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\GameBar", name: "ShowStartupPanel", opt: Dword(0), default: None },
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", name: "AllowGameDVR", opt: Dword(0), default: None },
        ]),
        "mmcss_gaming" => Some(&[
            RegRule { hive: Hklm, path: MM, name: "SystemResponsiveness", opt: Dword(0), default: Some(Dword(20)) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "GPU Priority", opt: Dword(8), default: Some(Dword(8)) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "Priority", opt: Dword(6), default: Some(Dword(2)) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "Scheduling Category", opt: Sz("High"), default: Some(Sz("Medium")) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "SFIO Priority", opt: Sz("High"), default: Some(Sz("Normal")) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "Background Only", opt: Sz("False"), default: Some(Sz("False")) },
            RegRule { hive: Hklm, path: MM_GAMES, name: "Clock Rate", opt: Dword(10000), default: Some(Dword(10000)) },
        ]),
        "game_mode" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\GameBar", name: "AutoGameModeEnabled", opt: Dword(1), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\GameBar", name: "AllowAutoGameMode", opt: Dword(1), default: None },
        ]),
        "win32_priority" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\PriorityControl", name: "Win32PrioritySeparation", opt: Dword(0x26), default: Some(Dword(2)) },
        ]),
        "power_throttling" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", name: "PowerThrottlingOff", opt: Dword(1), default: None },
        ]),
        "global_timer_resolution" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", name: "GlobalTimerResolutionRequests", opt: Dword(1), default: None },
        ]),
        "windowed_opt" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\DirectX\UserGpuPreferences", name: "DirectXUserGlobalSettings", opt: Sz("SwapEffectUpgradeEnable=1;"), default: None },
        ]),
        "fullscreen_opt" => Some(&[
            RegRule { hive: Hkcu, path: r"System\GameConfigStore", name: "GameDVR_FSEBehavior", opt: Dword(2), default: None },
            RegRule { hive: Hkcu, path: r"System\GameConfigStore", name: "GameDVR_HonorUserFSEBehaviorMode", opt: Dword(1), default: Some(Dword(0)) },
            RegRule { hive: Hkcu, path: r"System\GameConfigStore", name: "GameDVR_DXGIHonorFSEWindowsCompatible", opt: Dword(1), default: Some(Dword(0)) },
        ]),
        "hags" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", name: "HwSchMode", opt: Dword(2), default: None },
        ]),
        "mpo_disable" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Microsoft\Windows\Dwm", name: "OverlayTestMode", opt: Dword(5), default: None },
        ]),
        "fth_disable" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Microsoft\FTH", name: "Enabled", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "mouse_accel" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Mouse", name: "MouseSpeed", opt: Sz("0"), default: Some(Sz("1")) },
            RegRule { hive: Hkcu, path: r"Control Panel\Mouse", name: "MouseThreshold1", opt: Sz("0"), default: Some(Sz("6")) },
            RegRule { hive: Hkcu, path: r"Control Panel\Mouse", name: "MouseThreshold2", opt: Sz("0"), default: Some(Sz("10")) },
        ]),
        "keyboard_response" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Keyboard", name: "KeyboardDelay", opt: Sz("0"), default: Some(Sz("1")) },
            RegRule { hive: Hkcu, path: r"Control Panel\Keyboard", name: "KeyboardSpeed", opt: Sz("31"), default: Some(Sz("31")) },
        ]),
        "sticky_keys" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Accessibility\StickyKeys", name: "Flags", opt: Sz("506"), default: Some(Sz("510")) },
            RegRule { hive: Hkcu, path: r"Control Panel\Accessibility\ToggleKeys", name: "Flags", opt: Sz("58"), default: Some(Sz("62")) },
            RegRule { hive: Hkcu, path: r"Control Panel\Accessibility\Keyboard Response", name: "Flags", opt: Sz("122"), default: Some(Sz("126")) },
        ]),

        // ======================= СЕТЬ =======================
        "network_throttling" => Some(&[
            RegRule { hive: Hklm, path: MM, name: "NetworkThrottlingIndex", opt: Dword(0xFFFFFFFF), default: Some(Dword(10)) },
        ]),
        "dns_priority" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", name: "LocalPriority", opt: Dword(4), default: Some(Dword(499)) },
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", name: "HostsPriority", opt: Dword(5), default: Some(Dword(500)) },
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", name: "DnsPriority", opt: Dword(6), default: Some(Dword(2000)) },
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Services\Tcpip\ServiceProvider", name: "NetbtPriority", opt: Dword(7), default: Some(Dword(2001)) },
        ]),
        "delivery_optimization" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", name: "DODownloadMode", opt: Dword(0), default: None },
        ]),
        "tcp_params" => Some(&[
            RegRule { hive: Hklm, path: TCP, name: "DefaultTTL", opt: Dword(64), default: None },
            RegRule { hive: Hklm, path: TCP, name: "TcpTimedWaitDelay", opt: Dword(30), default: None },
            RegRule { hive: Hklm, path: TCP, name: "MaxUserPort", opt: Dword(65534), default: None },
        ]),
        "llmnr_disable" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", name: "EnableMulticast", opt: Dword(0), default: None },
        ]),

        // ======================= СИСТЕМА =======================
        "startup_delay" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", name: "StartupDelayInMSec", opt: Dword(0), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", name: "WaitForIdleState", opt: Dword(0), default: None },
        ]),
        "ntfs_last_access" => Some(&[
            RegRule { hive: Hklm, path: FS, name: "NtfsDisableLastAccessUpdate", opt: Dword(0x80000001), default: Some(Dword(0x80000002)) },
        ]),
        "ntfs_8dot3" => Some(&[
            RegRule { hive: Hklm, path: FS, name: "NtfsDisable8dot3NameCreation", opt: Dword(1), default: Some(Dword(2)) },
        ]),
        "fast_shutdown" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control", name: "WaitToKillServiceTimeout", opt: Sz("2000"), default: Some(Sz("5000")) },
        ]),
        "hung_apps" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Desktop", name: "HungAppTimeout", opt: Sz("2000"), default: None },
            RegRule { hive: Hkcu, path: r"Control Panel\Desktop", name: "WaitToKillAppTimeout", opt: Sz("5000"), default: None },
        ]),
        "paging_executive" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", name: "DisablePagingExecutive", opt: Dword(1), default: Some(Dword(0)) },
        ]),
        "update_no_reboot" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", name: "NoAutoRebootWithLoggedOnUsers", opt: Dword(1), default: None },
        ]),
        "auto_maintenance" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance", name: "MaintenanceDisabled", opt: Dword(1), default: None },
        ]),
        "fast_startup" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", name: "HiberbootEnabled", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "error_reporting" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Microsoft\Windows\Windows Error Reporting", name: "Disabled", opt: Dword(1), default: None },
        ]),
        "remote_assistance" => Some(&[
            RegRule { hive: Hklm, path: r"SYSTEM\CurrentControlSet\Control\Remote Assistance", name: "fAllowToGetHelp", opt: Dword(0), default: Some(Dword(1)) },
        ]),

        // ======================= ПРИВАТНОСТЬ =======================
        "telemetry" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", name: "AllowTelemetry", opt: Dword(0), default: None },
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", name: "DoNotShowFeedbackNotifications", opt: Dword(1), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Siuf\Rules", name: "NumberOfSIUFInPeriod", opt: Dword(0), default: None },
        ]),
        "advertising_id" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", name: "Enabled", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "tailored_experiences" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Privacy", name: "TailoredExperiencesWithDiagnosticDataEnabled", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "activity_history" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\System", name: "EnableActivityFeed", opt: Dword(0), default: None },
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\System", name: "PublishUserActivities", opt: Dword(0), default: None },
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\System", name: "UploadUserActivities", opt: Dword(0), default: None },
        ]),
        "suggestions_ads" => Some(&[
            RegRule { hive: Hkcu, path: CDM, name: "SystemPaneSuggestionsEnabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SilentInstalledAppsEnabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SoftLandingEnabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "RotatingLockScreenOverlayEnabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SubscribedContent-338387Enabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SubscribedContent-338388Enabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SubscribedContent-338389Enabled", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: CDM, name: "SubscribedContent-353694Enabled", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "start_tracking" => Some(&[
            RegRule { hive: Hkcu, path: ADV, name: "Start_TrackProgs", opt: Dword(0), default: None },
        ]),
        "input_personalization" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\InputPersonalization", name: "RestrictImplicitInkCollection", opt: Dword(1), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\InputPersonalization", name: "RestrictImplicitTextCollection", opt: Dword(1), default: None },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Personalization\Settings", name: "AcceptedPrivacyPolicy", opt: Dword(0), default: None },
        ]),
        "bing_search" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Search", name: "BingSearchEnabled", opt: Dword(0), default: None },
            RegRule { hive: Hkcu, path: r"Software\Policies\Microsoft\Windows\Explorer", name: "DisableSearchBoxSuggestions", opt: Dword(1), default: None },
        ]),
        "cortana" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", name: "AllowCortana", opt: Dword(0), default: None },
        ]),
        "copilot" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Policies\Microsoft\Windows\WindowsCopilot", name: "TurnOffWindowsCopilot", opt: Dword(1), default: None },
            RegRule { hive: Hkcu, path: ADV, name: "ShowCopilotButton", opt: Dword(0), default: None },
        ]),
        "widgets" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Dsh", name: "AllowNewsAndInterests", opt: Dword(0), default: None },
        ]),
        "edge_background" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Edge", name: "StartupBoostEnabled", opt: Dword(0), default: None },
            RegRule { hive: Hklm, path: r"SOFTWARE\Policies\Microsoft\Edge", name: "BackgroundModeEnabled", opt: Dword(0), default: None },
        ]),
        "background_apps" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", name: "GlobalUserDisabled", opt: Dword(1), default: None },
        ]),
        "location" => Some(&[
            RegRule { hive: Hklm, path: r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", name: "Value", opt: Sz("Deny"), default: Some(Sz("Allow")) },
        ]),

        // ======================= ИНТЕРФЕЙС =======================
        "menu_delay" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Desktop", name: "MenuShowDelay", opt: Sz("0"), default: Some(Sz("400")) },
        ]),
        "mouse_hover" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Mouse", name: "MouseHoverTime", opt: Sz("10"), default: Some(Sz("400")) },
        ]),
        "disable_transparency" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", name: "EnableTransparency", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "disable_animations" => Some(&[
            RegRule { hive: Hkcu, path: r"Control Panel\Desktop\WindowMetrics", name: "MinAnimate", opt: Sz("0"), default: Some(Sz("1")) },
            RegRule { hive: Hkcu, path: ADV, name: "TaskbarAnimations", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "dark_theme" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", name: "AppsUseLightTheme", opt: Dword(0), default: Some(Dword(1)) },
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", name: "SystemUsesLightTheme", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "show_extensions" => Some(&[
            RegRule { hive: Hkcu, path: ADV, name: "HideFileExt", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        "explorer_this_pc" => Some(&[
            RegRule { hive: Hkcu, path: ADV, name: "LaunchTo", opt: Dword(1), default: None },
        ]),
        "aero_shake" => Some(&[
            RegRule { hive: Hkcu, path: ADV, name: "DisallowShaking", opt: Dword(1), default: None },
        ]),
        "taskbar_end_task" => Some(&[
            RegRule { hive: Hkcu, path: r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings", name: "TaskbarEndTask", opt: Dword(1), default: None },
        ]),
        "sync_provider_ads" => Some(&[
            RegRule { hive: Hkcu, path: ADV, name: "ShowSyncProviderNotifications", opt: Dword(0), default: Some(Dword(1)) },
        ]),
        _ => None,
    }
}

const POWER_HIGH: &str = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c";
const POWER_ULTIMATE: &str = "e9a42b02-d5df-448d-aa00-03f14749eb61";
const POWER_BALANCED: &str = "381b4222-f694-41f0-9685-ff5bb260df2e";
const USB_SUB: &str = "2a737441-1930-4402-8d77-b2bebba308a3";
const USB_SET: &str = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226";
const CLASSIC_MENU_CLSID: &str = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}";
const TCP_IFACES: &str = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces";

fn extract_guid(text: &str) -> Option<String> {
    for word in text.split_whitespace() {
        let clean = word.trim_matches(|c: char| !c.is_ascii_hexdigit() && c != '-');
        if clean.len() == 36 && clean.chars().filter(|&c| c == '-').count() == 4 {
            return Some(clean.to_lowercase());
        }
    }
    None
}

fn active_power_scheme() -> Option<String> {
    let (_, out) = run_hidden(&["powercfg", "/getactivescheme"]);
    extract_guid(&out)
}

fn tcp_interfaces() -> Vec<String> {
    let mut res = Vec::new();
    for sub in reg::subkeys(Hive::Hklm, TCP_IFACES) {
        let path = format!("{}\\{}", TCP_IFACES, sub);
        let ip = reg::get_sz(Hive::Hklm, &path, "DhcpIPAddress")
            .or_else(|| reg::get_sz(Hive::Hklm, &path, "IPAddress"))
            .unwrap_or_default();
        if !ip.is_empty() && ip != "0.0.0.0" {
            res.push(path);
        }
    }
    res
}

fn svchost_target_kb() -> u32 {
    let ram = get_ram_info();
    ((ram.total_gb * 1024.0 * 1024.0) as u32).saturating_add(1024)
}

pub fn is_tweak_applied(id: &str) -> bool {
    if let Some(rules) = get_reg_rules(id) {
        for r in rules {
            match r.opt {
                RegVal::Dword(expected) => {
                    if reg::get_dword(r.hive, r.path, r.name) != Some(expected) {
                        return false;
                    }
                }
                RegVal::Sz(expected) => {
                    if reg::get_sz(r.hive, r.path, r.name).as_deref() != Some(expected) {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    match id {
        "power_plan" => {
            if let Some(s) = active_power_scheme() {
                s == POWER_HIGH
                    || s == POWER_ULTIMATE
                    || state::lookup_cmd("power_plan_new").as_deref() == Some(s.as_str())
            } else {
                false
            }
        }
        "usb_suspend" => {
            let (_, out) = run_hidden(&["powercfg", "/q", "scheme_current", USB_SUB, USB_SET]);
            let hexes: Vec<&str> = out
                .lines()
                .filter_map(|l| l.split("0x").nth(1))
                .map(|s| s.trim())
                .collect();
            hexes.len() >= 2 && u32::from_str_radix(hexes[hexes.len() - 2], 16).ok() == Some(0)
        }
        "disable_hibernation" => {
            reg::get_dword(Hive::Hklm, r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled") == Some(0)
        }
        "nagle" => {
            let ifaces = tcp_interfaces();
            !ifaces.is_empty()
                && ifaces.iter().all(|p| {
                    reg::get_dword(Hive::Hklm, p, "TcpAckFrequency") == Some(1)
                        && reg::get_dword(Hive::Hklm, p, "TCPNoDelay") == Some(1)
                })
        }
        "classic_menu" => reg::key_exists(Hive::Hkcu, &format!("{}\\InprocServer32", CLASSIC_MENU_CLSID)),
        "svchost_split" => {
            if let Some(v) = reg::get_dword(Hive::Hklm, r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB") {
                v >= svchost_target_kb().saturating_sub(2048)
            } else {
                false
            }
        }
        _ => false,
    }
}

pub fn apply_tweak(id: &str) -> (bool, String) {
    if let Some(rules) = get_reg_rules(id) {
        let mut changes = Vec::new();
        for r in rules {
            if let Err(e) = reg::set_val(r.hive, r.path, r.name, r.opt) {
                return (false, format!("ошибка доступа к реестру: {}", e));
            }
            let val_str = match r.opt {
                RegVal::Dword(v) if v > 0xFFFF => format!("0x{:X}", v),
                RegVal::Dword(v) => v.to_string(),
                RegVal::Sz(s) => s.to_string(),
            };
            changes.push(format!("{} = {}", r.name, val_str));
        }
        return (true, changes.join("; "));
    }

    match id {
        "power_plan" => {
            if let Some(cur) = active_power_scheme() {
                state::remember_cmd("power_plan", &cur);
            }
            let (mut ok, _) = run_hidden(&["powercfg", "/setactive", POWER_HIGH]);
            if !ok {
                let (_, dup_out) = run_hidden(&["powercfg", "-duplicatescheme", POWER_HIGH]);
                if let Some(guid) = extract_guid(&dup_out) {
                    state::remember_cmd("power_plan_new", &guid);
                    let (ok2, _) = run_hidden(&["powercfg", "/setactive", &guid]);
                    ok = ok2;
                }
            }
            if !ok {
                return (false, "не удалось активировать схему высокой производительности".to_string());
            }
            let _ = run_hidden(&["powercfg", "-setacvalueindex", "scheme_current", "sub_processor", "CPMINCORES", "100"]);
            let _ = run_hidden(&["powercfg", "-setacvalueindex", "scheme_current", "sub_processor", "PROCTHROTTLEMIN", "100"]);
            let _ = run_hidden(&["powercfg", "/setactive", "scheme_current"]);
            (true, "Схема «Высокая производительность»; парковка ядер = выкл; мин. ЦП = 100%".to_string())
        }
        "usb_suspend" => {
            let _ = run_hidden(&["powercfg", "-setacvalueindex", "scheme_current", USB_SUB, USB_SET, "0"]);
            let _ = run_hidden(&["powercfg", "/setactive", "scheme_current"]);
            (true, "Временное отключение USB-портов = выкл".to_string())
        }
        "disable_hibernation" => {
            let (ok, _) = run_hidden(&["powercfg", "-h", "off"]);
            if ok {
                (true, "powercfg -h off — файл hiberfil.sys удалён".to_string())
            } else {
                (false, "не удалось отключить гибернацию".to_string())
            }
        }
        "nagle" => {
            let ifaces = tcp_interfaces();
            if ifaces.is_empty() {
                return (false, "не найдено активных сетевых интерфейсов".to_string());
            }
            for p in &ifaces {
                let _ = reg::set_val(Hive::Hklm, p, "TcpAckFrequency", RegVal::Dword(1));
                let _ = reg::set_val(Hive::Hklm, p, "TCPNoDelay", RegVal::Dword(1));
            }
            (true, format!("TcpAckFrequency = 1, TCPNoDelay = 1 ({} интерфейсов)", ifaces.len()))
        }
        "classic_menu" => {
            let key_path = format!("{}\\InprocServer32", CLASSIC_MENU_CLSID);
            match reg::raw_set_sz(Hive::Hkcu, &key_path, "", "") {
                Ok(_) => (true, "включено классическое контекстное меню Windows 11".to_string()),
                Err(e) => (false, e),
            }
        }
        "svchost_split" => {
            let kb = svchost_target_kb();
            match reg::set_val(Hive::Hklm, r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB", RegVal::Dword(kb)) {
                Ok(_) => (true, format!("SvcHostSplitThresholdInKB = {} КБ", kb)),
                Err(e) => (false, e),
            }
        }
        _ => (false, format!("неизвестный твик: {}", id)),
    }
}

pub fn restore_tweak(id: &str) -> (bool, String) {
    if let Some(rules) = get_reg_rules(id) {
        let mut changes = Vec::new();
        for r in rules {
            let restored = reg::restore_val(r.hive, r.path, r.name, r.default);
            changes.push(format!("{} = {}", r.name, restored));
        }
        return (true, changes.join("; "));
    }

    match id {
        "power_plan" => {
            let guid = state::lookup_cmd("power_plan").unwrap_or_else(|| POWER_BALANCED.to_string());
            let (ok, _) = run_hidden(&["powercfg", "/setactive", &guid]);
            state::forget_cmd("power_plan");
            (ok, format!("возвращена схема электропитания ({})", guid))
        }
        "usb_suspend" => {
            let _ = run_hidden(&["powercfg", "-setacvalueindex", "scheme_current", USB_SUB, USB_SET, "1"]);
            let _ = run_hidden(&["powercfg", "/setactive", "scheme_current"]);
            (true, "Временное отключение USB-порта возвращено к стандарту".to_string())
        }
        "disable_hibernation" => {
            let (ok, _) = run_hidden(&["powercfg", "-h", "on"]);
            (ok, "powercfg -h on — гибернация включена".to_string())
        }
        "nagle" => {
            let ifaces = tcp_interfaces();
            for p in &ifaces {
                reg::restore_val(Hive::Hklm, p, "TcpAckFrequency", None);
                reg::restore_val(Hive::Hklm, p, "TCPNoDelay", None);
            }
            (true, format!("TcpAckFrequency / TCPNoDelay сброшены ({} интерфейсов)", ifaces.len()))
        }
        "classic_menu" => {
            reg::delete_tree(Hive::Hkcu, CLASSIC_MENU_CLSID);
            (true, "возвращено стандартное меню Windows 11".to_string())
        }
        "svchost_split" => {
            let val = reg::restore_val(
                Hive::Hklm,
                r"SYSTEM\CurrentControlSet\Control",
                "SvcHostSplitThresholdInKB",
                Some(RegVal::Dword(0x380000)),
            );
            (true, format!("SvcHostSplitThresholdInKB = {}", val))
        }
        _ => (false, format!("неизвестный твик: {}", id)),
    }
}
