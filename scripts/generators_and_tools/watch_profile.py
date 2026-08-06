import os
import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime

# Enforce UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def get_db_path():
    from core.engine import ULMEngine
    engine = ULMEngine()
    return str(Path(engine.target_yaml).with_suffix(".db"))

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    db_path = get_db_path()
    print(f"[*] Starting live terminal feed for database: {db_path}")
    
    # Store known metric IDs to only print new ones
    known_metrics = set()
    last_count = 0
    
    try:
        while True:
            if not os.path.exists(db_path):
                time.sleep(2)
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                # Fetch recent metrics
                c.execute("""
                    SELECT metric_id, category, name, description, confidence, frequency, last_seen 
                    FROM developer_profile 
                    ORDER BY last_seen DESC LIMIT 30
                """)
                rows = c.fetchall()
                conn.close()
                
                # Detect updates
                new_entries = []
                for r in rows:
                    m_id = r['metric_id']
                    if m_id not in known_metrics:
                        known_metrics.add(m_id)
                        new_entries.append(r)
                
                # Print new entries chronologically (oldest of the new first)
                if new_entries:
                    new_entries.reverse()
                    for r in new_entries:
                        last_seen_clean = r['last_seen'].split(".")[0].replace("T", " ") if r['last_seen'] else "N/A"
                        category_color = "\033[91m" if r['category'] == 'weakness' else (
                            "\033[92m" if r['category'] == 'strength' else (
                                "\033[95m" if r['category'] == 'milestone' else (
                                    "\033[96m" if r['category'] == 'vision' else (
                                        "\033[93m" if r['category'] == 'dynamic' else "\033[94m"
                                    )
                                )
                            )
                        )
                        reset_color = "\033[0m"
                        
                        print(f"[{last_seen_clean}] {category_color}[{r['category'].upper()}]{reset_color} "
                              f"\033[1m{r['name']}\033[0m (Conf: {r['confidence']*100:.1f}%, Freq: {r['frequency']})")
                        print(f"  └─ {r['description']}\n")
                        sys.stdout.flush()
                        
            except sqlite3.Error as e:
                # Silently wait if database is temporarily locked during a sync write
                pass
                
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n[*] Exiting live terminal feed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
