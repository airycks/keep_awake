# keep_awake

A lightweight Windows utility that simulates an F15 keypress on a regular interval to prevent your PC from going idle or locking the screen.

---

## Requirements

- **Windows** (uses Win32 APIs — will not run on macOS/Linux)
- **Python 3.8+** — [download from python.org](https://www.python.org/downloads/)
  - Tick **"Add Python to PATH"** during installation

---

## Quick Start

1. **Clone or download** this repository to any folder on your PC.

2. **Open a terminal** (PowerShell or Command Prompt) in that folder.

3. **Run the script:**

```powershell
python keep_awake.py
```

On first run, if the optional tray icon packages are not installed, the script will detect this and ask:

```
keep_awake: the following optional packages are not installed:
  - pystray>=0.19.4
  - Pillow>=9.0.0
These are required for the system-tray icon (--tray mode).
Install them now? [y/N]
```

Type `y` and press Enter to install them automatically. After that, a tray icon will appear in your system tray (bottom-right of the taskbar).

---

## Tray Icon

Right-click the tray icon for these options:

| Option | Description |
|---|---|
| **Toggle** | Pause or resume sending keypresses |
| **Run on Startup** | ✔ Checked = script launches automatically when you log in to Windows |
| **Quit** | Stop the script and remove the tray icon |

The **Run on Startup** option adds or removes a Windows registry entry (`HKCU\...\Run`) so the script starts silently with no console window every time you log in.

---

## Command-Line Options

```powershell
# Default: tray icon, press F15 every 60 seconds
python keep_awake.py

# Custom interval (every 30 seconds)
python keep_awake.py --interval 30

# Run for a fixed duration (10 minutes) then exit
python keep_awake.py --duration 600

# Console-only mode (no tray icon)
python keep_awake.py --no-tray
```

| Flag | Short | Default | Description |
|---|---|---|---|
| `--interval` | `-i` | `60` | Seconds between keypresses |
| `--duration` | `-d` | `0` (forever) | Total seconds to run before auto-exit |
| `--tray` / `--no-tray` | | `--tray` | Show or hide the system tray icon |

---

## Manual Dependency Install

If you prefer to install the tray dependencies yourself:

```powershell
python -m pip install -r requirements.txt
```

---

## Notes

- Uses a simulated **F15** keypress — an obscure key that won't interfere with any application shortcuts.
- If your machine has strict group policy power settings, a simulated keypress may not be enough; adjust your Windows power plan directly in those cases.
- The startup registry entry launches `pythonw.exe` (no console window) so it runs silently in the background.
