use winreg::enums::*;
use winreg::RegKey;

use crate::state::{self, SavedRegEntry};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Hive {
    Hkcu,
    Hklm,
}

impl Hive {
    pub fn root(self) -> RegKey {
        match self {
            Hive::Hkcu => RegKey::predef(HKEY_CURRENT_USER),
            Hive::Hklm => RegKey::predef(HKEY_LOCAL_MACHINE),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Hive::Hkcu => "HKCU",
            Hive::Hklm => "HKLM",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum RegVal {
    Dword(u32),
    Sz(&'static str),
}

fn key_id(hive: Hive, path: &str, name: &str) -> String {
    format!("{}\\{}::{}", hive.name(), path, name)
}

pub fn get_dword(hive: Hive, path: &str, name: &str) -> Option<u32> {
    let key = hive
        .root()
        .open_subkey_with_flags(path, KEY_READ | KEY_WOW64_64KEY)
        .ok()?;
    key.get_value::<u32, _>(name).ok()
}

pub fn get_sz(hive: Hive, path: &str, name: &str) -> Option<String> {
    let key = hive
        .root()
        .open_subkey_with_flags(path, KEY_READ | KEY_WOW64_64KEY)
        .ok()?;
    key.get_value::<String, _>(name).ok()
}

fn backup_value(hive: Hive, path: &str, name: &str) {
    let id = key_id(hive, path, name);
    if let Some(v) = get_dword(hive, path, name) {
        state::remember_reg(
            &id,
            SavedRegEntry {
                kind: Some(4), // REG_DWORD
                value: Some(serde_json::json!(v)),
            },
        );
    } else if let Some(s) = get_sz(hive, path, name) {
        state::remember_reg(
            &id,
            SavedRegEntry {
                kind: Some(1), // REG_SZ
                value: Some(serde_json::json!(s)),
            },
        );
    } else {
        state::remember_reg(
            &id,
            SavedRegEntry {
                kind: None,
                value: None,
            },
        );
    }
}

pub fn raw_set_dword(hive: Hive, path: &str, name: &str, val: u32) -> Result<(), String> {
    let (key, _) = hive
        .root()
        .create_subkey_with_flags(path, KEY_SET_VALUE | KEY_WOW64_64KEY)
        .map_err(|e| e.to_string())?;
    key.set_value(name, &val).map_err(|e| e.to_string())
}

pub fn raw_set_sz(hive: Hive, path: &str, name: &str, val: &str) -> Result<(), String> {
    let (key, _) = hive
        .root()
        .create_subkey_with_flags(path, KEY_SET_VALUE | KEY_WOW64_64KEY)
        .map_err(|e| e.to_string())?;
    key.set_value(name, &val).map_err(|e| e.to_string())
}

pub fn raw_delete(hive: Hive, path: &str, name: &str) {
    if let Ok(key) = hive
        .root()
        .open_subkey_with_flags(path, KEY_SET_VALUE | KEY_WOW64_64KEY)
    {
        let _ = key.delete_value(name);
    }
}

pub fn set_val(hive: Hive, path: &str, name: &str, val: RegVal) -> Result<(), String> {
    backup_value(hive, path, name);
    match val {
        RegVal::Dword(v) => raw_set_dword(hive, path, name, v),
        RegVal::Sz(s) => raw_set_sz(hive, path, name, s),
    }
}

pub fn restore_val(hive: Hive, path: &str, name: &str, fallback: Option<RegVal>) -> String {
    let id = key_id(hive, path, name);
    if let Some(saved) = state::take_reg(&id) {
        match (saved.kind, saved.value) {
            (Some(4), Some(v)) => {
                if let Some(num) = v.as_u64() {
                    let _ = raw_set_dword(hive, path, name, num as u32);
                    return format!("{}", num);
                }
            }
            (Some(1), Some(v)) => {
                if let Some(s) = v.as_str() {
                    let _ = raw_set_sz(hive, path, name, s);
                    return s.to_string();
                }
            }
            _ => {
                raw_delete(hive, path, name);
                return "по умолчанию Windows (удалено)".to_string();
            }
        }
    }

    match fallback {
        Some(RegVal::Dword(v)) => {
            let _ = raw_set_dword(hive, path, name, v);
            if v > 0xFFFF {
                format!("0x{:X}", v)
            } else {
                v.to_string()
            }
        }
        Some(RegVal::Sz(s)) => {
            let _ = raw_set_sz(hive, path, name, s);
            s.to_string()
        }
        None => {
            raw_delete(hive, path, name);
            "по умолчанию Windows (удалено)".to_string()
        }
    }
}

pub fn key_exists(hive: Hive, path: &str) -> bool {
    hive.root()
        .open_subkey_with_flags(path, KEY_READ | KEY_WOW64_64KEY)
        .is_ok()
}

pub fn delete_tree(hive: Hive, path: &str) {
    let _ = hive.root().delete_subkey_all(path);
}

pub fn subkeys(hive: Hive, path: &str) -> Vec<String> {
    if let Ok(key) = hive
        .root()
        .open_subkey_with_flags(path, KEY_READ | KEY_WOW64_64KEY)
    {
        key.enum_keys().filter_map(|k| k.ok()).collect()
    } else {
        Vec::new()
    }
}
