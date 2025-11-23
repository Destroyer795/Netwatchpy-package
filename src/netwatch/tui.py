import argparse
import sys
from textwrap import dedent

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static, TabbedContent, TabPane
from textual.reactive import var
from textual.css.query import NoMatches
from desktop_notifier import DesktopNotifier

from .utils import get_size, parse_limit
from .monitor import NetworkMonitorThread
from .db import init_db, get_historical_totals, clear_history, get_hourly_usage_last_24h
from .graph import generate_ascii_chart

class NetMonitorTUI(App):
    TITLE = "Network Usage Monitor"
    SUB_TITLE = "Press Ctrl+P for commands, Ctrl+Q to quit"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        ("r", "refresh_chart", "Refresh Chart"),
        ("ctrl+r", "reset_counters", "Reset Counters"),
        ("ctrl+s", "save_quota", "Info: Auto-Saved"),
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
            background: white;
            color: black;
        }
        .-dark-mode #stats_table {
            border: solid #666;
            background: #222;
            color: #e0e0e0;
        }
        
        ProgressBar { background: #e8e8e8; }
        .-dark-mode ProgressBar { background: #222; }

        ProgressBar > .progress-bar--bar { background: #007acc; }
        .-dark-mode ProgressBar > .progress-bar--bar { background: #55aaff; }

        #error_box {
            height: auto;
            padding: 1 2;
            color: red;
            display: none;
        }
        
        #chart_area {
            padding: 1 2;
            height: auto;
            border: solid #666;
        }
        .help-text {
            text-align: center;
            padding: 1;
            color: #888;
        }
    """)

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
        
        self.alert_80_sent = False
        self.alert_100_sent = False

    def compose(self) -> ComposeResult:
        yield Header()
        
        with TabbedContent(initial="live_tab"):
            with TabPane("Live Monitor", id="live_tab"):
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

            with TabPane("History (24h)", id="history_tab"):
                yield Static("Analyzing database...", id="chart_area")
                yield Static("\n[b]Press 'R' to refresh data[/b]", classes="help-text")
        
        yield Footer()

    def on_mount(self):
        """Executed when TUI is ready."""
        init_db()
        up, down = get_historical_totals()
        
        self.total_upload = up
        self.total_download = down
        self.total_usage = up + down

        # Build table
        table = self.query_one(DataTable)
        table.add_column("Time")
        table.add_column("Up Speed")
        table.add_column("Down Speed")
        table.add_column("Total Up")
        table.add_column("Total Down")
        table.add_column("Total Usage")

        if self.limit_bytes:
            try:
                bar = self.query_one(ProgressBar)
                bar.progress = self.total_usage
            except Exception:
                pass

        # Start monitoring thread
        self.monitor_thread = NetworkMonitorThread(
            self.on_data_update,
            interface=self.interface,
            log_file=self.log_file,
            initial_upload=up,
            initial_download=down,
        )
        self.monitor_thread.start()

        # Refresh chart on startup
        self.refresh_chart()

    def on_exit(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join(timeout=1.5)

    def on_data_update(self, data: dict):
        self.call_from_thread(self._process_data_packet, data)

    def _process_data_packet(self, data: dict):
        if "error" in data:
            try:
                box = self.query_one("#error_box")
                box.update("ERROR: " + data["error"])
                box.styles.display = "block"
            except NoMatches:
                pass
            return

        if "timestamp" not in data:
            return

        self.upload_speed = data["upload_speed"]
        self.download_speed = data["download_speed"]
        self.total_upload = data["total_upload"]
        self.total_download = data["total_download"]
        self.total_usage = data["total_usage"]

        try:
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
        except NoMatches:
            pass

    def watch_total_download(self, new):
        try:
            self.query_one("#total-dl-card").update(f"Total Download\n[b]{get_size(new)}[/b]")
        except NoMatches:
            pass

    def watch_total_upload(self, new):
        try:
            self.query_one("#total-ul-card").update(f"Total Upload\n[b]{get_size(new)}[/b]")
        except NoMatches:
            pass

    async def watch_total_usage(self, new_total_usage: int):
        try:
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
                            message=f"You have used {get_size(new_total_usage)}."
                        )
                    except Exception as e:
                        print(f"[Notification Error] {e}", file=sys.stderr)

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
                        print(f"[Notification Error] {e}", file=sys.stderr)
        except NoMatches:
            pass

    def on_tabbed_content_tab_activated(self, event):
        """Auto-refresh when user clicks the History tab."""
        if event.tab.id == "history_tab":
            self.refresh_chart()

    def refresh_chart(self):
        try:
            data = get_hourly_usage_last_24h()
            chart_str = generate_ascii_chart(data)
            self.query_one("#chart_area").update(chart_str)
        except NoMatches:
            pass
        except Exception as e:
            try:
                self.query_one("#chart_area").update(f"[red]Error loading chart:\n{e}[/red]")
            except:
                pass

    def action_refresh_chart(self):
        """Called when 'r' is pressed to refresh the chart."""
        self.sub_title = "Refreshing chart data..."
        self.refresh_chart()

    def action_toggle_dark(self):
        self.dark = not self.dark
        self.set_class(self.dark, "-dark-mode")
        self.sub_title = "🌙 Dark Mode" if self.dark else "☀️ Light Mode"

    def action_reset_counters(self):
        """Resets all counters to 0, clears DB, and refreshes chart."""
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join(timeout=1)

        clear_history()

        self.total_upload = 0
        self.total_download = 0
        self.total_usage = 0
        self.sub_title = "History Cleared"
        self.alert_80_sent = False
        self.alert_100_sent = False
        
        # Refresh chart to show empty state
        self.refresh_chart()

        self.monitor_thread = NetworkMonitorThread(
            self.on_data_update,
            interface=self.interface,
            log_file=self.log_file,
            initial_upload=0,
            initial_download=0,
        )
        self.monitor_thread.start()

    def action_save_quota(self) -> None:
        self.sub_title = "✅ Data is auto-saved to SQLite"

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