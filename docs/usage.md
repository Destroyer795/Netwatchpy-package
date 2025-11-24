# User Guide

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
        

TUI Controls & Shortcuts
------------------------

Once inside the application, use these keyboard shortcuts to control the interface.

*   **r** (Refresh Chart): Updates the graph in the "History" tab with the latest data.
    
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
    

### 2\. History Tab (24h)

This tab visualizes your traffic over the last 24 hours.

*   **Rows:** Each row represents a 1-hour block of time (e.g., 14:00 covers 2:00 PM to 2:59 PM).
    
*   **The Bar:**
    
    *   **Solid Block (█):** Represents **Download** traffic.
        
    *   **Shaded Block (░):** Represents **Upload** traffic.
        
*   **Total:** The text on the far right shows the exact data transferred during that hour.
    

> **Tip:** The graph does not auto-refresh to save resources. Press r whenever you want to see the latest bars.