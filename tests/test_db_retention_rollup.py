import unittest
import time
import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from netwatch.db import (
    init_db,
    log_traffic,
    log_interface_metrics,
    get_historical_totals,
    get_interface_totals,
    clear_history,
    prune_and_rollup_database,
    checkpoint_wal,
    _get_conn,
    DB_FILE,
)

class TestDatabaseRetentionAndRollup(unittest.TestCase):
    def setUp(self):
        init_db(retention_days=7)
        clear_history()

    def tearDown(self):
        clear_history()

    def test_hourly_summary_table_and_indices_exist(self):
        conn = _get_conn()
        try:
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hourly_summary'")
            self.assertIsNotNone(c.fetchone(), "hourly_summary table must exist")

            c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_hourly_ts_iface'")
            self.assertIsNotNone(c.fetchone(), "idx_hourly_ts_iface index must exist")
        finally:
            conn.close()

    def test_prune_and_rollup_global_metrics(self):
        conn = _get_conn()
        now = int(time.time())
        # 10 days ago (older than 7-day default retention)
        old_hour_start = (now - (10 * 86400)) // 3600 * 3600
        
        # Insert raw usage_log records in old hour
        try:
            c = conn.cursor()
            c.execute("INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                      (old_hour_start + 10, 1000, 5000))
            c.execute("INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                      (old_hour_start + 20, 2000, 3000))
            c.execute("INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                      (old_hour_start + 30, 3000, 4000))

            # Insert recent record (1 hour ago)
            recent_time = now - 3600
            c.execute("INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                      (recent_time, 500, 1500))
            conn.commit()
        finally:
            conn.close()

        # Execute pruning with 7 days retention
        prune_and_rollup_database(retention_days=7)

        conn = _get_conn()
        try:
            c = conn.cursor()
            # 1. Verify raw old records purged
            c.execute("SELECT COUNT(*) FROM usage_log WHERE timestamp < ?", (now - (7 * 86400),))
            self.assertEqual(c.fetchone()[0], 0, "Old raw records should be deleted from usage_log")

            # 2. Verify recent raw record preserved
            c.execute("SELECT COUNT(*) FROM usage_log WHERE timestamp >= ?", (now - (7 * 86400),))
            self.assertEqual(c.fetchone()[0], 1, "Recent raw record should be retained")

            # 3. Verify hourly_summary contains rolled up data
            c.execute("SELECT * FROM hourly_summary WHERE interface_name = '__all__'")
            row = c.fetchone()
            self.assertIsNotNone(row, "hourly_summary should have a record for '__all__'")
            
            # Columns: id, timestamp, interface_name, total_upload, total_download, min_up, max_up, avg_up, min_down, max_down, avg_down, sample_count
            ts, iface, tot_up, tot_down, min_up, max_up, avg_up, min_down, max_down, avg_down, count = row[1:]
            self.assertEqual(ts, old_hour_start)
            self.assertEqual(iface, "__all__")
            self.assertEqual(tot_up, 6000)      # 1000 + 2000 + 3000
            self.assertEqual(tot_down, 12000)   # 5000 + 3000 + 4000
            self.assertEqual(min_up, 1000)
            self.assertEqual(max_up, 3000)
            self.assertAlmostEqual(avg_up, 2000.0)
            self.assertEqual(min_down, 3000)
            self.assertEqual(max_down, 5000)
            self.assertAlmostEqual(avg_down, 4000.0)
            self.assertEqual(count, 3)
        finally:
            conn.close()

        # 4. Verify historical totals seamlessly combines rollup + recent raw
        total_up, total_down = get_historical_totals()
        self.assertEqual(total_up, 6000 + 500)
        self.assertEqual(total_down, 12000 + 1500)

    def test_prune_and_rollup_interface_metrics(self):
        conn = _get_conn()
        now = int(time.time())
        old_hour_start = (now - (12 * 86400)) // 3600 * 3600

        try:
            c = conn.cursor()
            # Old records for 'Wi-Fi'
            c.execute("INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
                      (old_hour_start + 5, "Wi-Fi", 400, 800))
            c.execute("INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
                      (old_hour_start + 15, "Wi-Fi", 600, 1200))

            # Old records for 'Ethernet'
            c.execute("INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
                      (old_hour_start + 5, "Ethernet", 1000, 2000))

            # Recent records
            c.execute("INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
                      (now - 100, "Wi-Fi", 100, 200))
            conn.commit()
        finally:
            conn.close()

        prune_and_rollup_database(retention_days=7)

        conn = _get_conn()
        try:
            c = conn.cursor()
            # Old records deleted
            c.execute("SELECT COUNT(*) FROM interface_metrics WHERE timestamp < ?", (now - (7 * 86400),))
            self.assertEqual(c.fetchone()[0], 0)

            # Summaries present
            c.execute("SELECT total_upload, total_download, min_upload_speed, max_upload_speed, sample_count FROM hourly_summary WHERE interface_name = 'Wi-Fi'")
            wifi_row = c.fetchone()
            self.assertIsNotNone(wifi_row)
            self.assertEqual(wifi_row[0], 1000)  # 400 + 600
            self.assertEqual(wifi_row[1], 2000)  # 800 + 1200
            self.assertEqual(wifi_row[2], 400)
            self.assertEqual(wifi_row[3], 600)
            self.assertEqual(wifi_row[4], 2)

            c.execute("SELECT total_upload, total_download FROM hourly_summary WHERE interface_name = 'Ethernet'")
            eth_row = c.fetchone()
            self.assertIsNotNone(eth_row)
            self.assertEqual(eth_row[0], 1000)
            self.assertEqual(eth_row[1], 2000)
        finally:
            conn.close()

        # Combined interface totals
        iface_totals = get_interface_totals()
        self.assertIn("Wi-Fi", iface_totals)
        self.assertIn("Ethernet", iface_totals)
        self.assertEqual(iface_totals["Wi-Fi"], (1000 + 100, 2000 + 200))
        self.assertEqual(iface_totals["Ethernet"], (1000, 2000))

    def test_wal_checkpoint(self):
        # Insert some traffic
        log_traffic(1024, 2048)
        # Checkpoint passive
        checkpoint_wal(truncate=False)
        # Checkpoint truncate
        checkpoint_wal(truncate=True)

        self.assertTrue(os.path.exists(DB_FILE))

    def test_clear_history_wipes_all_including_rollups(self):
        conn = _get_conn()
        try:
            c = conn.cursor()
            c.execute("INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                      (1000, 100, 200))
            c.execute("INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
                      (1000, "eth0", 50, 60))
            c.execute("INSERT INTO hourly_summary (timestamp, interface_name, total_upload, total_download) VALUES (?, ?, ?, ?)",
                      (1000, "__all__", 500, 600))
            conn.commit()
        finally:
            conn.close()

        clear_history()

        totals_up, totals_down = get_historical_totals()
        self.assertEqual(totals_up, 0)
        self.assertEqual(totals_down, 0)

        iface_totals = get_interface_totals()
        self.assertEqual(len(iface_totals), 0)

if __name__ == "__main__":
    unittest.main()
