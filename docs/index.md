# Netwatch TUI
---

Welcome to the official documentation for **Netwatch**, the advanced CLI network monitor.

Netwatch is a Python-based TUI (Text User Interface) application designed to help you track your internet usage, enforce data caps, and analyze traffic trends over time.

![Demo](https://raw.githubusercontent.com/Destroyer795/Netwatchpy-package/main/assets/demo.png)

## Key Features

* **SQLite Backend:** Crash-proof history storage that survives unexpected shutdowns.
* **Real-time Graphs:** Unicode-based visualization for 24-hour traffic analysis.
* **Zero-Dependencies:** Runs anywhere Python runs without heavy graphical libraries.
* **Smart Notifications:** Get alerted before you hit your data cap.
* **Auto-Migration:** Seamlessly imports data from older versions (`quota.json`) so you never lose history.

## Why Netwatch?

Unlike complex system monitoring tools (like Task Manager or `htop`) which focus on *current* speed, Netwatch is focused on **bandwidth accounting**.

It answers the simple but critical questions: 
* *"How much data have I used today?"*

* *"Did I hit my data cap yesterday?"*

* *"Am I mostly downloading or uploading?"*