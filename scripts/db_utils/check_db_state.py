import sqlite3
import os
import sys
from pathlib import Path

# Add project root to path to load engine modules
sys.path.append(r"D:\AI\Projects\antigravity-overdrive-sync")

from core.database import ULMDatabase
from core.engine import ULMEngine

engine = ULMEngine()
db_path = str(Path(engine.target_yaml).with_suffix(".db"))

db = ULMDatabase(db_path)
db.initialize_db()

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("\n=== DEVELOPER PROGRESS PROFILE ===")
try:
    c.execute("SELECT category, name, description, confidence, frequency FROM developer_profile")
    rows = c.fetchall()
    if not rows:
        print("No developer profile metrics recorded yet.")
    for row in rows:
        conf = f"{row['confidence'] * 100:.1f}%" if row['confidence'] else "N/A"
        print(f"[{row['category'].upper()}] {row['name']} ({conf}, freq: {row['frequency']}): {row['description']}")
except Exception as e:
    print(f"Error querying developer_profile: {e}")

print("\n=== RECENT EXTRACTED FACTS ===")
try:
    c.execute("SELECT category, fact, confidence FROM facts LIMIT 10")
    rows = c.fetchall()
    if not rows:
        print("No facts recorded yet.")
    for row in rows:
        print(f"[{row['category']}] ({row['confidence']:.2f}): {row['fact']}")
except Exception as e:
    print(f"Error querying facts: {e}")

print("\n=== SYSTEM PREFERENCES ===")
try:
    c.execute("SELECT pref_key, pref_value FROM preferences")
    rows = c.fetchall()
    if not rows:
        print("No preferences recorded yet.")
    for row in rows:
        print(f"{row['pref_key']}: {row['pref_value']}")
except Exception as e:
    print(f"Error querying preferences: {e}")

conn.close()
