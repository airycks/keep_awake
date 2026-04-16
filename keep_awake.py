"""keep_awake.py
Sends an F15 key press on Windows periodically to prevent idle sleep.

Usage:
  python keep_awake.py [--interval SECONDS] [--duration SECONDS] [--tray/--no-tray]

Defaults:
  interval: 60 seconds (time between presses)
  duration: run indefinitely until Quit from tray or Ctrl-C (if tray disabled)

This script uses ctypes and Win32 SendInput. When available, it will run with
a Windows tray icon using `pystray` and `Pillow` to create a small icon image.
If those packages are not installed, it falls back to console mode.
"""
from __future__ import annotations
import ctypes
import sys
import time
import argparse
import signal
import os
import logging
import subprocess
import threading
import winreg
from ctypes import wintypes

if sys.platform != "win32":
    raise SystemExit("This script only runs on Windows (win32).")

# Log file next to the script so errors are visible even without a console
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keep_awake.log")
logging.basicConfig(
    filename=_LOG_PATH,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Windows constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

# Virtual-Key code for F15: VK_F1 (0x70) + 14 = 0x7E
VK_F15 = 0x70 + 14

user32 = ctypes.WinDLL('user32', use_last_error=True)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTunion)]


def send_key(vk_code: int) -> None:
    """Send a single key press (down + up). Tries SendInput first, falls back to keybd_event."""
    try:
        # key down
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = KEYBDINPUT(vk_code, 0, 0, 0, 0)
        if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.02)
        # key up
        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.union.ki = KEYBDINPUT(vk_code, 0, KEYEVENTF_KEYUP, 0, 0)
        if user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up)) != 1:
            raise ctypes.WinError(ctypes.get_last_error())
    except OSError as e:
        # SendInput blocked (e.g. UIPI on corporate machines) — fall back to keybd_event
        logging.warning("SendInput failed (%s), falling back to keybd_event", e)
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0.02)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def hide_console() -> None:
    """Hide the Win32 console window so only the tray icon is visible."""
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0


def handle_sigint(signum, frame):
    print("\nExiting keep_awake.")
    raise SystemExit(0)


def worker_loop(interval: float, stop_event: threading.Event, running_event: threading.Event) -> None:
    """Background loop that sends the F15 key while running_event is set."""
    while not stop_event.is_set():
        if running_event.is_set():
            try:
                send_key(VK_F15)
            except Exception as e:
                logging.error("send_key error: %s", e)
            # sleep for the configured interval
            # check stop_event periodically if interval is large
            waited = 0.0
            step = 0.5
            while waited < interval and not stop_event.is_set() and running_event.is_set():
                time.sleep(min(step, interval - waited))
                waited += step
        else:
            time.sleep(0.2)


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "keep_awake"


def _startup_command() -> str:
    """Return the command stored in the registry to launch this script at login."""
    script = str(__file__)
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" "{script}" --tray'


def is_startup_enabled() -> bool:
    """Return True if the startup registry entry exists and matches this script."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            val, _ = winreg.QueryValueEx(key, _APP_NAME)
            return val == _startup_command()
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    """Add or remove the HKCU Run registry entry for this script."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass


def _msgbox(title: str, text: str, style: int) -> int:
    """Show a Win32 MessageBox and return the button pressed.
    style flags: 0x4 = Yes/No, 0x40 = info icon. Returns 6 for Yes, 7 for No.
    """
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)


def check_prerequisites() -> None:
    """Check for optional tray dependencies; offer to install if missing."""
    missing = []
    try:
        import pystray  # noqa: F401
    except ImportError:
        missing.append("pystray>=0.19.4")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow>=9.0.0")

    if not missing:
        return

    pkg_list = "\n".join(f"  • {p}" for p in missing)
    message = (
        "The following packages are needed for the system-tray icon:\n\n"
        f"{pkg_list}\n\n"
        "Install them now?"
    )
    # MB_YESNO | MB_ICONQUESTION
    answer = _msgbox("keep_awake – Missing Dependencies", message, 0x4 | 0x20)

    if answer == 6:  # IDYES
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + missing,
            check=False,
        )
        if result.returncode != 0:
            _msgbox("keep_awake", "Installation failed. Falling back to console mode.", 0x10)
    else:
        pass  # user declined; fall through to console mode


def main() -> None:
    check_prerequisites()

    parser = argparse.ArgumentParser(description="Press F15 periodically to keep the PC awake (Windows).")
    parser.add_argument("--interval", "-i", type=float, default=60.0, help="seconds between presses (default: 60)")
    parser.add_argument("--duration", "-d", type=float, default=0.0, help="total seconds to run (0 = run until Quit/Ctrl-C)")
    parser.add_argument("--tray", dest="tray", action="store_true", help="show system tray icon (if pystray available)")
    parser.add_argument("--no-tray", dest="tray", action="store_false", help="do not show a tray icon")
    parser.set_defaults(tray=True)
    args = parser.parse_args()

    if args.interval <= 0:
        raise SystemExit("interval must be > 0")

    signal.signal(signal.SIGINT, handle_sigint)

    stop_event = threading.Event()
    running_event = threading.Event()
    running_event.set()

    thread = threading.Thread(target=worker_loop, args=(args.interval, stop_event, running_event), daemon=True)
    thread.start()

    if args.duration > 0:
        # stop after duration seconds in a separate timer thread
        def stop_after():
            time.sleep(args.duration)
            stop_event.set()

        threading.Thread(target=stop_after, daemon=True).start()

    # Try to use pystray for a tray icon if requested
    if args.tray:
        try:
            import pystray
            from PIL import Image, ImageDraw

            def create_image() -> Image.Image:
                # 64x64 RGBA icon generated on the fly
                size = (64, 64)
                img = Image.new('RGBA', size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                # circle background
                draw.ellipse((8, 8, 56, 56), fill=(40, 120, 200, 255))
                # small white center dot
                draw.ellipse((28, 28, 36, 36), fill=(255, 255, 255, 255))
                return img

            icon_image = create_image()

            def on_toggle(icon, item):
                if running_event.is_set():
                    running_event.clear()
                    icon.notify('Paused keep_awake')
                else:
                    running_event.set()
                    icon.notify('Resumed keep_awake')

            def on_startup_toggle(icon, item):
                set_startup_enabled(not is_startup_enabled())

            def on_quit(icon, item):
                stop_event.set()
                icon.stop()

            menu = pystray.Menu(
                pystray.MenuItem('Toggle', on_toggle),
                pystray.MenuItem(
                    'Run on Startup',
                    on_startup_toggle,
                    checked=lambda item: is_startup_enabled(),
                ),
                pystray.MenuItem('Quit', on_quit),
            )

            icon = pystray.Icon('keep_awake', icon_image, 'keep_awake', menu)
            # Hide the console window so only the tray icon remains
            hide_console()
            # Run the icon (blocks until icon.stop() is called)
            print(f"keep_awake: running in tray (interval={args.interval}s). Right-click the tray icon to Quit.")
            icon.run()
        except Exception as e:
            print(f"Tray mode unavailable ({e}), falling back to console mode.")
            # fall through to console loop

    # Console mode: print status and wait until stop_event
    if not args.tray or stop_event.is_set() or not thread.is_alive():
        # If tray was used and then quit, stop_event will be set and we exit.
        # Otherwise, run until Ctrl-C or duration elapses
        print(f"keep_awake: pressing F15 every {args.interval} second(s). Ctrl-C to stop.")
        try:
            while not stop_event.is_set():
                time.sleep(0.5)
        except SystemExit:
            pass


if __name__ == "__main__":
    main()
