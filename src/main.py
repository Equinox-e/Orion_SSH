"""
OrionSSH - tabbed SSH/Telnet/Serial client for Windows.

Version 1.6 focuses on real terminal input: no command entry field,
keyboard shortcuts go directly to the remote PTY, and pyte is used to render
ANSI/TUI programs such as nano, vim and htop.
"""
from __future__ import annotations

import json
import os
import posixpath
import queue
import re
import socket
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, messagebox, ttk, simpledialog, colorchooser
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Tkinter is required. Install official Python for Windows.") from exc

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES  # type: ignore
    BASE_TK = TkinterDnD.Tk
except Exception:  # pragma: no cover
    TkinterDnD = None  # type: ignore
    DND_FILES = None  # type: ignore
    BASE_TK = tk.Tk

try:
    import paramiko
except Exception:  # pragma: no cover
    paramiko = None  # type: ignore

try:
    import pyte
except Exception:  # pragma: no cover
    pyte = None  # type: ignore

try:
    import keyring
except Exception:  # pragma: no cover
    keyring = None  # type: ignore

APP_NAME = "OrionSSH"
APP_VERSION = "1.0.0"
SERVICE_NAME = "OrionSSH"
DEFAULT_LANGUAGE = "en"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 20)
FONT_MONO_FAMILY = "Cascadia Mono"

THEMES: dict[str, dict[str, str]] = {
    "midnight": {
        "name": "Полночь", "bg": "#0b1220", "surface": "#111827", "surface2": "#172033",
        "surface3": "#1f2a44", "accent": "#38bdf8", "accent2": "#7dd3fc", "text": "#e5e7eb",
        "muted": "#94a3b8", "danger": "#fb7185", "success": "#34d399", "border": "#5a6d95",
        "term_bg": "#050816", "term_fg": "#d1d5db",
    },
    "graphite": {
        "name": "Графит", "bg": "#111111", "surface": "#1b1b1f", "surface2": "#24242a",
        "surface3": "#303039", "accent": "#a3e635", "accent2": "#bef264", "text": "#f3f4f6",
        "muted": "#a1a1aa", "danger": "#f87171", "success": "#4ade80", "border": "#73737d",
        "term_bg": "#080808", "term_fg": "#e4e4e7",
    },
    "nord": {
        "name": "Север", "bg": "#2e3440", "surface": "#3b4252", "surface2": "#434c5e",
        "surface3": "#4c566a", "accent": "#88c0d0", "accent2": "#8fbcbb", "text": "#eceff4",
        "muted": "#d8dee9", "danger": "#bf616a", "success": "#a3be8c", "border": "#81a1c1",
        "term_bg": "#242933", "term_fg": "#eceff4",
    },
    "dracula": {
        "name": "Дракула", "bg": "#282a36", "surface": "#343746", "surface2": "#3d4053",
        "surface3": "#44475a", "accent": "#bd93f9", "accent2": "#ff79c6", "text": "#f8f8f2",
        "muted": "#cfcfe6", "danger": "#ff5555", "success": "#50fa7b", "border": "#8be9fd",
        "term_bg": "#1e1f29", "term_fg": "#f8f8f2",
    },
    "solarized": {
        "name": "Solarized Dark", "bg": "#002b36", "surface": "#073642", "surface2": "#0b3f4d",
        "surface3": "#124b5b", "accent": "#268bd2", "accent2": "#2aa198", "text": "#eee8d5",
        "muted": "#93a1a1", "danger": "#dc322f", "success": "#859900", "border": "#839496",
        "term_bg": "#001f27", "term_fg": "#eee8d5",
    },
}

C = dict(THEMES["midnight"])

def apply_colors(settings: Optional["AppSettings"] = None) -> None:
    global C
    theme_id = settings.theme if settings else "midnight"
    if theme_id == "custom":
        base = dict(THEMES["midnight"])
        base.update(getattr(settings, "custom_colors", {}) or {})
        C = base
    else:
        C = dict(THEMES.get(theme_id, THEMES["midnight"]))



CURRENT_LANGUAGE = DEFAULT_LANGUAGE

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "home": "Главная", "sessions": "Подключения", "new": "+ Новое", "settings": "Настройки",
        "contacts": "Контакты", "search": "Поиск", "connect": "Подключить", "save": "Сохранить",
        "save_connect": "Сохранить и подключить", "cancel": "Закрыть", "delete": "Удалить", "edit": "Изменить",
        "quick": "Быстрое подключение", "host": "Хост / IP", "port": "Порт", "username": "Пользователь",
        "protocol": "Протокол", "name": "Название", "password": "Пароль", "save_password": "Сохранить пароль в Windows Credential Manager",
        "auth": "Тип входа", "key_path": "Приватный ключ", "browse": "Обзор", "group": "Группа",
        "all_groups": "Все группы", "group_filter": "Фильтр по группе", "add_new_group": "Добавить новую группу…", "new_group_placeholder": "Название новой группы", "create_group": "Добавить", "move_up": "Вверх", "move_down": "Вниз",
        "group_color": "Цвет группы", "favorite": "Избранное", "tags": "Теги через запятую", "start_dir": "Начальная папка",
        "notes": "Заметки", "tunnels": "SSH tunnels / port forwarding", "tunnels_hint": "Формат: L 127.0.0.1:8080 127.0.0.1:80 или 8080 -> 127.0.0.1:80",
        "serial_port": "Serial-порт", "serial_baud": "Baud rate", "terminal_hint": "Кликните в терминал и печатайте как в PuTTY. Ctrl+C/Ctrl+X/Ctrl+O отправляются на сервер. Ctrl+Shift+C / Ctrl+Shift+X — копировать, Ctrl+Shift+V / Shift+Insert — вставить. В TUI-программах колесо мыши отправляет стрелки вверх/вниз на сервер.",
        "split_horizontal": "Разделить ↔", "split_vertical": "Разделить ↕", "split_title": "Рабочая область",
        "split_workspace": "Split workspace", "split_2_columns": "2 колонки", "split_2_rows": "2 строки", "split_4": "4 панели",
        "select_session": "Выберите подключение", "open_in_pane": "Открыть", "replace_pane": "Заменить", "empty_pane": "Панель свободна",
        "files": "Файлы", "disconnect": "Отключить", "reconnect": "Переподключить", "clear": "Очистить",
        "copy": "Копировать", "paste": "Вставить", "connected": "Подключено", "connecting": "Подключение…",
        "offline": "Отключено", "not_connected": "Нет подключения", "password_prompt": "Пароль для {user}@{host}",
        "passphrase_prompt": "Passphrase для ключа {name}", "cred_ok": "Пароль сохранён в Windows Credential Manager.",
        "cred_unavailable": "keyring недоступен, пароль сохранён только на время запуска.",
        "connection_failed": "Ошибка подключения: {error}", "dns_error": "DNS-ошибка: {error}", "disconnected": "Соединение прервано.",
        "auto_reconnect": "Автопереподключение через {seconds} сек…", "auto_reconnect_now": "Переподключаюсь…",
        "ssh_missing": "Paramiko не установлен.", "pyte_missing": "Pyte не установлен: TUI-режим будет ограничен.",
        "file_browser": "Файлы сервера", "path": "Путь", "up": "↑ Вверх", "refresh": "Обновить", "go": "Перейти",
        "name_col": "Имя", "type_col": "Тип", "size_col": "Размер", "modified_col": "Изменено",
        "open_folder": "Открыть", "download": "Скачать", "upload": "Загрузить сюда", "new_folder": "Новая папка", "create": "Создать",
        "folder": "Папка", "file": "Файл", "select_file": "Выберите файл", "select_folder": "Выберите папку или файл",
        "drop_hint": "Можно перетащить файл из Проводника в список SFTP.", "dnd_off": "Drag-and-drop недоступен: установите tkinterdnd2.",
        "settings_title": "Настройки приложения", "theme": "Тема", "custom_theme": "Своя тема", "font_size": "Размер шрифта терминала",
        "connect_timeout": "Timeout подключения", "auth_timeout": "Timeout авторизации", "keepalive": "Keepalive, сек", "reconnect_delay": "Задержка reconnect, сек",
        "encoding": "Кодировка терминала", "animations": "Плавные эффекты", "custom_colors": "Палитра цветов", "color_palette_hint": "Выбирайте цвета из палитры. При выборе цвета тема автоматически переключается на «Своя тема». HEX вводить не нужно.", "more_colors": "Другая…", "language": "Язык", "language_hint": "English is the default. Полностью применится после перезапуска.",
        "support_title": "Поддержка и контакты", "support_body": "Встроенные контакты поддержки. Если рядом с программой есть contacts.json, приложение использует данные из него.",
        "email": "Почта", "telegram": "Telegram-бот", "website": "Сайт", "copied": "Скопировано.",
        "welcome_title": "OrionSSH", "welcome_body": "SSH-клиент с вкладками, TUI-терминалом, SFTP, защищёнными паролями и туннелями.",
        "dashboard": "Обзор", "total_sessions": "Подключений", "favorites_count": "В избранном", "groups_count": "Групп", "presets_count": "Пресетов",
        "recent_sessions": "Последние подключения", "quick_actions": "Быстрые действия", "tip_title": "Подсказка",
        "tip_text": "Дважды кликните по карточке слева или нажмите ▶. Кнопка ⧉ открывает вторую вкладку того же сервера.",
        "no_sessions": "Пока нет сохранённых подключений.", "required": "Название и хост обязательны.", "bad_port": "Порт должен быть числом от 1 до 65535.",
        "import": "Импорт", "export": "Экспорт", "imported": "Импортировано: {count}", "exported": "Экспортировано.",
        "delete_confirm": "Удалить подключение «{name}»?", "rdp_launch": "Открываю mstsc.exe для {host}:{port}",
        "rdp_hint": "RDP запускается через штатный клиент Windows. Встроить полноценную RDP-сессию в Tkinter нельзя без отдельного ActiveX/FreeRDP-компонента.",
        "telnet_hint": "Telnet без шифрования. Используйте только в доверенной сети.", "serial_hint": "Для Serial нужен pyserial и корректный COM-порт, например COM3.",
        "tunnel_started": "Туннель: {local} → {remote}", "tunnel_failed": "Не удалось поднять туннель {line}: {error}",
        "scp_drop_started": "Загрузка: {name} → {remote}", "upload_done": "Загружено: {remote}", "download_done": "Скачано: {local}",
        "error": "Ошибка: {error}", "new_session": "Новое подключение", "edit_session": "Редактирование подключения",
        "private_key": "Приватный ключ", "saved_restart": "Сохранено. Изменения интерфейса полностью применятся после перезапуска.",
        "open_new_tab": "Новое окно", "tab_already_open": "Подключение уже открыто, перехожу к вкладке.",
        "presets": "Пресеты", "command_presets": "Пресеты команд", "preset_name": "Название пресета", "commands": "Команды",
        "one_per_line": "Одна команда на строку. При запуске каждая строка отправляется с Enter.",
        "add_preset": "Добавить пресет", "update_preset": "Обновить", "delete_preset": "Удалить", "run_preset": "Выполнить",
        "preset_required": "Укажите название и хотя бы одну команду.", "preset_saved": "Пресет сохранён.", "preset_deleted": "Пресет удалён.",
        "no_presets": "Нет пресетов", "select_preset": "Выберите пресет", "preset_sent": "Пресет отправлен: {name}",
    },
    "en": {
        "home": "Home", "sessions": "Sessions", "new": "+ New", "settings": "Settings",
        "contacts": "Contacts", "search": "Search", "connect": "Connect", "save": "Save",
        "save_connect": "Save and connect", "cancel": "Close", "delete": "Delete", "edit": "Edit",
        "quick": "Quick connect", "host": "Host / IP", "port": "Port", "username": "Username",
        "protocol": "Protocol", "name": "Name", "password": "Password", "save_password": "Save password in Windows Credential Manager",
        "auth": "Auth type", "key_path": "Private key", "browse": "Browse", "group": "Group",
        "all_groups": "All groups", "group_filter": "Group filter", "add_new_group": "Add new group…", "new_group_placeholder": "New group name", "create_group": "Add", "move_up": "Up", "move_down": "Down",
        "group_color": "Group color", "favorite": "Favorite", "tags": "Tags, comma-separated", "start_dir": "Start directory",
        "notes": "Notes", "tunnels": "SSH tunnels / port forwarding", "tunnels_hint": "Format: L 127.0.0.1:8080 127.0.0.1:80 or 8080 -> 127.0.0.1:80",
        "serial_port": "Serial port", "serial_baud": "Baud rate", "terminal_hint": "Click the terminal and type like in PuTTY. Ctrl+C/Ctrl+X/Ctrl+O are sent to the server. Ctrl+Shift+C / Ctrl+Shift+X copies, Ctrl+Shift+V / Shift+Insert pastes. In TUI apps, the mouse wheel sends up/down arrows to the server.",
        "split_horizontal": "Split ↔", "split_vertical": "Split ↕", "split_title": "Workspace",
        "split_workspace": "Split workspace", "split_2_columns": "2 columns", "split_2_rows": "2 rows", "split_4": "4 panes",
        "select_session": "Select session", "open_in_pane": "Open", "replace_pane": "Replace", "empty_pane": "Empty pane",
        "files": "Files", "disconnect": "Disconnect", "reconnect": "Reconnect", "clear": "Clear",
        "copy": "Copy", "paste": "Paste", "connected": "Connected", "connecting": "Connecting…",
        "offline": "Offline", "not_connected": "Not connected", "password_prompt": "Password for {user}@{host}",
        "passphrase_prompt": "Passphrase for key {name}", "cred_ok": "Password saved in Windows Credential Manager.",
        "cred_unavailable": "keyring is unavailable; the password is kept only for this run.",
        "connection_failed": "Connection failed: {error}", "dns_error": "DNS error: {error}", "disconnected": "Connection lost.",
        "auto_reconnect": "Auto reconnect in {seconds}s…", "auto_reconnect_now": "Reconnecting…",
        "ssh_missing": "Paramiko is not installed.", "pyte_missing": "Pyte is not installed: TUI support will be limited.",
        "file_browser": "Server files", "path": "Path", "up": "↑ Up", "refresh": "Refresh", "go": "Go",
        "name_col": "Name", "type_col": "Type", "size_col": "Size", "modified_col": "Modified",
        "open_folder": "Open", "download": "Download", "upload": "Upload here", "new_folder": "New folder", "create": "Create",
        "folder": "Folder", "file": "File", "select_file": "Select a file", "select_folder": "Select a folder or file",
        "drop_hint": "Drag a file from Explorer into the SFTP list.", "dnd_off": "Drag-and-drop is unavailable: install tkinterdnd2.",
        "settings_title": "Application settings", "theme": "Theme", "custom_theme": "Custom theme", "font_size": "Terminal font size",
        "connect_timeout": "Connection timeout", "auth_timeout": "Auth timeout", "keepalive": "Keepalive, sec", "reconnect_delay": "Reconnect delay, sec",
        "encoding": "Terminal encoding", "animations": "Smooth effects", "custom_colors": "Color palette", "color_palette_hint": "Pick colors from the palette. Selecting any color automatically switches the theme to Custom theme. No HEX input is needed.", "more_colors": "Other…", "language": "Language", "language_hint": "English is the default. Full UI refresh requires restart.",
        "support_title": "Support and contacts", "support_body": "Built-in support contacts. If contacts.json exists next to the app, OrionSSH will use it instead.",
        "email": "Email", "telegram": "Telegram bot", "website": "Website", "copied": "Copied.",
        "welcome_title": "OrionSSH", "welcome_body": "Tabbed SSH client with TUI terminal, SFTP, protected passwords and tunneling.",
        "dashboard": "Dashboard", "total_sessions": "Sessions", "favorites_count": "Favorites", "groups_count": "Groups", "presets_count": "Presets",
        "recent_sessions": "Recent sessions", "quick_actions": "Quick actions", "tip_title": "Tip",
        "tip_text": "Double-click a card on the left or press ▶. The ⧉ button opens a second tab for the same server.",
        "no_sessions": "No saved sessions yet.", "required": "Name and host are required.", "bad_port": "Port must be a number from 1 to 65535.",
        "import": "Import", "export": "Export", "imported": "Imported: {count}", "exported": "Exported.",
        "delete_confirm": "Delete session “{name}”?", "rdp_launch": "Opening mstsc.exe for {host}:{port}",
        "rdp_hint": "RDP is launched via the standard Windows client. A full embedded RDP session in Tkinter requires a separate ActiveX/FreeRDP component.",
        "telnet_hint": "Telnet is not encrypted. Use it only on a trusted network.", "serial_hint": "Serial requires pyserial and a valid COM port, for example COM3.",
        "tunnel_started": "Tunnel: {local} → {remote}", "tunnel_failed": "Failed to start tunnel {line}: {error}",
        "scp_drop_started": "Uploading: {name} → {remote}", "upload_done": "Uploaded: {remote}", "download_done": "Downloaded: {local}",
        "error": "Error: {error}", "new_session": "New session", "edit_session": "Edit session",
        "private_key": "Private key", "saved_restart": "Saved. UI changes will fully apply after restart.",
        "open_new_tab": "New window", "tab_already_open": "This session is already open; switching to its tab.",
        "presets": "Presets", "command_presets": "Command presets", "preset_name": "Preset name", "commands": "Commands",
        "one_per_line": "One command per line. Each line is sent with Enter.",
        "add_preset": "Add preset", "update_preset": "Update", "delete_preset": "Delete", "run_preset": "Run",
        "preset_required": "Enter a preset name and at least one command.", "preset_saved": "Preset saved.", "preset_deleted": "Preset deleted.",
        "no_presets": "No presets", "select_preset": "Select preset", "preset_sent": "Preset sent: {name}",
    },
}

def t(key: str, **kwargs: Any) -> str:
    lang = CURRENT_LANGUAGE if CURRENT_LANGUAGE in TRANSLATIONS else DEFAULT_LANGUAGE
    text = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS["en"].get(key) or TRANSLATIONS["ru"].get(key) or key
    return text.format(**kwargs) if kwargs else text

def app_data_dir() -> Path:
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parents[1] / relative


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def is_hex(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()))


COLOR_PALETTE = [
    "#050816", "#0b1220", "#111827", "#172033", "#1f2937", "#374151", "#6b7280", "#9ca3af",
    "#d1d5db", "#e5e7eb", "#f3f4f6", "#ffffff", "#002b36", "#073642", "#2e3440", "#3b4252",
    "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16", "#22c55e", "#10b981", "#14b8a6",
    "#06b6d4", "#0ea5e9", "#38bdf8", "#3b82f6", "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
    "#ec4899", "#f43f5e", "#fb7185", "#7dd3fc", "#88c0d0", "#bd93f9", "#ff79c6", "#50fa7b",
    "#34d399", "#2aa198", "#268bd2", "#859900", "#dc322f", "#a3e635", "#eee8d5", "#000000",
]

COLOR_ROLE_NAMES = {
    "ru": {
        "bg": "Фон приложения", "surface": "Основные панели", "surface2": "Поля и карточки", "surface3": "Активные элементы",
        "accent": "Акцент / главные кнопки", "text": "Основной текст", "border": "Границы",
        "term_bg": "Фон терминала", "term_fg": "Текст терминала",
    },
    "en": {
        "bg": "App background", "surface": "Main panels", "surface2": "Fields and cards", "surface3": "Active elements",
        "accent": "Accent / primary buttons", "text": "Main text", "border": "Borders",
        "term_bg": "Terminal background", "term_fg": "Terminal text",
    },
}

def color_role_name(key: str) -> str:
    lang = CURRENT_LANGUAGE if CURRENT_LANGUAGE in COLOR_ROLE_NAMES else DEFAULT_LANGUAGE
    return COLOR_ROLE_NAMES.get(lang, COLOR_ROLE_NAMES[DEFAULT_LANGUAGE]).get(key, key)


@dataclass
class Session:
    id: str
    name: str
    host: str
    port: int = 22
    username: str = ""
    password: str = ""  # legacy only; not saved from v1.6 onward
    auth_mode: str = "password"  # password/key/agent
    key_path: str = ""
    start_dir: str = ""
    group: str = "Основные"
    color: str = "#38bdf8"
    notes: str = ""
    protocol: str = "ssh"  # ssh/telnet/rdp/serial
    tags: str = ""
    favorite: bool = False
    group_color: str = "#38bdf8"
    order: int = 0
    group_order: int = 0
    save_password: bool = False
    tunnels: str = ""
    serial_port: str = ""
    serial_baud: int = 9600

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        valid = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in valid}
        if not clean.get("id"):
            clean["id"] = uuid.uuid4().hex
        if not clean.get("protocol"):
            clean["protocol"] = "ssh"
        if "group_color" not in clean and "color" in clean:
            clean["group_color"] = clean.get("color") or "#38bdf8"
        try:
            clean["port"] = int(clean.get("port", 22))
        except Exception:
            clean["port"] = 22
        try:
            clean["serial_baud"] = int(clean.get("serial_baud", 9600))
        except Exception:
            clean["serial_baud"] = 9600
        for _k in ("order", "group_order"):
            try:
                clean[_k] = int(clean.get(_k, 0))
            except Exception:
                clean[_k] = 0
        return cls(**clean)

    def safe_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["password"] = ""
        return data


class AppSettings:
    def __init__(self) -> None:
        self.path = app_data_dir() / "settings.json"
        self.language = DEFAULT_LANGUAGE
        self.theme = "midnight"
        self.custom_colors: dict[str, str] = {}
        self.connect_timeout = 14
        self.auth_timeout = 18
        self.keepalive = 30
        self.reconnect_delay = 5
        self.auto_reconnect = True
        self.font_size = 11
        self.encoding = "utf-8"
        self.animations = True
        self.cols = 132
        self.rows = 38
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            lang = str(data.get("language", self.language)).lower()
            self.language = lang if lang in TRANSLATIONS else DEFAULT_LANGUAGE
            self.theme = str(data.get("theme", self.theme)) if str(data.get("theme", self.theme)) in THEMES or data.get("theme") == "custom" else self.theme
            cc = data.get("custom_colors", {})
            if isinstance(cc, dict):
                self.custom_colors = {str(k): str(v) for k, v in cc.items() if is_hex(str(v))}
            self.connect_timeout = int(data.get("connect_timeout", self.connect_timeout))
            self.auth_timeout = int(data.get("auth_timeout", self.auth_timeout))
            self.keepalive = int(data.get("keepalive", data.get("keepalive_seconds", self.keepalive)))
            self.reconnect_delay = int(data.get("reconnect_delay", self.reconnect_delay))
            self.auto_reconnect = bool(data.get("auto_reconnect", self.auto_reconnect))
            self.font_size = int(data.get("font_size", data.get("terminal_font_size", self.font_size)))
            self.encoding = str(data.get("encoding", data.get("terminal_encoding", self.encoding))) or "utf-8"
            self.animations = bool(data.get("animations", data.get("show_animations", self.animations)))
            self.cols = int(data.get("cols", data.get("terminal_width", self.cols)))
            self.rows = int(data.get("rows", data.get("terminal_height", self.rows)))
        except Exception:
            pass

    def save(self) -> None:
        data = {
            "app": APP_NAME, "version": APP_VERSION, "language": self.language, "theme": self.theme, "custom_colors": self.custom_colors,
            "connect_timeout": self.connect_timeout, "auth_timeout": self.auth_timeout, "keepalive": self.keepalive,
            "reconnect_delay": self.reconnect_delay, "auto_reconnect": self.auto_reconnect, "font_size": self.font_size,
            "encoding": self.encoding, "animations": self.animations, "cols": self.cols, "rows": self.rows,
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class SessionStore:
    def __init__(self) -> None:
        self.path = app_data_dir() / "sessions.json"
        self.sessions: list[Session] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.sessions = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data.get("sessions", data if isinstance(data, list) else [])
            self.sessions = []
            group_orders: dict[str, int] = {}
            next_group_order = 0
            for idx, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                session = Session.from_dict(row)
                session.group = (session.group or "Основные").strip() or "Основные"
                if "group_order" not in row:
                    if session.group not in group_orders:
                        group_orders[session.group] = next_group_order
                        next_group_order += 10
                    session.group_order = group_orders[session.group]
                else:
                    group_orders.setdefault(session.group, session.group_order)
                if "order" not in row:
                    session.order = idx * 10
                self.sessions.append(session)
            self.sessions.sort(key=lambda s: (s.group_order, s.order, s.name.lower()))
        except Exception:
            self.sessions = []

    def save(self) -> None:
        self.sessions.sort(key=lambda s: (s.group_order, s.order, s.name.lower()))
        data = {"app": APP_NAME, "version": APP_VERSION, "sessions": [s.safe_dict() for s in self.sessions]}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def group_names(self) -> list[str]:
        seen: dict[str, int] = {}
        for s in self.sessions:
            group = (s.group or "Основные").strip() or "Основные"
            seen[group] = min(seen.get(group, s.group_order), s.group_order)
        return [g for g, _ in sorted(seen.items(), key=lambda item: (item[1], item[0].lower()))]

    def _group_order_for(self, group: str) -> int:
        group = (group or "Основные").strip() or "Основные"
        orders = [s.group_order for s in self.sessions if (s.group or "Основные") == group]
        if orders:
            return min(orders)
        return (max([s.group_order for s in self.sessions], default=-10) + 10)

    def _next_order_in_group(self, group: str) -> int:
        group = (group or "Основные").strip() or "Основные"
        return max([s.order for s in self.sessions if (s.group or "Основные") == group], default=-10) + 10

    def upsert(self, session: Session) -> None:
        session.password = ""
        session.group = (session.group or "Основные").strip() or "Основные"
        for i, existing in enumerate(self.sessions):
            if existing.id == session.id:
                if (existing.group or "Основные") == session.group:
                    session.group_order = existing.group_order
                    session.order = existing.order
                else:
                    session.group_order = self._group_order_for(session.group)
                    session.order = self._next_order_in_group(session.group)
                self.sessions[i] = session
                self.save()
                return
        session.group_order = self._group_order_for(session.group)
        session.order = self._next_order_in_group(session.group)
        self.sessions.append(session)
        self.save()

    def delete(self, session_id: str) -> None:
        self.sessions = [s for s in self.sessions if s.id != session_id]
        self.save()

    def move_group(self, group: str, direction: int) -> None:
        groups = self.group_names()
        if group not in groups:
            return
        idx = groups.index(group)
        new_idx = max(0, min(len(groups) - 1, idx + direction))
        if new_idx == idx:
            return
        other = groups[new_idx]
        order_a = self._group_order_for(group)
        order_b = self._group_order_for(other)
        for s in self.sessions:
            if (s.group or "Основные") == group:
                s.group_order = order_b
            elif (s.group or "Основные") == other:
                s.group_order = order_a
        self.save()

    def move_session(self, session_id: str, direction: int) -> None:
        session = next((s for s in self.sessions if s.id == session_id), None)
        if session is None:
            return
        group = session.group or "Основные"
        rows = sorted([s for s in self.sessions if (s.group or "Основные") == group], key=lambda s: (s.order, s.name.lower()))
        idx = next((i for i, s in enumerate(rows) if s.id == session_id), -1)
        new_idx = max(0, min(len(rows) - 1, idx + direction))
        if idx < 0 or new_idx == idx:
            return
        rows[idx].order, rows[new_idx].order = rows[new_idx].order, rows[idx].order
        self.save()


class PasswordVault:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}

    def key(self, session: Session) -> str:
        user = session.username
        if not user:
            try:
                user = os.getlogin()
            except Exception:
                user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
        return f"{session.id}:{user}@{session.host}:{session.port}"

    def get(self, session: Session) -> Optional[str]:
        k = self.key(session)
        if k in self.cache:
            return self.cache[k]
        if keyring is None:
            return None
        try:
            value = keyring.get_password(SERVICE_NAME, k)
            if value:
                self.cache[k] = value
            return value
        except Exception:
            return None

    def set(self, session: Session, password: str) -> bool:
        k = self.key(session)
        self.cache[k] = password
        if keyring is None:
            return False
        try:
            keyring.set_password(SERVICE_NAME, k, password)
            return True
        except Exception:
            return False

    def delete(self, session: Session) -> None:
        k = self.key(session)
        self.cache.pop(k, None)
        if keyring is None:
            return
        try:
            keyring.delete_password(SERVICE_NAME, k)
        except Exception:
            pass



@dataclass
class CommandPreset:
    id: str
    name: str
    commands: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandPreset":
        return cls(id=str(data.get("id") or uuid.uuid4().hex), name=str(data.get("name") or ""), commands=str(data.get("commands") or ""))


class PresetStore:
    def __init__(self) -> None:
        self.path = app_data_dir() / "presets.json"
        self.presets: list[CommandPreset] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.presets = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data.get("presets", data if isinstance(data, list) else [])
            self.presets = [CommandPreset.from_dict(x) for x in rows if isinstance(x, dict)]
            self.presets.sort(key=lambda p: p.name.lower())
        except Exception:
            self.presets = []

    def save(self) -> None:
        data = {"app": APP_NAME, "version": APP_VERSION, "presets": [asdict(p) for p in self.presets]}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, preset: CommandPreset) -> None:
        for i, existing in enumerate(self.presets):
            if existing.id == preset.id:
                self.presets[i] = preset
                self.presets.sort(key=lambda p: p.name.lower())
                self.save()
                return
        self.presets.append(preset)
        self.presets.sort(key=lambda p: p.name.lower())
        self.save()

    def delete(self, preset_id: str) -> None:
        self.presets = [p for p in self.presets if p.id != preset_id]
        self.save()

    def by_name(self, name: str) -> Optional[CommandPreset]:
        for p in self.presets:
            if p.name == name:
                return p
        return None

class AppButton(tk.Button):
    def __init__(self, master: tk.Widget, text: str, command: Callable[[], None], *, kind: str = "secondary", **kw: Any) -> None:
        # Позволяем отдельным кнопкам задавать свои внутренние отступы.
        # В v1.9.0 padx/pady передавались дважды: здесь и через **kw, из-за чего
        # Tkinter падал при открытии настроек.
        padx = kw.pop("padx", 12)
        pady = kw.pop("pady", 7)
        font = kw.pop("font", FONT_UI_BOLD)
        palette = {
            "primary": (C["accent"], "#02111c", C["accent2"], C["text"]),
            "secondary": (C["surface3"], C["text"], C["surface2"], C["accent2"]),
            "danger": (C["danger"], "#32070a", "#fda4af", C["text"]),
            "ghost": (C["surface2"], C["text"], C["surface3"], C["accent2"]),
        }
        bg, fg, hover, border = palette.get(kind, palette["secondary"])
        super().__init__(master, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                         activeforeground=fg, relief="solid", bd=2, highlightthickness=2,
                         highlightbackground=border, highlightcolor=C["accent2"], cursor="hand2",
                         padx=padx, pady=pady, font=font, **kw)
        self._bg = bg; self._hover = hover
        self.bind("<Enter>", lambda _e: self.configure(bg=self._hover), add="+")
        self.bind("<Leave>", lambda _e: self.configure(bg=self._bg), add="+")


def bind_wheel(widget: tk.Widget, target: Any) -> None:
    def on_wheel(event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        amount = int(-delta / 120) if delta else (1 if getattr(event, "num", 0) == 5 else -1)
        target.yview_scroll(amount, "units")
        return "break"
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        try:
            widget.bind(seq, on_wheel, add="+")
        except Exception:
            pass


def bind_wheel_recursive(widget: tk.Widget, target: Any) -> None:
    bind_wheel(widget, target)
    for child in widget.winfo_children():
        bind_wheel_recursive(child, target)


class ScrollFrame(tk.Frame):
    def __init__(self, master: tk.Widget, **kw: Any) -> None:
        super().__init__(master, bg=kw.pop("bg", C["bg"]))
        self.canvas = tk.Canvas(self, bg=self["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = tk.Frame(self.canvas, bg=self["bg"])
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.content.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.after(50, lambda: bind_wheel_recursive(self, self.canvas))


class DarkDropdownBase(tk.Frame):
    """Theme-colored dropdown control.

    The previous version used a borderless Toplevel + Listbox. On some Windows/Tk
    builds that popup was rendered as a blank gray rectangle. This version uses a
    styled Tk menu instead, which is much more stable and still opens when the
    user clicks anywhere on the field.
    """
    def __init__(self, master: tk.Widget, variable: tk.StringVar, values: list[str],
                 command: Optional[Callable[[str], None]] = None, *, editable: bool = False) -> None:
        super().__init__(master, bg=C["surface2"], highlightthickness=2,
                         highlightbackground=C["border"], bd=1, relief="solid", cursor="hand2")
        self.variable = variable
        self.values = list(values)
        self.command = command
        self.editable = editable
        self.popup: Optional[tk.Menu] = None
        self.configure(takefocus=True)
        self.columnconfigure(0, weight=1)

        if editable:
            self.entry = tk.Entry(self, textvariable=self.variable, bg=C["surface2"], fg=C["text"],
                                  insertbackground=C["text"], relief="flat", bd=0, font=FONT_UI_BOLD)
            self.entry.grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=7)
            self.entry.bind("<Button-1>", lambda _e: self.after_idle(self.open_popup), add="+")
            self.entry.bind("<Alt-Down>", lambda e: (self.open_popup(), "break"), add="+")
        else:
            self.label = tk.Label(self, textvariable=self.variable, bg=C["surface2"], fg=C["text"],
                                  anchor="w", font=FONT_UI_BOLD, padx=10)
            self.label.grid(row=0, column=0, sticky="ew", pady=7)

        self.arrow = tk.Label(self, text="▾", bg=C["surface2"], fg=C["muted"], font=FONT_UI_BOLD,
                              padx=8, cursor="hand2")
        self.arrow.grid(row=0, column=1, sticky="ns")

        for w in (self, getattr(self, "label", None), getattr(self, "entry", None), self.arrow):
            if w is not None:
                w.bind("<Button-1>", lambda _e: self.open_popup(), add="+")
                w.bind("<Enter>", lambda _e: self._hover(True), add="+")
                w.bind("<Leave>", lambda _e: self._hover(False), add="+")
        self.bind("<Escape>", lambda _e: self.close_popup(), add="+")

    def _hover(self, active: bool) -> None:
        bg = C["surface3"] if active else C["surface2"]
        try:
            self.configure(bg=bg)
            for w in (getattr(self, "label", None), getattr(self, "entry", None), self.arrow):
                if w is not None:
                    w.configure(bg=bg)
        except Exception:
            pass

    def set_values(self, values: list[str]) -> None:
        self.values = list(values)
        if self.variable.get() not in self.values and self.values:
            self.variable.set(self.values[0])
        self.close_popup()

    def open_popup(self) -> None:
        self.close_popup()
        self.focus_set()
        menu = tk.Menu(self, tearoff=0, bg=C["surface2"], fg=C["text"],
                       activebackground=C["accent"], activeforeground="#041521",
                       disabledforeground=C["muted"], relief="solid", bd=1,
                       borderwidth=1, font=FONT_UI_BOLD)
        self.popup = menu

        if not self.values:
            menu.add_command(label="—", state="disabled")
        else:
            current = self.variable.get()
            for value in self.values:
                label = f"✓ {value}" if value == current else f"  {value}"
                menu.add_command(label=label, command=lambda v=value: self._choose(v))

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        try:
            # tk_popup grabs and releases the pointer correctly on Windows.
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _choose(self, value: str) -> None:
        self.variable.set(value)
        if self.command:
            self.command(value)
        self.close_popup()

    def close_popup(self) -> None:
        try:
            if self.popup is not None:
                self.popup.unpost()
                self.popup.destroy()
        except Exception:
            pass
        self.popup = None

    def _close_if_focus_left(self) -> None:
        self.close_popup()


class DarkCombo(DarkDropdownBase):
    def __init__(self, master: tk.Widget, variable: tk.StringVar, values: list[str], command: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(master, variable, values, command, editable=False)


class DarkEditableCombo(DarkDropdownBase):
    def __init__(self, master: tk.Widget, variable: tk.StringVar, values: list[str]) -> None:
        super().__init__(master, variable, values, editable=True)


class GroupPicker(tk.Frame):
    """Non-editable themed group selector with an inline "add group" mode.

    Directly editable comboboxes can put Tk into text-edit mode on Windows and
    may crash in some Tk builds when the menu is opened from the insertion
    cursor area. This widget only opens a menu for existing groups; new groups
    are added through an explicit inline mini-form.
    """
    def __init__(self, master: tk.Widget, variable: tk.StringVar, values: list[str],
                 on_change: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(master, bg=C["surface"])
        self.variable = variable
        self.values = list(dict.fromkeys([v for v in values if str(v).strip()]))
        self.on_change = on_change
        if not self.values:
            self.values = ["Основные" if CURRENT_LANGUAGE == "ru" else "Default"]
        if not str(self.variable.get()).strip():
            self.variable.set(self.values[0])
        self.menu: Optional[tk.Menu] = None
        self._build_display()

    def _build_display(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.columnconfigure(0, weight=1)
        self.display = tk.Frame(self, bg=C["surface2"], highlightthickness=2,
                                highlightbackground=C["border"], bd=1, relief="solid", cursor="hand2")
        self.display.grid(row=0, column=0, sticky="ew")
        self.display.columnconfigure(0, weight=1)
        self.label = tk.Label(self.display, textvariable=self.variable, bg=C["surface2"], fg=C["text"],
                              anchor="w", font=FONT_UI_BOLD, padx=10, cursor="hand2")
        self.label.grid(row=0, column=0, sticky="ew", pady=7)
        self.arrow = tk.Label(self.display, text="▾", bg=C["surface2"], fg=C["muted"],
                              font=FONT_UI_BOLD, padx=8, cursor="hand2")
        self.arrow.grid(row=0, column=1, sticky="ns")
        for w in (self, self.display, self.label, self.arrow):
            w.bind("<Button-1>", self._open_menu, add="+")
            w.bind("<Enter>", lambda _e: self._hover(True), add="+")
            w.bind("<Leave>", lambda _e: self._hover(False), add="+")

    def _hover(self, active: bool) -> None:
        bg = C["surface3"] if active else C["surface2"]
        for w in (getattr(self, "display", None), getattr(self, "label", None), getattr(self, "arrow", None)):
            try:
                w.configure(bg=bg)
            except Exception:
                pass

    def set_values(self, values: list[str]) -> None:
        self.values = list(dict.fromkeys([v for v in values if str(v).strip()]))
        current = str(self.variable.get()).strip()
        if current and current not in self.values:
            self.values.append(current)

    def _open_menu(self, event: Optional[tk.Event] = None) -> str:
        try:
            if self.menu is not None:
                self.menu.unpost(); self.menu.destroy()
        except Exception:
            pass
        menu = tk.Menu(self, tearoff=0, bg=C["surface2"], fg=C["text"],
                       activebackground=C["accent"], activeforeground="#041521",
                       disabledforeground=C["muted"], relief="solid", bd=1,
                       borderwidth=1, font=FONT_UI_BOLD)
        self.menu = menu
        current = str(self.variable.get()).strip()
        values = self.values or [current or ("Основные" if CURRENT_LANGUAGE == "ru" else "Default")]
        for value in values:
            label = f"✓ {value}" if value == current else f"  {value}"
            menu.add_command(label=label, command=lambda v=value: self._choose(v))
        menu.add_separator()
        menu.add_command(label=t("add_new_group"), command=self._show_add_form)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass
        return "break"

    def _choose(self, value: str) -> None:
        value = str(value).strip()
        if value:
            self.variable.set(value)
            if self.on_change:
                self.on_change(value)
        try:
            if self.menu is not None:
                self.menu.unpost(); self.menu.destroy()
        except Exception:
            pass
        self.menu = None

    def _show_add_form(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.columnconfigure(0, weight=1)
        self.new_var = tk.StringVar()
        box = tk.Frame(self, bg=C["surface2"], highlightthickness=2, highlightbackground=C["accent"], bd=1, relief="solid")
        box.grid(row=0, column=0, sticky="ew")
        box.columnconfigure(0, weight=1)
        entry = tk.Entry(box, textvariable=self.new_var, bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                         relief="flat", bd=0, font=FONT_UI_BOLD)
        entry.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=7)
        entry.insert(0, t("new_group_placeholder"))
        entry.selection_range(0, "end")
        AppButton(box, "✓", self._commit_new_group, kind="primary", width=2, padx=3, pady=2, font=("Segoe UI Symbol", 9, "bold")).grid(row=0, column=1, padx=(0, 4), pady=4)
        AppButton(box, "×", self._build_display, kind="ghost", width=2, padx=3, pady=2, font=("Segoe UI Symbol", 9, "bold")).grid(row=0, column=2, padx=(0, 4), pady=4)
        entry.bind("<Return>", lambda _e: (self._commit_new_group(), "break"), add="+")
        entry.bind("<Escape>", lambda _e: (self._build_display(), "break"), add="+")
        entry.focus_set()

    def _commit_new_group(self) -> None:
        value = str(getattr(self, "new_var", tk.StringVar()).get()).strip()
        if not value or value == t("new_group_placeholder"):
            self._build_display(); return
        if value not in self.values:
            self.values.append(value)
        self.variable.set(value)
        if self.on_change:
            self.on_change(value)
        self._build_display()


class PaletteColorPicker(tk.Frame):
    def __init__(self, master: tk.Widget, variable: tk.StringVar, *, columns: int = 12, on_change: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(master, bg=C["surface"])
        self.variable = variable
        self.columns = max(6, columns)
        self.on_change = on_change
        self.swatches: list[tuple[str, tk.Label]] = []
        self.preview = tk.Label(self, text="", width=5, height=2, bg=self._safe(variable.get()),
                                relief="solid", bd=1, highlightthickness=2, highlightbackground=C["border"])
        self.preview.pack(side="left", padx=(0, 10), pady=3)
        grid = tk.Frame(self, bg=C["surface"])
        grid.pack(side="left", fill="x", expand=True)
        for i, color in enumerate(COLOR_PALETTE):
            sw = tk.Label(grid, text="", width=2, height=1, bg=color, cursor="hand2",
                          relief="solid", bd=1, highlightthickness=2, highlightbackground=C["border"])
            sw.grid(row=i // self.columns, column=i % self.columns, padx=2, pady=2)
            sw.bind("<Button-1>", lambda _e, c=color: self.set_color(c), add="+")
            self.swatches.append((color.lower(), sw))
        more = AppButton(self, t("more_colors"), self.ask_custom, kind="ghost", padx=8, pady=4)
        more.pack(side="left", padx=(10, 0))
        self.refresh_selection()

    def _safe(self, value: str) -> str:
        return value if is_hex(value) else C["accent"]

    def set_color(self, color: str, *, notify: bool = True) -> None:
        if not is_hex(color):
            return
        self.variable.set(color)
        self.preview.configure(bg=color)
        self.refresh_selection()
        if notify and self.on_change:
            self.on_change(color)

    def ask_custom(self) -> None:
        try:
            _rgb, color = colorchooser.askcolor(color=self._safe(self.variable.get()), title=t("custom_colors"))
        except Exception:
            color = None
        if color:
            self.set_color(str(color))

    def refresh_selection(self) -> None:
        current = self._safe(self.variable.get()).lower()
        for color, widget in self.swatches:
            selected = color == current
            widget.configure(highlightbackground=C["accent2"] if selected else C["border"],
                             highlightcolor=C["accent2"] if selected else C["border"],
                             bd=2 if selected else 1)


class TabBook(tk.Frame):
    def __init__(self, master: tk.Widget, on_close: Optional[Callable[[tk.Widget], None]] = None) -> None:
        super().__init__(master, bg=C["bg"])
        self.on_close = on_close
        self.bar = tk.Frame(self, bg=C["bg"], height=38)
        self.bar.pack(fill="x")
        self.content = tk.Frame(self, bg=C["bg"])
        self.content.pack(fill="both", expand=True)
        self.tabs: list[dict[str, Any]] = []
        self.selected: Optional[tk.Widget] = None

    def add(self, page: tk.Widget, text: str, closable: bool = True, key: Optional[str] = None) -> tk.Widget:
        if key:
            existing = self.find_by_key(key)
            if existing is not None:
                try: page.destroy()
                except Exception: pass
                self.select(existing)
                return existing
        btn = tk.Frame(self.bar, bg=C["surface2"], highlightthickness=1, highlightbackground=C["border"])
        label = tk.Label(btn, text=text, bg=C["surface2"], fg=C["text"], padx=12, pady=7, font=FONT_UI_BOLD)
        label.pack(side="left")
        close = None
        if closable:
            close = tk.Label(btn, text=" ✕ ", bg=C["surface2"], fg=C["muted"], padx=6, pady=7, font=("Segoe UI Semibold", 11), cursor="hand2")
            close.pack(side="right")
            close.bind("<Button-1>", lambda _e, p=page: self.close(p), add="+")
        btn.pack(side="left", padx=(0, 3), pady=(4, 0))
        for w in (btn, label):
            w.bind("<Button-1>", lambda _e, p=page: self.select(p), add="+")
        page.place(in_=self.content, relx=0, rely=0, relwidth=1, relheight=1)
        self.tabs.append({"page": page, "button": btn, "label": label, "close": close, "text": text, "closable": closable, "key": key})
        self.select(page)
        return page

    def find_by_key(self, key: str) -> Optional[tk.Widget]:
        for item in self.tabs:
            if item.get("key") == key:
                return item["page"]
        return None

    def select(self, page: tk.Widget) -> None:
        for item in self.tabs:
            active = item["page"] is page
            bg = C["accent"] if active else C["surface2"]
            fg = "#06111d" if active else C["text"]
            close_fg = "#ffffff" if active else C["muted"]
            item["button"].configure(bg=bg, highlightbackground=C["accent2"] if active else C["border"])
            item["label"].configure(bg=bg, fg=fg)
            if item.get("close") is not None:
                item["close"].configure(bg=bg, fg=close_fg)
        self.selected = page
        page.lift()
        try:
            page.focus_set()
        except Exception:
            pass

    def close(self, page: tk.Widget) -> None:
        idx = next((i for i, it in enumerate(self.tabs) if it["page"] is page), -1)
        if idx < 0:
            return
        item = self.tabs.pop(idx)
        if self.on_close:
            self.on_close(page)
        item["button"].destroy()
        page.destroy()
        if self.tabs:
            self.select(self.tabs[min(idx, len(self.tabs)-1)]["page"])

class TerminalView(tk.Frame):
    """Terminal widget with normal scrollback + alternate-screen rendering.

    Shell output is kept in a normal scrollback buffer. Full-screen TUI programs
    such as nano/vim/htop usually switch to the alternate screen; that area is
    rendered by pyte and disappears again when the program exits, so the user
    returns to the previous shell history like in PuTTY.
    """
    ALT_RE = re.compile(r"(\x1b\[\?(?:47|1047|1048|1049)[hl])")
    ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[=>]")

    def __init__(self, master: tk.Widget, app: "OrionSSHApp", send_callback: Callable[[bytes], None]) -> None:
        super().__init__(master, bg=C["term_bg"])
        self.app = app
        self.send_callback = send_callback
        self.cols = max(80, app.settings.cols)
        self.rows = max(24, app.settings.rows)
        self.font = tkfont.Font(family=FONT_MONO_FAMILY, size=app.settings.font_size)
        self.text = tk.Text(self, bg=C["term_bg"], fg=C["term_fg"], insertbackground=C["accent"],
                            relief="flat", bd=0, padx=10, pady=10, wrap="none", undo=False,
                            font=self.font, exportselection=True)
        self.text.pack(fill="both", expand=True)
        self.text.configure(spacing1=0, spacing2=0, spacing3=0)
        self.normal_buffer = t("terminal_hint") + "\n"
        self.text.insert("1.0", self.normal_buffer)
        self.text.focus_set()
        self.in_alt_screen = False
        self.screen = None
        self.stream = None
        if pyte is not None:
            self.screen = pyte.Screen(self.cols, self.rows)
            self.stream = pyte.Stream(self.screen)
        self._pending_render = False
        self._bind_keys()
        self.text.bind("<Configure>", self._on_resize, add="+")
        self.after(100, self._on_resize)

    def _bind_keys(self) -> None:
        self.text.bind("<KeyPress>", self._on_key, add="+")
        self.text.bind("<Control-Shift-KeyPress-C>", self.copy_selection, add="+")
        self.text.bind("<Control-Shift-KeyPress-V>", self.paste_clipboard, add="+")
        self.text.bind("<Button-1>", lambda _e: self.text.focus_set(), add="+")
        # When a full-screen TUI program is open, the Tk Text widget must not
        # scroll its local buffer. Otherwise nano/vim can appear as an empty
        # black area after wheel scrolling. In alternate screen mode the wheel
        # is converted to arrow keys and sent to the remote PTY.
        self.text.bind("<MouseWheel>", self._on_mouse_wheel, add="+")
        self.text.bind("<Button-4>", self._on_mouse_wheel, add="+")
        self.text.bind("<Button-5>", self._on_mouse_wheel, add="+")

    def _on_mouse_wheel(self, event: tk.Event) -> Optional[str]:
        if not self.in_alt_screen:
            return None
        try:
            delta = int(getattr(event, "delta", 0) or 0)
            num = int(getattr(event, "num", 0) or 0)
            up = (delta > 0) or num == 4
            # Most TUI programs, including nano without mouse reporting, react
            # predictably to arrow keys. Send a few lines per wheel notch.
            seq = "\x1b[A" if up else "\x1b[B"
            repeat = 4
            self.send_callback((seq * repeat).encode("latin1"))
        except Exception:
            pass
        self.text.yview_moveto(0)
        return "break"

    def write_info(self, msg: str) -> None:
        self.feed("\r\n" + msg + "\r\n")

    def _enter_alt(self) -> None:
        self.in_alt_screen = True
        if self.screen is not None:
            try:
                self.screen.reset()
                self.screen.resize(lines=self.rows, columns=self.cols)
            except Exception:
                pass
        self.text.delete("1.0", "end")

    def _exit_alt(self) -> None:
        self.in_alt_screen = False
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.normal_buffer)
        self.text.see("end")
        if self.screen is not None:
            try:
                self.screen.reset()
                self.screen.resize(lines=self.rows, columns=self.cols)
            except Exception:
                pass

    def feed(self, data: str) -> None:
        if not data:
            return
        parts = self.ALT_RE.split(data)
        for part in parts:
            if not part:
                continue
            if part.endswith("h") and part.startswith("\x1b[?"):
                self._enter_alt()
                continue
            if part.endswith("l") and part.startswith("\x1b[?"):
                self._exit_alt()
                continue
            if self.in_alt_screen and self.stream is not None:
                try:
                    self.stream.feed(part)
                except Exception:
                    self.stream.feed(re.sub(r"\x1b[^A-Za-z0-9]*", "", part))
                self._schedule_render()
            else:
                self._append_normal(part)

    def _append_normal(self, data: str) -> None:
        text = data.replace("\r\n", "\n")
        text = self.ANSI_RE.sub("", text)
        if not text:
            return
        for ch in text:
            if ch in ("\b", "\x7f"):
                self._local_backspace()
                continue
            if ch == "\r":
                ch = "\n"
            if ch == "\x0c":
                self.clear()
                continue
            if ord(ch) < 32 and ch not in ("\n", "\t"):
                # Do not render raw control characters as strange boxes.
                continue
            self.normal_buffer += ch
            self.text.insert("end", ch)
        if len(self.normal_buffer) > 120000:
            self.normal_buffer = self.normal_buffer[-100000:]
        self.text.see("end")

    def _local_backspace(self) -> None:
        if self.normal_buffer:
            self.normal_buffer = self.normal_buffer[:-1]
        try:
            if self.text.compare("end-1c", ">", "1.0"):
                prev = self.text.get("end-2c", "end-1c")
                if prev != "\n":
                    self.text.delete("end-2c", "end-1c")
        except Exception:
            pass

    def _schedule_render(self) -> None:
        if self._pending_render:
            return
        self._pending_render = True
        self.after(16 if self.app.settings.animations else 32, self.render)

    def render(self) -> None:
        self._pending_render = False
        if self.screen is None or not self.in_alt_screen:
            return
        display = "\n".join(self.screen.display)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", display + "\n")
        try:
            self.text.configure(width=self.cols, height=self.rows)
        except Exception:
            pass
        try:
            y = int(getattr(self.screen.cursor, "y", 0)) + 1
            x = int(getattr(self.screen.cursor, "x", 0))
            self.text.mark_set("insert", f"{y}.{x}")
            # TUI applications use a fixed viewport. Do not auto-scroll the Tk Text
            # widget to the cursor: with nano/vim/htop it can expose blank space.
            self.text.yview_moveto(0)
        except Exception:
            self.text.yview_moveto(0)

    def _on_resize(self, _event: tk.Event | None = None) -> None:
        try:
            char_w = max(1, self.font.measure("W"))
            line_h = max(1, self.font.metrics("linespace"))
            width = max(100, self.text.winfo_width() - 22)
            height = max(100, self.text.winfo_height() - 22)
            cols = max(60, int(width / char_w))
            rows = max(18, int(height / line_h))
            if cols != self.cols or rows != self.rows:
                self.cols, self.rows = cols, rows
                self.app.settings.cols = cols
                self.app.settings.rows = rows
                if self.screen is not None:
                    self.screen.resize(lines=rows, columns=cols)
                self.event_generate("<<TerminalResize>>")
                self._schedule_render()
        except Exception:
            pass

    def clear(self) -> None:
        self.normal_buffer = ""
        self.in_alt_screen = False
        self.text.delete("1.0", "end")
        if self.screen is not None:
            try: self.screen.reset()
            except Exception: pass

    def copy_selection(self, event: tk.Event | None = None) -> str:
        try:
            selected = self.text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected)
        except Exception:
            pass
        return "break"

    def paste_clipboard(self, event: tk.Event | None = None) -> str:
        try:
            data = self.clipboard_get().replace("\n", "\r")
            self.send_callback(data.encode(self.app.settings.encoding, errors="replace"))
        except Exception:
            pass
        return "break"

    def _on_key(self, event: tk.Event) -> str:
        state = getattr(event, "state", 0)
        ctrl = bool(state & 0x0004)
        shift = bool(state & 0x0001)
        ks = str(event.keysym)
        if ctrl and shift and ks.lower() in {"c", "x"}:
            self.copy_selection(event)
            return "break"
        if (ctrl and shift and ks.lower() == "v") or (shift and ks == "Insert"):
            self.paste_clipboard(event)
            return "break"
        if ctrl and ks == "Insert":
            self.copy_selection(event)
            return "break"
        data = self._event_to_bytes(event)
        if data:
            self.send_callback(data)
        return "break"

    def _event_to_bytes(self, event: tk.Event) -> bytes:
        ks = event.keysym
        ctrl = bool(getattr(event, "state", 0) & 0x0004)
        alt = bool(getattr(event, "state", 0) & 0x0008 or getattr(event, "state", 0) & 0x20000)
        seqs = {
            "Return": "\r", "KP_Enter": "\r", "BackSpace": "\x08", "Tab": "\t", "Escape": "\x1b",
            "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C", "Left": "\x1b[D",
            "Home": "\x1b[H", "End": "\x1b[F", "Prior": "\x1b[5~", "Next": "\x1b[6~",
            "Insert": "\x1b[2~", "Delete": "\x1b[3~",
            "F1": "\x1bOP", "F2": "\x1bOQ", "F3": "\x1bOR", "F4": "\x1bOS",
            "F5": "\x1b[15~", "F6": "\x1b[17~", "F7": "\x1b[18~", "F8": "\x1b[19~",
            "F9": "\x1b[20~", "F10": "\x1b[21~", "F11": "\x1b[23~", "F12": "\x1b[24~",
        }
        if ctrl:
            ch = event.char or ""
            if ch and ch.isalpha():
                return bytes([ord(ch.lower()) - 96])
            if ks == "space":
                return b"\x00"
            if ks in ("bracketleft", "Escape"):
                return b"\x1b"
            if ks == "BackSpace":
                return b"\x17"
        if ks in seqs:
            s = seqs[ks]
            return ("\x1b" + s if alt and len(s) == 1 else s).encode("latin1")
        ch = event.char or ""
        if ch:
            if alt:
                ch = "\x1b" + ch
            return ch.encode(self.app.settings.encoding, errors="replace")
        return b""

class LocalForwarder:
    def __init__(self, tab: "TerminalTab", local_host: str, local_port: int, remote_host: str, remote_port: int, line: str) -> None:
        self.tab = tab
        self.local_host = local_host
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.line = line
        self.sock: Optional[socket.socket] = None
        self.stop = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.local_host, self.local_port))
        self.sock.listen(20)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def _loop(self) -> None:
        while not self.stop.is_set():
            try:
                client, addr = self.sock.accept() if self.sock else (None, None)  # type: ignore
            except Exception:
                break
            if client:
                threading.Thread(target=self._handle, args=(client, addr), daemon=True).start()

    def _handle(self, client: socket.socket, addr: Any) -> None:
        chan = None
        try:
            transport = self.tab.client.get_transport() if self.tab.client else None
            if not transport:
                client.close(); return
            chan = transport.open_channel("direct-tcpip", (self.remote_host, self.remote_port), addr)
            def copy_sock_to_chan() -> None:
                try:
                    while not self.stop.is_set():
                        data = client.recv(32768)
                        if not data: break
                        chan.sendall(data)
                except Exception:
                    pass
                try: chan.shutdown_write()
                except Exception: pass
            def copy_chan_to_sock() -> None:
                try:
                    while not self.stop.is_set():
                        data = chan.recv(32768)
                        if not data: break
                        client.sendall(data)
                except Exception:
                    pass
                try: client.shutdown(socket.SHUT_WR)
                except Exception: pass
            a = threading.Thread(target=copy_sock_to_chan, daemon=True); b = threading.Thread(target=copy_chan_to_sock, daemon=True)
            a.start(); b.start(); a.join(); b.join()
        except Exception as exc:
            self.tab.info(t("error", error=exc))
        finally:
            try: client.close()
            except Exception: pass
            try:
                if chan: chan.close()
            except Exception: pass


def parse_forward_line(line: str) -> Optional[tuple[str, int, str, int]]:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    raw = raw.replace("->", " ")
    parts = raw.split()
    if parts and parts[0].upper() == "L":
        parts = parts[1:]
    if len(parts) == 2:
        local, remote = parts
    elif len(parts) == 3:
        local = f"{parts[0]}:{parts[1]}"; remote = parts[2]
    else:
        raise ValueError("ожидается: L 127.0.0.1:8080 127.0.0.1:80")
    def split_endpoint(value: str, default_host: str) -> tuple[str, int]:
        if value.count(":") == 0:
            return default_host, int(value)
        h, p = value.rsplit(":", 1)
        return h or default_host, int(p)
    lh, lp = split_endpoint(local, "127.0.0.1")
    rh, rp = split_endpoint(remote, "127.0.0.1")
    return lh, lp, rh, rp


class TerminalTab(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp", session: Session) -> None:
        super().__init__(master, bg=C["term_bg"])
        self.app = app
        self.session = session
        self.client: Any = None
        self.channel: Any = None
        self.sock: Optional[socket.socket] = None
        self.serial: Any = None
        self.sftp: Any = None
        self.reader: Optional[threading.Thread] = None
        self.queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.connected = False
        self.manual_disconnect = False
        self.stop = threading.Event()
        self.forwarders: list[LocalForwarder] = []
        self._reconnect_after: Optional[str] = None
        self._build()
        self.after(60, self._pump)
        self.after(100, self.connect_async)

    def _build(self) -> None:
        # Two-line responsive toolbar: the action buttons no longer collapse into
        # thin broken controls when the application is not maximized.
        toolbar = tk.Frame(self, bg=C["surface"], padx=8, pady=7, highlightthickness=1, highlightbackground=C["border"])
        toolbar.pack(fill="x")
        top = tk.Frame(toolbar, bg=C["surface"])
        top.pack(fill="x")
        self.status = tk.Label(top, text=t("connecting"), bg=C["surface"], fg=C["muted"], font=FONT_UI)
        self.status.pack(side="left", padx=(0, 10))
        self.preset_var = tk.StringVar(value=t("select_preset"))
        self.preset_combo = DarkCombo(top, self.preset_var, self._preset_names())
        self.preset_combo.pack(side="left", fill="x", expand=True, padx=(4, 6))
        AppButton(top, t("run_preset"), self.run_selected_preset, kind="primary").pack(side="left", padx=3)

        actions = tk.Frame(toolbar, bg=C["surface"])
        actions.pack(fill="x", pady=(7, 0))
        if self.session.protocol == "ssh":
            AppButton(actions, t("files"), self.open_files, kind="primary").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("split_horizontal"), lambda: self.app.open_split_workspace(self.session, "horizontal"), kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("split_vertical"), lambda: self.app.open_split_workspace(self.session, "vertical"), kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("reconnect"), self.reconnect, kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("copy"), self.copy, kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("paste"), self.paste, kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("clear"), self.clear, kind="ghost").pack(side="left", padx=3, pady=2)
        AppButton(actions, t("disconnect"), self.disconnect, kind="danger").pack(side="left", padx=3, pady=2)
        self.term = TerminalView(self, self.app, self.send_bytes)
        self.term.pack(fill="both", expand=True)
        self.term.bind("<<TerminalResize>>", lambda _e: self.resize_remote(), add="+")


    def _preset_names(self) -> list[str]:
        names = [p.name for p in self.app.preset_store.presets]
        return [t("select_preset")] + names if names else [t("no_presets")]

    def refresh_presets(self) -> None:
        try:
            names = self._preset_names()
            self.preset_combo.set_values(names)
            if self.preset_var.get() not in names:
                self.preset_var.set(names[0])
        except Exception:
            pass

    def run_selected_preset(self) -> None:
        name = self.preset_var.get()
        preset = self.app.preset_store.by_name(name)
        if not preset:
            self.term.write_info(t("select_preset"))
            return
        for line in preset.commands.splitlines():
            cmd = line.rstrip()
            if not cmd:
                continue
            self.send_bytes((cmd + "\r").encode(self.app.settings.encoding, errors="replace"))
            time.sleep(0.04)
        self.term.write_info(t("preset_sent", name=preset.name))

    def info(self, msg: str) -> None:
        self.queue.put((msg + "\n", "info"))

    def clear(self) -> None:
        self.term.clear()

    def copy(self) -> None:
        self.term.copy_selection()

    def paste(self) -> None:
        self.term.paste_clipboard()

    def connect_async(self) -> None:
        self.stop.clear()
        self.manual_disconnect = False
        self.connected = False
        self.status.configure(text=t("connecting"), fg=C["muted"])
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self) -> None:
        proto = self.session.protocol.lower()
        try:
            if proto == "ssh":
                self._connect_ssh()
            elif proto == "telnet":
                self._connect_telnet()
            elif proto == "serial":
                self._connect_serial()
            elif proto == "rdp":
                self._launch_rdp()
            else:
                raise RuntimeError(f"unknown protocol: {proto}")
        except socket.gaierror as exc:
            self.queue.put((t("dns_error", error=exc) + "\n", "error"))
            self._mark_disconnected(schedule=False)
        except Exception as exc:
            self.queue.put((t("connection_failed", error=exc) + "\n", "error"))
            self._mark_disconnected(schedule=True)

    def _connect_ssh(self) -> None:
        if paramiko is None:
            raise RuntimeError(t("ssh_missing"))
        username = self.session.username or os.environ.get("USERNAME") or ""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict[str, Any] = {
            "hostname": self.session.host, "port": self.session.port, "username": username,
            "timeout": self.app.settings.connect_timeout, "banner_timeout": self.app.settings.connect_timeout,
            "auth_timeout": self.app.settings.auth_timeout, "look_for_keys": self.session.auth_mode == "agent",
            "allow_agent": self.session.auth_mode in {"agent", "key"},
        }
        if self.session.auth_mode == "password":
            password = self.app.vault.get(self.session)
            if password is None:
                password = self.app.ask_password(t("password_prompt", user=username, host=self.session.host))
                if not password:
                    raise RuntimeError("отменено пользователем")
                if self.session.save_password:
                    self.app.vault.set(self.session, password)
            kwargs.update({"password": password, "look_for_keys": False, "allow_agent": False})
        elif self.session.auth_mode == "key":
            if not self.session.key_path:
                raise RuntimeError("не указан приватный ключ")
            kwargs["key_filename"] = str(Path(self.session.key_path).expanduser())
            pp = self.app.ask_password(t("passphrase_prompt", name=Path(self.session.key_path).name), allow_empty=True)
            if pp:
                kwargs["passphrase"] = pp
        client.connect(**kwargs)
        transport = client.get_transport()
        if transport:
            transport.set_keepalive(self.app.settings.keepalive)
        chan = client.invoke_shell(term="xterm-256color", width=self.term.cols, height=self.term.rows)
        chan.settimeout(0.0)
        self.client = client; self.channel = chan; self.connected = True
        self.queue.put((f"{t('connected')}: {username}@{self.session.host}:{self.session.port}\n", "success"))
        if self.session.start_dir:
            chan.send(f"cd {self.session.start_dir}\r".encode("utf-8"))
        self._start_forwarders()
        self.reader = threading.Thread(target=self._ssh_reader, daemon=True); self.reader.start()

    def _connect_telnet(self) -> None:
        self.queue.put((t("telnet_hint") + "\n", "info"))
        s = socket.create_connection((self.session.host, self.session.port or 23), timeout=self.app.settings.connect_timeout)
        s.settimeout(0.05)
        self.sock = s; self.connected = True
        self.queue.put((f"{t('connected')}: telnet://{self.session.host}:{self.session.port}\n", "success"))
        self.reader = threading.Thread(target=self._socket_reader, daemon=True); self.reader.start()

    def _connect_serial(self) -> None:
        self.queue.put((t("serial_hint") + "\n", "info"))
        try:
            import serial  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"pyserial не установлен: {exc}")
        port_name = self.session.serial_port or self.session.host
        ser = serial.Serial(port=port_name, baudrate=self.session.serial_baud, timeout=0.05)
        self.serial = ser; self.connected = True
        self.queue.put((f"{t('connected')}: {port_name} @ {self.session.serial_baud}\n", "success"))
        self.reader = threading.Thread(target=self._serial_reader, daemon=True); self.reader.start()

    def _launch_rdp(self) -> None:
        self.queue.put((t("rdp_hint") + "\n", "info"))
        target = f"{self.session.host}:{self.session.port or 3389}"
        self.queue.put((t("rdp_launch", host=self.session.host, port=self.session.port or 3389) + "\n", "success"))
        subprocess.Popen(["mstsc.exe", f"/v:{target}"], shell=False)
        self.connected = False
        self.status.configure(text="RDP", fg=C["success"])

    def _ssh_reader(self) -> None:
        while not self.stop.is_set() and self.channel is not None:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(65535)
                    if not data: break
                    self.queue.put((data.decode(self.app.settings.encoding, errors="replace"), "term"))
                elif self.channel.exit_status_ready():
                    break
                else:
                    time.sleep(0.01)
            except socket.timeout:
                continue
            except Exception as exc:
                if not self.stop.is_set(): self.queue.put((t("error", error=exc) + "\n", "error"))
                break
        self._mark_disconnected(schedule=True)

    def _socket_reader(self) -> None:
        while not self.stop.is_set() and self.sock is not None:
            try:
                data = self.sock.recv(65535)
                if not data: break
                self.queue.put((data.decode(self.app.settings.encoding, errors="replace"), "term"))
            except socket.timeout:
                continue
            except Exception as exc:
                if not self.stop.is_set(): self.queue.put((t("error", error=exc) + "\n", "error"))
                break
        self._mark_disconnected(schedule=True)

    def _serial_reader(self) -> None:
        while not self.stop.is_set() and self.serial is not None:
            try:
                data = self.serial.read(4096)
                if data:
                    self.queue.put((data.decode(self.app.settings.encoding, errors="replace"), "term"))
                else:
                    time.sleep(0.01)
            except Exception as exc:
                if not self.stop.is_set(): self.queue.put((t("error", error=exc) + "\n", "error"))
                break
        self._mark_disconnected(schedule=True)

    def _pump(self) -> None:
        try:
            while True:
                text, kind = self.queue.get_nowait()
                if kind == "term":
                    self.term.feed(text)
                else:
                    self.term.write_info(text.rstrip("\n"))
                    if kind == "success": self.status.configure(text=t("connected"), fg=C["success"])
                    if kind == "error": self.status.configure(text=t("offline"), fg=C["danger"])
        except queue.Empty:
            pass
        self.after(50, self._pump)

    def send_bytes(self, data: bytes) -> None:
        if not self.connected:
            self.term.write_info(t("not_connected")); return
        try:
            if self.channel is not None:
                self.channel.send(data)
            elif self.sock is not None:
                self.sock.sendall(data)
            elif self.serial is not None:
                self.serial.write(data)
        except Exception as exc:
            self.term.write_info(t("error", error=exc))

    def resize_remote(self) -> None:
        if self.channel is not None and self.connected:
            try:
                self.channel.resize_pty(width=self.term.cols, height=self.term.rows)
            except Exception:
                pass

    def _mark_disconnected(self, schedule: bool) -> None:
        if self.connected:
            self.queue.put((t("disconnected") + "\n", "info"))
        self.connected = False
        if schedule and not self.manual_disconnect and self.app.settings.auto_reconnect and self.session.protocol in {"ssh", "telnet", "serial"}:
            self.after(0, self._schedule_reconnect)

    def _schedule_reconnect(self) -> None:
        if self._reconnect_after:
            return
        seconds = self.app.settings.reconnect_delay
        self.term.write_info(t("auto_reconnect", seconds=seconds))
        def again() -> None:
            self._reconnect_after = None
            if not self.manual_disconnect:
                self.term.write_info(t("auto_reconnect_now"))
                self.connect_async()
        self._reconnect_after = self.after(seconds * 1000, again)

    def _start_forwarders(self) -> None:
        for raw in self.session.tunnels.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"): continue
            try:
                parsed = parse_forward_line(line)
                if not parsed: continue
                lh, lp, rh, rp = parsed
                fwd = LocalForwarder(self, lh, lp, rh, rp, line)
                fwd.start()
                self.forwarders.append(fwd)
                self.queue.put((t("tunnel_started", local=f"{lh}:{lp}", remote=f"{rh}:{rp}") + "\n", "success"))
            except Exception as exc:
                self.queue.put((t("tunnel_failed", line=line, error=exc) + "\n", "error"))

    def _close_forwarders(self) -> None:
        for fwd in self.forwarders:
            fwd.close()
        self.forwarders.clear()

    def disconnect(self) -> None:
        self.manual_disconnect = True
        self.stop.set()
        if self._reconnect_after:
            try: self.after_cancel(self._reconnect_after)
            except Exception: pass
            self._reconnect_after = None
        self._close_forwarders()
        for obj in (self.sftp, self.channel, self.client, self.sock, self.serial):
            try:
                if obj: obj.close()
            except Exception:
                pass
        self.sftp = self.channel = self.client = self.sock = self.serial = None
        self.connected = False
        self.status.configure(text=t("offline"), fg=C["muted"])

    def reconnect(self) -> None:
        self.disconnect()
        self.manual_disconnect = False
        self.after(200, self.connect_async)

    def _get_sftp(self) -> Any:
        if self.session.protocol != "ssh" or not self.client:
            raise RuntimeError(t("not_connected"))
        if self.sftp is None:
            self.sftp = self.client.open_sftp()
        return self.sftp

    def open_files(self) -> None:
        if not self.connected:
            self.term.write_info(t("not_connected")); return
        self.app.open_remote_file_browser(self)



class SplitPane(tk.Frame):
    def __init__(self, master: tk.Widget, workspace: "SplitTerminalPage", index: int, initial_session: Optional[Session] = None) -> None:
        super().__init__(master, bg=C["bg"], highlightthickness=1, highlightbackground=C["border"])
        self.workspace = workspace
        self.app = workspace.app
        self.index = index
        self.current_session: Optional[Session] = None
        self.terminal: Optional[TerminalTab] = None
        self._build()
        if initial_session is not None:
            self.after(80, lambda s=initial_session: self.open_session(s))

    def _label_for(self, session: Session) -> str:
        user = f"{session.username}@" if session.username else ""
        return f"{session.name}  —  {session.protocol.upper()} {user}{session.host}:{session.port}"

    def _session_labels(self) -> dict[str, Session]:
        result: dict[str, Session] = {}
        for session in self.app.store.sessions:
            label = self._label_for(session)
            # Names can repeat. Keep labels unique without exposing internal ids.
            if label in result:
                label = f"{label} #{session.id[:6]}"
            result[label] = session
        return result

    def _build(self) -> None:
        self.header = tk.Frame(self, bg=C["surface"], padx=6, pady=5)
        self.header.pack(fill="x")
        tk.Label(self.header, text=f"{self.index + 1}", bg=C["surface"], fg=C["accent2"], font=FONT_UI_BOLD).pack(side="left", padx=(0, 6))
        self.session_map = self._session_labels()
        values = list(self.session_map.keys()) or [t("no_sessions")]
        self.var = tk.StringVar(value=values[0] if values else t("select_session"))
        self.combo = DarkCombo(self.header, self.var, values)
        self.combo.pack(side="left", fill="x", expand=True, padx=(0, 6))
        AppButton(self.header, t("open_in_pane"), self.open_selected, kind="primary", padx=8, pady=4).pack(side="left")
        AppButton(self.header, "×", self.close_terminal, kind="ghost", padx=8, pady=4).pack(side="left", padx=(4, 0))
        self.body = tk.Frame(self, bg=C["term_bg"])
        self.body.pack(fill="both", expand=True)
        self.placeholder = tk.Label(self.body, text=t("empty_pane"), bg=C["term_bg"], fg=C["muted"], font=("Segoe UI", 14))
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def refresh_sessions(self) -> None:
        self.session_map = self._session_labels()
        values = list(self.session_map.keys()) or [t("no_sessions")]
        try:
            menu = self.combo["menu"]
            menu.delete(0, "end")
            for value in values:
                menu.add_command(label=value, command=lambda v=value: self.var.set(v))
            if self.var.get() not in values:
                self.var.set(values[0])
        except Exception:
            pass

    def open_selected(self) -> None:
        self.refresh_sessions()
        session = self.session_map.get(self.var.get())
        if session is not None:
            self.open_session(session)

    def open_session(self, session: Session) -> None:
        self.close_terminal()
        self.current_session = session
        try:
            self.placeholder.place_forget()
        except Exception:
            pass
        self.terminal = TerminalTab(self.body, self.app, session)
        self.terminal.pack(fill="both", expand=True)
        # Keep the combo in sync with the active pane session.
        for label, value in self.session_map.items():
            if value.id == session.id:
                self.var.set(label)
                break

    def close_terminal(self) -> None:
        if self.terminal is not None:
            try:
                self.terminal.disconnect()
            except Exception:
                pass
            try:
                self.terminal.destroy()
            except Exception:
                pass
        self.terminal = None
        self.current_session = None
        try:
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

    def disconnect(self) -> None:
        self.close_terminal()


class SplitTerminalPage(tk.Frame):
    """Workspace with independent terminal panes.

    Unlike the old duplicate-split implementation, each pane can open a
    different saved connection. The layout can be switched between 2 columns,
    2 rows and a 2x2 grid for four simultaneous connections.
    """
    def __init__(self, master: tk.Widget, app: "OrionSSHApp", session: Optional[Session] = None, orientation: str = "horizontal") -> None:
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.initial_session = session
        self.layout = "2_rows" if orientation == "vertical" else "2_columns"
        self.panes: list[SplitPane] = []
        self._build()

    def _build(self) -> None:
        top = tk.Frame(self, bg=C["surface"], padx=8, pady=7, highlightthickness=1, highlightbackground=C["border"])
        top.pack(fill="x")
        tk.Label(top, text=t("split_workspace"), bg=C["surface"], fg=C["text"], font=FONT_UI_BOLD).pack(side="left", padx=(0, 10))
        AppButton(top, t("split_2_columns"), lambda: self.set_layout("2_columns"), kind="ghost", padx=8, pady=4).pack(side="left", padx=3)
        AppButton(top, t("split_2_rows"), lambda: self.set_layout("2_rows"), kind="ghost", padx=8, pady=4).pack(side="left", padx=3)
        AppButton(top, t("split_4"), lambda: self.set_layout("4"), kind="ghost", padx=8, pady=4).pack(side="left", padx=3)
        self.area = tk.Frame(self, bg=C["bg"])
        self.area.pack(fill="both", expand=True)
        self.set_layout(self.layout, preserve=False)

    def _current_sessions(self) -> list[Optional[Session]]:
        sessions: list[Optional[Session]] = []
        for pane in self.panes:
            sessions.append(pane.current_session)
        if not sessions and self.initial_session is not None:
            sessions.append(self.initial_session)
        return sessions

    def set_layout(self, layout: str, preserve: bool = True) -> None:
        keep = self._current_sessions() if preserve else ([self.initial_session] if self.initial_session is not None else [])
        for pane in self.panes:
            try:
                pane.disconnect()
            except Exception:
                pass
            try:
                pane.destroy()
            except Exception:
                pass
        self.panes = []
        for child in self.area.winfo_children():
            try: child.destroy()
            except Exception: pass
        for i in range(4):
            self.area.grid_rowconfigure(i, weight=0)
            self.area.grid_columnconfigure(i, weight=0)
        self.layout = layout
        if layout == "4":
            count, positions = 4, [(0, 0), (0, 1), (1, 0), (1, 1)]
            for r in (0, 1): self.area.grid_rowconfigure(r, weight=1, uniform="split_rows")
            for c in (0, 1): self.area.grid_columnconfigure(c, weight=1, uniform="split_cols")
        elif layout == "2_rows":
            count, positions = 2, [(0, 0), (1, 0)]
            for r in (0, 1): self.area.grid_rowconfigure(r, weight=1, uniform="split_rows")
            self.area.grid_columnconfigure(0, weight=1)
        else:
            count, positions = 2, [(0, 0), (0, 1)]
            self.area.grid_rowconfigure(0, weight=1)
            for c in (0, 1): self.area.grid_columnconfigure(c, weight=1, uniform="split_cols")
        for idx in range(count):
            initial = keep[idx] if idx < len(keep) else None
            pane = SplitPane(self.area, self, idx, initial)
            r, c = positions[idx]
            pane.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            self.panes.append(pane)

    def refresh_sessions(self) -> None:
        for pane in self.panes:
            pane.refresh_sessions()

    def disconnect(self) -> None:
        for pane in self.panes:
            try:
                pane.disconnect()
            except Exception:
                pass

class SessionEditor(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp", session: Optional[Session] = None) -> None:
        super().__init__(master, bg=C["bg"])
        self.app = app; self.session = session
        self.vars: dict[str, tk.Variable] = {
            "protocol": tk.StringVar(value=(session.protocol if session else "ssh")),
            "name": tk.StringVar(value=session.name if session else ""),
            "host": tk.StringVar(value=session.host if session else ""),
            "port": tk.StringVar(value=str(session.port if session else 22)),
            "username": tk.StringVar(value=session.username if session else ""),
            "password": tk.StringVar(value=""),
            "save_password": tk.BooleanVar(value=session.save_password if session else False),
            "auth_mode": tk.StringVar(value=session.auth_mode if session else "password"),
            "key_path": tk.StringVar(value=session.key_path if session else ""),
            "group": tk.StringVar(value=session.group if session else "Основные"),
            "group_color": tk.StringVar(value=session.group_color if session else C["accent"]),
            "favorite": tk.BooleanVar(value=session.favorite if session else False),
            "tags": tk.StringVar(value=session.tags if session else ""),
            "start_dir": tk.StringVar(value=session.start_dir if session else ""),
            "serial_port": tk.StringVar(value=session.serial_port if session else ""),
            "serial_baud": tk.StringVar(value=str(session.serial_baud if session else 9600)),
        }
        if session and app.vault.get(session):
            self.vars["password"].set("********")
        self._build()

    def _label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=C["surface"], fg=C["muted"], anchor="w", font=FONT_UI)

    def _entry(self, parent: tk.Widget, key: str, show: str = "") -> tk.Entry:
        e = tk.Entry(parent, textvariable=self.vars[key], bg=C["surface2"], fg=C["text"], insertbackground=C["text"],
                     relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI, show=show)
        return e

    def _row(self, parent: tk.Widget, row: int, label: str, widget: tk.Widget) -> None:
        self._label(parent, label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=7)
        widget.grid(row=row, column=1, sticky="ew", pady=7, ipady=6)

    def _build(self) -> None:
        sf = ScrollFrame(self, bg=C["bg"]); sf.pack(fill="both", expand=True)
        card = tk.Frame(sf.content, bg=C["surface"], padx=24, pady=20, highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x", padx=18, pady=18)
        card.columnconfigure(1, weight=1)
        title = t("edit_session") if self.session else t("new_session")
        tk.Label(card, text=title, bg=C["surface"], fg=C["text"], font=FONT_TITLE).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))
        row = 1
        proto = DarkCombo(card, self.vars["protocol"], ["ssh", "telnet", "rdp", "serial"], command=lambda _v: self._protocol_changed())
        self._row(card, row, t("protocol"), proto); row += 1
        for label, key in [(t("name"), "name"), (t("host"), "host"), (t("port"), "port"), (t("username"), "username")]:
            self._row(card, row, label, self._entry(card, key)); row += 1
        self._row(card, row, t("password"), self._entry(card, "password", show="*")); row += 1
        cb = tk.Checkbutton(card, text=t("save_password"), variable=self.vars["save_password"], bg=C["surface"], fg=C["text"],
                            activebackground=C["surface"], activeforeground=C["text"], selectcolor=C["surface2"], font=FONT_UI)
        cb.grid(row=row, column=1, sticky="w", pady=6); row += 1
        self._row(card, row, t("auth"), DarkCombo(card, self.vars["auth_mode"], ["password", "key", "agent"])); row += 1
        key_box = tk.Frame(card, bg=C["surface"]); key_box.columnconfigure(0, weight=1)
        self._entry(key_box, "key_path").grid(row=0, column=0, sticky="ew", ipady=6)
        AppButton(key_box, t("browse"), self._browse_key, kind="ghost").grid(row=0, column=1, padx=(8, 0))
        self._row(card, row, t("key_path"), key_box); row += 1
        group_values = self.app.store.group_names()
        current_group = str(self.vars["group"].get()).strip() or "Основные"
        if current_group not in group_values:
            group_values.append(current_group)
        self._row(card, row, t("group"), GroupPicker(card, self.vars["group"], group_values or ["Основные"])); row += 1
        self._row(card, row, t("group_color"), PaletteColorPicker(card, self.vars["group_color"], columns=12)); row += 1
        for label, key in [(t("tags"), "tags"), (t("start_dir"), "start_dir"), (t("serial_port"), "serial_port"), (t("serial_baud"), "serial_baud")]:
            self._row(card, row, label, self._entry(card, key)); row += 1
        fav = tk.Checkbutton(card, text=t("favorite"), variable=self.vars["favorite"], bg=C["surface"], fg=C["text"],
                             activebackground=C["surface"], activeforeground=C["text"], selectcolor=C["surface2"], font=FONT_UI_BOLD)
        fav.grid(row=row, column=1, sticky="w", pady=6); row += 1
        self._label(card, t("tunnels")).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=7)
        self.tunnels = tk.Text(card, height=4, bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=1,
                               highlightthickness=2, highlightbackground=C["border"], font=FONT_UI, wrap="word")
        self.tunnels.grid(row=row, column=1, sticky="ew", pady=7)
        self.tunnels.insert("1.0", self.session.tunnels if self.session else "")
        row += 1
        tk.Label(card, text=t("tunnels_hint"), bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9), wraplength=760, justify="left").grid(row=row, column=1, sticky="w"); row += 1
        self._label(card, t("notes")).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=7)
        self.notes = tk.Text(card, height=5, bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=1,
                             highlightthickness=2, highlightbackground=C["border"], font=FONT_UI, wrap="word")
        self.notes.grid(row=row, column=1, sticky="ew", pady=7)
        self.notes.insert("1.0", self.session.notes if self.session else "")
        row += 1
        self.status = tk.Label(card, text="", bg=C["surface"], fg=C["accent2"], font=FONT_UI, anchor="w")
        self.status.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 4)); row += 1
        btns = tk.Frame(card, bg=C["surface"]); btns.grid(row=row, column=0, columnspan=2, sticky="e")
        AppButton(btns, t("cancel"), lambda: self.app.close_page(self), kind="ghost").pack(side="left", padx=5)
        AppButton(btns, t("save"), self.save_only, kind="secondary").pack(side="left", padx=5)
        AppButton(btns, t("save_connect"), self.save_connect, kind="primary").pack(side="left", padx=5)
        self.after(100, lambda: bind_wheel_recursive(self, sf.canvas))

    def _protocol_changed(self) -> None:
        proto = str(self.vars["protocol"].get())
        if proto == "telnet" and str(self.vars["port"].get()) == "22": self.vars["port"].set("23")
        if proto == "rdp" and str(self.vars["port"].get()) in {"22", "23"}: self.vars["port"].set("3389")
        if proto == "serial" and not str(self.vars["serial_port"].get()): self.vars["serial_port"].set(str(self.vars["host"].get()))

    def _browse_key(self) -> None:
        p = filedialog.askopenfilename(title=t("private_key"))
        if p: self.vars["key_path"].set(p)

    def _make(self) -> Optional[Session]:
        name = str(self.vars["name"].get()).strip(); host = str(self.vars["host"].get()).strip()
        if not name or not host:
            self.status.configure(text=t("required"), fg=C["danger"]); return None
        try:
            port = int(str(self.vars["port"].get()).strip())
            if port <= 0 or port > 65535: raise ValueError
        except Exception:
            self.status.configure(text=t("bad_port"), fg=C["danger"]); return None
        try:
            baud = int(str(self.vars["serial_baud"].get()).strip() or "9600")
        except Exception:
            baud = 9600
        color = str(self.vars["group_color"].get()).strip() or C["accent"]
        if not is_hex(color): color = C["accent"]
        s = Session(
            id=self.session.id if self.session else uuid.uuid4().hex,
            name=name, host=host, port=port, username=str(self.vars["username"].get()).strip(),
            auth_mode=str(self.vars["auth_mode"].get()), key_path=str(self.vars["key_path"].get()).strip(),
            start_dir=str(self.vars["start_dir"].get()).strip(), group=str(self.vars["group"].get()).strip() or "Основные",
            color=color, group_color=color, notes=self.notes.get("1.0", "end-1c").strip(), protocol=str(self.vars["protocol"].get()),
            tags=str(self.vars["tags"].get()).strip(), favorite=bool(self.vars["favorite"].get()), save_password=bool(self.vars["save_password"].get()),
            tunnels=self.tunnels.get("1.0", "end-1c").strip(), serial_port=str(self.vars["serial_port"].get()).strip(), serial_baud=baud,
            order=self.session.order if self.session else 0, group_order=self.session.group_order if self.session else 0,
        )
        password = str(self.vars["password"].get())
        if password and password != "********" and s.save_password:
            ok = self.app.vault.set(s, password)
            self.status.configure(text=t("cred_ok") if ok else t("cred_unavailable"), fg=C["success"] if ok else C["muted"])
        if not s.save_password:
            self.app.vault.delete(s)
        return s

    def save_only(self) -> None:
        s = self._make()
        if not s: return
        self.app.store.upsert(s); self.app.refresh_sessions(); self.app.close_page(self)

    def save_connect(self) -> None:
        s = self._make()
        if not s: return
        self.app.store.upsert(s); self.app.refresh_sessions(); self.app.close_page(self); self.app.open_session(s)



class PresetsPage(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp") -> None:
        super().__init__(master, bg=C["bg"])
        self.app = app
        self.current_id: Optional[str] = None
        self.name_var = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = tk.Frame(self, bg=C["bg"], padx=18, pady=18)
        outer.pack(fill="both", expand=True)
        card = tk.Frame(outer, bg=C["surface"], padx=20, pady=18, highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True)
        tk.Label(card, text=t("command_presets"), bg=C["surface"], fg=C["text"], font=FONT_TITLE).pack(anchor="w", pady=(0, 14))
        body = tk.Frame(card, bg=C["surface"]); body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1); body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=C["surface"], width=260); left.grid(row=0, column=0, sticky="nsw", padx=(0, 14)); left.grid_propagate(False)
        self.tree = ttk.Treeview(left, columns=("commands",), show="tree", selectmode="browse", style="Dark.Treeview")
        self.tree.heading("#0", text=t("preset_name")); self.tree.column("#0", width=240, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.load_selected(), add="+")
        bind_wheel(self.tree, self.tree)
        form = tk.Frame(body, bg=C["surface"]); form.grid(row=0, column=1, sticky="nsew"); form.columnconfigure(1, weight=1); form.rowconfigure(3, weight=1)
        tk.Label(form, text=t("preset_name"), bg=C["surface"], fg=C["muted"], font=FONT_UI).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        tk.Entry(form, textvariable=self.name_var, bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI).grid(row=0, column=1, sticky="ew", pady=6, ipady=7)
        tk.Label(form, text=t("commands"), bg=C["surface"], fg=C["muted"], font=FONT_UI).grid(row=1, column=0, sticky="nw", pady=6, padx=(0, 12))
        tk.Label(form, text=t("one_per_line"), bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9), wraplength=700, justify="left").grid(row=1, column=1, sticky="w", pady=(6, 2))
        self.commands = tk.Text(form, height=14, bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI, wrap="word")
        self.commands.grid(row=2, column=1, sticky="nsew", pady=6)
        btns = tk.Frame(form, bg=C["surface"]); btns.grid(row=3, column=1, sticky="ew", pady=(10, 0))
        AppButton(btns, t("add_preset"), self.new_preset, kind="ghost").pack(side="left", padx=(0, 6))
        AppButton(btns, t("save"), self.save, kind="primary").pack(side="left", padx=(0, 6))
        AppButton(btns, t("delete_preset"), self.delete, kind="danger").pack(side="left", padx=(0, 6))
        AppButton(btns, t("cancel"), lambda: self.app.close_page(self), kind="ghost").pack(side="right")
        self.status = tk.Label(card, text="", bg=C["surface"], fg=C["accent2"], font=FONT_UI, anchor="w")
        self.status.pack(fill="x", pady=(12, 0))

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for preset in self.app.preset_store.presets:
            self.tree.insert("", "end", iid=preset.id, text=preset.name)
        self.app.refresh_preset_controls()

    def load_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        pid = sel[0]
        preset = next((p for p in self.app.preset_store.presets if p.id == pid), None)
        if not preset:
            return
        self.current_id = preset.id
        self.name_var.set(preset.name)
        self.commands.delete("1.0", "end")
        self.commands.insert("1.0", preset.commands)

    def new_preset(self) -> None:
        self.current_id = None
        self.name_var.set("")
        self.commands.delete("1.0", "end")
        self.status.configure(text="")

    def save(self) -> None:
        name = self.name_var.get().strip()
        commands = self.commands.get("1.0", "end-1c").strip()
        if not name or not commands:
            self.status.configure(text=t("preset_required"), fg=C["danger"])
            return
        preset = CommandPreset(id=self.current_id or uuid.uuid4().hex, name=name, commands=commands)
        self.app.preset_store.upsert(preset)
        self.current_id = preset.id
        self.status.configure(text=t("preset_saved"), fg=C["success"])
        self.refresh()
        try: self.tree.selection_set(preset.id)
        except Exception: pass

    def delete(self) -> None:
        if not self.current_id:
            return
        self.app.preset_store.delete(self.current_id)
        self.new_preset()
        self.status.configure(text=t("preset_deleted"), fg=C["success"])
        self.refresh()

class SettingsPage(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp") -> None:
        super().__init__(master, bg=C["bg"]); self.app = app
        theme_name = THEMES.get(app.settings.theme, {}).get("name", t("custom_theme")) if app.settings.theme != "custom" else t("custom_theme")
        self.vars: dict[str, tk.Variable] = {
            "language": tk.StringVar(value="Русский" if app.settings.language == "ru" else "English"),
            "theme": tk.StringVar(value=theme_name), "font_size": tk.StringVar(value=str(app.settings.font_size)),
            "connect_timeout": tk.StringVar(value=str(app.settings.connect_timeout)), "auth_timeout": tk.StringVar(value=str(app.settings.auth_timeout)),
            "keepalive": tk.StringVar(value=str(app.settings.keepalive)), "reconnect_delay": tk.StringVar(value=str(app.settings.reconnect_delay)),
            "auto_reconnect": tk.BooleanVar(value=app.settings.auto_reconnect), "encoding": tk.StringVar(value=app.settings.encoding),
            "animations": tk.BooleanVar(value=app.settings.animations),
        }
        self.color_vars = {k: tk.StringVar(value=app.settings.custom_colors.get(k, C.get(k, "#000000"))) for k in ["bg", "surface", "surface2", "accent", "text", "border", "term_bg", "term_fg"]}
        self._build()

    def _build(self) -> None:
        sf = ScrollFrame(self, bg=C["bg"]); sf.pack(fill="both", expand=True)
        card = tk.Frame(sf.content, bg=C["surface"], padx=24, pady=20, highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="x", padx=18, pady=18); card.columnconfigure(1, weight=1)
        tk.Label(card, text=t("settings_title"), bg=C["surface"], fg=C["text"], font=FONT_TITLE).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row = 1
        def entry(key: str) -> tk.Entry:
            return tk.Entry(card, textvariable=self.vars[key], bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI)
        def label(text: str) -> None:
            nonlocal row
            tk.Label(card, text=text, bg=C["surface"], fg=C["muted"], font=FONT_UI, anchor="w").grid(row=row, column=0, sticky="w", pady=7, padx=(0, 14))
        label(t("language")); DarkCombo(card, self.vars["language"], ["English", "Русский"]).grid(row=row, column=1, sticky="ew", pady=7); row += 1
        tk.Label(card, text=t("language_hint"), bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9), wraplength=760, justify="left").grid(row=row, column=1, sticky="w", pady=(0, 7)); row += 1
        label(t("theme")); DarkCombo(card, self.vars["theme"], [v["name"] for v in THEMES.values()] + [t("custom_theme")]).grid(row=row, column=1, sticky="ew", pady=7); row += 1
        for key, text in [("font_size", t("font_size")), ("encoding", t("encoding")), ("connect_timeout", t("connect_timeout")), ("auth_timeout", t("auth_timeout")), ("keepalive", t("keepalive")), ("reconnect_delay", t("reconnect_delay"))]:
            label(text); entry(key).grid(row=row, column=1, sticky="ew", pady=7, ipady=6); row += 1
        for key, text in [("auto_reconnect", "Автопереподключение" if self.app.settings.language == "ru" else "Auto reconnect"), ("animations", t("animations"))]:
            cb = tk.Checkbutton(card, text=text, variable=self.vars[key], bg=C["surface"], fg=C["text"], activebackground=C["surface"], activeforeground=C["text"], selectcolor=C["surface2"], font=FONT_UI)
            cb.grid(row=row, column=1, sticky="w", pady=6); row += 1
        tk.Label(card, text=t("custom_colors"), bg=C["surface"], fg=C["text"], font=FONT_UI_BOLD).grid(row=row, column=0, columnspan=2, sticky="w", pady=(18, 4)); row += 1
        tk.Label(card, text=t("color_palette_hint"), bg=C["surface"], fg=C["muted"], font=("Segoe UI", 9), wraplength=760, justify="left").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10)); row += 1
        def switch_to_custom(_color: str) -> None:
            self.vars["theme"].set(t("custom_theme"))
        for key, var in self.color_vars.items():
            tk.Label(card, text=color_role_name(key), bg=C["surface"], fg=C["muted"], font=FONT_UI).grid(row=row, column=0, sticky="w", pady=7)
            PaletteColorPicker(card, var, columns=12, on_change=switch_to_custom).grid(row=row, column=1, sticky="ew", pady=5)
            row += 1
        self.status = tk.Label(card, text="", bg=C["surface"], fg=C["accent2"], font=FONT_UI); self.status.grid(row=row, column=0, columnspan=2, sticky="ew", pady=8); row += 1
        btns = tk.Frame(card, bg=C["surface"]); btns.grid(row=row, column=0, columnspan=2, sticky="e")
        AppButton(btns, t("cancel"), lambda: self.app.close_page(self), kind="ghost").pack(side="left", padx=5)
        AppButton(btns, t("save"), self.save, kind="primary").pack(side="left")
        self.after(100, lambda: bind_wheel_recursive(self, sf.canvas))

    def save(self) -> None:
        try:
            s = self.app.settings
            name = str(self.vars["theme"].get())
            s.language = "ru" if str(self.vars["language"].get()) == "Русский" else "en"
            custom_labels = {TRANSLATIONS["en"]["custom_theme"], TRANSLATIONS["ru"]["custom_theme"]}
            s.theme = "custom" if name in custom_labels else next((k for k, v in THEMES.items() if v["name"] == name), "midnight")
            global CURRENT_LANGUAGE
            CURRENT_LANGUAGE = s.language
            s.font_size = int(str(self.vars["font_size"].get()))
            s.connect_timeout = int(str(self.vars["connect_timeout"].get()))
            s.auth_timeout = int(str(self.vars["auth_timeout"].get()))
            s.keepalive = int(str(self.vars["keepalive"].get()))
            s.reconnect_delay = int(str(self.vars["reconnect_delay"].get()))
            s.auto_reconnect = bool(self.vars["auto_reconnect"].get())
            s.encoding = str(self.vars["encoding"].get()) or "utf-8"
            s.animations = bool(self.vars["animations"].get())
            colors = {k: v.get().strip() for k, v in self.color_vars.items() if is_hex(v.get().strip())}
            s.custom_colors = colors
            s.save()
            self.status.configure(text=t("saved_restart"), fg=C["success"])
        except Exception as exc:
            self.status.configure(text=t("error", error=exc), fg=C["danger"])


class ContactsPage(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp") -> None:
        super().__init__(master, bg=C["bg"]); self.app = app; self.contacts = self._load(); self._build()

    def _load(self) -> dict[str, str]:
        paths = [exe_dir() / "contacts.json", resource_path("contacts.json")]
        for p in paths:
            try:
                if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
            except Exception: pass
        return {
            "email": "dev.equinox.e@gmail.com",
            "telegram_bot": "https://t.me/equinox_robot",
            "website": "https://github.com/Equinox-e/Orion_ssh",
            "support_text_ru": "Напишите нам, если нашли ошибку или нужна помощь с подключением.",
            "support_text_en": "Contact us if you found a bug or need help with a connection."
        }

    def _build(self) -> None:
        sf = ScrollFrame(self, bg=C["bg"]); sf.pack(fill="both", expand=True)
        card = tk.Frame(sf.content, bg=C["surface"], padx=24, pady=20, highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        title = "Справка и контакты" if self.app.settings.language == "ru" else "Help and contacts"
        tk.Label(card, text=title, bg=C["surface"], fg=C["text"], font=FONT_TITLE).pack(anchor="w")
        subtitle = ("Краткая справка по основным функциям OrionSSH и контакты поддержки." if self.app.settings.language == "ru"
                    else "Quick help for the main OrionSSH features and support contacts.")
        tk.Label(card, text=subtitle, bg=C["surface"], fg=C["muted"], font=FONT_UI, wraplength=900, justify="left").pack(anchor="w", fill="x", pady=(8, 16))

        help_card = tk.Frame(card, bg=C["surface2"], padx=16, pady=14, highlightthickness=1, highlightbackground=C["border"])
        help_card.pack(fill="x", pady=(0, 16))
        help_title = "Как пользоваться" if self.app.settings.language == "ru" else "How to use"
        tk.Label(help_card, text=help_title, bg=C["surface2"], fg=C["accent2"], font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 8))
        for head, body in self._help_sections():
            block = tk.Frame(help_card, bg=C["surface2"])
            block.pack(fill="x", pady=5)
            tk.Label(block, text=head, bg=C["surface2"], fg=C["text"], font=FONT_UI_BOLD).pack(anchor="w")
            tk.Label(block, text=body, bg=C["surface2"], fg=C["muted"], font=FONT_UI, wraplength=900, justify="left").pack(anchor="w", fill="x", pady=(2, 0))

        contact_title = "Контакты поддержки" if self.app.settings.language == "ru" else "Support contacts"
        tk.Label(card, text=contact_title, bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 15)).pack(anchor="w", pady=(0, 6))
        tk.Label(card, text=self.contacts.get("support_text_ru" if self.app.settings.language == "ru" else "support_text_en", t("support_body")), bg=C["surface"], fg=C["muted"], font=FONT_UI, wraplength=900, justify="left").pack(anchor="w", fill="x", pady=(0, 10))
        for label, key in [(t("email"), "email"), (t("telegram"), "telegram_bot"), (t("website"), "website")]:
            self._row(card, label, self.contacts.get(key, ""))
        AppButton(card, t("cancel"), lambda: self.app.close_page(self), kind="ghost").pack(anchor="e", pady=(20, 0))
        self.status = tk.Label(card, text="", bg=C["surface"], fg=C["accent2"], font=FONT_UI); self.status.pack(anchor="w", fill="x", pady=(12, 0))
        self.after(100, lambda: bind_wheel_recursive(self, sf.canvas))

    def _help_sections(self) -> list[tuple[str, str]]:
        if self.app.settings.language == "ru":
            return [
                ("Подключения", "Нажмите «+ Новое», заполните хост, порт, пользователя и тип входа. Группу можно выбрать из списка или создать новую."),
                ("Вкладки и несколько окон", "Кнопка ▶ открывает подключение. Кнопка ⧉ открывает ещё одну вкладку того же сервера. Split ↔ / Split ↕ создают рабочую область с несколькими независимыми панелями."),
                ("Терминал", "Кликните в терминал и вводите команды как в PuTTY. Ctrl+C, Ctrl+X и другие сочетания передаются на сервер. Ctrl+Shift+C / Ctrl+Shift+X копируют, Ctrl+Shift+V вставляет."),
                ("SFTP", "Кнопка «Файлы» открывает проводник сервера. Можно открывать папки, загружать, скачивать файлы и создавать каталоги."),
                ("Пресеты команд", "Во вкладке «Пресеты» создайте одну команду или список команд. Затем выберите пресет в терминале и нажмите «Run»."),
                ("Группы и порядок", "Фильтр групп показывает только нужные подключения. Стрелки у групп и карточек меняют порядок отображения."),
            ]
        return [
            ("Sessions", "Click + New, enter host, port, username and authentication type. You can pick an existing group or type a new one."),
            ("Tabs and split workspace", "▶ opens a connection. ⧉ opens another tab for the same server. Split ↔ / Split ↕ create a workspace with multiple independent panes."),
            ("Terminal", "Click the terminal and type like in PuTTY. Ctrl+C, Ctrl+X and other shortcuts are sent to the server. Ctrl+Shift+C / Ctrl+Shift+X copy, Ctrl+Shift+V pastes."),
            ("SFTP", "The Files button opens the server file manager. You can browse folders, upload, download and create directories."),
            ("Command presets", "Create one command or a command list in Presets. Then select it in a terminal and press Run."),
            ("Groups and order", "The group filter shows only matching sessions. Arrows near groups and cards change their display order."),
        ]

    def _row(self, parent: tk.Widget, label: str, value: str) -> None:
        box = tk.Frame(parent, bg=C["surface2"], padx=14, pady=12, highlightthickness=1, highlightbackground=C["border"])
        box.pack(fill="x", pady=6)
        tk.Label(box, text=label, bg=C["surface2"], fg=C["muted"], font=FONT_UI).pack(anchor="w")
        inner = tk.Frame(box, bg=C["surface2"]); inner.pack(fill="x", pady=(6, 0))
        tk.Label(inner, text=value or "—", bg=C["surface2"], fg=C["text"], font=FONT_UI_BOLD, anchor="w", wraplength=650).pack(side="left", fill="x", expand=True)
        AppButton(inner, t("copy"), lambda v=value: self._copy(v), kind="secondary").pack(side="right")

    def _copy(self, value: str) -> None:
        self.clipboard_clear(); self.clipboard_append(value); self.status.configure(text=t("copied"), fg=C["success"])


class RemoteFileBrowserPage(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp", tab: TerminalTab) -> None:
        super().__init__(master, bg=C["bg"]); self.app = app; self.tab = tab; self.sftp = tab._get_sftp()
        self.current_path = self._initial_path(); self.items: dict[str, dict[str, Any]] = {}; self.new_folder = tk.StringVar(); self._build(); self.load_path(self.current_path)

    def _initial_path(self) -> str:
        if self.tab.session.start_dir: return self.tab.session.start_dir
        try: return self.sftp.getcwd() or "."
        except Exception: return "."

    def _build(self) -> None:
        top = tk.Frame(self, bg=C["surface"], padx=10, pady=10, highlightthickness=1, highlightbackground=C["border"]); top.pack(fill="x", padx=10, pady=(10, 0))
        AppButton(top, t("up"), self.go_up, kind="ghost").pack(side="left", padx=(0, 6))
        tk.Label(top, text=t("path"), bg=C["surface"], fg=C["muted"], font=FONT_UI).pack(side="left", padx=(0, 6))
        self.path_var = tk.StringVar(value=self.current_path)
        tk.Entry(top, textvariable=self.path_var, bg=C["term_bg"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI).pack(side="left", fill="x", expand=True, ipady=7)
        AppButton(top, t("go"), lambda: self.load_path(self.path_var.get()), kind="primary").pack(side="left", padx=(8, 0))
        AppButton(top, t("refresh"), lambda: self.load_path(self.current_path), kind="ghost").pack(side="left", padx=(6, 0))
        body = tk.Frame(self, bg=C["bg"], padx=10, pady=10); body.pack(fill="both", expand=True)
        cols = ("type", "size", "modified")
        self.tree = ttk.Treeview(body, columns=cols, show="tree headings", selectmode="browse", style="Dark.Treeview")
        for col, text, width, anchor in [("#0", t("name_col"), 420, "w"), ("type", t("type_col"), 120, "w"), ("size", t("size_col"), 120, "e"), ("modified", t("modified_col"), 190, "w")]:
            self.tree.heading(col, text=text, anchor=anchor); self.tree.column(col, width=width, anchor=anchor)
        y = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview); x = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set); self.tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1); body.columnconfigure(0, weight=1); bind_wheel(self.tree, self.tree)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        if DND_FILES is not None:
            try:
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<Drop>>", self._drop)  # type: ignore[attr-defined]
            except Exception:
                pass
        bottom = tk.Frame(self, bg=C["surface"], padx=10, pady=10, highlightthickness=1, highlightbackground=C["border"]); bottom.pack(fill="x", padx=10, pady=(0, 10))
        AppButton(bottom, t("open_folder"), self.open_selected, kind="ghost").pack(side="left", padx=(0, 6))
        AppButton(bottom, t("download"), self.download_selected, kind="primary").pack(side="left", padx=(0, 6))
        AppButton(bottom, t("upload"), self.upload_here, kind="primary").pack(side="left", padx=(0, 6))
        tk.Label(bottom, text=t("new_folder"), bg=C["surface"], fg=C["muted"], font=FONT_UI).pack(side="left", padx=(10, 6))
        tk.Entry(bottom, textvariable=self.new_folder, bg=C["term_bg"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI, width=18).pack(side="left", ipady=7)
        AppButton(bottom, t("create"), self.create_folder, kind="ghost").pack(side="left", padx=(6, 0))
        AppButton(bottom, t("cancel"), lambda: self.app.close_page(self), kind="ghost").pack(side="right")
        self.status = tk.Label(self, text=t("drop_hint") if DND_FILES is not None else t("dnd_off"), bg=C["bg"], fg=C["accent2"], font=FONT_UI, anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 8))

    def _fmt_size(self, n: int) -> str:
        if n < 1024: return str(n)
        value = float(n)
        for unit in ["KB", "MB", "GB", "TB"]:
            value /= 1024
            if value < 1024: return f"{value:.1f} {unit}"
        return f"{value:.1f} PB"

    def _fmt_time(self, m: int) -> str:
        try: return time.strftime("%Y-%m-%d %H:%M", time.localtime(m))
        except Exception: return ""

    def _join(self, base: str, name: str) -> str:
        return name if base in {"", "."} else posixpath.normpath(posixpath.join(base, name))

    def load_path(self, path: str) -> None:
        path = path.strip() or "."
        try: entries = self.sftp.listdir_attr(path)
        except Exception as exc:
            self.status.configure(text=t("error", error=exc), fg=C["danger"]); return
        self.current_path = path; self.path_var.set(path); self.tree.delete(*self.tree.get_children()); self.items.clear()
        entries = sorted(entries, key=lambda e: (not stat.S_ISDIR(e.st_mode), e.filename.lower()))
        for entry in entries:
            is_dir = stat.S_ISDIR(entry.st_mode); iid = uuid.uuid4().hex; remote = self._join(path, entry.filename)
            self.items[iid] = {"path": remote, "name": entry.filename, "is_dir": is_dir}
            self.tree.insert("", "end", iid=iid, text=("📁 " if is_dir else "📄 ") + entry.filename,
                             values=(t("folder") if is_dir else t("file"), "" if is_dir else self._fmt_size(int(getattr(entry, "st_size", 0) or 0)), self._fmt_time(int(getattr(entry, "st_mtime", 0) or 0))))
        self.status.configure(text=t("drop_hint") if DND_FILES is not None else t("dnd_off"), fg=C["accent2"])

    def selected(self) -> Optional[dict[str, Any]]:
        sel = self.tree.selection(); return self.items.get(sel[0]) if sel else None

    def open_selected(self) -> None:
        item = self.selected()
        if not item: self.status.configure(text=t("select_folder"), fg=C["danger"]); return
        if item["is_dir"]: self.load_path(item["path"])
        else: self.download_selected()

    def go_up(self) -> None:
        self.load_path(posixpath.dirname(self.current_path.rstrip("/")) or "/")

    def upload_here(self) -> None:
        files = filedialog.askopenfilenames(title=t("upload"))
        for f in files: self._upload_one(f)

    def _upload_one(self, local: str) -> None:
        if not local: return
        remote = self._join(self.current_path, Path(local).name)
        self.status.configure(text=t("scp_drop_started", name=Path(local).name, remote=remote), fg=C["accent2"])
        threading.Thread(target=self._upload_worker, args=(local, remote), daemon=True).start()

    def _upload_worker(self, local: str, remote: str) -> None:
        try:
            self.sftp.put(local, remote)
            self.after(0, lambda: (self.status.configure(text=t("upload_done", remote=remote), fg=C["success"]), self.load_path(self.current_path)))
        except Exception as exc:
            self.after(0, lambda: self.status.configure(text=t("error", error=exc), fg=C["danger"]))

    def _drop(self, event: Any) -> str:
        try:
            files = self.tk.splitlist(event.data)
        except Exception:
            files = [event.data]
        for f in files:
            p = str(f).strip("{}")
            if Path(p).is_file(): self._upload_one(p)
        return "break"

    def download_selected(self) -> None:
        item = self.selected()
        if not item or item["is_dir"]: self.status.configure(text=t("select_file"), fg=C["danger"]); return
        local = filedialog.asksaveasfilename(title=t("download"), initialfile=item["name"])
        if not local: return
        threading.Thread(target=self._download_worker, args=(item["path"], local), daemon=True).start()

    def _download_worker(self, remote: str, local: str) -> None:
        try:
            self.sftp.get(remote, local)
            self.after(0, lambda: self.status.configure(text=t("download_done", local=local), fg=C["success"]))
        except Exception as exc:
            self.after(0, lambda: self.status.configure(text=t("error", error=exc), fg=C["danger"]))

    def create_folder(self) -> None:
        name = self.new_folder.get().strip()
        if not name: return
        try:
            self.sftp.mkdir(self._join(self.current_path, name)); self.new_folder.set(""); self.load_path(self.current_path)
        except Exception as exc:
            self.status.configure(text=t("error", error=exc), fg=C["danger"])


class HomePage(tk.Frame):
    def __init__(self, master: tk.Widget, app: "OrionSSHApp") -> None:
        super().__init__(master, bg=C["bg"]); self.app = app; self._build()

    def _build(self) -> None:
        sf = ScrollFrame(self, bg=C["bg"]); sf.pack(fill="both", expand=True)
        wrap = tk.Frame(sf.content, bg=C["bg"], padx=26, pady=24); wrap.pack(fill="both", expand=True)
        hero = tk.Frame(wrap, bg=C["bg"]); hero.pack(fill="x")
        tk.Label(hero, text=t("welcome_title"), bg=C["bg"], fg=C["text"], font=("Segoe UI Semibold", 34)).pack(anchor="w")
        tk.Label(hero, text=t("welcome_body"), bg=C["bg"], fg=C["muted"], font=("Segoe UI", 12), wraplength=940, justify="left").pack(anchor="w", pady=(8, 18))

        stat_row = tk.Frame(wrap, bg=C["bg"]); stat_row.pack(fill="x", pady=(0, 14))
        sessions = self.app.store.sessions
        groups = {s.group or "Default" for s in sessions}
        stats = [
            (t("total_sessions"), str(len(sessions))),
            (t("favorites_count"), str(sum(1 for s in sessions if s.favorite))),
            (t("groups_count"), str(len(groups) if sessions else 0)),
            (t("presets_count"), str(len(self.app.preset_store.presets))),
        ]
        for i, (label, value) in enumerate(stats):
            stat_row.columnconfigure(i, weight=1)
            box = tk.Frame(stat_row, bg=C["surface"], padx=16, pady=14, highlightthickness=2, highlightbackground=C["border"])
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0 if i == len(stats)-1 else 6))
            tk.Label(box, text=value, bg=C["surface"], fg=C["accent"], font=("Segoe UI Semibold", 24)).pack(anchor="w")
            tk.Label(box, text=label, bg=C["surface"], fg=C["muted"], font=FONT_UI_BOLD).pack(anchor="w")

        card = tk.Frame(wrap, bg=C["surface"], padx=22, pady=18, highlightthickness=2, highlightbackground=C["border"]); card.pack(fill="x", pady=(0, 14))
        tk.Label(card, text=t("quick"), bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 18)).pack(anchor="w")
        grid = tk.Frame(card, bg=C["surface"]); grid.pack(fill="x", pady=(12, 0)); grid.columnconfigure(1, weight=1)
        self.host = tk.StringVar(); self.port = tk.StringVar(value="22"); self.user = tk.StringVar()
        for r, (label, var) in enumerate([(t("host"), self.host), (t("port"), self.port), (t("username"), self.user)]):
            tk.Label(grid, text=label, bg=C["surface"], fg=C["muted"], font=FONT_UI).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=6)
            tk.Entry(grid, textvariable=var, bg=C["surface2"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI).grid(row=r, column=1, sticky="ew", pady=6, ipady=7)
        AppButton(card, t("connect"), self.quick_connect, kind="primary").pack(anchor="e", pady=(12, 0))

        lower = tk.Frame(wrap, bg=C["bg"]); lower.pack(fill="both", expand=True)
        lower.columnconfigure(0, weight=2); lower.columnconfigure(1, weight=1)
        recent = tk.Frame(lower, bg=C["surface"], padx=18, pady=16, highlightthickness=2, highlightbackground=C["border"])
        recent.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(recent, text=t("recent_sessions"), bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(0, 10))
        shown = sorted(sessions, key=lambda s: (not s.favorite, s.name.lower()))[:6]
        if shown:
            for sess in shown:
                row = tk.Frame(recent, bg=C["surface2"], padx=12, pady=9, highlightthickness=1, highlightbackground=sess.group_color or C["border"], cursor="hand2")
                row.pack(fill="x", pady=4)
                tk.Label(row, text=("★ " if sess.favorite else "") + sess.name, bg=C["surface2"], fg=C["text"], font=FONT_UI_BOLD).pack(side="left")
                tk.Label(row, text=f"{sess.protocol.upper()}  {sess.username + '@' if sess.username else ''}{sess.host}:{sess.port}", bg=C["surface2"], fg=C["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))
                AppButton(row, "▶", lambda s=sess: self.app.open_session(s), kind="ghost", width=3).pack(side="right")
                row.bind("<Double-1>", lambda _e, s=sess: self.app.open_session(s), add="+")
        else:
            tk.Label(recent, text=t("no_sessions"), bg=C["surface"], fg=C["muted"], font=FONT_UI).pack(anchor="w")

        actions = tk.Frame(lower, bg=C["surface"], padx=18, pady=16, highlightthickness=2, highlightbackground=C["border"])
        actions.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(actions, text=t("quick_actions"), bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(0, 10))
        AppButton(actions, t("new_session"), self.app.add_session, kind="primary").pack(fill="x", pady=4)
        AppButton(actions, t("presets"), self.app.open_presets, kind="ghost").pack(fill="x", pady=4)
        AppButton(actions, t("settings"), self.app.open_settings, kind="ghost").pack(fill="x", pady=4)
        AppButton(actions, t("contacts"), self.app.open_contacts, kind="ghost").pack(fill="x", pady=4)
        tip = tk.Frame(actions, bg=C["surface2"], padx=12, pady=12, highlightthickness=1, highlightbackground=C["border"])
        tip.pack(fill="x", pady=(14, 0))
        tk.Label(tip, text=t("tip_title"), bg=C["surface2"], fg=C["accent2"], font=FONT_UI_BOLD).pack(anchor="w")
        tk.Label(tip, text=t("tip_text"), bg=C["surface2"], fg=C["muted"], font=FONT_UI, wraplength=300, justify="left").pack(anchor="w", fill="x", pady=(4, 0))
        self.after(100, lambda: bind_wheel_recursive(self, sf.canvas))

    def quick_connect(self) -> None:
        try:
            port = int(self.port.get() or "22")
            if port <= 0 or port > 65535: raise ValueError
        except Exception:
            messagebox.showerror(APP_NAME, t("bad_port")); return
        host = self.host.get().strip()
        if not host:
            messagebox.showerror(APP_NAME, t("required")); return
        s = Session(id=uuid.uuid4().hex, name=host, host=host, port=port, username=self.user.get().strip(), protocol="ssh", auth_mode="password")
        self.app.open_session(s)


class OrionSSHApp(BASE_TK):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings(); apply_colors(self.settings)
        global CURRENT_LANGUAGE
        CURRENT_LANGUAGE = self.settings.language
        self.store = SessionStore(); self.preset_store = PresetStore(); self.vault = PasswordVault(); self.tabs: dict[str, TerminalTab] = {}
        self.title(f"{APP_NAME} {APP_VERSION}"); self.geometry("1220x760"); self.minsize(980, 620); self.configure(bg=C["bg"])
        try:
            self.iconbitmap(str(resource_path("assets/orionssh.ico")))
        except Exception: pass
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._style(); self._build()

    def _style(self) -> None:
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("Dark.Treeview", background=C["surface2"], fieldbackground=C["surface2"], foreground=C["text"], rowheight=26, bordercolor=C["border"], lightcolor=C["border"], darkcolor=C["border"])
        style.configure("Dark.Treeview.Heading", background=C["surface3"], foreground=C["text"], relief="solid", font=FONT_UI_BOLD)
        style.map("Dark.Treeview", background=[("selected", C["accent"])], foreground=[("selected", "#06111d")])
        style.configure("Vertical.TScrollbar", background=C["surface3"], troughcolor=C["surface"], arrowcolor=C["text"], bordercolor=C["border"])
        style.configure("Horizontal.TScrollbar", background=C["surface3"], troughcolor=C["surface"], arrowcolor=C["text"], bordercolor=C["border"])
        style.configure("Dark.TCombobox", fieldbackground=C["surface2"], background=C["surface2"], foreground=C["text"], bordercolor=C["border"], arrowcolor=C["text"], padding=6)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", C["surface2"])], foreground=[("readonly", C["text"])] )

    def _build(self) -> None:
        root = tk.Frame(self, bg=C["bg"]); root.pack(fill="both", expand=True)
        side = tk.Frame(root, bg=C["surface"], width=320, highlightthickness=1, highlightbackground=C["border"]); side.pack(side="left", fill="y"); side.pack_propagate(False)
        logo_row = tk.Frame(side, bg=C["surface"], padx=18, pady=16); logo_row.pack(fill="x")
        try:
            img = tk.PhotoImage(file=str(resource_path("assets/orionssh.png"))).subsample(6, 6)
            self.logo_img = img
            tk.Label(logo_row, image=img, bg=C["surface"]).pack(side="left", padx=(0, 10))
        except Exception:
            tk.Label(logo_row, text="▸", bg=C["surface"], fg=C["accent"], font=("Segoe UI", 24)).pack(side="left", padx=(0, 10))
        tk.Label(logo_row, text=APP_NAME, bg=C["surface"], fg=C["text"], font=("Segoe UI Semibold", 22)).pack(side="left")
        btnrow = tk.Frame(side, bg=C["surface"], padx=14); btnrow.pack(fill="x")
        btnrow.columnconfigure(0, weight=1); btnrow.columnconfigure(1, weight=1)
        AppButton(btnrow, t("new"), self.add_session, kind="primary").grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        AppButton(btnrow, t("presets"), self.open_presets, kind="ghost").grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        AppButton(btnrow, t("settings"), self.open_settings, kind="ghost").grid(row=1, column=0, sticky="ew", padx=(0, 4))
        AppButton(btnrow, t("contacts"), self.open_contacts, kind="ghost").grid(row=1, column=1, sticky="ew", padx=(4, 0))
        self.search = tk.StringVar(); self.search.trace_add("write", lambda *_: self.refresh_sessions())
        tk.Entry(side, textvariable=self.search, bg=C["term_bg"], fg=C["text"], insertbackground=C["text"], relief="solid", bd=2, highlightthickness=2, highlightbackground=C["border"], font=FONT_UI).pack(fill="x", padx=14, pady=(12, 6), ipady=7)
        self.group_filter = tk.StringVar(value=t("all_groups"))
        self.group_filter_combo = DarkCombo(side, self.group_filter, [t("all_groups")], command=lambda _v: self.refresh_sessions())
        self.group_filter_combo.pack(fill="x", padx=14, pady=(0, 12))
        list_outer = tk.Frame(side, bg=C["surface"]); list_outer.pack(fill="both", expand=True)
        self.session_canvas = tk.Canvas(list_outer, bg=C["surface"], highlightthickness=0)
        sc = ttk.Scrollbar(list_outer, orient="vertical", command=self.session_canvas.yview)
        self.session_list = tk.Frame(self.session_canvas, bg=C["surface"])
        win = self.session_canvas.create_window((0, 0), window=self.session_list, anchor="nw")
        self.session_canvas.configure(yscrollcommand=sc.set); self.session_canvas.pack(side="left", fill="both", expand=True); sc.pack(side="right", fill="y")
        self.session_list.bind("<Configure>", lambda _e: self.session_canvas.configure(scrollregion=self.session_canvas.bbox("all")))
        self.session_canvas.bind("<Configure>", lambda e: self.session_canvas.itemconfigure(win, width=e.width))
        bind_wheel_recursive(list_outer, self.session_canvas)
        bottom = tk.Frame(side, bg=C["surface"], padx=14, pady=10); bottom.pack(fill="x")
        AppButton(bottom, t("import"), self.import_sessions, kind="ghost").pack(side="left", fill="x", expand=True, padx=(0, 4))
        AppButton(bottom, t("export"), self.export_sessions, kind="ghost").pack(side="left", fill="x", expand=True, padx=(4, 0))
        main = tk.Frame(root, bg=C["bg"]); main.pack(side="left", fill="both", expand=True)
        self.book = TabBook(main, on_close=self._tab_closed); self.book.pack(fill="both", expand=True)
        self.home = HomePage(self.book.content, self); self.book.add(self.home, t("home"), closable=False)
        self.refresh_sessions()

    def _refresh_group_filter_options(self) -> None:
        if not hasattr(self, "group_filter_combo"):
            return
        current = self.group_filter.get() if hasattr(self, "group_filter") else t("all_groups")
        values = [t("all_groups")] + self.store.group_names()
        if current not in values:
            current = t("all_groups")
            self.group_filter.set(current)
        try:
            self.group_filter_combo.set_values(values)
        except Exception:
            pass

    def refresh_sessions(self) -> None:
        self._refresh_group_filter_options()
        for w in self.session_list.winfo_children():
            w.destroy()
        q = self.search.get().lower().strip() if hasattr(self, "search") else ""
        selected_group = self.group_filter.get() if hasattr(self, "group_filter") else t("all_groups")
        sessions = []
        for s in self.store.sessions:
            haystack = " ".join([s.name, s.host, s.username, s.group, s.tags, s.notes, s.protocol]).lower()
            if q and q not in haystack:
                continue
            if selected_group != t("all_groups") and (s.group or "Основные") != selected_group:
                continue
            sessions.append(s)
        if not sessions:
            tk.Label(self.session_list, text=t("no_sessions"), bg=C["surface"], fg=C["muted"], font=FONT_UI, padx=16, pady=14).pack(anchor="w")
            return
        grouped: dict[str, list[Session]] = {}
        for s in sessions:
            grouped.setdefault(s.group or "Основные", []).append(s)
        all_groups = self.store.group_names()
        group_sort = {g: i for i, g in enumerate(all_groups)}
        for group in sorted(grouped, key=lambda g: (group_sort.get(g, 9999), g.lower())):
            rows = sorted(grouped[group], key=lambda x: (x.order, not x.favorite, x.name.lower()))
            color = rows[0].group_color or C["accent"]
            self._group_header(group, color)
            for sess in rows:
                self._session_card(sess)

    def _group_header(self, group: str, color: str) -> None:
        row = tk.Frame(self.session_list, bg=C["surface"], padx=14, pady=6)
        row.pack(fill="x")
        tk.Label(row, text="■", bg=C["surface"], fg=color, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(row, text=group.upper(), bg=C["surface"], fg=C["muted"], font=("Segoe UI Semibold", 8), anchor="w").pack(side="left", padx=(5, 0), fill="x", expand=True)
        for text, cmd in [("↑", lambda g=group: self.move_group(g, -1)), ("↓", lambda g=group: self.move_group(g, 1))]:
            btn = AppButton(row, text, cmd, kind="ghost", padx=4, pady=1, width=2, font=("Segoe UI Symbol", 8, "bold"))
            btn.pack(side="right", padx=1)
        bind_wheel_recursive(row, self.session_canvas)

    def _fixed_button(self, parent: tk.Widget, text: str, command: Callable[[], None], kind: str = "ghost") -> tk.Widget:
        holder = tk.Frame(parent, bg=C["surface2"], width=36, height=30)
        holder.pack_propagate(False)
        btn = AppButton(holder, text, command, kind=kind, width=2, padx=0, pady=0, font=("Segoe UI Symbol", 10, "bold"))
        btn.pack(fill="both", expand=True)
        return holder

    def _session_card(self, s: Session) -> None:
        frame = tk.Frame(self.session_list, bg=C["surface2"], padx=10, pady=8, highlightthickness=1, highlightbackground=s.group_color or C["border"], cursor="hand2")
        frame.pack(fill="x", padx=12, pady=5)
        frame.columnconfigure(0, weight=1, minsize=120)
        frame.columnconfigure(1, weight=0, minsize=122)
        left = tk.Frame(frame, bg=C["surface2"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        title = ("★ " if s.favorite else "") + s.name
        tk.Label(left, text=title, bg=C["surface2"], fg=C["text"], font=FONT_UI_BOLD, anchor="w", wraplength=155, justify="left").pack(anchor="w", fill="x")
        sub = f"{s.protocol.upper()}  {s.username + '@' if s.username else ''}{s.host}:{s.port}"
        tk.Label(left, text=sub, bg=C["surface2"], fg=C["muted"], font=("Segoe UI", 9), anchor="w", wraplength=155, justify="left").pack(anchor="w", fill="x")
        if s.tags:
            tk.Label(left, text="🏷 " + s.tags, bg=C["surface2"], fg=C["accent2"], font=("Segoe UI", 9), anchor="w", wraplength=155, justify="left").pack(anchor="w", fill="x", pady=(2, 0))
        if s.notes:
            prev = s.notes.replace("\n", " ")[:90] + ("…" if len(s.notes) > 90 else "")
            tk.Label(left, text=prev, bg=C["surface2"], fg=C["muted"], font=("Segoe UI", 9), anchor="w", wraplength=155, justify="left").pack(anchor="w", fill="x", pady=(2, 0))
        right = tk.Frame(frame, bg=C["surface2"], width=118)
        right.grid(row=0, column=1, sticky="ne")
        top = tk.Frame(right, bg=C["surface2"]); top.pack(anchor="e")
        bottom = tk.Frame(right, bg=C["surface2"]); bottom.pack(anchor="e", pady=(4, 0))
        for holder in [
            self._fixed_button(top, "▶", lambda s=s: self.open_session(s), "ghost"),
            self._fixed_button(top, "⧉", lambda s=s: self.open_session(s, force_new=True), "ghost"),
            self._fixed_button(top, "✎", lambda s=s: self.edit_session(s), "ghost"),
        ]:
            holder.pack(side="left", padx=2)
        for holder in [
            self._fixed_button(bottom, "↑", lambda s=s: self.move_session(s, -1), "ghost"),
            self._fixed_button(bottom, "↓", lambda s=s: self.move_session(s, 1), "ghost"),
            self._fixed_button(bottom, "×", lambda s=s: self.delete_session(s), "danger"),
        ]:
            holder.pack(side="left", padx=2)
        for w in (frame, left):
            w.bind("<Double-1>", lambda _e: self.open_session(s), add="+")
        bind_wheel_recursive(frame, self.session_canvas)

    def move_group(self, group: str, direction: int) -> None:
        self.store.move_group(group, direction)
        self.refresh_sessions()

    def move_session(self, session: Session, direction: int) -> None:
        self.store.move_session(session.id, direction)
        self.refresh_sessions()

    def open_session(self, s: Session, force_new: bool = False) -> None:
        if not force_new and s.id in self.tabs:
            self.book.select(self.tabs[s.id])
            return
        tab = TerminalTab(self.book.content, self, s)
        key = None if force_new else f"terminal:{s.id}"
        self.book.add(tab, s.name, closable=True, key=key)
        self.tabs[s.id if not force_new else f"{s.id}:{uuid.uuid4().hex}"] = tab

    def add_session(self) -> None:
        self.book.add(SessionEditor(self.book.content, self), t("new_session"), closable=True, key="editor:new")

    def edit_session(self, s: Session) -> None:
        self.book.add(SessionEditor(self.book.content, self, s), f"{t('edit')}: {s.name}", closable=True, key=f"editor:{s.id}")

    def delete_session(self, s: Session) -> None:
        if messagebox.askyesno(APP_NAME, t("delete_confirm", name=s.name)):
            self.store.delete(s.id); self.vault.delete(s); self.refresh_sessions()

    def open_settings(self) -> None:
        self.book.add(SettingsPage(self.book.content, self), t("settings"), closable=True, key="settings")

    def open_contacts(self) -> None:
        self.book.add(ContactsPage(self.book.content, self), t("contacts"), closable=True, key="contacts")

    def open_presets(self) -> None:
        self.book.add(PresetsPage(self.book.content, self), t("presets"), closable=True, key="presets")

    def open_split_workspace(self, session: Optional[Session] = None, orientation: str = "horizontal") -> None:
        title = f"{t('split_title')}: {session.name}" if session is not None else t("split_title")
        self.book.add(SplitTerminalPage(self.book.content, self, session, orientation), title, closable=True)

    def refresh_preset_controls(self) -> None:
        for tab in list(self.tabs.values()):
            try: tab.refresh_presets()
            except Exception: pass

    def open_remote_file_browser(self, tab: TerminalTab) -> None:
        self.book.add(RemoteFileBrowserPage(self.book.content, self, tab), f"{t('file_browser')} — {tab.session.name}", closable=True, key=f"files:{id(tab)}")

    def close_page(self, page: tk.Widget) -> None:
        self.book.close(page)

    def _tab_closed(self, page: tk.Widget) -> None:
        if isinstance(page, TerminalTab):
            page.disconnect()
            for sid, tab in list(self.tabs.items()):
                if tab is page: self.tabs.pop(sid, None)
        elif isinstance(page, SplitTerminalPage):
            page.disconnect()

    def ask_password(self, prompt: str, allow_empty: bool = False) -> Optional[str]:
        result: dict[str, Optional[str]] = {"value": None}; ev = threading.Event()
        def ask() -> None:
            v = simpledialog.askstring(APP_NAME, prompt, show="*", parent=self)
            result["value"] = v if (allow_empty or v) else None; ev.set()
        self.after(0, ask); ev.wait(); return result["value"]

    def import_sessions(self) -> None:
        p = filedialog.askopenfilename(title=t("import"), filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not p: return
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8")); rows = data.get("sessions", data if isinstance(data, list) else [])
            count = 0
            for row in rows:
                if isinstance(row, dict): self.store.upsert(Session.from_dict(row)); count += 1
            self.refresh_sessions(); messagebox.showinfo(APP_NAME, t("imported", count=count))
        except Exception as exc:
            messagebox.showerror(APP_NAME, t("error", error=exc))

    def export_sessions(self) -> None:
        p = filedialog.asksaveasfilename(title=t("export"), defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not p: return
        try:
            Path(p).write_text(json.dumps({"app": APP_NAME, "version": APP_VERSION, "sessions": [s.safe_dict() for s in self.store.sessions]}, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo(APP_NAME, t("exported"))
        except Exception as exc:
            messagebox.showerror(APP_NAME, t("error", error=exc))

    def on_close(self) -> None:
        self.settings.save()
        for tab in list(self.tabs.values()):
            try: tab.disconnect()
            except Exception: pass
        self.destroy()


def main() -> None:
    app = OrionSSHApp()
    app.mainloop()

if __name__ == "__main__":
    main()
