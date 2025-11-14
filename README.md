# Netwatch TUI (netwatchpy)

[![PyPI Version](https://img.shields.io/pypi/v/netwatchpy.svg)](https://pypi.org/project/netwatchpy/)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

A TUI (Text-based User Interface) for monitoring network usage in real-time, with support for data limits and desktop notifications.

---
<p align="center">
<img width="800" height="500" alt="netwatch_demo" src="/assets/netwatch_demo.png" />
</p>

---

## Features

* **Real-time Dashboard:** A clean, terminal-based dashboard showing total download, upload, and current speeds.
* **Data Cap Monitoring:** Set a data limit (e.g., `10GB`) and see your usage on a real-time progress bar.
* **Desktop Notifications:** Get native desktop notifications when you hit 80% and 100% of your data limit.
* **Live Activity Log:** An interactive, scrolling log of all network activity, updated every second.
* **Command Palette & Dark Mode:** A modern TUI experience with a built-in command palette (`Ctrl+P`) and dark mode support (`Ctrl+D`).
* **CSV Logging:** Optionally log all network traffic to a CSV file for later analysis.
* **Cross-Platform:** Runs on Windows, macOS, and Linux.

---

## Installation

`netwatchpy` is available on PyPI. All you need is Python 3.8+ and `pip`.

```bash
pip install netwatchpy
```
---

## Usage

Once installed, the netwatch command will be available in your terminal.

**To start the monitor (monitors all interfaces):**

```bash
netwatch
```

**To see all available options and help:**

```bash
netwatch --help
```
---
## Command-Line Arguments

You can control the monitor with these arguments:

*   **`-h`,` --help`**
    
    *   Shows the help message and all options.
        
*   **`-i INTERFACE`,` --interface INTERFACE`**
    
    *   Monitors a single, specific network interface (e.g., -i "Wi-Fi"). Defaults to "all".
        
*   **`-l LIMIT`,` --limit LIMIT`**
    
    *   Sets a data cap and shows a progress bar (e.g., -l "10GB" or -l "500MB").
        
*   **`--log LOG`**
    
    *   Saves all network activity to a specified CSV file (e.g., --log "usage.csv").
        
---

### Examples

**Set a 10GB data limit:**

```bash
netwatch -l "10GB"
```

**Monitor a specific interface ("Wi-Fi") and log to a file:**

```bash
netwatch -i "Wi-Fi" --log "my_usage.csv"
```
---
### In-App Keybindings

*   **`Ctrl+P`**: Open the Command Palette
    
*   **`Ctrl+D`**: Toggle Dark / Light Mode
    
*   **`r`**: Reset all counters back to zero
    
*   **`Ctrl+Q`**: Quit the application
    
---

Bug Reports & Feature Requests
---------------------------------

Found a bug or have a great idea? Please [open an issue]([https://github.com/destroyer795/Netwatchpy-package/issues](https://github.com/destroyer795/Netwatchpy-package/issues)) on the GitHub repository.

License
----------

This project is licensed under the MIT License.
