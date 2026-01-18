#!/usr/bin/env python3
"""Migrate database to add h5_meter_id column to loads table"""
import sqlite3

db_path = '/Users/steinar/PycharmProjects/energydesk-sample-venclient/config/resources.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking current schema...")

# Check if loads table exists and has h5_meter_id column
cursor.execute("PRAGMA table_info(loads)")
columns = {row[1]: row for row in cursor.fetchall()}
print(f"Current loads table columns: {list(columns.keys())}")

if 'h5_meter_id' not in columns:
    print("\nDropping and recreating loads table with correct schema...")
    cursor.execute("DROP TABLE IF EXISTS loads")
    cursor.execute("""
        CREATE TABLE loads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            load_id TEXT UNIQUE NOT NULL,
            resource_id TEXT NOT NULL,
            load_component TEXT NOT NULL,
            load_name TEXT,
            h5_meter_id TEXT NOT NULL,
            vtn_resource_id TEXT,
            registration_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources(resource_id)
        )
    """)
    print("✓ Loads table recreated with h5_meter_id column")
else:
    print("✓ Loads table already has h5_meter_id column")

# Check resources table
cursor.execute("PRAGMA table_info(resources)")
columns = {row[1]: row for row in cursor.fetchall()}
print(f"\nCurrent resources table columns: {list(columns.keys())}")

if 'h5_meter_id' not in columns:
    print("\nAdding h5_meter_id column to resources table...")
    cursor.execute("ALTER TABLE resources ADD COLUMN h5_meter_id TEXT")
    print("✓ Added h5_meter_id column to resources table")
else:
    print("✓ Resources table already has h5_meter_id column")

# Create indexes
print("\nCreating indexes...")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_load_resource_id 
    ON loads(resource_id)
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_load_h5_meter_id 
    ON loads(h5_meter_id)
""")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_load_vtn_resource_id 
    ON loads(vtn_resource_id)
""")
print("✓ Indexes created")

conn.commit()
conn.close()

print("\n✓ Migration complete!")
