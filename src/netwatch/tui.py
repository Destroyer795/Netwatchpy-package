import argparse
import json
import os
import sys
from textwrap import dedent
from platformdirs import user_config_dir

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static
from textual.reactive import var
from desktop_notifier import DesktopNotifier

from .utils import get_size, parse_limit
from .monitor import NetworkMonitorThread



class NetMonitorTUI(App):
    TITLE = "Network Usage Monitor"
    SUB_TITLE = "Press Ctrl+P for commands, Ctrl+Q to quit"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        ("r", "reset_counters", "Reset Counters"),
        ("ctrl+s", "save_quota", "Save Quota"),
        ("ctrl+q", "quit", "Quit"),
    ]

    CSS = dedent("""
        Screen { background: #f8f8f8; color: black; }
        .-dark-mode Screen { background: #101010; color: #f0f0f0; }

        #main_container { layout: vertical; }
        #summary_cards { layout: horizontal; height: auto; padding: 1 0; }

        .summary_card {
            width: 1fr;
            min-height: 5;
            border: solid black;
            padding: 1;
            margin: 0 1;
            background: #e8e8e8;
        }
        .-dark-mode .summary_card {
            border: solid #888;
            background: #222;
            color: #e0e0e0;
        }

        #limit_container { height: auto; padding: 0 1 1 1; }
        
        #stats_table {
            height: 1fr;
            margin: 0 1;
            border: solid black;
            background: white; /* Light mode background */
            color: black;      /* Light mode text */
        }
        .-dark-mode #stats_table {
            border: solid #666;
            background: #222; /* Dark mode background */
            color: #e0e0e0;   /* Dark mode text */
        }
        
        ProgressBar {
            background: #e8e8e8; /* Light mode track */
        }
        .-dark-mode ProgressBar {
            background: #222; /* Dark mode track */
        }

        ProgressBar > .progress-bar--bar { background: #007acc; }
        .-dark-mode ProgressBar > .progress-bar--bar { background: #55aaff; }

        #error_box {
            height: auto;
            padding: 1 2;
            color: red;
            display: none;
        }
    """)

    # Reactive vars (auto update UI)
    total_upload = var(0)
    total_download = var(0)
    total_usage = var(0)
    upload_speed = var(0)
    download_speed = var(0)
    dark = var(False)

    def __init__(self, interface="all", limit_str=None, log_file=None):
        super().__init__()
        self.interface = interface
        self.limit_bytes = parse_limit(limit_str)
        self.limit_str = limit_str or "No Limit"
        self.log_file = log_file

        self.notifier = DesktopNotifier(app_name="Netwatch")
        self.monitor_thread = None
        self._save_lock = None # added in on_mount
        
        self.alert_80_sent = False
        self.alert_100_sent = False

        # Persistent storage location
        self.config_dir = user_config_dir("netwatchpy")
        self.quota_file = os.path.join(self.config_dir, "quota.json")

    def _load_persistent_quota(self):
        try:
            with open(self.quota_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return (
                int(data.get("total_upload", 0)),
                int(data.get("total_download", 0)),
            )
        except Exception:
            return 0, 0

    def _save_persistent_quota(self):
        """Safe atomic save of totals."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)

            payload = {
                "total_upload": int(self.total_upload),
                "total_download": int(self.total_download),
            }

            tmp = self.quota_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            os.replace(tmp, self.quota_file)
        except Exception as e:
            print(f"[netwatch save error] {e}", file=sys.stderr)

    def compose(self) -> ComposeResult:
        yield Header()

        with VerticalScroll(id="main_container"):
            with Horizontal(id="summary_cards"):
                yield Static("Total Download\n[b]0.00 B[/b]", id="total-dl-card", classes="summary_card")
                yield Static("Total Upload\n[b]0.00 B[/b]", id="total-ul-card", classes="summary_card")
                yield Static("Total Usage\n[b]0.00 B[/b]", id="total-usage-card", classes="summary_card")

            with Container(id="limit_container"):
                if self.limit_bytes:
                    yield Static(f"Usage Limit: {get_size(self.limit_bytes)}")
                    yield ProgressBar(id="limit_bar", total=self.limit_bytes, show_eta=False)
                else:
                    yield Static("Usage Limit: Not Set")

            yield Static(id="error_box")
            yield DataTable(id="stats_table")

        yield Footer()

    def on_mount(self):
        """Executed when TUI is ready."""
        from threading import Lock
        self._save_lock = Lock()

        # Build table
        table = self.query_one(DataTable)
        table.add_column("Time")
        table.add_column("Up Speed")
        table.add_column("Down Speed")
        table.add_column("Total Up")
        table.add_column("Total Down")
        table.add_column("Total Usage")

        # Load saved totals before thread start
        up, down = self._load_persistent_quota()
        self.total_upload = up
        self.total_download = down
        self.total_usage = up + down

        if self.limit_bytes:
            try:
                bar = self.query_one(ProgressBar)
                bar.progress = self.total_usage
            except Exception:
                pass

        # Start autosave (every 10 seconds)
        self.set_interval(10, self._autosave_job)

        self.monitor_thread = NetworkMonitorThread(
            self.on_data_update,
            interface=self.interface,
            log_file=self.log_file,
            initial_upload=up,
            initial_download=down,
        )
        self.monitor_thread.start()

    def on_exit(self):
        """
        Stop the thread, then do a final save.
        """
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join(timeout=1.5)
        
        print("\n[netwatch] Quitting... saving final quota.")
        if self._save_lock.acquire(timeout=2.0):
            try:
                self._save_persistent_quota()
                print("[netwatch] Final save complete.")
            except Exception as e:
                print(f"[netwatch] Final save failed: {e}", file=sys.stderr)
            finally:
                self._save_lock.release()
        else:
            print("[netwatch] Could not acquire lock, final save skipped.", file=sys.stderr)

    def _autosave_job(self):
        """Called every 10 seconds."""
        if self._save_lock.acquire(timeout=0.1):
            try:
                self._save_persistent_quota()
            finally:
                self._save_lock.release()

    def on_data_update(self, data: dict):
        self.call_from_thread(self._process_data_packet, data)

    def _process_data_packet(self, data: dict):
        if "error" in data:
            box = self.query_one("#error_box")
            box.update("ERROR: " + data["error"])
            box.styles.display = "block"
            return

        if "timestamp" not in data:
            return

        self.upload_speed = data["upload_speed"]
        self.download_speed = data["download_speed"]
        self.total_upload = data["total_upload"]
        self.total_download = data["total_download"]
        self.total_usage = data["total_usage"]

        table = self.query_one(DataTable)
        table.add_row(
            data["timestamp"].split(" ")[1],
            f"{get_size(self.upload_speed)}/s",
            f"{get_size(self.download_speed)}/s",
            get_size(self.total_upload),
            get_size(self.total_download),
            get_size(self.total_usage),
        )
        table.scroll_end(animate=False)

        if table.row_count > 50:
            first_key = next(iter(table.rows.keys()))
            table.remove_row(first_key)

    def watch_total_download(self, new):
        self.query_one("#total-dl-card").update(
            f"Total Download\n[b]{get_size(new)}[/b]"
        )

    def watch_total_upload(self, new):
        self.query_one("#total-ul-card").update(
            f"Total Upload\n[b]{get_size(new)}[/b]"
        )

    async def watch_total_usage(self, new_total_usage: int):
        self.query_one("#total-usage-card").update(
            f"Total Usage\n[b]{get_size(new_total_usage)}[/b]"
        )
        
        if self.limit_bytes:
            bar = self.query_one(ProgressBar)
            bar.progress = new_total_usage

            # 80% warning
            if new_total_usage >= 0.8 * self.limit_bytes and not self.alert_80_sent:
                self.alert_80_sent = True
                bar.styles.color = "yellow"
                self.sub_title = "⚠️ 80% of limit reached!"
                try:
                    await self.notifier.send(
                        title="Netwatch: 80% Usage Warning",
                        message=f"You have used {get_size(new_total_usage)} of your {get_size(self.limit_bytes)} limit."
                    )
                except Exception as e:
                    print(f"[Notification Error] {e}", file=sys.stderr) # Log to stderr

            # 100% alert
            if new_total_usage >= self.limit_bytes and not self.alert_100_sent:
                self.alert_100_sent = True
                bar.styles.color = "red"
                self.sub_title = "🚨 Data limit exceeded!"
                try:
                    await self.notifier.send(
                        title="Netwatch: Data Limit Exceeded!",
                        message=f"You have exceeded your {get_size(self.limit_bytes)} data limit."
                    )
                except Exception as e:
                    print(f"[Notification Error] {e}", file=sys.stderr) # Log to stderr

    def action_toggle_dark(self):
        self.dark = not self.dark
        self.set_class(self.dark, "-dark-mode")
        self.sub_title = "🌙 Dark Mode" if self.dark else "☀️ Light Mode"

    def action_reset_counters(self):
        """Resets all counters to 0 and saves this reset."""
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join(timeout=1)

        self.total_upload = 0
        self.total_download = 0
        self.total_usage = 0
        self.sub_title = "Quota Reset to 0"

        self.alert_80_sent = False
        self.alert_100_sent = False

        # get lock to save the reset
        if self._save_lock.acquire(timeout=1.0):
            try:
                self._save_persistent_quota()
            finally:
                self._save_lock.release()

        # Restart fresh thread
        self.monitor_thread = NetworkMonitorThread(
            self.on_data_update,
            interface=self.interface,
            log_file=self.log_file,
            initial_upload=0,
            initial_download=0,
        )
        self.monitor_thread.start()

    def action_save_quota(self) -> None:
        """Manually save the current quota totals."""
        if self._save_lock.acquire(timeout=0.1):
            try:
                self._save_persistent_quota()
                self.sub_title = "Quota Saved!"
            finally:
                self._save_lock.release()
        else:
            self.sub_title = "Saving... please wait."

def main():
    parser = argparse.ArgumentParser(description="Network Usage Monitor TUI")
    parser.add_argument("-i", "--interface", default="all")
    parser.add_argument("-l", "--limit")
    parser.add_argument("--log")
    args = parser.parse_args()

    app = NetMonitorTUI(
        interface=args.interface,
        limit_str=args.limit,
        log_file=args.log,
    )
    app.run()


if __name__ == "__main__":
    main()