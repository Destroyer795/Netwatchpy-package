import unittest
import time
import sqlite3
import os
from unittest.mock import MagicMock
from collections import namedtuple

from netwatch.monitor import is_active_interface, NetworkMonitorThread
from netwatch.db import (
    init_db,
    log_interface_metrics,
    get_interface_totals,
    get_interface_hourly_usage,
    clear_history,
    _get_conn,
)
from netwatch.graph import generate_interface_activity_chart

NetStats = namedtuple("NetStats", ["bytes_sent", "bytes_recv"])

class TestInterfaceFiltering(unittest.TestCase):
    def test_filter_loopback(self):
        # Linux / Unix lo
        self.assertFalse(is_active_interface("lo", NetStats(1000, 2000)))
        # macOS / BSD lo0, lo1
        self.assertFalse(is_active_interface("lo0", NetStats(1000, 2000)))
        self.assertFalse(is_active_interface("lo1", NetStats(1000, 2000)))
        # Windows loopback
        self.assertFalse(is_active_interface("Loopback Pseudo-Interface 1", NetStats(1000, 2000)))
        # Npcap loopback
        self.assertFalse(is_active_interface("Npcap Loopback Adapter", NetStats(1000, 2000)))
        # Case insensitivity
        self.assertFalse(is_active_interface("LO", NetStats(1000, 2000)))
        self.assertFalse(is_active_interface("LO0", NetStats(1000, 2000)))

    def test_filter_inactive(self):
        # Inactive interfaces with 0 bytes sent and 0 bytes recv
        self.assertFalse(is_active_interface("eth0", NetStats(0, 0)))
        self.assertFalse(is_active_interface("Bluetooth Network Connection", NetStats(0, 0)))

    def test_keep_active(self):
        # Active interfaces
        self.assertTrue(is_active_interface("Wi-Fi", NetStats(500000, 1000000)))
        self.assertTrue(is_active_interface("eth0", NetStats(100, 0)))
        self.assertTrue(is_active_interface("en0", NetStats(0, 500)))

class TestInterfaceDatabase(unittest.TestCase):
    def setUp(self):
        init_db()
        clear_history()

    def tearDown(self):
        clear_history()

    def test_table_creation(self):
        conn = _get_conn()
        try:
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interface_metrics'")
            self.assertIsNotNone(c.fetchone())
            c.execute("PRAGMA table_info(interface_metrics)")
            columns = {row[1]: row[2] for row in c.fetchall()}
            self.assertIn("timestamp", columns)
            self.assertIn("interface_name", columns)
            self.assertIn("bytes_sent", columns)
            self.assertIn("bytes_recv", columns)
        finally:
            conn.close()

    def test_bulk_insert_and_totals(self):
        now = int(time.time())
        records = [
            (now, "Wi-Fi", 1024, 2048),
            (now, "eth0", 512, 1024),
            (now, "Wi-Fi", 2048, 4096),
        ]
        log_interface_metrics(records)

        totals = get_interface_totals()
        self.assertIn("Wi-Fi", totals)
        self.assertIn("eth0", totals)
        self.assertEqual(totals["Wi-Fi"], (3072, 6144))
        self.assertEqual(totals["eth0"], (512, 1024))

    def test_hourly_usage(self):
        now = int(time.time())
        records = [
            (now, "Wi-Fi", 10000, 20000),
        ]
        log_interface_metrics(records)
        hourly = get_interface_hourly_usage("Wi-Fi")
        self.assertTrue(len(hourly) > 0)
        self.assertEqual(hourly[0][1], 10000)
        self.assertEqual(hourly[0][2], 20000)

    def test_clear_history(self):
        now = int(time.time())
        log_interface_metrics([(now, "Wi-Fi", 100, 200)])
        clear_history()
        totals = get_interface_totals()
        self.assertEqual(totals, {})

class TestGraphRendering(unittest.TestCase):
    def test_activity_chart_empty(self):
        output = generate_interface_activity_chart([])
        self.assertIn("Waiting for traffic", output)

    def test_activity_chart_content(self):
        samples = [(1000, 5000), (2000, 10000), (5000, 25000)]
        output = generate_interface_activity_chart(samples, width=20, height=5)
        self.assertIn("REAL-TIME TRAFFIC GRAPH", output)
        self.assertIn("Current:", output)
        self.assertIn("Peak:", output)
        self.assertIn("Legend:", output)

if __name__ == "__main__":
    unittest.main()
