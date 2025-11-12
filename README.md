Netwatch TUI (netwatchpy)

A TUI (Text-based User Interface) for monitoring network usage in real-time, with support for data limits and desktop notifications.

Installation

pip install netwatchpy


Usage

Once installed, the netwatch command will be available in your terminal.

Run the monitor (monitors all interfaces):

netwatch


See all available options:

netwatch --help


Examples

Set a 10GB data limit:

netwatch -l "10GB"


Monitor a specific interface and log to a file:

netwatch -i "Wi-Fi" --log "my_usage.csv"


Features

Real-time dashboard for Upload/Download speeds and totals.

Data limit progress bar and desktop notifications for 80% and 100% usage.

Interactive log of all activity.

Dark Mode (Ctrl+D) and Command Palette (Ctrl+P).

Ability to log all traffic to a CSV file (--log).