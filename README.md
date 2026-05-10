# OrionSSH

<p align="center">
  <img src="docs/screenshots/banner.png" alt="OrionSSH banner" width="100" />
</p>

<p align="center">
  <b>A modern Windows SSH client with sessions, tabs, SFTP, themes, command presets, and secure credential storage.</b>
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ru.md">Русский</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version 1.0.0" />
  <img src="https://img.shields.io/badge/platform-Windows-0078D6" alt="Windows" />
  <img src="https://img.shields.io/badge/python-3.12%2B-yellow" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT" />
</p>

---

## Screenshots



<p align="center">
  <img src="docs/screenshots/main.png" alt="OrionSSH home screen" width="850" />
</p>

<p align="center">
  <img src="docs/screenshots/console.png" alt="OrionSSH terminal" width="850" />
  <img src="docs/screenshots/sftp.png" alt="OrionSSH SFTP file manager" width="850" />
</p>

<p align="center">
  <img src="docs/screenshots/settings.png" alt="OrionSSH settings" width="850" />
  <img src="docs/screenshots/presets.png" alt="OrionSSH command presets" width="850" />
</p>

---

## About

**OrionSSH** is a desktop SSH client for Windows designed for everyday server administration. It combines a tab-based terminal, saved connections, SFTP file management, secure password storage, themes, command presets, and SSH tunneling in a single application window.

The goal of OrionSSH is to provide a clean and familiar SSH workflow while keeping the interface simple, customizable, and comfortable for long sessions.

---

## Features

### Terminal

- SSH terminal with direct keyboard input, similar to PuTTY-style clients.
- Support for common key combinations such as `Ctrl+C`, `Ctrl+X`, `Ctrl+O`, arrows, `Tab`, function keys, and terminal shortcuts.
- Improved rendering for TUI applications such as `nano`, `vim`, `htop`, and `mc`.
- Tabbed connections with close buttons.
- Option to open the same session in a new tab.
- Auto-reconnect when a connection is interrupted.

### Sessions

- Save and manage SSH connection profiles.
- Store host, port, username, notes, tags, protocol, and group color.
- Favorites for frequently used servers.
- Tags and color groups for better organization.
- Search and filtering for saved sessions.
- Quick connect from the home screen.

### Security

- Password storage through **Windows Credential Manager**.
- Session data is stored separately from passwords.
- SSH key authentication support.
- Configurable connection timeout, authentication timeout, keepalive, and reconnect delay.

### File Management

- Built-in SFTP file browser.
- Browse remote directories like a file manager.
- Upload and download files.
- Create folders on the server.
- Drag-and-drop file upload support where available.
- SCP-oriented workflow for fast file transfer tasks.

### SSH Tunneling

- Local port forwarding.
- Saved tunnel configuration per session.
- Useful for forwarding databases, internal panels, development services, and private web interfaces through SSH.

### Command Presets

- Create reusable command presets.
- Store one command or a list of commands.
- Run a preset in the active terminal with one click.
- Useful for deployment, diagnostics, log viewing, updates, and routine administration.

### Customization

- Light and dark-inspired visual themes.
- Built-in theme presets.
- Custom theme editor with color palette selection.
- Adjustable terminal font size.
- Configurable terminal dimensions.
- Smooth UI mode and optional animations.

### Additional Protocols

OrionSSH is focused on SSH, but also includes optional connection modes:

- SSH
- Telnet, experimental
- RDP via Windows Remote Desktop client
- Serial connections, experimental

---

## Installation

### Portable EXE

Download or build `OrionSSH.exe`, then run it directly.

```bat
OrionSSH.exe
```

### Build from source

Requirements:

- Windows 10/11
- Python 3.12 or newer
- Git, optional

Clone the repository:

```bat
git clone https://github.com/YOUR_USERNAME/OrionSSH.git
cd OrionSSH
```

Run the application without building:

```bat
run_windows.bat
```

Build a portable executable:

```bat
build_windows.bat
```

The executable will be created here:

```text
dist\OrionSSH.exe
```

---

## Project Structure

```text
OrionSSH/
├─ src/
│  └─ main.py
├─ assets/
│  └─ orionssh.ico
├─ installer/
│  └─ OrionSSH.iss
├─ docs/
│  └─ screenshots/
├─ contacts.json
├─ requirements.txt
├─ run_windows.bat
├─ build_windows.bat
├─ README.md
└─ README.ru.md
```

---

## Roadmap Ideas

- More terminal compatibility improvements.
- More file transfer tools.
- Import and export of sessions.
- Synchronization of settings across devices.
- More protocol-specific settings.
- Plugin system.

---

## License

This project is distributed under the MIT License. See `LICENSE` for details.

---

<p align="center">
  Made for comfortable SSH work on Windows.
</p>
