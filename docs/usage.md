# User Guide
---

## Basic Usage

To start monitoring all network interfaces immediately, simply run:

```bash
netwatch
```

This will launch the TUI. Netwatch runs in the background, logging your usage to its internal database every second.

Command Line Arguments
----------------------

You can customize how Netwatch starts using flags.

*   **\-i, --interface**: Monitor only one specific interface (e.g., Wi-Fi, Ethernet).
    
    *   Example: netwatch -i "Ethernet"
        
*   **\-l, --limit**: Set a usage quota. Supports KB, MB, GB, TB.
    
    *   Example: netwatch -l "50GB"
        
*   **\--log**: Export live session data to a CSV file.
    
    *   Example: netwatch --log "session.csv"
        
*   **\--retention-days**: Set data retention period in days for raw granular metrics (default: 7). Older records are rolled up into hourly summaries before being purged.
    
    *   Example: netwatch --retention-days 14
        

TUI Controls & Shortcuts
------------------------

Once inside the application, use these keyboard shortcuts to control the interface.

*   **r** (Refresh Chart): Updates the graph in the "History" tab with the latest data.
    
*   **Ctrl+b** (Toggle Bits/Bytes): Switch between Bits (Mbps) and Bytes (MB/s) display.

*   **Ctrl+r** (Reset All): Wipes the database and resets all counters to 0. **Use with caution.**
    
*   **Ctrl+d** (Dark Mode): Toggles between Light and Dark themes.
    
*   **Ctrl+s** (Save Status): Displays a message confirming data is auto-saved.
    
*   **Ctrl+q** (Quit): Exits the application safely.
    

Understanding the Interface
---------------------------

### 1\. Live Monitor Tab

This is the default view containing real-time stats:

*   **Summary Cards:** Total Upload, Download, and Combined Usage for the current session + history.
    
*   **Quota Bar:** If a limit was set, this bar fills up. It turns **Yellow at 80%** and **Red at 100%**.
    
*   **Live Table:** A scrolling list of network speeds recorded every second.
    

### 2\. Per-Interface Tab

This tab provides a segmented master-detail view of individual active network interfaces (e.g. Wi-Fi, Ethernet). Virtual and inactive connections (such as loopback) are automatically filtered out.

*   **Active Interfaces Sidebar (Left):** Selectable list of active network adapters. Use the arrow keys or mouse to highlight any interface.
    
*   **Focused Metrics (Right):** Displays current upload and download speeds, session totals, and hardware adapter totals for the selected interface.
    
*   **Real-time Activity Graph:** An uncluttered 2D waveform graph that continuously plots recent traffic patterns for the chosen interface in real time (`█` for Download, `░` for Upload).

### 3\. History Tab (24h)

This tab visualizes your traffic over the last 24 hours with detailed analytics.

*   **Traffic Summary:** Displays total upload/download with percentages, peak hour, and average usage per hour.
    
*   **Hourly Breakdown:** Each row represents a 1-hour block of time (e.g., 14:00 covers 2:00 PM to 2:59 PM).
    
*   **The Bar:**
    
    *   **Solid Block (█):** Represents **Download** traffic.
        
    *   **Shaded Block (░):** Represents **Upload** traffic.
        
*   **Peak Hour:** Highlighted with a (PEAK) marker to show when you used the most data.
    
*   **Total:** The text on the far right shows the exact data transferred during that hour.
    

> **Tip:** The graph does not auto-refresh to save resources. Press r whenever you want to see the latest data and statistics.

Database Retention & Downsampling
---------------------------------

Netwatch automatically optimizes its internal SQLite database to prevent unbounded file growth during 24/7 continuous operation:

*   **Automated Data Retention:** Granular, second-by-second records are retained for a configurable window (default: 7 days, controlled via `--retention-days`).
*   **Hourly Aggregations (Rollups):** Older records beyond the retention threshold are compressed into hourly summaries (`hourly_summary` table) storing total transfer volume and min/max/average speeds before raw records are purged. Historical totals are preserved seamlessly.
*   **WAL Maintenance:** Passive checkpoints run periodically and truncate checkpoints run on clean exit to keep SQLite WAL files minimal on disk.