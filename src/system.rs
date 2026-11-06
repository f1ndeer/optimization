use std::env;
use std::ffi::OsStr;
use std::fs;
use std::os::windows::ffi::OsStrExt;
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::Command;

use windows_sys::Win32::Foundation::CloseHandle;
use windows_sys::Win32::Graphics::Gdi::{SetSysColors, COLOR_DESKTOP};
use windows_sys::Win32::System::ProcessStatus::{EmptyWorkingSet, EnumProcesses};
use windows_sys::Win32::System::SystemInformation::{GlobalMemoryStatusEx, MEMORYSTATUSEX};
use windows_sys::Win32::System::Threading::{OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_SET_QUOTA};
use windows_sys::Win32::UI::Shell::{
    IsUserAnAdmin, SHEmptyRecycleBinW, ShellExecuteW, SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI, SHERB_NOSOUND,
};
use windows_sys::Win32::UI::WindowsAndMessaging::{
    SystemParametersInfoW, SPIF_SENDWININICHANGE, SPIF_UPDATEINIFILE, SPI_GETDESKWALLPAPER, SPI_SETDESKWALLPAPER,
    SW_SHOWNORMAL,
};

use crate::models::{backup_dir, logs_dir};
use crate::registry::{self as reg, Hive};
use crate::state::{self, WallpaperBackup};

const CREATE_NO_WINDOW: u32 = 0x08000000;

pub fn to_wide(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(std::iter::once(0)).collect()
}

pub fn is_admin() -> bool {
    unsafe { IsUserAnAdmin() != 0 }
}

pub fn relaunch_as_admin() {
    if let Ok(exe) = env::current_exe() {
        let verb = to_wide("runas");
        let file = to_wide(&exe.to_string_lossy());
        let args: String = env::args().skip(1).map(|a| format!("\"{}\"", a)).collect::<Vec<_>>().join(" ");
        let params = to_wide(&args);
        unsafe {
            ShellExecuteW(
                std::ptr::null_mut(),
                verb.as_ptr(),
                file.as_ptr(),
                params.as_ptr(),
                std::ptr::null(),
                SW_SHOWNORMAL as i32,
            );
        }
    }
}

pub fn run_hidden(args: &[&str]) -> (bool, String) {
    if args.is_empty() {
        return (false, String::new());
    }
    match Command::new(args[0])
        .args(&args[1..])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
    {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout).to_string();
            let stderr = String::from_utf8_lossy(&out.stderr).to_string();
            let combined = if stdout.trim().is_empty() { stderr } else { stdout };
            (out.status.success(), combined)
        }
        Err(e) => (false, e.to_string()),
    }
}

pub fn run_powershell(script: &str) -> (bool, String) {
    run_hidden(&["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script])
}

// ==================== ПАМЯТЬ, ДИСК И СИСТЕМА ====================

#[derive(Debug, Clone, Copy)]
pub struct RamInfo {
    pub load_percent: u32,
    pub total_gb: f64,
    pub used_gb: f64,
    pub avail_gb: f64,
    pub avail_mb: f64,
}

pub fn get_ram_info() -> RamInfo {
    unsafe {
        let mut stat: MEMORYSTATUSEX = std::mem::zeroed();
        stat.dwLength = std::mem::size_of::<MEMORYSTATUSEX>() as u32;
        GlobalMemoryStatusEx(&mut stat);
        let total_gb = (stat.ullTotalPhys as f64) / 1_073_741_824.0;
        let avail_gb = (stat.ullAvailPhys as f64) / 1_073_741_824.0;
        let used_gb = (total_gb - avail_gb).max(0.0);
        let avail_mb = (stat.ullAvailPhys as f64) / 1_048_576.0;
        RamInfo {
            load_percent: stat.dwMemoryLoad,
            total_gb: (total_gb * 10.0).round() / 10.0,
            used_gb: (used_gb * 10.0).round() / 10.0,
            avail_gb: (avail_gb * 10.0).round() / 10.0,
            avail_mb: (avail_mb * 10.0).round() / 10.0,
        }
    }
}

pub fn get_disk_free_gb() -> (f64, f64) {
    let sys_drive = env::var("SystemDrive").unwrap_or_else(|_| "C:".to_string()) + "\\";
    let wide = to_wide(&sys_drive);
    let mut free_avail: u64 = 0;
    let mut total_bytes: u64 = 0;
    let mut total_free: u64 = 0;
    unsafe {
        if windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW(
            wide.as_ptr(),
            &mut free_avail,
            &mut total_bytes,
            &mut total_free,
        ) != 0
        {
            let free = ((total_free as f64) / 1_073_741_824.0 * 10.0).round() / 10.0;
            let total = ((total_bytes as f64) / 1_073_741_824.0 * 10.0).round() / 10.0;
            return (free, total);
        }
    }
    (0.0, 0.0)
}

#[derive(Debug, Clone)]
pub struct SystemSummary {
    pub cpu: String,
    pub os: String,
}

pub fn get_system_summary() -> SystemSummary {
    let cpu = reg::get_sz(
        Hive::Hklm,
        r"HARDWARE\Description\System\CentralProcessor\0",
        "ProcessorNameString",
    )
    .unwrap_or_else(|| "Процессор x64".to_string());

    let mut os_name = reg::get_sz(Hive::Hklm, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName")
        .unwrap_or_else(|| "Windows".to_string());
    let display_ver = reg::get_sz(Hive::Hklm, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion")
        .unwrap_or_default();
    let build = reg::get_sz(Hive::Hklm, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuild")
        .unwrap_or_default();
    if let Ok(b) = build.parse::<u32>() {
        if b >= 22000 && os_name.contains("Windows 10") {
            os_name = os_name.replace("Windows 10", "Windows 11");
        }
    }

    SystemSummary {
        cpu: cpu.trim().to_string(),
        os: format!("{} {} (Build {})", os_name, display_ver, build).trim().to_string(),
    }
}

// ==================== ЧЁРНЫЕ ОБОИ (OLED BLACK) С ВОЗВРАТОМ ====================

fn black_bmp_path() -> PathBuf {
    backup_dir().join("oled_black_wallpaper.bmp")
}

fn ensure_black_bmp() -> PathBuf {
    let dir = backup_dir();
    let _ = fs::create_dir_all(&dir);
    let path = black_bmp_path();
    if path.is_file() {
        return path;
    }

    // Генерируем минимальный 16x16 24-битный чисто чёрный BMP
    let width: u32 = 16;
    let height: u32 = 16;
    let pixel_size: u32 = width * height * 3;
    let file_size: u32 = 14 + 40 + pixel_size;

    let mut data = Vec::with_capacity(file_size as usize);
    data.extend_from_slice(b"BM");
    data.extend_from_slice(&file_size.to_le_bytes());
    data.extend_from_slice(&0u32.to_le_bytes());
    data.extend_from_slice(&54u32.to_le_bytes());

    data.extend_from_slice(&40u32.to_le_bytes());
    data.extend_from_slice(&width.to_le_bytes());
    data.extend_from_slice(&height.to_le_bytes());
    data.extend_from_slice(&1u16.to_le_bytes());
    data.extend_from_slice(&24u16.to_le_bytes());
    data.extend_from_slice(&0u32.to_le_bytes());
    data.extend_from_slice(&pixel_size.to_le_bytes());
    data.extend_from_slice(&2835u32.to_le_bytes());
    data.extend_from_slice(&2835u32.to_le_bytes());
    data.extend_from_slice(&0u32.to_le_bytes());
    data.extend_from_slice(&0u32.to_le_bytes());

    data.resize(file_size as usize, 0u8);
    let _ = fs::write(&path, data);
    path
}

fn current_wallpaper_path() -> String {
    let mut buf = [0u16; 512];
    unsafe {
        SystemParametersInfoW(SPI_GETDESKWALLPAPER, 512, buf.as_mut_ptr() as *mut _, 0);
    }
    let end = buf.iter().position(|&c| c == 0).unwrap_or(buf.len());
    let s = String::from_utf16_lossy(&buf[..end]).trim().to_string();
    if !s.is_empty() {
        return s;
    }
    reg::get_sz(Hive::Hkcu, r"Control Panel\Desktop", "Wallpaper").unwrap_or_default()
}

fn set_desktop_rgb(r: u8, g: u8, b: u8) {
    let color_ref: u32 = (r as u32) | ((g as u32) << 8) | ((b as u32) << 16);
    let elem: i32 = COLOR_DESKTOP as i32;
    unsafe {
        SetSysColors(1, &elem, &color_ref);
    }
}

pub fn is_black_wallpaper() -> bool {
    if let Some(wp) = state::get_wallpaper() {
        if wp.active {
            return true;
        }
    }
    let cur = current_wallpaper_path();
    let black = black_bmp_path();
    !cur.is_empty() && cur.eq_ignore_ascii_case(&black.to_string_lossy())
}

pub fn has_saved_wallpaper() -> bool {
    state::get_wallpaper().map(|w| w.saved).unwrap_or(false)
}

pub fn set_black_wallpaper() -> (bool, String) {
    let _ = fs::create_dir_all(backup_dir());
    let cur = current_wallpaper_path();
    let black_bmp = ensure_black_bmp();
    let black_str = black_bmp.to_string_lossy().to_string();

    let already_black = !cur.is_empty() && cur.eq_ignore_ascii_case(&black_str);
    let existing = state::get_wallpaper();

    if !already_black && !existing.as_ref().map(|w| w.saved).unwrap_or(false) {
        let mut copied_file = String::new();
        if !cur.is_empty() && Path::new(&cur).is_file() {
            let ext = Path::new(&cur)
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("jpg");
            let dst = backup_dir().join(format!("original_wallpaper.{}", ext));
            if fs::copy(&cur, &dst).is_ok() {
                copied_file = dst.to_string_lossy().to_string();
            }
        }

        state::set_wallpaper(WallpaperBackup {
            saved: true,
            active: true,
            original_path: cur,
            backup_file: copied_file,
            style: reg::get_sz(Hive::Hkcu, r"Control Panel\Desktop", "WallpaperStyle")
                .unwrap_or_else(|| "10".to_string()),
            tile: reg::get_sz(Hive::Hkcu, r"Control Panel\Desktop", "TileWallpaper")
                .unwrap_or_else(|| "0".to_string()),
            background: reg::get_sz(Hive::Hkcu, r"Control Panel\Colors", "Background")
                .unwrap_or_else(|| "0 0 0".to_string()),
        });
    } else if let Some(mut wp) = existing {
        wp.active = true;
        state::set_wallpaper(wp);
    }

    let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Colors", "Background", "0 0 0");
    let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Desktop", "Wallpaper", &black_str);

    let wide = to_wide(&black_str);
    unsafe {
        SystemParametersInfoW(
            SPI_SETDESKWALLPAPER,
            0,
            wide.as_ptr() as *mut _,
            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
        );
    }
    set_desktop_rgb(0, 0, 0);

    (
        true,
        "Установлены чисто чёрные обои (OLED Black #000000). Прежние обои сохранены в резервную копию.".to_string(),
    )
}

pub fn restore_wallpaper() -> (bool, String) {
    if let Some(mut wp) = state::get_wallpaper() {
        if wp.saved {
            let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Desktop", "WallpaperStyle", &wp.style);
            let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Desktop", "TileWallpaper", &wp.tile);
            let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Colors", "Background", &wp.background);

            let parts: Vec<u8> = wp
                .background
                .split_whitespace()
                .filter_map(|p| p.parse::<u8>().ok())
                .collect();
            if parts.len() == 3 {
                set_desktop_rgb(parts[0], parts[1], parts[2]);
            }

            let target = if !wp.original_path.is_empty() && Path::new(&wp.original_path).is_file() {
                wp.original_path.clone()
            } else {
                wp.backup_file.clone()
            };

            let msg = if !target.is_empty() && Path::new(&target).is_file() {
                let _ = reg::raw_set_sz(Hive::Hkcu, r"Control Panel\Desktop", "Wallpaper", &target);
                let wide = to_wide(&target);
                unsafe {
                    SystemParametersInfoW(
                        SPI_SETDESKWALLPAPER,
                        0,
                        wide.as_ptr() as *mut _,
                        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
                    );
                }
                format!("Прежние обои успешно восстановлены ({})", target)
            } else {
                let empty = to_wide("");
                unsafe {
                    SystemParametersInfoW(
                        SPI_SETDESKWALLPAPER,
                        0,
                        empty.as_ptr() as *mut _,
                        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
                    );
                }
                "Восстановлен исходный цвет фона рабочего стола.".to_string()
            };

            wp.active = false;
            state::set_wallpaper(wp);
            return (true, msg);
        }
    }

    if let Ok(appdata) = env::var("APPDATA") {
        let transcoded = Path::new(&appdata).join(r"Microsoft\Windows\Themes\TranscodedWallpaper");
        if transcoded.is_file() {
            let s = transcoded.to_string_lossy().to_string();
            let wide = to_wide(&s);
            unsafe {
                SystemParametersInfoW(
                    SPI_SETDESKWALLPAPER,
                    0,
                    wide.as_ptr() as *mut _,
                    SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
                );
            }
            return (true, "Восстановлены обои из кэша темы Windows (TranscodedWallpaper).".to_string());
        }
    }

    (false, "Резервная копия обоев не найдена.".to_string())
}

// ==================== СЛУЖБЫ WINDOWS ====================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ServiceState {
    Running,
    Stopped,
    Unknown,
}

pub fn get_service_status(name: &str) -> ServiceState {
    let (_, out) = run_hidden(&["sc", "query", name]);
    let up = out.to_uppercase();
    if up.contains("RUNNING") {
        ServiceState::Running
    } else if up.contains("STOPPED") {
        ServiceState::Stopped
    } else {
        ServiceState::Unknown
    }
}

pub fn manage_service(name: &str, stop: bool) -> (bool, String) {
    let st = get_service_status(name);
    if st == ServiceState::Unknown {
        return (false, format!("Служба {} отсутствует в этой версии Windows", name));
    }

    if stop {
        if st == ServiceState::Stopped {
            return (true, format!("Служба {} уже остановлена", name));
        }
        let (ok, _) = run_hidden(&["net", "stop", name, "/y"]);
        if ok || get_service_status(name) == ServiceState::Stopped {
            state::add_stopped_service(name);
            return (true, format!("Остановлена служба: {}", name));
        }
        (false, format!("Не удалось остановить {} (защищена системой)", name))
    } else {
        if st == ServiceState::Running {
            state::remove_stopped_service(name);
            return (true, format!("Служба {} уже работает", name));
        }
        let (ok, _) = run_hidden(&["net", "start", name]);
        if ok || get_service_status(name) == ServiceState::Running {
            state::remove_stopped_service(name);
            return (true, format!("Запущена служба: {}", name));
        }
        (false, format!("Не удалось запустить {} (запуск по требованию или отключена)", name))
    }
}

// ==================== ОЧИСТКА МУСОРА И РАЗГРУЗКА ОЗУ ====================

fn dir_size(path: &Path) -> u64 {
    let mut sum = 0u64;
    if let Ok(entries) = fs::read_dir(path) {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() {
                sum += dir_size(&p);
            } else if let Ok(meta) = p.metadata() {
                sum += meta.len();
            }
        }
    }
    sum
}

fn clean_folders<F: Fn(&str) -> bool>(folders: &[PathBuf], filter: Option<F>) -> (usize, f64) {
    let mut count = 0usize;
    let mut bytes = 0u64;

    for folder in folders {
        if !folder.is_dir() {
            continue;
        }
        if let Ok(entries) = fs::read_dir(folder) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if let Some(ref f) = filter {
                    if !f(&name) {
                        continue;
                    }
                }
                let p = entry.path();
                if p.is_file() || p.is_symlink() {
                    let sz = p.metadata().map(|m| m.len()).unwrap_or(0);
                    if fs::remove_file(&p).is_ok() {
                        count += 1;
                        bytes += sz;
                    }
                } else if p.is_dir() && filter.is_none() {
                    let sz = dir_size(&p);
                    if fs::remove_dir_all(&p).is_ok() {
                        count += 1;
                        bytes += sz;
                    }
                }
            }
        }
    }

    let mb = ((bytes as f64) / 1_048_576.0 * 100.0).round() / 100.0;
    (count, mb)
}

pub fn clean_temp_files() -> (usize, f64) {
    let mut dirs = Vec::new();
    if let Ok(t) = env::var("TEMP") {
        dirs.push(PathBuf::from(t));
    }
    let sys_root = env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_string());
    dirs.push(Path::new(&sys_root).join("Temp"));
    clean_folders::<fn(&str) -> bool>(&dirs, None)
}

pub fn clean_shader_cache() -> (usize, f64) {
    let local = PathBuf::from(env::var("LOCALAPPDATA").unwrap_or_default());
    let appdata = PathBuf::from(env::var("APPDATA").unwrap_or_default());
    let dirs = vec![
        local.join("D3DSCache"),
        local.join("NVIDIA").join("DXCache"),
        local.join("NVIDIA").join("GLCache"),
        appdata.join("NVIDIA").join("ComputeCache"),
        local.join("AMD").join("DxCache"),
        local.join("AMD").join("DxcCache"),
        local.join("AMD").join("VkCache"),
        local.join("Intel").join("ShaderCache"),
    ];
    clean_folders::<fn(&str) -> bool>(&dirs, None)
}

pub fn clean_windows_update_cache() -> (usize, f64) {
    let _ = run_hidden(&["net", "stop", "wuauserv", "/y"]);
    let _ = run_hidden(&["net", "stop", "bits", "/y"]);
    let sys_root = env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_string());
    let dir = Path::new(&sys_root).join("SoftwareDistribution").join("Download");
    let res = clean_folders::<fn(&str) -> bool>(&[dir], None);
    let _ = run_hidden(&["net", "start", "bits"]);
    let _ = run_hidden(&["net", "start", "wuauserv"]);
    res
}

pub fn clean_crash_dumps() -> (usize, f64) {
    let root = PathBuf::from(env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_string()));
    let pd = PathBuf::from(env::var("ProgramData").unwrap_or_else(|_| r"C:\ProgramData".to_string()));
    let local = PathBuf::from(env::var("LOCALAPPDATA").unwrap_or_default());
    let dirs = vec![
        root.join("Minidump"),
        root.join("LiveKernelReports"),
        local.join("CrashDumps"),
        pd.join(r"Microsoft\Windows\WER\ReportArchive"),
        pd.join(r"Microsoft\Windows\WER\ReportQueue"),
        local.join(r"Microsoft\Windows\WER\ReportArchive"),
        local.join(r"Microsoft\Windows\WER\ReportQueue"),
    ];
    clean_folders::<fn(&str) -> bool>(&dirs, None)
}

pub fn clean_browser_cache() -> (usize, f64) {
    let local = PathBuf::from(env::var("LOCALAPPDATA").unwrap_or_default());
    let dirs = vec![
        local.join(r"Google\Chrome\User Data\Default\Cache\Cache_Data"),
        local.join(r"Google\Chrome\User Data\Default\Code Cache\js"),
        local.join(r"Google\Chrome\User Data\Default\GPUCache"),
        local.join(r"Microsoft\Edge\User Data\Default\Cache\Cache_Data"),
        local.join(r"Microsoft\Edge\User Data\Default\Code Cache\js"),
        local.join(r"Microsoft\Edge\User Data\Default\GPUCache"),
        local.join(r"BraveSoftware\Brave-Browser\User Data\Default\Cache\Cache_Data"),
        local.join(r"Yandex\YandexBrowser\User Data\Default\Cache\Cache_Data"),
        local.join(r"Opera Software\Opera Stable\Cache\Cache_Data"),
        local.join(r"Opera Software\Opera GX Stable\Cache\Cache_Data"),
    ];
    clean_folders::<fn(&str) -> bool>(&dirs, None)
}

pub fn clean_logs_and_thumbs() -> (usize, f64) {
    let root = PathBuf::from(env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_string()));
    let local = PathBuf::from(env::var("LOCALAPPDATA").unwrap_or_default());
    let (c1, m1) = clean_folders::<fn(&str) -> bool>(
        &[
            root.join(r"Logs\CBS"),
            root.join(r"Logs\DISM"),
            root.join(r"Logs\MoSetup"),
        ],
        None,
    );
    let exp = local.join(r"Microsoft\Windows\Explorer");
    let (c2, m2) = clean_folders(&[exp], Some(|name: &str| name.to_lowercase().starts_with("thumbcache_")));
    (c1 + c2, ((m1 + m2) * 100.0).round() / 100.0)
}

pub fn empty_recycle_bin() -> bool {
    unsafe {
        let res = SHEmptyRecycleBinW(
            std::ptr::null_mut(),
            std::ptr::null(),
            SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND,
        );
        res == 0 || (res as u32) == 0x8000FFFF
    }
}

pub fn flush_dns_cache() -> bool {
    run_hidden(&["ipconfig", "/flushdns"]).0
}

pub fn reset_network_stack() -> (bool, bool) {
    let (r1, _) = run_hidden(&["netsh", "winsock", "reset"]);
    let (r2, _) = run_hidden(&["netsh", "int", "ip", "reset"]);
    let _ = run_hidden(&["netsh", "winhttp", "reset", "proxy"]);
    (r1, r2)
}

pub fn create_restore_point() -> (bool, String) {
    let ps = "$ErrorActionPreference='Stop'; \
              try { Enable-ComputerRestore -Drive \"$env:SystemDrive\\\" } catch {}; \
              New-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' \
              -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null; \
              Checkpoint-Computer -Description 'WinOptimizer Pro (Rust)' -RestorePointType MODIFY_SETTINGS; \
              Write-Output 'OK'";
    let (ok, out) = run_powershell(ps);
    if ok && out.contains("OK") {
        (true, "Точка восстановления системы успешно создана.".to_string())
    } else {
        let first_line = out.lines().next().unwrap_or("служба восстановления отключена");
        (false, format!("Не удалось создать точку восстановления: {}", first_line))
    }
}

pub fn optimize_ram_workingset() -> (usize, f64) {
    let before = get_ram_info().avail_mb;
    let mut pids = [0u32; 4096];
    let mut bytes_returned = 0u32;
    let mut count_optimized = 0usize;

    unsafe {
        if EnumProcesses(
            pids.as_mut_ptr(),
            std::mem::size_of_val(&pids) as u32,
            &mut bytes_returned,
        ) != 0
        {
            let num = (bytes_returned as usize) / std::mem::size_of::<u32>();
            for &pid in &pids[..num] {
                if pid == 0 {
                    continue;
                }
                let h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, 0, pid);
                if !h.is_null() {
                    if EmptyWorkingSet(h) != 0 {
                        count_optimized += 1;
                    }
                    CloseHandle(h);
                }
            }
        }
    }

    let after = get_ram_info().avail_mb;
    let freed = ((after - before).max(0.0) * 10.0).round() / 10.0;
    (count_optimized, freed)
}

pub fn restart_explorer() -> bool {
    let _ = run_hidden(&["taskkill", "/f", "/im", "explorer.exe"]);
    Command::new("explorer.exe").spawn().is_ok()
}

pub fn generate_battery_report() -> (bool, String) {
    let dir = logs_dir();
    let _ = fs::create_dir_all(&dir);
    let report = dir.join("battery_report.html");
    let report_str = report.to_string_lossy().to_string();
    let (ok, _) = run_hidden(&["powercfg", "/batteryreport", "/output", &report_str]);
    if ok && report.is_file() {
        open_system_tool(&report_str);
        (true, format!("Отчёт о батарее сохранён и открыт: {}", report_str))
    } else {
        (false, "Аккумулятор не найден (доступно только на ноутбуках).".to_string())
    }
}

pub fn open_system_tool(cmd: &str) -> bool {
    if cmd.is_empty() {
        return false;
    }
    match cmd {
        "special:hosts" => {
            let root = env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_string());
            let hosts = Path::new(&root).join(r"System32\drivers\etc\hosts");
            return Command::new("notepad.exe").arg(hosts).spawn().is_ok();
        }
        "special:sfc" => {
            return Command::new("cmd.exe")
                .args(["/k", "title Проверка целостности Windows (SFC) & sfc /scannow"])
                .spawn()
                .is_ok();
        }
        "special:dism" => {
            return Command::new("cmd.exe")
                .args([
                    "/k",
                    "title Восстановление образа Windows (DISM) & DISM.exe /Online /Cleanup-image /Restorehealth",
                ])
                .spawn()
                .is_ok();
        }
        "special:battery" => {
            return generate_battery_report().0;
        }
        _ => {}
    }

    let verb = to_wide("open");
    let file = to_wide(cmd);
    let res = unsafe {
        ShellExecuteW(
            std::ptr::null_mut(),
            verb.as_ptr(),
            file.as_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            SW_SHOWNORMAL as i32,
        )
    };
    if (res as isize) > 32 {
        return true;
    }
    Command::new("cmd.exe").args(["/c", "start", "", cmd]).creation_flags(CREATE_NO_WINDOW).spawn().is_ok()
}
