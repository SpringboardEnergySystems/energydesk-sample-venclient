#!/usr/bin/env python3
"""Check database state and initialize if needed"""
import sqlite3

def main():
    conn = sqlite3.connect('config/resources.db')
    cursor = conn.cursor()

    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    result = []
    result.append(f"Tables: {tables}")

    if 'loads' in tables:
        cursor.execute('SELECT COUNT(*) FROM loads')
        count = cursor.fetchone()[0]
        result.append(f"Loads count: {count}")
    else:
        result.append("Loads table does NOT exist")

    cursor.execute('SELECT COUNT(*) FROM resources')
    count = cursor.fetchone()[0]
    result.append(f"Resources count: {count}")

    # Check if h5_meter_id column exists in resources
    cursor.execute("PRAGMA table_info(resources)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'h5_meter_id' in columns:
        cursor.execute('SELECT COUNT(*) FROM resources WHERE h5_meter_id IS NOT NULL')
        count = cursor.fetchone()[0]
        result.append(f"Resources with h5_meter_id: {count}")
    else:
        result.append("h5_meter_id column does NOT exist in resources table")

    conn.close()

    # Write to file and print
    output = '\n'.join(result)
    with open('/tmp/db_status.txt', 'w') as f:
        f.write(output)
    print(output)

if __name__ == '__main__':
    main()
