import sqlite3
import datetime
import hashlib

class ULMDatabase:
    def __init__(self, db_path):
        self.db_path = db_path

    def initialize_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        source TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        topics TEXT
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        role TEXT,
                        content TEXT,
                        created_at TEXT,
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS facts (
                        fact_id TEXT PRIMARY KEY,
                        fact TEXT,
                        category TEXT,
                        confidence REAL,
                        first_seen TEXT,
                        last_seen TEXT
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS preferences (
                        pref_key TEXT PRIMARY KEY,
                        pref_value TEXT,
                        updated_at TEXT
                    );
                """)
                conn.commit()
            print("[+] ULM SQLite Database successfully initialized.")
        except sqlite3.Error as e:
            print(f"[-] Error initializing database: {e}")

    def upsert_session(self, session_id, source, topics):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT created_at FROM sessions WHERE session_id = ?", (session_id,))
                row = c.fetchone()
                created_at = row[0] if row else now
                
                c.execute("""
                    INSERT OR REPLACE INTO sessions (session_id, source, created_at, updated_at, topics)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, source, created_at, now, topics))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] Error upserting session: {e}")







    def generate_message_id(self, session_id, role, content, created_at=None):
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Generate a stable, deterministic message ID by hashing the session ID + role + content + timestamp
        message_id = hashlib.sha256(f"{session_id}{role}{content}{created_at}".encode('utf-8')).hexdigest()[:16]
        return message_id
    def insert_message(self, session_id, role, content, created_at=None):
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message_id = self.generate_message_id(session_id, role, content, created_at)
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT OR IGNORE INTO messages (message_id, session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (message_id, session_id, role, content, created_at))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] Error inserting message: {e}")

    def upsert_fact(self, fact, category, confidence):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fact_id = hashlib.sha256(fact.strip().lower().encode('utf-8')).hexdigest()[:16]
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT first_seen FROM facts WHERE fact_id = ?", (fact_id,))
                row = c.fetchone()
                first_seen = row[0] if row else now
                
                c.execute("""
                    INSERT OR REPLACE INTO facts (fact_id, fact, category, confidence, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (fact_id, fact, category, confidence, first_seen, now))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] Error upserting fact: {e}")

    def set_preference(self, key, value):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, value, now))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] Error setting preference: {e}")

    def get_recent_context(self, limit=5):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT sessions.session_id, messages.role, messages.content, messages.created_at
                    FROM messages
                    JOIN sessions ON sessions.session_id = messages.session_id
                    ORDER BY messages.created_at DESC
                    LIMIT ?
                """, (limit,))
                results = c.fetchall()
                return results
        except sqlite3.Error as e:
            print(f"[-] Error retrieving recent context: {e}")
            return []
