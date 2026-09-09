import sqlite3
import os
import json
import time
from datetime import datetime
from platformdirs import user_config_dir

APP_NAME = "netwatchpy"
DB_DIR = user_config_dir(APP_NAME)
DB_FILE = os.path.join(DB_DIR, "netwatch_history.db")
LEGACY_FILE = os.path.join(DB_DIR, "quota.json")

def _get_conn():
    """Create a connection to the SQLite database."""
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db(retention_days: int = 7):
    """Initialize the database table, enable WAL, migrate old data, and prune expired records."""
    conn = _get_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL;") 
        
        c = conn.cursor()
        # timestamp is (Unix Epoch) instead of TEXT
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                upload_bytes INTEGER,
                download_bytes INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON usage_log (timestamp)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS interface_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                interface_name TEXT,
                bytes_sent INTEGER,
                bytes_recv INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_iface_ts ON interface_metrics (interface_name, timestamp)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS hourly_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                interface_name TEXT,
                total_upload INTEGER,
                total_download INTEGER,
                min_upload_speed INTEGER,
                max_upload_speed INTEGER,
                avg_upload_speed REAL,
                min_download_speed INTEGER,
                max_download_speed INTEGER,
                avg_download_speed REAL,
                sample_count INTEGER,
                UNIQUE(timestamp, interface_name)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_hourly_ts_iface ON hourly_summary (interface_name, timestamp)")
        conn.commit()
    finally:
        conn.close()
    
    _migrate_legacy_json()
    prune_and_rollup_database(retention_days)

def _migrate_legacy_json():
    """
    Check for an old 'quota.json' file. If it exists, import its totals
    into the database as a single 'baseline' entry, then rename the file.
    """
    if not os.path.exists(LEGACY_FILE):
        return

    print("[netwatch] Migrating legacy quota.json to database...")
    try:
        with open(LEGACY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        old_up = int(data.get("total_upload", 0))
        old_down = int(data.get("total_download", 0))

        if old_up > 0 or old_down > 0:
            conn = _get_conn()
            try:
                c = conn.cursor()
                # Use current Epoch time
                ts = int(time.time())
                c.execute(
                    "INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                    (ts, old_up, old_down)
                )
                conn.commit()
            finally:
                conn.close()

        new_name = LEGACY_FILE + ".migrated"
        os.rename(LEGACY_FILE, new_name)
        print(f"[netwatch] Migration successful. Renamed to {new_name}")

    except Exception as e:
        print(f"[netwatch] Migration failed: {e}")

def log_traffic(up_delta: int, down_delta: int):
    """Log a slice of traffic usage."""
    if up_delta == 0 and down_delta == 0:
        return

    conn = _get_conn()
    try:
        c = conn.cursor()
        ts = int(time.time())
        c.execute(
            "INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
            (ts, int(up_delta), int(down_delta))
        )
        conn.commit()
    finally:
        conn.close()

def get_historical_totals():
    """Calculate total upload/download from both hourly summaries and raw usage log."""
    if not os.path.exists(DB_FILE):
        return 0, 0
    
    conn = _get_conn()
    try:
        c = conn.cursor()
        # Sum from hourly_summary for global traffic
        c.execute("SELECT SUM(total_upload), SUM(total_download) FROM hourly_summary WHERE interface_name = '__all__'")
        s_row = c.fetchone()
        s_up = int(s_row[0] or 0) if s_row else 0
        s_down = int(s_row[1] or 0) if s_row else 0

        # Sum from active raw records
        c.execute("SELECT SUM(upload_bytes), SUM(download_bytes) FROM usage_log")
        r_row = c.fetchone()
        r_up = int(r_row[0] or 0) if r_row else 0
        r_down = int(r_row[1] or 0) if r_row else 0

        return s_up + r_up, s_down + r_down
    finally:
        conn.close()

def get_hourly_usage_last_24h():
    """
    Returns a list of tuples: (hour_label, upload_bytes, download_bytes)
    for the last 24 hours.
    
    We perform the aggregation in SQL using Unix Epoch math.
    'unixepoch' and 'localtime' modifiers convert the int back to a string
    only for the final grouped output, keeping the WHERE clause fast.
    """
    conn = _get_conn()
    try:
        c = conn.cursor()
        
        cutoff_time = int(time.time()) - 86400  # 24 hours ago in seconds
        
        query = """
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp, 'unixepoch', 'localtime') as hour_bucket,
                SUM(upload_bytes),
                SUM(download_bytes)
            FROM usage_log
            WHERE timestamp >= ?
            GROUP BY hour_bucket
            ORDER BY hour_bucket ASC
        """
        c.execute(query, (cutoff_time,))
        return c.fetchall()
    finally:
        conn.close()

def log_interface_metrics(records):
    """
    Bulk insert interface metrics to minimize database write locks.
    records: list of tuples (timestamp, interface_name, bytes_sent, bytes_recv)
    """
    if not records:
        return

    conn = _get_conn()
    try:
        c = conn.cursor()
        c.executemany(
            "INSERT INTO interface_metrics (timestamp, interface_name, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?)",
            records
        )
        conn.commit()
    finally:
        conn.close()

def get_interface_totals():
    """
    Returns a dictionary of total bytes sent and received per interface:
    {interface_name: (total_sent, total_recv)}
    Combines both hourly summaries and active raw metrics.
    """
    if not os.path.exists(DB_FILE):
        return {}

    conn = _get_conn()
    try:
        c = conn.cursor()
        totals = {}

        # 1. Rollup totals
        c.execute("""
            SELECT interface_name, SUM(total_upload), SUM(total_download)
            FROM hourly_summary
            WHERE interface_name != '__all__'
            GROUP BY interface_name
        """)
        for row in c.fetchall():
            totals[row[0]] = [int(row[1] or 0), int(row[2] or 0)]

        # 2. Raw metrics totals
        c.execute("""
            SELECT interface_name, SUM(bytes_sent), SUM(bytes_recv)
            FROM interface_metrics
            GROUP BY interface_name
        """)
        for row in c.fetchall():
            iface = row[0]
            if iface not in totals:
                totals[iface] = [0, 0]
            totals[iface][0] += int(row[1] or 0)
            totals[iface][1] += int(row[2] or 0)

        return {k: (v[0], v[1]) for k, v in totals.items()}
    finally:
        conn.close()

def get_interface_hourly_usage(interface_name: str):
    """
    Returns a list of tuples: (hour_label, bytes_sent, bytes_recv)
    for a specific interface over the last 24 hours.
    """
    conn = _get_conn()
    try:
        c = conn.cursor()
        cutoff_time = int(time.time()) - 86400
        query = """
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp, 'unixepoch', 'localtime') as hour_bucket,
                SUM(bytes_sent),
                SUM(bytes_recv)
            FROM interface_metrics
            WHERE interface_name = ? AND timestamp >= ?
            GROUP BY hour_bucket
            ORDER BY hour_bucket ASC
        """
        c.execute(query, (interface_name, cutoff_time))
        return c.fetchall()
    finally:
        conn.close()

def prune_and_rollup_database(retention_days: int = 7):
    """
    Compress records older than `retention_days` into hourly summaries,
    then purge the granular second-by-second records from usage_log
    and interface_metrics.
    """
    if not os.path.exists(DB_FILE):
        return

    if retention_days < 1:
        retention_days = 1

    cutoff_time = int(time.time()) - (retention_days * 86400)

    conn = _get_conn()
    try:
        c = conn.cursor()

        # 1. Rollup usage_log older than cutoff_time into hourly_summary ('__all__')
        rollup_global_query = """
            INSERT INTO hourly_summary (
                timestamp,
                interface_name,
                total_upload,
                total_download,
                min_upload_speed,
                max_upload_speed,
                avg_upload_speed,
                min_download_speed,
                max_download_speed,
                avg_download_speed,
                sample_count
            )
            SELECT
                (timestamp / 3600) * 3600 AS hour_ts,
                '__all__' AS interface_name,
                SUM(upload_bytes) AS total_upload,
                SUM(download_bytes) AS total_download,
                MIN(upload_bytes) AS min_upload_speed,
                MAX(upload_bytes) AS max_upload_speed,
                AVG(upload_bytes) AS avg_upload_speed,
                MIN(download_bytes) AS min_download_speed,
                MAX(download_bytes) AS max_download_speed,
                AVG(download_bytes) AS avg_download_speed,
                COUNT(*) AS sample_count
            FROM usage_log
            WHERE timestamp < ?
            GROUP BY hour_ts
            ON CONFLICT(timestamp, interface_name) DO UPDATE SET
                total_upload = total_upload + excluded.total_upload,
                total_download = total_download + excluded.total_download,
                min_upload_speed = MIN(hourly_summary.min_upload_speed, excluded.min_upload_speed),
                max_upload_speed = MAX(hourly_summary.max_upload_speed, excluded.max_upload_speed),
                avg_upload_speed = (hourly_summary.avg_upload_speed * hourly_summary.sample_count + excluded.avg_upload_speed * excluded.sample_count) / (hourly_summary.sample_count + excluded.sample_count),
                min_download_speed = MIN(hourly_summary.min_download_speed, excluded.min_download_speed),
                max_download_speed = MAX(hourly_summary.max_download_speed, excluded.max_download_speed),
                avg_download_speed = (hourly_summary.avg_download_speed * hourly_summary.sample_count + excluded.avg_download_speed * excluded.sample_count) / (hourly_summary.sample_count + excluded.sample_count),
                sample_count = hourly_summary.sample_count + excluded.sample_count
        """
        c.execute(rollup_global_query, (cutoff_time,))

        # Delete purged usage_log records
        c.execute("DELETE FROM usage_log WHERE timestamp < ?", (cutoff_time,))

        # 2. Rollup interface_metrics older than cutoff_time into hourly_summary
        rollup_iface_query = """
            INSERT INTO hourly_summary (
                timestamp,
                interface_name,
                total_upload,
                total_download,
                min_upload_speed,
                max_upload_speed,
                avg_upload_speed,
                min_download_speed,
                max_download_speed,
                avg_download_speed,
                sample_count
            )
            SELECT
                (timestamp / 3600) * 3600 AS hour_ts,
                interface_name,
                SUM(bytes_sent) AS total_upload,
                SUM(bytes_recv) AS total_download,
                MIN(bytes_sent) AS min_upload_speed,
                MAX(bytes_sent) AS max_upload_speed,
                AVG(bytes_sent) AS avg_upload_speed,
                MIN(bytes_recv) AS min_download_speed,
                MAX(bytes_recv) AS max_download_speed,
                AVG(bytes_recv) AS avg_download_speed,
                COUNT(*) AS sample_count
            FROM interface_metrics
            WHERE timestamp < ?
            GROUP BY hour_ts, interface_name
            ON CONFLICT(timestamp, interface_name) DO UPDATE SET
                total_upload = total_upload + excluded.total_upload,
                total_download = total_download + excluded.total_download,
                min_upload_speed = MIN(hourly_summary.min_upload_speed, excluded.min_upload_speed),
                max_upload_speed = MAX(hourly_summary.max_upload_speed, excluded.max_upload_speed),
                avg_upload_speed = (hourly_summary.avg_upload_speed * hourly_summary.sample_count + excluded.avg_upload_speed * excluded.sample_count) / (hourly_summary.sample_count + excluded.sample_count),
                min_download_speed = MIN(hourly_summary.min_download_speed, excluded.min_download_speed),
                max_download_speed = MAX(hourly_summary.max_download_speed, excluded.max_download_speed),
                avg_download_speed = (hourly_summary.avg_download_speed * hourly_summary.sample_count + excluded.avg_download_speed * excluded.sample_count) / (hourly_summary.sample_count + excluded.sample_count),
                sample_count = hourly_summary.sample_count + excluded.sample_count
        """
        c.execute(rollup_iface_query, (cutoff_time,))

        # Delete purged interface_metrics records
        c.execute("DELETE FROM interface_metrics WHERE timestamp < ?", (cutoff_time,))

        conn.commit()
    finally:
        conn.close()

def checkpoint_wal(truncate: bool = False):
    """
    Trigger a WAL checkpoint to flush pages and keep -wal file size minimal.
    PASSIVE: Checkpoint non-blocking without waiting for readers/writers.
    TRUNCATE: Checkpoint all frames and truncate the WAL file to zero bytes.
    """
    if not os.path.exists(DB_FILE):
        return
    conn = _get_conn()
    try:
        mode = "TRUNCATE" if truncate else "PASSIVE"
        conn.execute(f"PRAGMA wal_checkpoint({mode});")
    except Exception:
        pass
    finally:
        conn.close()

def clear_history():
    """Wipe all historical data including rollups."""
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM usage_log")
        c.execute("DELETE FROM interface_metrics")
        c.execute("DELETE FROM hourly_summary")
        conn.commit()
    finally:
        conn.close()