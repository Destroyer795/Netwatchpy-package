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
        

Examples
--------

**Start with default settings (all interfaces, 7-day retention):**
```bash
netwatch
```

**Set custom data retention (e.g., 14 days):**
```bash
netwatch --retention-days 14
```

**Set a 10GB data usage cap:**
```bash
netwatch -l "10GB"
```

**Monitor a specific interface and save session log to CSV:**
```bash
netwatch -i "Wi-Fi" --log "session.csv"
```

**Combine options (e.g., 20GB limit, 30-day retention on Wi-Fi):**
```bash
netwatch -i "Wi-Fi" -l "20GB" --retention-days 30
```

TUI Controls & Shortcuts
------------------------

Once inside the application, use these keyboard shortcuts to control the interface. The footer bar is specifically formatted to fit standard 80x24 terminal windows without requiring horizontal scrolling.

*   **Ctrl+p** (Command Palette): Opens the Textual command palette to search and trigger actions.

*   **Ctrl+d** (Theme): Toggles between Dark and Light mode.

*   **Ctrl+b** (Toggle Units): Switch between Bits (Mbps) and Bytes (MB/s) display.

*   **r** (Refresh Chart): Updates the graph in the "History" tab with the latest data.

*   **Ctrl+r** (Reset All): Wipes the database and resets all counters to 0. **Use with caution.**

*   **Ctrl+s** (Save Status): Displays a temporary status confirming data is continuously auto-saved.

*   **Ctrl+q** (Quit): Exits the application safely, running WAL truncate checkpoints.


Understanding the Interface
---------------------------

### 1. Live Monitor Tab

This is the default view containing real-time telemetry and network accounting:

*   **Summary Cards:** Four real-time cards provide an immediate high-level overview:
    *   **Total Downloaded:** Total downloaded data across both current session and persistent history.
    *   **Total Uploaded:** Total uploaded data across both current session and persistent history.
    *   **Total Bandwidth:** Combined data consumption across all monitored traffic.
    *   **Current Speed:** Real-time combined throughput (live upload + download speed).

*   **Smart Quota Dashboard & Burn-Rate ETA:** When a usage limit is configured (e.g., `-l 10GB`), a compact 3-row dashboard appears above the log table:
    *   **Usage Limit Header:** Displays the configured target limit (e.g., `Usage Limit: 10.00 GB`).
    *   **Dynamic Progress Bar:** Visual bar showing the exact percentage of your quota consumed.
    *   **Live Telemetry Badge:** A single-line status badge providing real-time forecasting:
        *   **Remaining Quota:** Exact data remaining before limit exhaustion (e.g., `1.2 GB remaining`).
        *   **Percentage Used:** Formatted percentage consumed (e.g., `(88.0%)`).
        *   **Active Burn Rate:** Live transfer speed at which the quota is being burned (e.g., `• 4.5 MB/s`).
        *   **Dynamic ETA Forecaster:** Calculates the estimated time remaining until the quota runs out based on your current burn rate (e.g., `• ETA: 4m 27s`). When traffic is stagnant, it displays `• ETA: Idle`. Once exhausted, it indicates `Quota Exceeded`.
    *   **Visual Warning Tiers:**
        *   **Normal (< 80%):** Standard accent / primary theme color.
        *   **Warning (>= 80%):** Transitions to amber/yellow to warn that data cap is approaching.
        *   **Exceeded (>= 100%):** Transitions to bold red to alert that data cap has been crossed.

*   **Live Activity Table:** A scrolling log recording timestamp, download speed, and upload speed every second.

*   **Debounced Subtitle Feedback:** The header subtitle displays active interface and unit status. When shortcuts are pressed (e.g., unit change, auto-save status, or quota reset), a temporary status notification flashes on the top bar and automatically resets back to the default status after 3 seconds.

### 2. Per-Interface Tab

This tab provides a segmented master-detail view of individual active network interfaces (e.g. Wi-Fi, Ethernet). Virtual and inactive connections (such as loopback) are automatically filtered out.

*   **Active Interfaces Sidebar (Left):** Selectable list of active network adapters. Use the arrow keys or mouse to highlight any interface.
    
*   **Focused Metrics (Right):** Displays current upload and download speeds, session totals, and hardware adapter totals for the selected interface.
    
*   **Real-time Activity Graph:** An uncluttered 2D waveform graph that continuously plots recent traffic patterns for the chosen interface in real time (`█` for Download, `░` for Upload).

### 3. History Tab (24h)

This tab visualizes your traffic over the last 24 hours with detailed analytics.

*   **Traffic Summary:** Displays total upload/download with percentages, peak hour, and average usage per hour.
    
*   **Hourly Breakdown:** Each row represents a 1-hour block of time (e.g., 14:00 covers 2:00 PM to 2:59 PM).
    
*   **The Bar:**
    
    *   **Solid Block (█):** Represents **Download** traffic.
        
    *   **Shaded Block (░):** Represents **Upload** traffic.
        
*   **Peak Hour:** Highlighted with a (PEAK) marker to show when you used the most data.
    
*   **Total:** The text on the far right shows the exact data transferred during that hour.
    

> **Tip:** The graph does not auto-refresh to save resources. Press `r` whenever you want to see the latest data and statistics.

Desktop Notifications
---------------------

Netwatch includes a universal cross-platform notification engine that dispatches native desktop alerts:

*   **80% Warning Notification:** Dispatched once cumulative bandwidth reaches 80% of your configured cap.
*   **100% Exceeded Notification:** Dispatched immediately upon crossing 100% of your limit.
*   **Operating System Support:**
    *   **Windows:** Dispatches native WinRT Toast notifications with the Netwatch talisman icon branded directly into the notification attribution banner via Windows Shell AppUserModelId registration.
    *   **macOS:** Dispatches native Notification Center banners via AppleScript (`osascript`).
    *   **Linux:** Dispatches D-Bus desktop notifications with automatic fallback to standard `notify-send`.

Database Retention & Downsampling
---------------------------------

Netwatch automatically optimizes its internal SQLite database to prevent unbounded file growth during 24/7 continuous operation:

*   **Automated Data Retention:** Granular, second-by-second records are retained for a configurable window (default: 7 days, controlled via `--retention-days`).
*   **Hourly Aggregations (Rollups):** Older records beyond the retention threshold are compressed into hourly summaries (`hourly_summary` table) storing total transfer volume and min/max/average speeds before raw records are purged. Lifetime usage totals and trends remain preserved.
*   **WAL Maintenance:** Passive checkpoints run periodically and truncate checkpoints run on clean exit to keep SQLite WAL files minimal on disk.

### How to use `--retention-days`:

```bash
# Keep granular 1-second records for 14 days:
netwatch --retention-days 14

# Minimal storage footprint for lightweight devices (e.g. Raspberry Pi):
netwatch --retention-days 3

# Extended granular history (e.g. 30 days):
netwatch --retention-days 30
```

> **Note:** Data retention pruning runs automatically when Netwatch starts up and operates seamlessly in the background without affecting your lifetime usage statistics.