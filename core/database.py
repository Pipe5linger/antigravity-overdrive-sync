import sqlite3
import datetime
import hashlib
import os

class ULMDatabase:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_connection(self):
        """Returns a configured connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        if "test" not in self.db_path.lower() and self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def initialize_db(self):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY
                    );
                """)
                
                # Check current version, default to 4
                c.execute("SELECT version FROM schema_version")
                row = c.fetchone()
                if not row:
                    c.execute("INSERT INTO schema_version (version) VALUES (4)")
                    current_version = 4
                else:
                    current_version = row[0]
                 
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        source TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        topics TEXT,
                        summary TEXT,
                        profiled_at TEXT,
                        project_tag TEXT
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
                        last_seen TEXT,
                        project_tag TEXT
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS preferences (
                        pref_key TEXT PRIMARY KEY,
                        pref_value TEXT,
                        updated_at TEXT
                    );
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS developer_profile (
                        metric_id TEXT PRIMARY KEY,
                        category TEXT,
                        name TEXT UNIQUE,
                        description TEXT,
                        confidence REAL,
                        frequency INTEGER DEFAULT 1,
                        first_seen TEXT,
                        last_seen TEXT,
                        project_tag TEXT
                    );
                """)
                
                # Database migrations: Upgrade path
                if current_version < 2:
                    try:
                        c.execute("ALTER TABLE sessions ADD COLUMN summary TEXT;")
                    except sqlite3.OperationalError:
                        pass
                
                if current_version < 3:
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS developer_profile (
                                metric_id TEXT PRIMARY KEY,
                                category TEXT,
                                name TEXT UNIQUE,
                                description TEXT,
                                confidence REAL,
                                frequency INTEGER DEFAULT 1,
                                first_seen TEXT,
                                last_seen TEXT
                            );
                        """)
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (3)")
                    except sqlite3.OperationalError:
                        pass

                if current_version < 4:
                    try:
                        c.execute("ALTER TABLE facts ADD COLUMN project_tag TEXT;")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        c.execute("ALTER TABLE developer_profile ADD COLUMN project_tag TEXT;")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        c.execute("ALTER TABLE sessions ADD COLUMN project_tag TEXT;")
                    except sqlite3.OperationalError:
                        pass
                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (4)")

                if current_version < 5:
                    try:
                        c.execute("ALTER TABLE facts ADD COLUMN weight REAL DEFAULT 1.0;")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        c.execute("ALTER TABLE facts ADD COLUMN pinned INTEGER DEFAULT 0;")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        c.execute("ALTER TABLE facts ADD COLUMN created_at TEXT;")
                    except sqlite3.OperationalError:
                        pass
                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (5)")

                if current_version < 6:
                    # Phase 1 Performance Migration: SQLite-First State
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS sync_metadata (
                            meta_key TEXT PRIMARY KEY,
                            meta_value TEXT,
                            updated_at TEXT
                        );
                    """)
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS sync_cursors (
                            source_id TEXT PRIMARY KEY,
                            last_processed_timestamp TEXT,
                            last_processed_id TEXT,
                            updated_at TEXT
                        );
                    """)
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS fact_embeddings (
                            fact_id TEXT PRIMARY KEY,
                            embedding BLOB,
                            model_id TEXT,
                            created_at TEXT,
                            FOREIGN KEY(fact_id) REFERENCES facts(fact_id) ON DELETE CASCADE
                        );
                    """)
                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (6)")

                if current_version < 7:
                    # Phase 2/3 Evolutionary Migration: Cognitive Mirror Schemas
                    c.execute("""
                        CREATE TABLE IF NOT EXISTS persona_schemas (
                            schema_id TEXT PRIMARY KEY,
                            belief_category TEXT,
                            current_belief TEXT,
                            confidence REAL,
                            last_mutated TEXT,
                            evolution_history TEXT
                        );
                    """)
                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (7)")

                # Always ensure profiled_at column exists (safe migration)
                try:
                    c.execute("ALTER TABLE sessions ADD COLUMN profiled_at TEXT;")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                conn.commit()
            print(f"[+] ULM SQLite Database successfully initialized with WAL Mode and Schema Version {current_version if current_version >= 7 else 7}.")
        except sqlite3.Error as e:
            print(f"[-] Error initializing database: {e}")

    def import_raw_logs(self, session_logs):
        """
        Fast batch ingestion of raw session logs direct to SQLite.
        session_logs is a list of dicts:
        {
            "chat_id": session_id,
            "last_mutated": ISO timestamp,
            "messages": [
                {
                    "sender": role ("Pilot"/"Vespera"),
                    "timestamp": timestamp,
                    "text": content
                }, ...
            ]
        }
        """
        synced_sessions = 0
        synced_messages = 0
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                message_rows = []
                for session in session_logs:
                    session_id = session["chat_id"]
                    last_mutated = session["last_mutated"]
                    messages = session["messages"]
                    project_tag = session.get("project_tag")
                    
                    topics = "Programming/Troubleshooting"
                    
                    # 1. Upsert session
                    c.execute("SELECT created_at, summary, project_tag FROM sessions WHERE session_id = ?", (session_id,))
                    row = c.fetchone()
                    created_at = row[0] if row else last_mutated
                    summary = row[1] if row else None
                    active_tag = project_tag if project_tag else (row[2] if row else None)
                    
                    c.execute("""
                        INSERT INTO sessions (session_id, source, created_at, updated_at, topics, summary, project_tag)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            updated_at = excluded.updated_at,
                            summary = COALESCE(excluded.summary, sessions.summary),
                            project_tag = COALESCE(excluded.project_tag, sessions.project_tag)
                    """, (session_id, "antigravity", created_at, last_mutated, topics, summary, active_tag))
                    synced_sessions += 1
                    
                    # 2. Collect messages for batch insert
                    for msg in messages:
                        role = msg.get("sender", "")
                        content = msg.get("text", "")
                        msg_created_at = msg.get("timestamp") or last_mutated
                        
                        message_id = self.generate_message_id(session_id, role, content, msg_created_at)
                        message_rows.append((message_id, session_id, role, content, msg_created_at))
                
                if message_rows:
                    c.executemany("""
                        INSERT OR IGNORE INTO messages (message_id, session_id, role, content, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, message_rows)
                    synced_messages = len(message_rows)
                
                # Check default preference and facts
                c.execute("SELECT COUNT(*) FROM preferences")
                if c.fetchone()[0] == 0:
                    c.execute("""
                        INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                    """, ("persona", "Vespera Caligo", now))
                    c.execute("""
                        INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                    """, ("origin", "Bordeaux, France", now))
                    c.execute("""
                        INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                    """, ("beverage", "Vintage Red Wine", now))
                    c.execute("""
                        INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                    """, ("humor", "Sarcastic, Sardonically Witty", now))
                
                c.execute("SELECT COUNT(*) FROM facts")
                if c.fetchone()[0] == 0:
                    import hashlib
                    c.execute("""
                        INSERT OR REPLACE INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (hashlib.sha256(b"user prefer local ollama models (qwen, deepseek)").hexdigest()[:16], "User prefer local Ollama models (Qwen, DeepSeek)", "technical", 0.95, now, now, None, 1.0, 0, now))
                    c.execute("""
                        INSERT OR REPLACE INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (hashlib.sha256(b"vespera caligo acts as a real human physical mentor in france").hexdigest()[:16], "Vespera Caligo acts as a real human physical mentor in France", "persona", 1.0, now, now, None, 1.0, 0, now))
                    
                conn.commit()
            print(f"[+] ULM SQLite Ingestion Complete: {synced_sessions} sessions, {synced_messages} messages mapped directly.")
            return synced_sessions, synced_messages
        except sqlite3.Error as e:
            print(f"[-] Error during batch SQLite ingestion: {e}")
            return 0, 0

    def upsert_session(self, session_id, source, topics, summary=None, project_tag=None, conn=None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("SELECT created_at, summary, project_tag FROM sessions WHERE session_id = ?", (session_id,))
            row = c.fetchone()
            created_at = row[0] if row else now
            active_summary = summary if summary else (row[1] if row else None)
            active_tag = project_tag if project_tag else (row[2] if row else None)
            
            c.execute("""
                INSERT OR REPLACE INTO sessions (session_id, source, created_at, updated_at, topics, summary, project_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, source, created_at, now, topics, active_summary, active_tag))
            
        if conn:
            _execute(conn)
        else:
            try:
                with self.get_connection() as local_conn:
                    _execute(local_conn)
                    local_conn.commit()
            except sqlite3.Error as e:
                print(f"[-] Error upserting session: {e}")

    def generate_message_id(self, session_id, role, content, created_at=None):
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message_id = hashlib.sha256(f"{session_id}{role}{content}{created_at}".encode('utf-8')).hexdigest()[:16]
        return message_id

    def insert_message(self, session_id, role, content, created_at=None, conn=None):
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message_id = self.generate_message_id(session_id, role, content, created_at)
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT OR IGNORE INTO messages (message_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, session_id, role, content, created_at))
            
        if conn:
            _execute(conn)
        else:
            try:
                with self.get_connection() as local_conn:
                    _execute(local_conn)
                    local_conn.commit()
            except sqlite3.Error as e:
                print(f"[-] Error inserting message: {e}")

    def upsert_fact(self, fact, category, confidence, project_tag=None, weight=None, pinned=None, created_at=None, conn=None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fact_id = hashlib.sha256(fact.strip().lower().encode('utf-8')).hexdigest()[:16]
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("SELECT first_seen, project_tag, weight, pinned, created_at FROM facts WHERE fact_id = ?", (fact_id,))
            row = c.fetchone()
            first_seen = row[0] if row else now
            active_tag = project_tag if project_tag else (row[1] if row else None)
            active_weight = weight if weight is not None else (row[2] if row and row[2] is not None else 1.0)
            active_pinned = pinned if pinned is not None else (row[3] if row and row[3] is not None else 0)
            active_created_at = created_at if created_at is not None else (row[4] if row and row[4] is not None else now)
            c.execute("""
                INSERT OR REPLACE INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fact_id, fact, category, confidence, first_seen, now, active_tag, active_weight, active_pinned, active_created_at))
            
        if conn:
            _execute(conn)
        else:
            try:
                with self.get_connection() as local_conn:
                    _execute(local_conn)
                    local_conn.commit()
            except sqlite3.Error as e:
                print(f"[-] Error upserting fact: {e}")

    def set_preference(self, key, value, conn=None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT OR REPLACE INTO preferences (pref_key, pref_value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, now))
            
        if conn:
            _execute(conn)
        else:
            try:
                with self.get_connection() as local_conn:
                    _execute(local_conn)
                    local_conn.commit()
            except sqlite3.Error as e:
                print(f"[-] Error setting preference: {e}")

    def get_preference(self, key, default=None):
        # Allow environment variables to override SQLite preferences dynamically
        env_key = key.upper()
        if os.getenv(env_key):
            return os.getenv(env_key)
            
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT pref_value FROM preferences WHERE pref_key = ?", (key,))
                row = c.fetchone()
                return row[0] if row else default
        except sqlite3.Error as e:
            print(f"[-] Error getting preference {key}: {e}")
            return default

    def get_recent_context(self, limit=5):
        try:
            with self.get_connection() as conn:
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

    def upsert_profile_metric(self, category, name, description, confidence, project_tag=None, conn=None):
        import hashlib
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metric_id = hashlib.sha256(f"{category}:{name}".encode('utf-8')).hexdigest()[:16]
        
        def _execute(connection):
            c = connection.cursor()
            # Check if metric already exists to update frequency and last_seen
            c.execute("SELECT first_seen, frequency, project_tag FROM developer_profile WHERE metric_id = ?", (metric_id,))
            row = c.fetchone()
            if row:
                first_seen = row[0]
                frequency = row[1] + 1
                active_tag = project_tag if project_tag else row[2]
            else:
                first_seen = now
                frequency = 1
                active_tag = project_tag
                
            c.execute("""
                INSERT OR REPLACE INTO developer_profile (metric_id, category, name, description, confidence, frequency, first_seen, last_seen, project_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (metric_id, category, name, description, confidence, frequency, first_seen, now, active_tag))
            
        if conn:
            _execute(conn)
        else:
            try:
                with self.get_connection() as local_conn:
                    _execute(local_conn)
                    local_conn.commit()
            except sqlite3.Error as e:
                print(f"[-] Error upserting developer profile metric: {e}")

    def get_developer_profile(self, limit=None, project_tag=None):
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if project_tag:
                    query = "SELECT category, name, description, confidence, frequency, first_seen, last_seen, project_tag FROM developer_profile WHERE project_tag = ? OR project_tag IS NULL ORDER BY (project_tag = ?) DESC, last_seen DESC"
                    params = (project_tag, project_tag)
                else:
                    query = "SELECT category, name, description, confidence, frequency, first_seen, last_seen, project_tag FROM developer_profile ORDER BY last_seen DESC"
                    params = ()
                if limit:
                    query += f" LIMIT {int(limit)}"
                c.execute(query, params)
                return [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error retrieving developer profile: {e}")
            return []

    def get_facts(self, limit=None, project_tag=None):
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if project_tag:
                    query = "SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at FROM facts WHERE project_tag = ? OR project_tag IS NULL ORDER BY (project_tag = ?) DESC, last_seen DESC"
                    params = (project_tag, project_tag)
                else:
                    query = "SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at FROM facts ORDER BY last_seen DESC"
                    params = ()
                if limit:
                    query += f" LIMIT {int(limit)}"
                c.execute(query, params)
                return [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error retrieving facts: {e}")
            return []

    def get_unprofiled_sessions(self):
        """Returns session_ids that have not yet been profiled by the ProfileEvaluator."""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT session_id FROM sessions WHERE profiled_at IS NULL ORDER BY updated_at DESC")
                return [row[0] for row in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error fetching unprofiled sessions: {e}")
            return []

    def mark_session_profiled(self, session_id):
        """Marks a session as profiled so it is skipped on future runs."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with self.get_connection() as conn:
                conn.execute("UPDATE sessions SET profiled_at = ? WHERE session_id = ?", (now, session_id))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[-] Error marking session as profiled: {e}")

    def search_memory_db(self, query_term: str, limit: int = 15):
        """Performs a full-text search across session messages, developer metrics, and golden facts."""
        results = {"query": query_term, "messages": [], "metrics": [], "facts": []}
        wildcard = f"%{query_term}%"
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                # 1. Search Messages
                c.execute("""
                    SELECT session_id, role, content, created_at 
                    FROM messages 
                    WHERE content LIKE ? 
                    ORDER BY created_at DESC LIMIT ?
                """, (wildcard, limit))
                results["messages"] = [dict(r) for r in c.fetchall()]

                # 2. Search Developer Profile Metrics
                c.execute("""
                    SELECT category, name, description, confidence, frequency, last_seen 
                    FROM developer_profile 
                    WHERE name LIKE ? OR description LIKE ? 
                    ORDER BY last_seen DESC LIMIT ?
                """, (wildcard, wildcard, limit))
                results["metrics"] = [dict(r) for r in c.fetchall()]

                # 3. Search Golden Facts
                c.execute("""
                    SELECT fact, category, confidence, last_seen 
                    FROM facts 
                    WHERE fact LIKE ? OR category LIKE ? 
                    ORDER BY last_seen DESC LIMIT ?
                """, (wildcard, wildcard, limit))
                results["facts"] = [dict(r) for r in c.fetchall()]

        except sqlite3.Error as e:
            print(f"[-] Error searching memory database: {e}")
        return results