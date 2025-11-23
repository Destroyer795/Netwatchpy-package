import psutil
import threading
from datetime import datetime
import csv
from .utils import get_size
from .db import log_traffic

class NetworkMonitorThread(threading.Thread):
    def __init__(self, callback, interface="all", log_file=None,
                 initial_upload=0, initial_download=0, interval=1.0):
        super().__init__()
        self.daemon = True
        self.callback = callback
        self.interface = interface
        self.log_file = log_file
        self.interval = interval
        self.stop_event = threading.Event()

        self.total_up = int(initial_upload)
        self.total_down = int(initial_download)
        
        if self.log_file:
            try:
                file_exists = False
                try:
                    with open(self.log_file, "r", encoding="utf-8"):
                        file_exists = True
                except FileNotFoundError:
                    file_exists = False
                with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["Timestamp", "Upload Speed (B/s)", "Download Speed (B/s)", "Total Upload", "Total Download", "Total Usage"])
            except Exception:
                self.log_file = None

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            last = psutil.net_io_counters(pernic=True)
        except Exception:
            self.callback({"error": "Failed to get initial network stats."})
            return

        if not last:
            self.callback({"error": "No network interfaces found."})
            return
        if self.interface != 'all' and self.interface not in last:
            self.callback({"error": f"Interface '{self.interface}' not found."})
            return
            
        while not self.stop_event.is_set():
            try:
                self.stop_event.wait(self.interval)
                if self.stop_event.is_set():
                    break

                now = psutil.net_io_counters(pernic=True)
                if not now:
                    continue

                up = 0
                down = 0

                if self.interface == "all":
                    for iface in now:
                        if iface in last:
                            up += now[iface].bytes_sent - last[iface].bytes_sent
                            down += now[iface].bytes_recv - last[iface].bytes_recv
                else:
                    if self.interface in now and self.interface in last:
                        up = now[self.interface].bytes_sent - last[self.interface].bytes_sent
                        down = now[self.interface].bytes_recv - last[self.interface].bytes_recv

                last = now

                up = max(0, int(up))
                down = max(0, int(down))

                # Persist delta to SQLite with error logging
                try:
                    log_traffic(up, down)
                except Exception as e:
                    # Log silently to file to aid debugging without crashing TUI
                    with open("netwatch_debug.log", "a") as f:
                        f.write(f"DB Error: {e}\n")

                self.total_up += up
                self.total_down += down

                packet = {
                    "upload_speed": up,
                    "download_speed": down,
                    "total_upload": self.total_up,
                    "total_download": self.total_down,
                    "total_usage": self.total_up + self.total_down,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }

                if self.log_file:
                    try:
                        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            writer.writerow([packet["timestamp"], up, down, get_size(self.total_up), get_size(self.total_down), get_size(packet["total_usage"])])
                    except Exception:
                        self.log_file = None

                if self.stop_event.is_set():
                    break
                self.callback(packet)
            
            except Exception as e:
                if not self.stop_event.is_set():
                    self.callback({"error": f"Error in monitor loop: {e}"})
                    self.stop_event.wait(3.0)