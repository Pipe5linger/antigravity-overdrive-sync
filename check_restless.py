import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db')
c = conn.cursor()

# Check A Restless Interaction.json in full
c.execute("SELECT role, content FROM messages WHERE session_id = 'A Restless Interaction.json' ORDER BY rowid ASC")
rows = c.fetchall()
print(f"A Restless Interaction.json has {len(rows)} messages")
for role, text in rows:
    if any(w in text.lower() for w in ['script', 'taboo', 'failure', 'error', 'ulm', 'pipeline', 'custom node']):
        print(f"[{role}]: {text[:400].strip()}\n")

conn.close()

