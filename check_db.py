#!/usr/bin/env python3
import sqlite3
import sys

db_path = 'config/resources.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables in database: {tables}", file=sys.stderr, flush=True)

    # Check if loads table exists
    if 'loads' in tables:
        cursor.execute("SELECT COUNT(*) FROM loads")
        count = cursor.fetchone()[0]
        print(f"Loads table exists with {count} records", file=sys.stderr, flush=True)
    else:
        print("Loads table does NOT exist", file=sys.stderr, flush=True)

    # Check resources
    cursor.execute("SELECT COUNT(*) FROM resources")
    count = cursor.fetchone()[0]
    print(f"Resources table has {count} records", file=sys.stderr, flush=True)

    conn.close()
    print("DONE", file=sys.stderr, flush=True)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
