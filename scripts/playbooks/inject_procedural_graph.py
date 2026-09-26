import sqlite3
import os
import sys
import datetime
import argparse
from pathlib import Path

# Target active ULM memory core
DEFAULT_DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

def forge_procedural_graph(db_path=DEFAULT_DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Node Table: The "Procedures"
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS procedures (
        node_id TEXT PRIMARY KEY,
        action_name TEXT NOT NULL,
        target_script_path TEXT,
        expected_outcome TEXT,
        last_execution_status TEXT,
        updated_at TEXT
    )
    ''')

    # Edge Table: The "Relations" (Connecting the Triplets)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS procedural_relations (
        edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_node_id TEXT NOT NULL,
        relation_type TEXT NOT NULL, -- e.g., "ON_SUCCESS_TRIGGER", "ON_FAILURE_FALLBACK"
        target_node_id TEXT NOT NULL,
        condition_logic TEXT, -- Raw Python or logic string to evaluate
        FOREIGN KEY (source_node_id) REFERENCES procedures(node_id),
        FOREIGN KEY (target_node_id) REFERENCES procedures(node_id)
    )
    ''')

    # Secondary indexes for instantaneous traversal
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_procedural_relations_source ON procedural_relations(source_node_id)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_procedural_relations_target ON procedural_relations(target_node_id)
    ''')

    # Ensure schema_version reflects migration
    cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_ver = row[0] if row and row[0] is not None else 10
    if current_ver < 11:
        cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (11)")

    conn.commit()
    conn.close()
    
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] [+] Procedural Graph schema successfully injected into ULM Cortex: {db_path}")
    print("[+] Triplet relational mapping is now online.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forge Procedural Graph schema into ULM Cortex")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database")
    args = parser.parse_args()
    forge_procedural_graph(args.db)
