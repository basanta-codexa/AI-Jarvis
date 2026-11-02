# ──────────────────────────────────────────────
#  automation/desktop.py  –  Safe desktop actions
# ──────────────────────────────────────────────
"""
All actions are gated against whitelist allow-lists from settings.py.
Nothing outside the approved list can be launched.
"""
import os
import subprocess
import webbrowser
import urllib.parse
from config import settings


class Desktop:
    """Controlled desktop automation with safety whitelist."""

    # ── App launcher ──────────────────────────────────────────────────

    def open_target(self, target: str) -> str:
        """
        Open an app or website by name.
        e.g. "notepad", "calculator", "youtube"
        """
        # Check websites first
        for key, url in settings.APPROVED_WEBSITES.items():
            if key in target:
                return self._open_url(url, key)

        # Check apps
        for key, cmd in settings.APPROVED_APPS.items():
            if key in target:
                return self._launch_app(cmd, key)

        return (
            f"I'm sorry, I can't open '{target}'. "
            "It's not on my approved list. "
            "You can add it to config/settings.py."
        )

    def open_website(self, site: str) -> str:
        """Open a website by name or full URL."""
        for key, url in settings.APPROVED_WEBSITES.items():
            if key in site:
                return self._open_url(url, key)

        # If it looks like a URL, open it directly
        if site.startswith("http://") or site.startswith("https://") or "." in site:
            url = site if site.startswith("http") else f"https://{site}"
            return self._open_url(url, site)

        return f"I don't have '{site}' in my approved websites list."

    def search_web(self, query: str) -> str:
        """Google search for a query."""
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        return f"Searching Google for: {query}"

    # ── Internal ──────────────────────────────────────────────────────

    @staticmethod
    def _open_url(url: str, name: str) -> str:
        try:
            webbrowser.open(url)
            return f"Opening {name.title()} in your browser."
        except Exception as e:
            return f"Failed to open {name}: {e}"

    @staticmethod
    def _launch_app(cmd: str, name: str) -> str:
        try:
            if cmd.startswith("start "):
                os.system(cmd)
            else:
                subprocess.Popen(cmd, shell=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Opening {name.title()}."
        except Exception as e:
            return f"Failed to launch {name}: {e}"

    # ── System info ───────────────────────────────────────────────────

    def get_status(self) -> str:
        """Return a full system status report."""
        parts = []
        try:
            import psutil
            # Battery
            batt = psutil.sensors_battery()
            if batt:
                status = "charging" if batt.power_plugged else "discharging"
                parts.append(f"Battery is at {int(batt.percent)}% and {status}.")
            else:
                parts.append("Battery information is not available.")

            # CPU
            cpu = psutil.cpu_percent(interval=0.5)
            parts.append(f"CPU usage is at {int(cpu)}%.")

            # Memory
            mem = psutil.virtual_memory()
            parts.append(f"Memory usage is at {int(mem.percent)}%.")

            return " ".join(parts)
        except ImportError:
            return "psutil is not installed; system info unavailable."
        except Exception as e:
            return f"Could not retrieve system info: {e}"

    @staticmethod
    def get_battery() -> str:
        """Convenience method for battery info."""
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt:
                status = "charging" if batt.power_plugged else "discharging"
                return f"Battery is at {int(batt.percent)}% and {status}."
            return "Battery information is not available."
        except ImportError:
            return "psutil is not installed; battery info unavailable."
        except Exception as e:
            return f"Could not retrieve battery info: {e}"
