use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};

use crate::models::backup_dir;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedRegEntry {
    pub kind: Option<i32>,
    pub value: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct WallpaperBackup {
    pub saved: bool,
    pub active: bool,
    pub original_path: String,
    pub backup_file: String,
    pub style: String,
    pub tile: String,
    pub background: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StateData {
    #[serde(default)]
    pub registry: HashMap<String, SavedRegEntry>,
    #[serde(default)]
    pub stopped_services: Vec<String>,
    #[serde(default)]
    pub wallpaper: Option<WallpaperBackup>,
    #[serde(default)]
    pub commands: HashMap<String, String>,
}

static STATE: OnceLock<Mutex<StateData>> = OnceLock::new();

fn state_path() -> PathBuf {
    backup_dir().join("state.json")
}

fn get_mutex() -> &'static Mutex<StateData> {
    STATE.get_or_init(|| {
        let path = state_path();
        let data = fs::read_to_string(&path)
            .ok()
            .and_then(|s| serde_json::from_str::<StateData>(&s).ok())
            .unwrap_or_default();
        Mutex::new(data)
    })
}

fn save_locked(data: &StateData) {
    let dir = backup_dir();
    let _ = fs::create_dir_all(&dir);
    let path = state_path();
    let tmp = path.with_extension("json.tmp");
    if let Ok(json) = serde_json::to_string_pretty(data) {
        if fs::write(&tmp, json).is_ok() {
            let _ = fs::rename(&tmp, &path);
        }
    }
}

pub fn remember_reg(key_id: &str, entry: SavedRegEntry) {
    if let Ok(mut guard) = get_mutex().lock() {
        if !guard.registry.contains_key(key_id) {
            guard.registry.insert(key_id.to_string(), entry);
            save_locked(&guard);
        }
    }
}

pub fn take_reg(key_id: &str) -> Option<SavedRegEntry> {
    if let Ok(mut guard) = get_mutex().lock() {
        let removed = guard.registry.remove(key_id);
        if removed.is_some() {
            save_locked(&guard);
        }
        return removed;
    }
    None
}

pub fn remember_cmd(key: &str, value: &str) {
    if let Ok(mut guard) = get_mutex().lock() {
        if !guard.commands.contains_key(key) {
            guard.commands.insert(key.to_string(), value.to_string());
            save_locked(&guard);
        }
    }
}

pub fn lookup_cmd(key: &str) -> Option<String> {
    get_mutex()
        .lock()
        .ok()
        .and_then(|g| g.commands.get(key).cloned())
}

pub fn forget_cmd(key: &str) {
    if let Ok(mut guard) = get_mutex().lock() {
        if guard.commands.remove(key).is_some() {
            save_locked(&guard);
        }
    }
}

pub fn add_stopped_service(name: &str) {
    if let Ok(mut guard) = get_mutex().lock() {
        if !guard.stopped_services.iter().any(|s| s == name) {
            guard.stopped_services.push(name.to_string());
            save_locked(&guard);
        }
    }
}

pub fn remove_stopped_service(name: &str) {
    if let Ok(mut guard) = get_mutex().lock() {
        let len_before = guard.stopped_services.len();
        guard.stopped_services.retain(|s| s != name);
        if guard.stopped_services.len() != len_before {
            save_locked(&guard);
        }
    }
}

pub fn get_stopped_services() -> Vec<String> {
    get_mutex()
        .lock()
        .ok()
        .map(|g| g.stopped_services.clone())
        .unwrap_or_default()
}

pub fn get_wallpaper() -> Option<WallpaperBackup> {
    get_mutex()
        .lock()
        .ok()
        .and_then(|g| g.wallpaper.clone())
}

pub fn set_wallpaper(wp: WallpaperBackup) {
    if let Ok(mut guard) = get_mutex().lock() {
        guard.wallpaper = Some(wp);
        save_locked(&guard);
    }
}
