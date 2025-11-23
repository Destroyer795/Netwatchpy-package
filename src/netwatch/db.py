import sqlite3
import os
import json
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

def init_db():
    """Initialize the database table and migrate old data if found."""
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                upload_bytes INTEGER,
                download_bytes INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON usage_log (timestamp)")
        conn.commit()
    finally:
        conn.close()
    
    _migrate_legacy_json()

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
                ts = datetime.now().isoformat(sep=' ', timespec='seconds')
                c.execute(
                    "INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
                    (ts, old_up, old_down)
                )
                conn.commit()
            finally:
                conn.close()

        new_name = LEGACY_FILE + ".migrated" # Prevent re-migration
        os.rename(LEGACY_FILE, new_name)
        print(f"[netwatch] Migration successful. Renamed {LEGACY_FILE} to {new_name}")

    except Exception as e:
        print(f"[netwatch] Migration failed: {e}")

def log_traffic(up_delta: int, down_delta: int):
    """Log a slice of traffic usage."""
    if up_delta == 0 and down_delta == 0:
        return

    conn = _get_conn()
    try:
        c = conn.cursor()
        ts = datetime.now().isoformat(sep=' ', timespec='seconds')
        c.execute(
            "INSERT INTO usage_log (timestamp, upload_bytes, download_bytes) VALUES (?, ?, ?)",
            (ts, int(up_delta), int(down_delta))
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_historical_totals():
    """Calculate total upload/download from the entire history."""
    if not os.path.exists(DB_FILE):
        return 0, 0
    
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT SUM(upload_bytes), SUM(download_bytes) FROM usage_log")
        row = c.fetchone()
        if row and row[0] is not None:
            return int(row[0]), int(row[1])
        return 0, 0
    finally:
        conn.close()

def clear_history():
    """Remove all historical data."""
    conn = _get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM usage_log")
        conn.commit()
    finally:
        conn.close()