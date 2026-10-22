import sys
import subprocess
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ICON_PATH = Path(__file__).parent / "resources" / "icon.png"

# On Windows, patch desktop_notifier's register_hkey so it writes a raw filesystem path
# instead of a file:/// URI. Windows Shell cannot load file:/// URIs for toast header icons,
# which causes the logo in the notification title banner to appear blank.
if sys.platform == "win32":
    try:
        import desktop_notifier.backends.winrt as winrt_backend
        import winreg

        def _patched_register_hkey(app_id: str, app_name: str, app_icon=None) -> None:
            winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key_path = f"SOFTWARE\\Classes\\AppUserModelId\\{app_id}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as master_key:
                winreg.SetValueEx(master_key, "DisplayName", 0, winreg.REG_SZ, app_name)
                if app_icon is not None and app_icon.is_file():
                    raw_path = str(app_icon.path.resolve())
                    winreg.SetValueEx(master_key, "IconUri", 0, winreg.REG_SZ, raw_path)
                winreg.SetValueEx(master_key, "ShowInSettings", 0, winreg.REG_DWORD, 1)

        winrt_backend.register_hkey = _patched_register_hkey
    except Exception as e:
        logger.debug(f"Failed to patch WinRT register_hkey: {e}")

class AppNotifier:
    """Universal notification dispatcher supporting Windows, macOS, and Linux."""

    def __init__(self, app_name: str = "Netwatch"):
        self.app_name = app_name
        self._desktop_notifier = None

        if sys.platform == "win32":
            try:
                from desktop_notifier import DesktopNotifier, Icon
                app_icon = Icon(path=_ICON_PATH) if _ICON_PATH.exists() else None
                self._desktop_notifier = DesktopNotifier(app_name=self.app_name, app_icon=app_icon)
            except Exception as e:
                logger.debug(f"WinRT DesktopNotifier init failed: {e}")

        elif sys.platform.startswith("linux"):
            try:
                from desktop_notifier import DesktopNotifier, Icon
                app_icon = Icon(path=_ICON_PATH) if _ICON_PATH.exists() else None
                self._desktop_notifier = DesktopNotifier(app_name=self.app_name, app_icon=app_icon)
            except Exception as e:
                logger.debug(f"Linux DesktopNotifier init failed: {e}")

    async def send(self, title: str, message: str) -> None:
        """Send a desktop notification across Windows, macOS, and Linux."""
        # 1. macOS: Use native AppleScript (reliable for all terminal and CLI tools)
        if sys.platform == "darwin":
            try:
                clean_msg = message.replace('"', '\\"')
                clean_title = title.replace('"', '\\"')
                script = f'display notification "{clean_msg}" with title "{self.app_name}" subtitle "{clean_title}"'
                subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
                return
            except Exception as e:
                logger.debug(f"macOS osascript notification failed: {e}")

        # 2. Windows: Use desktop_notifier (WinRT Toast) with custom icon
        if sys.platform == "win32" and self._desktop_notifier:
            try:
                from desktop_notifier import Icon
                icon = Icon(path=_ICON_PATH) if _ICON_PATH.exists() else None
                await self._desktop_notifier.send(
                    title=title,
                    message=message,
                    icon=icon,
                )
                return
            except Exception as e:
                logger.debug(f"Windows desktop_notifier failed: {e}")

        # 3. Linux: Try D-Bus desktop_notifier, then fall back to notify-send
        if sys.platform.startswith("linux"):
            if self._desktop_notifier:
                try:
                    await self._desktop_notifier.send(title=f"{self.app_name}: {title}", message=message)
                    return
                except Exception as e:
                    logger.debug(f"Linux D-Bus notification failed: {e}")

            notify_send = shutil.which("notify-send")
            if notify_send:
                try:
                    cmd = [notify_send, "-a", self.app_name, title, message]
                    if _ICON_PATH.exists():
                        cmd.extend(["-i", str(_ICON_PATH)])
                    subprocess.run(cmd, check=False, capture_output=True)
                    return
                except Exception as e:
                    logger.debug(f"notify-send fallback failed: {e}")
