use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceItem {
    pub name: String,
    pub title: String,
    pub description: String,
    #[serde(default)]
    pub recommended: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TweakItem {
    pub id: String,
    pub title: String,
    pub description: String,
    pub category: String,
    #[serde(default)]
    pub recommended: bool,
    #[serde(default)]
    pub reboot: bool,
    #[serde(default)]
    pub profile: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArticleItem {
    pub id: String,
    pub title: String,
    pub tag: String,
    #[serde(default)]
    pub action_label: String,
    #[serde(default)]
    pub action_cmd: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolEntry {
    pub title: String,
    pub cmd: String,
    pub desc: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCategory {
    pub category: String,
    pub items: Vec<ToolEntry>,
}

#[derive(Debug, Clone)]
pub struct AppDataConfig {
    pub services: Vec<ServiceItem>,
    pub tweaks: Vec<TweakItem>,
    pub articles: Vec<ArticleItem>,
    pub tools: Vec<ToolCategory>,
}

// Встроенные JSON-данные (позволяют запускать скомпилированный .exe автономно в любом месте)
const EMBEDDED_SERVICES: &str = include_str!("../data/services.json");
const EMBEDDED_TWEAKS: &str = include_str!("../data/tweaks.json");
const EMBEDDED_ARTICLES: &str = include_str!("../data/articles.json");
const EMBEDDED_TOOLS: &str = include_str!("../data/tools.json");

pub fn app_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

pub fn data_dir() -> PathBuf {
    let local = app_dir().join("data");
    if local.is_dir() {
        return local;
    }
    PathBuf::from("data")
}

pub fn backup_dir() -> PathBuf {
    app_dir().join("backup")
}

pub fn logs_dir() -> PathBuf {
    app_dir().join("logs")
}

fn load_or_embedded<T: for<'de> Deserialize<'de>>(filename: &str, embedded: &str) -> Vec<T> {
    let path = data_dir().join(filename);
    if let Ok(text) = fs::read_to_string(&path) {
        if let Ok(parsed) = serde_json::from_str::<Vec<T>>(&text) {
            if !parsed.is_empty() {
                return parsed;
            }
        }
    }
    serde_json::from_str::<Vec<T>>(embedded).unwrap_or_default()
}

pub fn load_app_data() -> AppDataConfig {
    AppDataConfig {
        services: load_or_embedded("services.json", EMBEDDED_SERVICES),
        tweaks: load_or_embedded("tweaks.json", EMBEDDED_TWEAKS),
        articles: load_or_embedded("articles.json", EMBEDDED_ARTICLES),
        tools: load_or_embedded("tools.json", EMBEDDED_TOOLS),
    }
}
