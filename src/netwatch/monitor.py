import psutil
import threading
import time
from datetime import datetime
import csv
from .utils import get_size
from .db import log_traffic, log_interface_metrics

def is_active_interface(name: str, stats) -> bool:
    """
    Filter out virtual or inactive interfaces across Linux, macOS, and Windows:
    - Exclude loopback interfaces:
      * Linux: 'lo'
      * macOS / BSD: 'lo0', 'lo1', etc.
      * Windows: 'Loopback Pseudo-Interface 1', 'Npcap Loopback Adapter', etc.
    - Exclude interfaces where both bytes_sent and bytes_recv are 0
    """
    name_lower = name.lower().strip()
    if "loopback" in name_lower:
        return False
    if name_lower == "lo" or (name_lower.startswith("lo") and name_lower[2:].isdigit()):
        return False
    if stats.bytes_sent == 0 and stats.bytes_recv == 0:
        return False
    return True

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
        self.interface_totals = {}
        
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

                interfaces_data = {}
                db_interface_records = []
                ts = int(time.time())

                # Collect segmented data and filter inactive/loopback interfaces
                for iface, stats in now.items():
                    if not is_active_interface(iface, stats):
                        continue

                    iface_up = 0
                    iface_down = 0
                    if iface in last:
                        iface_up = max(0, int(stats.bytes_sent - last[iface].bytes_sent))
                        iface_down = max(0, int(stats.bytes_recv - last[iface].bytes_recv))

                    if iface not in self.interface_totals:
                        self.interface_totals[iface] = {"upload": 0, "download": 0}
                    self.interface_totals[iface]["upload"] += iface_up
                    self.interface_totals[iface]["download"] += iface_down

                    interfaces_data[iface] = {
                        "upload_speed": iface_up,
                        "download_speed": iface_down,
                        "session_upload": self.interface_totals[iface]["upload"],
                        "session_download": self.interface_totals[iface]["download"],
                        "bytes_sent": stats.bytes_sent,
                        "bytes_recv": stats.bytes_recv,
                    }

                    if iface_up > 0 or iface_down > 0:
                        db_interface_records.append((ts, iface, iface_up, iface_down))

                up = 0
                down = 0

                if self.interface == "all":
                    for iface, data in interfaces_data.items():
                        up += data["upload_speed"]
                        down += data["download_speed"]
                else:
                    if self.interface in interfaces_data:
                        up = interfaces_data[self.interface]["upload_speed"]
                        down = interfaces_data[self.interface]["download_speed"]
                    elif self.interface in now and self.interface in last:
                        up = max(0, int(now[self.interface].bytes_sent - last[self.interface].bytes_sent))
                        down = max(0, int(now[self.interface].bytes_recv - last[self.interface].bytes_recv))

                last = now

                up = max(0, int(up))
                down = max(0, int(down))

                # Persist deltas to SQLite (WAL mode bulk insert for interfaces)
                try:
                    log_traffic(up, down)
                    if db_interface_records:
                        log_interface_metrics(db_interface_records)
                except Exception as e:
                    # Log silently to file to aid debugging without crashing TUI
                    if not self.stop_event.is_set():
                        self.callback({"error": f"DB Error: {e}"})
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
                    "interfaces": interfaces_data,
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