<p align="center">
  <img src="docs/screenshots/banner.png" alt="OrionSSH banner" width="160" />
</p>

<h1 align="center">OrionSSH</h1>

<p align="center">
  A modern Windows SSH/SFTP client built with Electron, xterm.js and ssh2.
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.ru.md">Русский</a>
</p>

---

## About

OrionSSH is a desktop SSH client with a real terminal engine based on **xterm.js**. It is designed for working with interactive TUI applications such as `nano`, `vim`, `htop`, `mc`, `tmux` and `screen`.

This Electron version replaces the old Tkinter terminal implementation and uses Node/Electron tooling for a much more reliable terminal experience.

## Features

- SSH terminal powered by xterm.js
- SSH connections through ssh2
- Correct TUI behavior for nano, vim, htop, tmux and similar tools
- Tabs and split workspaces
- 2-pane and 4-pane layouts for multiple servers at once
- SFTP file manager
- Upload/download progress indicators
- Drag-and-drop upload to SFTP
- Command presets with bulk multi-line execution
- Groups, favorites, tags and custom group colors
- Group filtering and manual ordering
- SSH local port forwarding
- Telnet, Serial and RDP launch support
- Theme customization with color pickers
- English and Russian UI
- Secure password storage through OS keyring / Windows Credential Manager when available, with encrypted Electron safeStorage fallback
- Custom titlebar matching the selected theme

## Screenshots


<p align="center">
  <img src="docs/screenshots/main.png" alt="OrionSSH main screen" width="850" />
</p>

<p align="center">
  <img src="docs/screenshots/console.png" alt="OrionSSH terminal" width="850" />
  <img src="docs/screenshots/sftp.png" alt="OrionSSH SFTP" width="850" />
</p>

## Requirements

- Windows 10/11
- Node.js LTS
- npm

## Run from source

```bat
npm install
npm run dev
```

Or on Windows:

```bat
run_windows.bat
```

## Build Windows EXE / installer

```bat
npm install
npm run build
```

Or:

```bat
build_windows.bat
```

Build output appears in:

```text
release/
```

## Project structure

```text
src/main/       Electron main process, SSH/SFTP services, storage, credentials
src/renderer/   UI, xterm.js terminal, themes, tabs and split panes
assets/         App icon and logo
docs/           Screenshots and documentation
```

## Support

- Email: dev.equinox.e@gmail.com
- Telegram: https://t.me/equinox_robot
- GitHub: https://github.com/Equinox-e/Orion_SSH

## License

MIT
