import argparse
import sys
import os
from textwrap import dedent

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal, Container
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static, TabbedContent, TabPane, OptionList
from textual.widgets.option_list import Option
from textual.reactive import var
from textual.css.query import NoMatches
from desktop_notifier import DesktopNotifier

from .utils import get_size, parse_limit
from .monitor import NetworkMonitorThread
from .db import init_db, get_historical_totals, clear_history, get_hourly_usage_last_24h, get_interface_totals
from .graph import generate_ascii_chart, generate_interface_activity_chart

class NetMonitorTUI(App):
    TITLE = "Network Usage Monitor"
    SUB_TITLE = "Press Ctrl+P for commands, Ctrl+Q to quit"

    BINDINGS = [
        ("ctrl+p", "command_palette", "Command Palette"),
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        ("ctrl+b", "toggle_bits", "Toggle Bits/Bytes"),  # <--- NEW KEYBINDING
        ("r", "refresh_chart", "Refresh Chart"),
        ("ctrl+r", "reset_counters", "Reset Counters"),
        ("ctrl+s", "save_quota", "Save Status"),
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

        /* Split-pane layout for Per-Interface tab */
        #interfaces_split_view {
            layout: horizontal;
            height: 1fr;
        }

        #interfaces_sidebar {
            width: 32;
            min-width: 25;
            max-width: 38;
            height: 1fr;
            border-right: solid black;
            padding: 1;
            background: #f0f0f0;
        }
        .-dark-mode #interfaces_sidebar {
            border-right: solid #666;
            background: #181818;
        }

        #iface_sidebar_title {
            text-align: center;
            text-style: bold;
            color: #007acc;
            margin-bottom: 1;
        }
        .-dark-mode #iface_sidebar_title {
            color: #55aaff;
        }

        #iface_option_list {
            height: 1fr;
            background: transparent;
            border: none;
        }

        #interface_detail_pane {
            width: 1fr;
            height: 1fr;
            padding: 0 1;
        }

        #iface_summary_cards {
            layout: horizontal;
            height: auto;
            padding: 1 0;
        }

        #iface_totals_card {
            height: auto;
            padding: 1 2;
            margin: 0 1 1 1;
            border: solid black;
            background: #e8e8e8;
        }
        .-dark-mode #iface_totals_card {
            border: solid #888;
            background: #222;
            color: #e0e0e0;
        }

        #iface_graph_container {
            height: auto;
            border: solid black;
            padding: 1 2;
            margin: 0 1;
            background: white;
            color: black;
        }
        .-dark-mode #iface_graph_container {
            border: solid #666;
            background: #222;
            color: #e0e0e0;
        }

        #iface_graph_area {
            height: auto;
        }
    """)

    total_upload = var(0)
    total_download = var(0)
    total_usage = var(0)
    upload_speed = var(0)
    download_speed = var(0)
    dark = var(False)
    show_bits = var(False)  # <--- NEW STATE VARIABLE

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

        self.selected_interface = None
        self.interfaces_data = {}
        self.interface_history = {}
        self.known_interfaces = []

    def _log_event(self, message: str):
        if self.log_file:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(self.log_file, "a") as f:
                    f.write(f"[{timestamp}] [EVENT] {message}\n")
            except Exception as e:
                self.query_one("#error_box").update(f"ERROR: Failed to write to log file: {e}")

    def _log_error(self, message: str):
        if self.log_file:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(self.log_file, "a") as f:
                    f.write(f"[{timestamp}] [ERROR] {message}\n")
            except Exception as e:
                self.query_one("#error_box").update(f"ERROR: Failed to write to log file: {e}")

    def compose(self) -> ComposeResult:
        yield Header()
        
        with TabbedContent(initial="live_tab"):
            with TabPane("Live Monitor", id="live_tab"):
                with VerticalScroll(id="main_container"):
                    with Horizontal(id="summary_cards"):
                        # Initial labels will be updated by watch methods immediately
                        yield Static("Total Download\n[b]0.00 B[/b]", id="total-dl-card", classes="summary_card")
                        yield Static("Total Upload\n[b]0.00 B[/b]", id="total-ul-card", classes="summary_card")
                        yield Static("Total Usage\n[b]0.00 B[/b]", id="total-usage-card", classes="summary_card")

                    with Container(id="limit_container"):
                        if self.limit_bytes:
                            # Note: Limits are usually kept in Bytes (GB), but we can toggle this too if desired.
                            # For now, limits usually stay in Bytes as that's how quotas work.
                            yield Static(f"Usage Limit: {get_size(self.limit_bytes, False)}", id="limit_label")
                            yield ProgressBar(id="limit_bar", total=self.limit_bytes, show_eta=False)
                        else:
                            yield Static("Usage Limit: Not Set")

                    yield Static(id="error_box")
                    yield DataTable(id="stats_table")

            with TabPane("Per-Interface", id="interfaces_tab"):
                with Horizontal(id="interfaces_split_view"):
                    with Container(id="interfaces_sidebar"):
                        yield Static("ACTIVE INTERFACES", id="iface_sidebar_title")
                        yield OptionList(id="iface_option_list")
                    with VerticalScroll(id="interface_detail_pane"):
                        with Horizontal(id="iface_summary_cards"):
                            yield Static("Interface\n[b]None[/b]", id="iface-name-card", classes="summary_card")
                            yield Static("Download Speed\n[b]0.00 B/s[/b]", id="iface-dl-card", classes="summary_card")
                            yield Static("Upload Speed\n[b]0.00 B/s[/b]", id="iface-ul-card", classes="summary_card")
                        with Container(id="iface_totals_card"):
                            yield Static("Session Total:  ▼ 0.00 B  |  ▲ 0.00 B\nAdapter Total:  ▼ 0.00 B  |  ▲ 0.00 B", id="iface_totals_label")
                        with Container(id="iface_graph_container"):
                            yield Static("Waiting for traffic...", id="iface_graph_area")

            with TabPane("History (24h)", id="history_tab"):
                yield Static("Analyzing database...", id="chart_area")
                yield Static("\n[b]Press 'R' to refresh data[/b]", classes="help-text")
        
        yield Footer()

    def on_mount(self):
        if self.log_file and os.path.exists(self.log_file):
            self._log_event("SESSION STARTED")

        init_db()
        up, down = get_historical_totals()
        
        self.total_upload = up
        self.total_download = down
        self.total_usage = up + down

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

        self.monitor_thread = NetworkMonitorThread(
            self.on_data_update,
            interface=self.interface,
            log_file=self.log_file,
            initial_upload=up,
            initial_download=down,
        )
        self.monitor_thread.start()

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
                error_message = data["error"]
                self._log_error(error_message)
                box = self.query_one("#error_box")
                box.update("ERROR: " + error_message)
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
            # Use self.show_bits for formatting
            table.add_row(
                data["timestamp"].split(" ")[1],
                f"{get_size(self.upload_speed, self.show_bits)}/s",
                f"{get_size(self.download_speed, self.show_bits)}/s",
                get_size(self.total_upload, self.show_bits),
                get_size(self.total_download, self.show_bits),
                get_size(self.total_usage, self.show_bits),
            )
            table.scroll_end(animate=False)

            if table.row_count > 50:
                first_key = next(iter(table.rows.keys()))
                table.remove_row(first_key)
        except NoMatches:
            pass

        # Process per-interface metrics
        if "interfaces" in data:
            self.interfaces_data = data["interfaces"]
            active_names = sorted(list(self.interfaces_data.keys()))

            # Update option list if the interface list changed
            if active_names != self.known_interfaces:
                self.known_interfaces = list(active_names)
                try:
                    opt_list = self.query_one("#iface_option_list", OptionList)
                    opt_list.clear_options()
                    for name in active_names:
                        opt_list.add_option(Option(f" {name}", id=name))
                    
                    if not self.selected_interface or self.selected_interface not in active_names:
                        if active_names:
                            self.selected_interface = active_names[0]
                            opt_list.highlighted = 0
                except NoMatches:
                    pass

            # Record history for each active interface
            for name, if_data in self.interfaces_data.items():
                if name not in self.interface_history:
                    self.interface_history[name] = []
                self.interface_history[name].append((if_data["upload_speed"], if_data["download_speed"]))
                if len(self.interface_history[name]) > 60:
                    self.interface_history[name].pop(0)

            # Update interface detail view for currently selected interface
            if self.selected_interface:
                self._update_interface_detail_view()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        if event.option_id:
            self.selected_interface = event.option_id
            self._update_interface_detail_view()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option_id:
            self.selected_interface = event.option_id
            self._update_interface_detail_view()

    def _update_interface_detail_view(self):
        if not self.selected_interface:
            try:
                self.query_one("#iface-name-card").update("Interface\n[b]None[/b]")
                self.query_one("#iface-dl-card").update("Download Speed\n[b]0.00 B/s[/b]")
                self.query_one("#iface-ul-card").update("Upload Speed\n[b]0.00 B/s[/b]")
                self.query_one("#iface_totals_label").update("No active network interfaces detected.")
                self.query_one("#iface_graph_area").update("[i]Waiting for active network interface...[/i]")
            except NoMatches:
                pass
            return

        iface = self.selected_interface
        stats = self.interfaces_data.get(iface, {
            "upload_speed": 0,
            "download_speed": 0,
            "session_upload": 0,
            "session_download": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
        })

        try:
            self.query_one("#iface-name-card").update(f"Interface\n[b]{iface}[/b]")
            self.query_one("#iface-dl-card").update(f"Download Speed\n[b]{get_size(stats['download_speed'], self.show_bits)}/s[/b]")
            self.query_one("#iface-ul-card").update(f"Upload Speed\n[b]{get_size(stats['upload_speed'], self.show_bits)}/s[/b]")

            session_down = get_size(stats.get("session_download", 0), self.show_bits)
            session_up = get_size(stats.get("session_upload", 0), self.show_bits)
            session_tot = get_size(stats.get("session_download", 0) + stats.get("session_upload", 0), self.show_bits)

            hw_down = get_size(stats.get("bytes_recv", 0), self.show_bits)
            hw_up = get_size(stats.get("bytes_sent", 0), self.show_bits)

            totals_text = (
                f"[b]Session Total:[/b]  ▼ {session_down}  |  ▲ {session_up}  (Combined: {session_tot})\n"
                f"[b]Adapter Total:[/b]  ▼ {hw_down}  |  ▲ {hw_up}"
            )
            self.query_one("#iface_totals_label").update(totals_text)

            history = self.interface_history.get(iface, [])
            chart_str = generate_interface_activity_chart(history, width=38, height=6, show_bits=self.show_bits)
            self.query_one("#iface_graph_area").update(chart_str)
        except NoMatches:
            pass

    # --- WATCHERS: These update the UI whenever variables change ---

    def watch_total_download(self, new):
        try:
            self.query_one("#total-dl-card").update(f"Total Download\n[b]{get_size(new, self.show_bits)}[/b]")
        except NoMatches:
            pass

    def watch_total_upload(self, new):
        try:
            self.query_one("#total-ul-card").update(f"Total Upload\n[b]{get_size(new, self.show_bits)}[/b]")
        except NoMatches:
            pass

    async def watch_total_usage(self, new_total_usage: int):
        try:
            self.query_one("#total-usage-card").update(f"Total Usage\n[b]{get_size(new_total_usage, self.show_bits)}[/b]")
            
            if self.limit_bytes:
                bar = self.query_one(ProgressBar)
                bar.progress = new_total_usage

                if not self.alert_80_sent and not self.alert_100_sent:
                    bar.styles.color = "#00c853" if not self.dark else "#64dd17"

                if new_total_usage >= 0.8 * self.limit_bytes and not self.alert_80_sent:
                    self.alert_80_sent = True
                    bar.styles.color = "yellow"
                    self.sub_title = "⚠️ 80% of limit reached!"
                    self._log_event("80% of data limit reached.")
                    try:
                        await self.notifier.send(
                            title="Netwatch: 80% Usage Warning",
                            message=f"You have used {get_size(new_total_usage, False)}." # Keep notifications in Bytes usually
                        )
                    except Exception as e:
                        self._log_error(f"Failed to send 80% notification: {e}")

                if new_total_usage >= self.limit_bytes and not self.alert_100_sent:
                    self.alert_100_sent = True
                    bar.styles.color = "red"
                    self.sub_title = "🚨 Data limit exceeded!"
                    self._log_event("100% of data limit reached.")
                    try:
                        await self.notifier.send(
                            title="Netwatch: Data Limit Exceeded!",
                            message=f"You have exceeded your {get_size(self.limit_bytes, False)} data limit."
                        )
                    except Exception as e:
                        self._log_error(f"Failed to send 100% notification: {e}")
        except NoMatches:
            pass

    # --- NEW WATCHER FOR BITS TOGGLE ---
    def watch_show_bits(self, new_val):
        """When show_bits toggles, force update the summary cards immediately."""
        # We manually trigger the updates using current values
        self.watch_total_download(self.total_download)
        self.watch_total_upload(self.total_upload)
        # Note: The table will update rows from *now on*, but old rows remain as they were.
        # If you want to update the limit label too:
        if self.limit_bytes:
            try:
                self.query_one("#limit_label").update(f"Usage Limit: {get_size(self.limit_bytes, new_val)}")
            except NoMatches:
                pass
        
        self._update_interface_detail_view()
        unit = "Bits (Mb)" if new_val else "Bytes (MB)"
        self.sub_title = f"Switched to {unit}"

    def on_tabbed_content_tab_activated(self, event):
        if event.tab.id == "history_tab":
            self.refresh_chart()
        elif event.tab.id == "interfaces_tab":
            self._update_interface_detail_view()

    def refresh_chart(self):
        try:
            data = get_hourly_usage_last_24h()
            chart_str = generate_ascii_chart(data)
            self.query_one("#chart_area").update(chart_str)
        except NoMatches:
            pass
        except Exception as e:
            self._log_error(f"Error loading chart: {e}")
            try:
                self.query_one("#chart_area").update(f"[red]Error loading chart:\n{e}[/red]")
            except:
                pass

    def action_refresh_chart(self):
        self.sub_title = "Refreshing chart data..."
        self.refresh_chart()
        self._update_interface_detail_view()

    def action_toggle_dark(self):
        self.dark = not self.dark
        self.set_class(self.dark, "-dark-mode")
        self.sub_title = "🌙 Dark Mode" if self.dark else "☀️ Light Mode"

    def action_toggle_bits(self):
        """Toggle between Bytes (MB) and Bits (Mb)."""
        self.show_bits = not self.show_bits

    def action_reset_counters(self):
        self._log_event("Counters reset.")
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.join(timeout=1)

        clear_history()

        self.total_upload = 0
        self.total_download = 0
        self.total_usage = 0
        self.interface_history = {}
        self.interfaces_data = {}
        self.sub_title = "History Cleared"
        self.alert_80_sent = False
        self.alert_100_sent = False
        
        try:
            bar = self.query_one(ProgressBar)
            bar.styles.color = None
        except NoMatches:
            pass

        self.refresh_chart()
        self._update_interface_detail_view()

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
    parser = argparse.ArgumentParser(
        description="A TUI-based network usage monitor.",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=35, width=100)
    )
    parser.add_argument(
        "-i", "--interface", 
        default="all",
        help="Network interface to monitor (e.g., 'eth0', 'Wi-Fi')."
    )
    parser.add_argument(
        "-l", "--limit",
        help="Set a data usage limit (e.g., '10GB', '500MB')."
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        help="Log all captured traffic to a specified file."
    )
    args = parser.parse_args()

    app = NetMonitorTUI(
        interface=args.interface,
        limit_str=args.limit,
        log_file=args.log,
    )
    app.run()

if __name__ == "__main__":
    main()