"""Platform-specific auto-start registration.

macOS: ~/Library/LaunchAgents/com.chromachecker.mosquitto.plist
Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MACOS_PLIST_ID = "com.chromachecker.mosquitto"
_WINDOWS_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WINDOWS_REG_NAME = "CCMosquitto"


def _app_executable() -> str:
    """Return the path to the running executable."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return f"{sys.executable} -m cc_mosquitto"


# -- macOS ----------------------------------------------------------------

def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_MACOS_PLIST_ID}.plist"


def _macos_enable() -> None:
    plist = _macos_plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    exe = _app_executable()
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_MACOS_PLIST_ID}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
    plist.write_text(content, encoding="utf-8")
    logger.info("Autostart enabled: %s", plist)


def _macos_disable() -> None:
    plist = _macos_plist_path()
    if plist.is_file():
        plist.unlink()
        logger.info("Autostart disabled: removed %s", plist)


def _macos_is_enabled() -> bool:
    return _macos_plist_path().is_file()


# -- Windows --------------------------------------------------------------

def _windows_enable() -> None:
    try:
        import winreg

        exe = _app_executable()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WINDOWS_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, _WINDOWS_REG_NAME, 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
        logger.info("Autostart enabled (Windows Registry)")
    except Exception:
        logger.exception("Failed to enable autostart on Windows")


def _windows_disable() -> None:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WINDOWS_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, _WINDOWS_REG_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        logger.info("Autostart disabled (Windows Registry)")
    except Exception:
        logger.exception("Failed to disable autostart on Windows")


def _windows_is_enabled() -> bool:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WINDOWS_REG_KEY, 0, winreg.KEY_QUERY_VALUE
        )
        try:
            winreg.QueryValueEx(key, _WINDOWS_REG_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


# -- Public API -----------------------------------------------------------

def enable_autostart() -> None:
    """Register the app to start on system boot."""
    if platform.system() == "Darwin":
        _macos_enable()
    elif platform.system() == "Windows":
        _windows_enable()
    else:
        logger.warning("Autostart not supported on %s", platform.system())


def disable_autostart() -> None:
    """Remove the app from system boot."""
    if platform.system() == "Darwin":
        _macos_disable()
    elif platform.system() == "Windows":
        _windows_disable()


def is_autostart_enabled() -> bool:
    """Check whether auto-start is currently registered."""
    if platform.system() == "Darwin":
        return _macos_is_enabled()
    if platform.system() == "Windows":
        return _windows_is_enabled()
    return False
