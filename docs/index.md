# Netwatch TUI
---

Welcome to the official documentation for **Netwatch**, the advanced CLI network monitor.

Netwatch is a Python-based TUI (Text User Interface) application designed to help you track your internet usage, enforce data caps, and analyze traffic trends over time.

![Demo](https://raw.githubusercontent.com/Destroyer795/Netwatchpy-package/main/assets/demo.png)

## Key Features

* **Real-time Telemetry:** Live dashboard with summary cards for Total Downloaded, Total Uploaded, Total Bandwidth, and Combined Current Speed.
* **Smart Quota Dashboard & Burn-Rate ETA:** Real-time progress bar with remaining quota, percentage badge, active burn rate, and a dynamic countdown ETA forecaster estimating quota exhaustion.
* **Per-Interface Monitoring:** Dedicated split-pane view to inspect real-time bandwidth and 2D activity charts segmented per active network adapter with automatic loopback filtering.
* **Universal Desktop Notifications:** Native desktop alerts across Windows (WinRT Toast with custom icon branding), macOS (Notification Center), and Linux (D-Bus / notify-send) triggered at 80% and 100% quota thresholds.
* **Crash-Proof SQLite Backend:** Powered by SQLite with Write-Ahead Logging (WAL) to survive unexpected shutdowns and power loss.
* **Automated Data Retention & Downsampling:** Configurable retention policy (`--retention-days`) compressing older granular records into hourly rollups to keep disk storage minimal.
* **24-Hour Analytics & Trends:** Unicode-based hourly breakdown chart with peak hour identification, upload/download ratios, and average usage statistics.
* **Instant Unit Switching:** Seamlessly toggle between Bits (Mbps) and Bytes (MB/s) with `Ctrl+B` to match ISP plans or file sizes.
* **Optimized TUI Design:** Streamlined, non-scrolling footer fitting standard 80x24 terminals, command palette (`Ctrl+P`), dark/light theme switching (`Ctrl+D`), and auto-resetting status feedback.
* **Auto-Migration:** Automatically detects and imports legacy `quota.json` files on first launch.

## Why Netwatch?

Unlike complex system monitoring tools (like Task Manager or `htop`) which focus on *current* speed, Netwatch is focused on **bandwidth accounting**.

It answers the simple but critical questions:

* *"How much data have I used today?"*

* *"Did I hit my data cap yesterday?"*

* *"Am I mostly downloading or uploading?"*
