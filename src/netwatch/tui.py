import psutil
import time
import argparse
import threading
import csv
from datetime import datetime
from textwrap import dedent
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static
from textual.reactive import var
from desktop_notifier import DesktopNotifier

def get_size(byte_val):
    """Converts bytes to a human-readable format (KB, MB, GB)."""
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_val >= power and n < len(power_labels) - 1:
        byte_val /= power
        n += 1
    return f"{byte_val:.2f} {power_labels[n]}B"


def parse_limit(size_str):
    """Parses a size string (e.g., '10GB', '500MB') into bytes."""
    if not size_str:
        return None
    size_str = size_str.upper().strip()
    if size_str.endswith('GB'):
        return int(float(size_str[:-2]) * 1024**3)
    elif size_str.endswith('MB'):
        return int(float(size_str[:-2]) * 1024**2)
    elif size_str.endswith('KB'):
        return int(float(size_str[:-2]) * 1024)
    else:
        try:
            return int(float(size_str))
        except ValueError:
            return None



class NetworkMonitorThread(threading.Thread):
    """A separate thread that monitors network stats."""

    def __init__(self, app_callback, interface='all', log_file=None):
        super().__init__()
        self.daemon = True
        self.app_callback = app_callback
        self.interface = interface
        self.stop_event = threading.Event()
        self.log_file = log_file

        if log_file:
            try:
                with open(log_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Timestamp", "Upload Speed (B/s)", "Download Speed (B/s)",
                        "Total Upload", "Total Download", "Total Usage"
                    ])
            except Exception as e:
                self.app_callback({"error": f"Failed to create log file: {e}"})
                self.log_file = None

    def stop(self):
        self.stop_event.set()

    def run(self):
        total_upload = 0
        total_download = 0

        try:
            last_stats = psutil.net_io_counters(pernic=True)
            if not last_stats:
                self.app_callback({"error": "No network interfaces found."})
                return
            if self.interface != 'all' and self.interface not in last_stats:
                self.app_callback({"error": f"Interface '{self.interface}' not found."})
                return
        except Exception as e:
            self.app_callback({"error": f"Error getting stats: {e}"})
            return

        while not self.stop_event.is_set():
            try:
                time.sleep(1)
                current_stats = psutil.net_io_counters(pernic=True)
                if not current_stats:
                    continue

                upload_delta, download_delta = 0, 0
                if self.interface == 'all':
                    for iface in current_stats:
                        if iface in last_stats:
                            upload_delta += current_stats[iface].bytes_sent - last_stats[iface].bytes_sent
                            download_delta += current_stats[iface].bytes_recv - last_stats[iface].bytes_recv
                else:
                    if self.interface in current_stats and self.interface in last_stats:
                        upload_delta = current_stats[self.interface].bytes_sent - last_stats[self.interface].bytes_sent
                        download_delta = current_stats[self.interface].bytes_recv - last_stats[self.interface].bytes_recv

                last_stats = current_stats
                upload_delta = max(upload_delta, 0)
                download_delta = max(download_delta, 0)
                total_upload += upload_delta
                total_download += download_delta

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                total_usage = total_upload + total_download
                data_packet = {
                    "upload_speed": upload_delta,
                    "download_speed": download_delta,
                    "total_upload": total_upload,
                    "total_download": total_download,
                    "total_usage": total_usage,
                    "timestamp": timestamp
                }

                if self.log_file:
                    with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp,
                            upload_delta,
                            download_delta,
                            get_size(total_upload),
                            get_size(total_download),
                            get_size(total_usage)
                        ])

                self.app_callback(data_packet)
            except Exception as e:
                self.app_callback({"error": f"Error in loop: {e}"})
                time.sleep(3)



class NetMonitorTUI(App):
    """A Textual TUI for the network monitor."""

    TITLE = "Network Usage Monitor"
    SUB_TITLE = "Press Ctrl+P for commands, Ctrl+Q to quit"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        ("r", "reset_counters", "Reset Counters"),
        ("ctrl+q", "quit", "Quit"),
    ]

    CSS = dedent("""
    Screen {
        background: #f8f8f8;
        color: black;
    }

    .-dark-mode Screen {
        background: #101010;
        color: #f0f0f0;
    }

    #main_container {
        layout: vertical;
    }

    #summary_cards {
        layout: horizontal;
        height: auto;
        padding: 1 0;
    }

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

    #limit_container {
        height: auto;
        padding: 0 1 1 1;
    }

    #stats_table {
        height: 1fr;
        margin: 0 1;
        border: solid black;
    }

    .-dark-mode #stats_table {
        border: solid #666;
        color: #e0e0e0;
    }

    ProgressBar > .progress-bar--bar {
        background: #007acc;
    }

    .-dark-mode ProgressBar > .progress-bar--bar {
        background: #55aaff;
    }

    #footer {
        color: white;
    }

    #header {
        color: white;
    }

    #error_box {
        height: auto;
        padding: 1 2;
        color: red;
        display: none;
    }
    """)

    total_usage = var(0)
    total_upload = var(0)
    total_download = var(0)
    upload_speed = var(0)
    download_speed = var(0)
    dark = var(False)

    def __init__(self, interface='all', limit_str=None, log_file=None):
        super().__init__()
        self.interface = interface
        self.limit_bytes = parse_limit(limit_str)
        self.limit_str = limit_str or "No Limit"
        self.monitor_thread = None
        self.alert_80_sent = False
        self.alert_100_sent = False
        self.notifier = DesktopNotifier(app_name="Netwatch")
        self.log_file = log_file

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

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Time", key="time")
        table.add_column("Up Speed", key="up_spd")
        table.add_column("Down Speed", key="dl_spd")
        table.add_column("Total Up", key="total_up")
        table.add_column("Total Down", key="total_dl")
        table.add_column("Total Usage", key="total")

        self.monitor_thread = NetworkMonitorThread(
            app_callback=self.on_data_update,
            interface=self.interface,
            log_file=self.log_file
        )
        self.monitor_thread.start()

    def on_exit(self) -> None:
        """Gracefully stop monitoring thread on exit."""
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join()  # <-- ADD THIS LINE

    def on_data_update(self, data: dict) -> None:
        self.call_from_thread(self._process_data_packet, data)

    def _process_data_packet(self, data: dict) -> None:
        if "error" in data:
            error_box = self.query_one("#error_box")
            error_box.update(f"ERROR: {data['error']}")
            error_box.styles.display = "block"
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
            get_size(self.total_usage)
        )
        table.scroll_end(animate=False)

        if table.row_count > 50:
            first_key = next(iter(table.rows.keys()))
            table.remove_row(first_key)

    def action_toggle_dark(self):
        """Toggle dark/light mode properly."""
        self.dark = not self.dark
        self.set_class(self.dark, "-dark-mode")
        self.sub_title = "🌙 Dark Mode ON" if self.dark else "☀️ Light Mode ON"

    def action_reset_counters(self):
        """Reset counters."""
        self.total_upload = self.total_download = self.total_usage = 0
        self.alert_80_sent = self.alert_100_sent = False
        self.sub_title = "Counters Reset!"
        if self.limit_bytes:
            bar = self.query_one(ProgressBar)
            bar.styles.color = None

    def watch_total_download(self, new_val: int) -> None:
        self.query_one("#total-dl-card").update(f"Total Download\n[b]{get_size(new_val)}[/b]")

    def watch_total_upload(self, new_val: int) -> None:
        self.query_one("#total-ul-card").update(f"Total Upload\n[b]{get_size(new_val)}[/b]")

    async def watch_total_usage(self, new_total_usage: int) -> None:
        self.query_one("#total-usage-card").update(f"Total Usage\n[b]{get_size(new_total_usage)}[/b]")
        if self.limit_bytes:
            bar = self.query_one(ProgressBar)
            bar.progress = new_total_usage
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
                    print(f"[Notification Error] {e}")
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
                    print(f"[Notification Error] {e}")



def main():
    parser = argparse.ArgumentParser(description="Network Usage Monitor TUI")
    parser.add_argument('-i', '--interface', type=str, default='all', help="Network interface to monitor (e.g., 'Wi-Fi'). Default is 'all'.")
    parser.add_argument('-l', '--limit', type=str, help="Set data usage cap (e.g., '10GB', '500MB').")
    parser.add_argument('--log', type=str, help="Optional CSV file to log network usage data.")
    args = parser.parse_args()

    app = NetMonitorTUI(interface=args.interface, limit_str=args.limit, log_file=args.log)
    app.run()


if __name__ == "__main__":
    main()
