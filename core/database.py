import sqlite3
import datetime
import hashlib
import os
import time
import random
import threading
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "sync_state.db"

def get_canonical_db_path() -> Path:
    """Returns canonical absolute Path to the ULM SQLite database."""
    return DEFAULT_DB_PATH

class ULMDatabase:
    def __init__(self, db_path=None):
        self.db_path = str(db_path) if db_path else str(DEFAULT_DB_PATH)
        self._local = threading.local()

    def get_connection(self):
        """Returns a thread-local configured connection to the SQLite database."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=5.0)
            if self.db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return conn

    def close(self):
        """Closes the current thread's connection if active."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    def close_connection(self):
        """Alias for close()."""
        self.close()

    @staticmethod
    def make_fact_id(text: str) -> str:
        """Standardized fact ID hashing across the ecosystem (normalized lowercase stripped)."""
        return hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()[:16]

    def _run_transaction(self, fn, retries=5, initial_backoff=0.05):
        """Runs a write transaction on a thread-local connection with exponential backoff on lock contention and rollback on error."""
        last_err = None
        for attempt in range(retries):
            local_conn = self.get_connection()
            try:
                res = fn(local_conn)
                local_conn.commit()
                return res
            except sqlite3.OperationalError as oe:
                last_err = oe
                try:
                    local_conn.rollback()
                except Exception:
                    pass
                err_str = str(oe).lower()
                if "locked" in err_str or "busy" in err_str:
                    time.sleep(initial_backoff * (2 ** attempt) + random.uniform(0.01, 0.05))
                    continue
                raise
            except Exception:
                try:
                    local_conn.rollback()
                except Exception:
                    pass
                raise
        if last_err:
            raise last_err

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
                c.execute("SELECT MAX(version) FROM schema_version")
                row = c.fetchone()
                if not row or row[0] is None:
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
                        project_tag TEXT,
                        source_pointer TEXT
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

                if current_version < 8:
                    # Phase 3 Performance: Critical secondary indexes
                    index_statements = [
                        "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)",
                        "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",
                        "CREATE INDEX IF NOT EXISTS idx_sessions_profiled_at ON sessions(profiled_at)",
                        "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at)",
                        "CREATE INDEX IF NOT EXISTS idx_facts_project_tag ON facts(project_tag)",
                        "CREATE INDEX IF NOT EXISTS idx_facts_last_seen ON facts(last_seen)",
                        "CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)",
                        "CREATE INDEX IF NOT EXISTS idx_developer_profile_confidence ON developer_profile(confidence)",
                        "CREATE INDEX IF NOT EXISTS idx_fact_embeddings_fact_id ON fact_embeddings(fact_id)",
                    ]
                    for stmt in index_statements:
                        try:
                            c.execute(stmt)
                        except sqlite3.OperationalError:
                            pass
                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (8)")

                if current_version < 9:
                    # Phase 4 Performance: SQLite FTS5 Virtual Tables for Ultra-Fast Search
                    try:
                        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(session_id UNINDEXED, role UNINDEXED, content, created_at UNINDEXED)")
                        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(fact_id UNINDEXED, fact, category, project_tag)")
                        
                        # Check if FTS is populated; if empty, sync from base tables
                        c.execute("SELECT COUNT(*) FROM messages_fts")
                        if c.fetchone()[0] == 0:
                            c.execute("INSERT INTO messages_fts (session_id, role, content, created_at) SELECT session_id, role, content, created_at FROM messages")
                        
                        c.execute("SELECT COUNT(*) FROM facts_fts")
                        if c.fetchone()[0] == 0:
                            c.execute("INSERT INTO facts_fts (fact_id, fact, category, project_tag) SELECT fact_id, fact, category, project_tag FROM facts WHERE fact_id IS NOT NULL")
                    except Exception as e:
                        print(f"[-] Warning creating FTS5 tables: {e}")

                    # Bootstrap Cognitive Mirror (persona_schemas) if persona_baseline.yaml exists
                    try:
                        c.execute("SELECT COUNT(*) FROM persona_schemas")
                        if c.fetchone()[0] == 0:
                            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            # Check for optional persona_baseline.yaml in project root or config/
                            baseline_yaml_path = Path(__file__).resolve().parent.parent / "persona_baseline.yaml"
                            if not baseline_yaml_path.exists():
                                baseline_yaml_path = Path(__file__).resolve().parent.parent / "config" / "persona_baseline.yaml"
                            
                            core_beliefs = []
                            if baseline_yaml_path.exists():
                                try:
                                    import yaml
                                    with open(baseline_yaml_path, "r", encoding="utf-8") as f:
                                        data = yaml.safe_load(f)
                                        if data and "core_beliefs" in data:
                                            for item in data["core_beliefs"]:
                                                core_beliefs.append((item.get("category", "core"), item.get("belief", ""), float(item.get("confidence", 1.0))))
                                except Exception as ye:
                                    print(f"[-] Warning loading persona_baseline.yaml: {ye}")

                            if core_beliefs:
                                for b_cat, b_text, b_conf in core_beliefs:
                                    s_id = hashlib.sha256(b_cat.encode('utf-8')).hexdigest()[:12]
                                    c.execute("""
                                        INSERT INTO persona_schemas (schema_id, belief_category, current_belief, confidence, last_mutated)
                                        VALUES (?, ?, ?, ?, ?)
                                        ON CONFLICT(schema_id) DO UPDATE SET
                                            current_belief = excluded.current_belief,
                                            confidence = excluded.confidence,
                                            last_mutated = excluded.last_mutated
                                    """, (s_id, b_cat, b_text, b_conf, now))
                                print(f"[+] Initialized Cognitive Mirror with {len(core_beliefs)} baseline persona schemas from yaml.")
                    except Exception as e:
                        print(f"[-] Error bootstrapping persona schemas: {e}")

                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (9)")

                if current_version < 10:
                    # Phase 5 Performance & Integrity: Real-Time FTS5 Triggers & Timestamp Backfill
                    try:
                        c.execute("UPDATE facts SET created_at = COALESCE(first_seen, last_seen, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')) WHERE created_at IS NULL")
                    except Exception as e:
                        print(f"[-] Warning backfilling facts created_at: {e}")

                    # Resync FTS5 virtual tables to eliminate historical drift
                    try:
                        c.execute("DELETE FROM messages_fts")
                        c.execute("INSERT INTO messages_fts (session_id, role, content, created_at) SELECT session_id, role, content, created_at FROM messages")
                        c.execute("DELETE FROM facts_fts")
                        c.execute("INSERT INTO facts_fts (fact_id, fact, category, project_tag) SELECT fact_id, fact, category, project_tag FROM facts WHERE fact_id IS NOT NULL")
                    except Exception as e:
                        print(f"[-] Warning resyncing FTS5 tables: {e}")

                    # Automatic synchronization triggers
                    triggers = [
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages
                        BEGIN
                            INSERT INTO messages_fts (session_id, role, content, created_at)
                            VALUES (new.session_id, new.role, new.content, new.created_at);
                        END;
                        """,
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages
                        BEGIN
                            DELETE FROM messages_fts WHERE session_id = old.session_id AND created_at = old.created_at AND content = old.content;
                        END;
                        """,
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_facts_ai AFTER INSERT ON facts
                        BEGIN
                            INSERT INTO facts_fts (fact_id, fact, category, project_tag)
                            VALUES (new.fact_id, new.fact, new.category, new.project_tag);
                        END;
                        """,
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_facts_ad AFTER DELETE ON facts
                        BEGIN
                            DELETE FROM facts_fts WHERE fact_id = old.fact_id;
                        END;
                        """,
                        """
                        CREATE TRIGGER IF NOT EXISTS trg_facts_au AFTER UPDATE ON facts
                        BEGIN
                            DELETE FROM facts_fts WHERE fact_id = old.fact_id;
                            INSERT INTO facts_fts (fact_id, fact, category, project_tag)
                            VALUES (new.fact_id, new.fact, new.category, new.project_tag);
                        END;
                        """
                    ]
                    for stmt in triggers:
                        try:
                            c.execute(stmt)
                        except Exception as e:
                            print(f"[-] Warning creating trigger: {e}")

                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (10)")

                if current_version < 11:
                    # Phase 6: Procedural Graphs & Triplet Relational Mapping
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS procedures (
                                node_id TEXT PRIMARY KEY,
                                action_name TEXT NOT NULL,
                                target_script_path TEXT,
                                expected_outcome TEXT,
                                last_execution_status TEXT,
                                updated_at TEXT
                            );
                        """)
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS procedural_relations (
                                edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                source_node_id TEXT NOT NULL,
                                relation_type TEXT NOT NULL,
                                target_node_id TEXT NOT NULL,
                                condition_logic TEXT,
                                FOREIGN KEY (source_node_id) REFERENCES procedures(node_id),
                                FOREIGN KEY (target_node_id) REFERENCES procedures(node_id)
                            );
                        """)
                        c.execute("CREATE INDEX IF NOT EXISTS idx_procedural_relations_source ON procedural_relations(source_node_id);")
                        c.execute("CREATE INDEX IF NOT EXISTS idx_procedural_relations_target ON procedural_relations(target_node_id);")
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (11)")
                    except Exception as e:
                        print(f"[-] Warning creating procedural graph tables: {e}")

                if current_version < 12:
                    # Phase 7: Graveyard Miner & Taboo Rules
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS tool_execution_logs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                chat_id TEXT,
                                command TEXT,
                                stderr TEXT,
                                exit_code INTEGER,
                                timestamp TEXT
                            );
                        """)
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS taboo_rules (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                failure_intent TEXT UNIQUE,
                                regex_pattern TEXT,
                                remediation TEXT,
                                hit_count INTEGER DEFAULT 1,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (12)")
                    except Exception as e:
                        print(f"[-] Warning creating v12 schema (Graveyard Miner): {e}")

                if current_version < 13:
                    # Phase 8: Autonomous Script Vault & Scratch Code Recall
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS script_vault (
                                script_id TEXT PRIMARY KEY,
                                script_name TEXT,
                                category TEXT,
                                docstring_summary TEXT,
                                code_content TEXT,
                                sha256_hash TEXT UNIQUE,
                                source_session TEXT,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                execution_count INTEGER DEFAULT 1
                            );
                        """)
                        c.execute("""
                            CREATE VIRTUAL TABLE IF NOT EXISTS script_vault_fts USING fts5(
                                script_id UNINDEXED,
                                script_name,
                                category,
                                docstring_summary,
                                code_content
                            );
                        """)
                        c.execute("""
                            CREATE TRIGGER IF NOT EXISTS trg_script_vault_ai AFTER INSERT ON script_vault BEGIN
                                INSERT INTO script_vault_fts(script_id, script_name, category, docstring_summary, code_content)
                                VALUES (new.script_id, new.script_name, new.category, new.docstring_summary, new.code_content);
                            END;
                        """)
                        c.execute("""
                            CREATE TRIGGER IF NOT EXISTS trg_script_vault_ad AFTER DELETE ON script_vault BEGIN
                                DELETE FROM script_vault_fts WHERE script_id = old.script_id;
                            END;
                        """)
                        c.execute("""
                            CREATE TRIGGER IF NOT EXISTS trg_script_vault_au AFTER UPDATE ON script_vault BEGIN
                                DELETE FROM script_vault_fts WHERE script_id = old.script_id;
                                INSERT INTO script_vault_fts(script_id, script_name, category, docstring_summary, code_content)
                                VALUES (new.script_id, new.script_name, new.category, new.docstring_summary, new.code_content);
                            END;
                        """)
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (13)")
                    except Exception as e:
                        print(f"[-] Warning creating v13 schema (Script Vault): {e}")

                # Ensure scope column exists on script_vault (GLOBAL vs RECIPE)
                try:
                    c.execute("ALTER TABLE script_vault ADD COLUMN scope TEXT DEFAULT 'GLOBAL';")
                except sqlite3.OperationalError:
                    pass

                # Always ensure profiled_at column exists (safe migration)
                try:
                    c.execute("ALTER TABLE sessions ADD COLUMN profiled_at TEXT;")
                except sqlite3.OperationalError:
                    pass  # Column already exists

                # Ensure source_pointer column exists on facts (safe migration)
                try:
                    c.execute("ALTER TABLE facts ADD COLUMN source_pointer TEXT;")
                except sqlite3.OperationalError:
                    pass

                if current_version < 14:
                    # Phase 9: Fact Soft-Archive, Pinned Fact Immunity & Provenance Security
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS facts_archive (
                                archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                fact_id TEXT,
                                fact TEXT,
                                category TEXT,
                                confidence REAL,
                                project_tag TEXT,
                                weight REAL,
                                pinned INTEGER,
                                reason TEXT,
                                archived_at TEXT
                            );
                        """)
                        c.execute("CREATE INDEX IF NOT EXISTS idx_facts_archive_fact_id ON facts_archive(fact_id);")

                        try:
                            c.execute("ALTER TABLE facts ADD COLUMN origin TEXT DEFAULT 'user';")
                        except sqlite3.OperationalError:
                            pass

                        c.execute("""
                            CREATE TABLE IF NOT EXISTS pending_taboo_rules (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                failure_intent TEXT UNIQUE,
                                regex_pattern TEXT,
                                remediation TEXT,
                                hit_count INTEGER DEFAULT 1,
                                status TEXT DEFAULT 'pending',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            );
                        """)
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (14)")
                    except Exception as e:
                        print(f"[-] Warning creating v14 schema (Facts Archive & Security): {e}")

                if current_version < 15:
                    # Phase 10: Strict Provenance Reset & Facts Archive Origin Tracking
                    try:
                        # 1. Reset all unpinned legacy facts from 'user' to 'unverified'
                        # Only explicitly pinned facts retain 'user' Golden Truth!
                        c.execute("""
                            UPDATE facts 
                            SET origin = 'unverified' 
                            WHERE (pinned IS NULL OR pinned = 0) AND (origin = 'user' OR origin IS NULL);
                        """)

                        # 2. Add origin column to facts_archive if missing
                        try:
                            c.execute("ALTER TABLE facts_archive ADD COLUMN origin TEXT;")
                        except sqlite3.OperationalError:
                            pass

                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (15)")
                    except Exception as e:
                        print(f"[-] Warning creating v15 schema (Provenance Reset): {e}")

                if current_version < 16:
                    # Phase 11: Comprehensive Retroactive Secret Scrubbing & Forensic Eradication
                    # Commit any prior pending migration operations before taking pre-migration backup
                    conn.commit()
                    # 1. Pre-migration backup
                    db_file = Path(self.db_path)
                    if db_file.exists() and self.db_path != ":memory:":
                        backup_path = db_file.with_suffix(f".pre_v16_backup_{int(time.time())}.db")
                        try:
                            b_conn = sqlite3.connect(str(backup_path))
                            conn.backup(b_conn)
                            b_conn.close()
                            print(f"[+] Created pre-migration v16 backup at {backup_path}")
                        except Exception as be:
                            print(f"[-] Pre-migration backup warning: {be}")

                    from core.utils import scrub_secrets

                    # 2. Scrub messages
                    c.execute("SELECT message_id, content FROM messages WHERE content IS NOT NULL")
                    msg_rows = c.fetchall()
                    msg_updates = []
                    for mid, content in msg_rows:
                        clean = scrub_secrets(content)
                        if clean != content:
                            msg_updates.append((clean, mid))
                    if msg_updates:
                        c.executemany("UPDATE messages SET content = ? WHERE message_id = ?", msg_updates)

                    # 3. Scrub tool_execution_logs
                    c.execute("SELECT id, command, stderr FROM tool_execution_logs")
                    log_rows = c.fetchall()
                    log_updates = []
                    for lid, cmd, stderr in log_rows:
                        clean_cmd = scrub_secrets(cmd) if cmd else cmd
                        clean_stderr = scrub_secrets(stderr) if stderr else stderr
                        if clean_cmd != cmd or clean_stderr != stderr:
                            log_updates.append((clean_cmd, clean_stderr, lid))
                    if log_updates:
                        c.executemany("UPDATE tool_execution_logs SET command = ?, stderr = ? WHERE id = ?", log_updates)

                    # 4. Scrub facts
                    c.execute("SELECT fact_id, fact FROM facts WHERE fact IS NOT NULL")
                    fact_rows = c.fetchall()
                    fact_updates = []
                    for fid, ftext in fact_rows:
                        clean = scrub_secrets(ftext)
                        if clean != ftext:
                            fact_updates.append((clean, fid))
                    if fact_updates:
                        c.executemany("UPDATE facts SET fact = ? WHERE fact_id = ?", fact_updates)

                    # 5. Scrub facts_archive
                    c.execute("SELECT archive_id, fact FROM facts_archive WHERE fact IS NOT NULL")
                    archive_rows = c.fetchall()
                    archive_updates = []
                    for aid, ftext in archive_rows:
                        clean = scrub_secrets(ftext)
                        if clean != ftext:
                            archive_updates.append((clean, aid))
                    if archive_updates:
                        c.executemany("UPDATE facts_archive SET fact = ? WHERE archive_id = ?", archive_updates)

                    # 6. Resync FTS tables
                    try:
                        c.execute("DELETE FROM messages_fts")
                        c.execute("INSERT INTO messages_fts (session_id, role, content, created_at) SELECT session_id, role, content, created_at FROM messages")
                        c.execute("DELETE FROM facts_fts")
                        c.execute("INSERT INTO facts_fts (fact_id, fact, category, project_tag) SELECT fact_id, fact, category, project_tag FROM facts WHERE fact_id IS NOT NULL")
                    except Exception as ftse:
                        print(f"[-] Warning resyncing FTS tables during v16 migration: {ftse}")

                    conn.commit()

                    # 7. Forensic zeroing of freed pages and WAL truncation
                    c.execute("PRAGMA secure_delete = ON;")
                    c.execute("VACUUM;")
                    if self.db_path != ":memory:":
                        c.execute("PRAGMA wal_checkpoint(TRUNCATE);")

                    c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (16)")

                if current_version < 17:
                    # Phase 12: Open Loops / Parked Thoughts Engine
                    try:
                        c.execute("""
                            CREATE TABLE IF NOT EXISTS parked_thoughts (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                thought TEXT NOT NULL,
                                context_project TEXT DEFAULT '',
                                status TEXT DEFAULT 'parked',
                                priority TEXT DEFAULT 'normal',
                                source_context TEXT DEFAULT '',
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                reminded_count INTEGER DEFAULT 0,
                                last_reminded_at TEXT,
                                resolved_at TEXT
                            );
                        """)
                        c.execute("CREATE INDEX IF NOT EXISTS idx_parked_thoughts_status ON parked_thoughts(status);")
                        c.execute("CREATE INDEX IF NOT EXISTS idx_parked_thoughts_proj ON parked_thoughts(context_project);")
                        c.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (17)")
                    except Exception as e:
                        print(f"[-] Warning creating v17 schema (Parked Thoughts): {e}")

                conn.commit()
                c.execute("SELECT MAX(version) FROM schema_version")
                final_version = c.fetchone()[0]

            print(f"[+] ULM SQLite Database successfully initialized with WAL Mode and Schema Version {final_version}.")
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
                    
                    # 2. Collect messages for batch insert with secrets scrubbed
                    from core.utils import scrub_secrets
                    for msg in messages:
                        role = msg.get("sender", "")
                        raw_content = msg.get("text", "")
                        msg_created_at = msg.get("timestamp") or last_mutated
                        
                        # Generate ID using raw content for zero deduplication discrepancies on re-sync
                        message_id = self.generate_message_id(session_id, role, raw_content, msg_created_at)
                        clean_content = scrub_secrets(raw_content)
                        message_rows.append((message_id, session_id, role, clean_content, msg_created_at))
                
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
                        INSERT INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value, updated_at = excluded.updated_at
                    """, ("llm_provider", "local_ollama", now))
                    c.execute("""
                        INSERT INTO preferences (pref_key, pref_value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(pref_key) DO UPDATE SET pref_value = excluded.pref_value, updated_at = excluded.updated_at
                    """, ("vector_model", "nomic-embed-text:latest", now))
                
                c.execute("SELECT COUNT(*) FROM facts")
                if c.fetchone()[0] == 0:
                    # Optional persona loader from persona_baseline.yaml if present
                    baseline_yaml_path = Path(__file__).resolve().parent.parent / "persona_baseline.yaml"
                    if not baseline_yaml_path.exists():
                        baseline_yaml_path = Path(__file__).resolve().parent.parent / "config" / "persona_baseline.yaml"
                    
                    seeded_facts = []
                    if baseline_yaml_path.exists():
                        try:
                            import yaml
                            with open(baseline_yaml_path, "r", encoding="utf-8") as f:
                                data = yaml.safe_load(f)
                                if data and "facts" in data:
                                    for item in data["facts"]:
                                        f_text = item.get("fact", "")
                                        f_cat = item.get("category", "General")
                                        f_conf = float(item.get("confidence", 1.0))
                                        seeded_facts.append((self.make_fact_id(f_text), f_text, f_cat, f_conf))
                        except Exception as ye:
                            print(f"[-] Warning loading facts from persona_baseline.yaml: {ye}")

                    for fid, f_text, f_cat, f_conf in seeded_facts:
                        c.execute("""
                            INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 0, ?)
                            ON CONFLICT(fact_id) DO NOTHING
                        """, (fid, f_text, f_cat, f_conf, now, now, None, now))
                    
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
            c.execute("""
                INSERT INTO sessions (session_id, source, created_at, updated_at, topics, summary, project_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    source = excluded.source,
                    updated_at = excluded.updated_at,
                    topics = excluded.topics,
                    summary = COALESCE(excluded.summary, sessions.summary),
                    project_tag = COALESCE(excluded.project_tag, sessions.project_tag)
            """, (session_id, source, now, now, topics, summary, project_tag))
            
        if conn:
            _execute(conn)
        else:
            self._run_transaction(_execute)

    def generate_message_id(self, session_id, role, content, created_at=None):
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message_id = hashlib.sha256(f"{session_id}{role}{content}{created_at}".encode('utf-8')).hexdigest()[:16]
        return message_id

    def insert_message(self, session_id, role, content, created_at=None, conn=None):
        from core.utils import scrub_secrets
        clean_content = scrub_secrets(content)
        if not created_at:
            created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        message_id = self.generate_message_id(session_id, role, clean_content, created_at)
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT OR IGNORE INTO messages (message_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, session_id, role, clean_content, created_at))
            
        if conn:
            _execute(conn)
        else:
            self._run_transaction(_execute)

    def upsert_fact(self, fact, category, confidence, project_tag=None, weight=None, pinned=None, created_at=None, source_pointer=None, origin=None, conn=None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fact_id = self.make_fact_id(fact)
        assigned_origin = origin if origin else "unverified"
        
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, source_pointer, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    fact = excluded.fact,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    last_seen = excluded.last_seen,
                    project_tag = COALESCE(excluded.project_tag, facts.project_tag),
                    weight = COALESCE(excluded.weight, facts.weight),
                    pinned = CASE WHEN facts.pinned = 1 AND (excluded.pinned IS NULL OR excluded.pinned = 0) THEN 1 ELSE COALESCE(excluded.pinned, facts.pinned) END,
                    source_pointer = COALESCE(excluded.source_pointer, facts.source_pointer),
                    origin = CASE 
                        WHEN facts.origin = 'user' THEN 'user' 
                        WHEN facts.origin = 'agent_pending' THEN facts.origin 
                        ELSE COALESCE(excluded.origin, facts.origin, 'unverified') 
                    END
            """, (
                fact_id, 
                fact, 
                category, 
                confidence, 
                now, 
                now, 
                project_tag, 
                weight if weight is not None else 1.0, 
                pinned if pinned is not None else 0, 
                created_at or now, 
                source_pointer,
                assigned_origin
            ))
            
        if conn:
            _execute(conn)
        else:
            self._run_transaction(_execute)

    def upsert_consolidated_fact(self, fact_id, fact, category, confidence, created_at, project_tag, origin, conn=None):
        """Upserts a synthesized Golden Truth from consolidator, strictly preserving user and agent_pending origin."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 0, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    fact = excluded.fact,
                    category = excluded.category,
                    confidence = excluded.confidence,
                    last_seen = excluded.last_seen,
                    project_tag = COALESCE(excluded.project_tag, facts.project_tag),
                    weight = excluded.weight,
                    pinned = facts.pinned,
                    origin = CASE 
                        WHEN facts.origin = 'user' THEN 'user'
                        WHEN facts.origin = 'agent_pending' THEN 'agent_pending'
                        WHEN excluded.origin = 'agent_pending' THEN 'agent_pending'
                        ELSE facts.origin
                    END
            """, (fact_id, fact, category, confidence, created_at or now, now, project_tag, created_at or now, origin))
            return c.rowcount
        if conn:
            return _execute(conn)
        else:
            return self._run_transaction(_execute)

    def prune_expired_pending_facts(self, ttl_hours=168, conn=None) -> int:
        """Archives and removes unreviewed agent_pending facts older than ttl_hours (default: 7 days)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = (now - datetime.timedelta(hours=ttl_hours)).isoformat()
        now_str = now.isoformat()
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT INTO facts_archive (fact_id, fact, category, confidence, project_tag, weight, pinned, reason, archived_at, origin)
                SELECT fact_id, fact, category, confidence, project_tag, weight, pinned, 'pending_ttl_expired', ?, origin
                FROM facts
                WHERE origin = 'agent_pending' AND created_at < ? AND (pinned IS NULL OR pinned = 0)
            """, (now_str, cutoff))
            c.execute("""
                DELETE FROM facts
                WHERE origin = 'agent_pending' AND created_at < ? AND (pinned IS NULL OR pinned = 0)
            """, (cutoff,))
            return c.rowcount
        if conn:
            return _execute(conn)
        else:
            return self._run_transaction(_execute)

    def delete_fact(self, fact_id: str, conn=None) -> bool:
        """Deletes a fact from the active facts table if unpinned."""
        def _execute(connection):
            c = connection.cursor()
            c.execute("DELETE FROM facts WHERE fact_id = ? AND (pinned IS NULL OR pinned = 0)", (fact_id,))
            return c.rowcount > 0
        if conn:
            return _execute(conn)
        else:
            return self._run_transaction(_execute)

    def promote_fact(self, fact_id: str, conn=None) -> bool:
        """Promotes a quarantined or unverified fact to immutable user-approved Golden Truth (pinned=1, weight=2.0, origin='user')."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                UPDATE facts
                SET pinned = 1,
                    weight = 2.0,
                    origin = 'user',
                    last_seen = ?
                WHERE fact_id = ?
            """, (now, fact_id))
            return c.rowcount > 0
        if conn:
            return _execute(conn)
        else:
            return self._run_transaction(_execute)

    def restore_fact(self, archive_id: int, conn=None) -> bool:
        """Restores a soft-archived fact from facts_archive back into the active facts table, preserving its original provenance."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT OR IGNORE INTO facts (fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, origin)
                SELECT fact_id, fact, category, confidence, archived_at, ?, project_tag, COALESCE(weight, 1.0), 0, ?, COALESCE(origin, 'restored')
                FROM facts_archive
                WHERE archive_id = ?
            """, (now, now, archive_id))
            return c.rowcount > 0
        if conn:
            return _execute(conn)
        else:
            return self._run_transaction(_execute)

    def get_pending_facts(self, limit=50) -> list:
        """Returns all unapproved facts quarantined with origin='agent_pending'."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("""
                    SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, source_pointer, origin
                    FROM facts
                    WHERE origin = 'agent_pending'
                    ORDER BY last_seen DESC
                    LIMIT ?
                """, (int(limit),))
                return [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error retrieving pending facts: {e}")
            return []

    def archive_fact(self, fact_id: str, reason: str = "manual", conn=None):
        """Soft-archives a fact into facts_archive before deletion or pruning, preserving origin."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def _execute(connection):
            c = connection.cursor()
            c.execute("""
                INSERT INTO facts_archive (fact_id, fact, category, confidence, project_tag, weight, pinned, reason, archived_at, origin)
                SELECT fact_id, fact, category, confidence, project_tag, weight, pinned, ?, ?, origin
                FROM facts WHERE fact_id = ?
            """, (reason, now, fact_id))
        if conn:
            _execute(conn)
        else:
            self._run_transaction(_execute)

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
            self._run_transaction(_execute)

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

    def get_facts(self, limit=None, project_tag=None, exclude_pinned=False, exclude_pending=True):
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                filters = []
                params = []
                if exclude_pinned:
                    filters.append("(pinned IS NULL OR pinned = 0)")
                if exclude_pending:
                    filters.append("(origin != 'agent_pending' OR origin IS NULL)")
                
                if project_tag:
                    filters.append("(project_tag = ? OR project_tag IS NULL)")
                    params.append(project_tag)
                    where_clause = " WHERE " + " AND ".join(filters) if filters else ""
                    query = f"SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, source_pointer, origin FROM facts{where_clause} ORDER BY (project_tag = ?) DESC, last_seen DESC"
                    params.append(project_tag)
                else:
                    where_clause = " WHERE " + " AND ".join(filters) if filters else ""
                    query = f"SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag, weight, pinned, created_at, source_pointer, origin FROM facts{where_clause} ORDER BY last_seen DESC"
                
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
        """Performs a full-text search across session messages, developer metrics, and golden facts using FTS5 when available."""
        results = {"query": query_term, "messages": [], "metrics": [], "facts": []}
        wildcard = f"%{query_term}%"
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                # 1. Search Messages (Try FTS5 first for sub-millisecond BM25 ranking)
                try:
                    clean_fts_query = '"' + query_term.replace('"', '""') + '"'
                    c.execute("""
                        SELECT session_id, role, content, created_at 
                        FROM messages_fts 
                        WHERE messages_fts MATCH ? 
                        LIMIT ?
                    """, (clean_fts_query, limit))
                    results["messages"] = [dict(r) for r in c.fetchall()]
                except Exception:
                    # Fallback to standard LIKE scan
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

                # 3. Search Golden Facts (Try FTS5 first, strictly quarantine agent_pending)
                try:
                    clean_fts_query = '"' + query_term.replace('"', '""') + '"'
                    c.execute("""
                        SELECT f.fact, f.category, f.confidence, f.last_seen 
                        FROM facts_fts fts
                        JOIN facts f ON fts.fact_id = f.fact_id
                        WHERE facts_fts MATCH ? AND (f.origin != 'agent_pending' OR f.origin IS NULL)
                        LIMIT ?
                    """, (clean_fts_query, limit))
                    results["facts"] = [dict(r) for r in c.fetchall()]
                except Exception:
                    c.execute("""
                        SELECT fact, category, confidence, last_seen 
                        FROM facts 
                        WHERE (fact LIKE ? OR category LIKE ?) AND (origin != 'agent_pending' OR origin IS NULL)
                        ORDER BY last_seen DESC LIMIT ?
                    """, (wildcard, wildcard, limit))
                    results["facts"] = [dict(r) for r in c.fetchall()]

        except sqlite3.Error as e:
            print(f"[-] Error searching memory database: {e}")
        return results

    def semantic_recall(self, query_vector: list, limit: int = 5, min_similarity: float = 0.5, model_id: str = ""):
        """Retrieves the top-k most semantically relevant facts using cosine similarity against fact_embeddings."""
        import struct
        import math

        def cosine_sim(v1, v2):
            if len(v1) != len(v2):
                return 0.0
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if model_id:
                    c.execute("""
                        SELECT fe.fact_id, fe.embedding, f.fact, f.category, f.confidence, f.project_tag,
                               f.last_seen, f.pinned, f.weight, f.created_at, f.source_pointer
                        FROM fact_embeddings fe
                        JOIN facts f ON fe.fact_id = f.fact_id
                        WHERE fe.model_id = ? AND (f.origin != 'agent_pending' OR f.origin IS NULL)
                    """, (model_id,))
                else:
                    c.execute("""
                        SELECT fe.fact_id, fe.embedding, f.fact, f.category, f.confidence, f.project_tag,
                               f.last_seen, f.pinned, f.weight, f.created_at, f.source_pointer
                        FROM fact_embeddings fe
                        JOIN facts f ON fe.fact_id = f.fact_id
                        WHERE (f.origin != 'agent_pending' OR f.origin IS NULL)
                    """)
                rows = c.fetchall()
                
                scored = []
                for row in rows:
                    raw_blob = row["embedding"]
                    num_floats = len(raw_blob) // 4
                    vec = struct.unpack(f"{num_floats}f", raw_blob)
                    if len(query_vector) != len(vec):
                        continue
                    sim = cosine_sim(query_vector, vec)
                    if sim >= min_similarity:
                        scored.append({
                            "fact_id": row["fact_id"],
                            "fact": row["fact"],
                            "category": row["category"],
                            "confidence": row["confidence"],
                            "project_tag": row["project_tag"],
                            "last_seen": row["last_seen"],
                            "pinned": row["pinned"],
                            "weight": row["weight"],
                            "created_at": row["created_at"],
                            "source_pointer": row["source_pointer"],
                            "similarity": round(sim, 4)
                        })
                
                scored.sort(key=lambda x: x["similarity"], reverse=True)
                return scored[:limit]
        except Exception as e:
            print(f"[-] Error executing semantic recall: {e}")
            return []

    def cleanup_orphan_embeddings(self):
        """Removes embedding cache entries for facts that no longer exist."""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM fact_embeddings WHERE fact_id IS NULL OR fact_id = '' OR fact_id NOT IN (SELECT fact_id FROM facts WHERE fact_id IS NOT NULL AND fact_id != '')")
                deleted = c.rowcount
                conn.commit()
                if deleted > 0:
                    print(f"[+] Cleaned up {deleted} orphaned embedding cache entries.")
                return deleted
        except sqlite3.Error as e:
            print(f"[-] Error cleaning orphan embeddings: {e}")
            return 0

    # =========================================================================
    # Procedural Graph & Execution Triplet Interface
    # =========================================================================

    def add_procedure(self, node_id, action_name, target_script_path=None, expected_outcome=None, last_execution_status=None):
        """Adds or updates a procedure node in the procedural graph."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO procedures (node_id, action_name, target_script_path, expected_outcome, last_execution_status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        action_name = excluded.action_name,
                        target_script_path = COALESCE(excluded.target_script_path, procedures.target_script_path),
                        expected_outcome = COALESCE(excluded.expected_outcome, procedures.expected_outcome),
                        last_execution_status = COALESCE(excluded.last_execution_status, procedures.last_execution_status),
                        updated_at = excluded.updated_at
                """, (node_id, action_name, target_script_path, expected_outcome, last_execution_status, now))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"[-] Error adding procedure '{node_id}': {e}")
            return False

    def add_relation(self, source_node_id, relation_type, target_node_id, condition_logic=None):
        """Adds a relational edge between two procedure nodes if not already present."""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT edge_id FROM procedural_relations
                    WHERE source_node_id = ? AND relation_type = ? AND target_node_id = ?
                """, (source_node_id, relation_type, target_node_id))
                row = c.fetchone()
                if row:
                    return row[0]
                c.execute("""
                    INSERT INTO procedural_relations (source_node_id, relation_type, target_node_id, condition_logic)
                    VALUES (?, ?, ?, ?)
                """, (source_node_id, relation_type, target_node_id, condition_logic))
                conn.commit()
                return c.lastrowid
        except sqlite3.Error as e:
            print(f"[-] Error adding relation ({source_node_id} -[{relation_type}]-> {target_node_id}): {e}")
            return None

    def get_procedure(self, node_id):
        """Fetches a specific procedure node by ID."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM procedures WHERE node_id = ?", (node_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"[-] Error fetching procedure '{node_id}': {e}")
            return None

    def get_next_procedures(self, source_node_id, relation_type=None):
        """Retrieves adjacent target procedure nodes given a source node and optional relation filter."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if relation_type:
                    c.execute("""
                        SELECT p.*, r.edge_id, r.relation_type, r.condition_logic
                        FROM procedural_relations r
                        JOIN procedures p ON r.target_node_id = p.node_id
                        WHERE r.source_node_id = ? AND r.relation_type = ?
                    """, (source_node_id, relation_type))
                else:
                    c.execute("""
                        SELECT p.*, r.edge_id, r.relation_type, r.condition_logic
                        FROM procedural_relations r
                        JOIN procedures p ON r.target_node_id = p.node_id
                        WHERE r.source_node_id = ?
                    """, (source_node_id,))
                return [dict(row) for row in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error getting next procedures for '{source_node_id}': {e}")
            return []

    def update_procedure_status(self, node_id, status):
        """Updates the execution status of a procedure node."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("UPDATE procedures SET last_execution_status = ?, updated_at = ? WHERE node_id = ?", (status, now, node_id))
                conn.commit()
                return c.rowcount > 0
        except sqlite3.Error as e:
            print(f"[-] Error updating procedure status '{node_id}': {e}")
            return False

    def list_procedures(self, limit=100):
        """Lists procedures registered in the graph."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM procedures ORDER BY updated_at DESC LIMIT ?", (limit,))
                return [dict(row) for row in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error listing procedures: {e}")
            return []

    def list_relations(self, limit=100):
        """Lists procedural relational edges."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM procedural_relations ORDER BY edge_id DESC LIMIT ?", (limit,))
                return [dict(row) for row in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error listing relations: {e}")
            return []
    # =========================================================================
    # Taboo Matrix / Graveyard Miner Interface
    # =========================================================================

    def insert_tool_log(self, chat_id, command, stderr, exit_code, timestamp):
        """Inserts a tool execution log into the graveyard after scrubbing secrets."""
        try:
            from core.utils import scrub_secrets
            clean_command = scrub_secrets(command) if command else command
            clean_stderr = scrub_secrets(stderr) if stderr else stderr
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO tool_execution_logs (chat_id, command, stderr, exit_code, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (chat_id, clean_command, clean_stderr, exit_code, timestamp))
                conn.commit()
                return c.lastrowid
        except sqlite3.Error as e:
            print(f"[-] Error inserting tool log: {e}")
            return None

    def get_failed_tool_logs(self, limit=50):
        """Retrieves failed tool executions for distillation."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("""
                    SELECT * FROM tool_execution_logs 
                    WHERE exit_code != 0 OR (stderr IS NOT NULL AND stderr != '') 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                return [dict(row) for row in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error fetching failed tool logs: {e}")
            return []

    def deduplicate_persona_schemas(self):
        """
        Consolidates redundant persona schemas into canonical belief categories.
        Collapses near-duplicate schemas (e.g. slight phrasing variations of workspace/paths),
        preserving the highest-confidence, most detailed belief for each canonical category.
        """
        def canonical_category(cat: str) -> str:
            c_clean = cat.lower().replace('-', ' ').replace('_', ' ').strip()
            if any(k in c_clean for k in ['directory', 'workspace', 'storage', 'drive', 'tool', 'environment', 'setup', 'technology', 'system architecture', 'software configuration', 'file path', 'file location', 'project space', 'project structure', 'project path', 'project organization', 'caching']):
                return 'workspace_and_tooling'
            elif any(k in c_clean for k in ['ethos', 'engineering', 'pragmatic', 'principle', 'quality']):
                return 'engineering_ethos'
            elif any(k in c_clean for k in ['relationship', 'bond', 'pilot', 'persona', 'communication']):
                return 'relationship_bond'
            elif any(k in c_clean for k in ['image', 'synthesis', 'zit', 'flux', 'lora', 'render']):
                return 'image_synthesis'
            elif any(k in c_clean for k in ['hardware', 'gpu', 'vram', 'rtx', 'topology']):
                return 'hardware_and_topology'
            elif any(k in c_clean for k in ['profile', 'background', 'identity', 'user']):
                return 'personal_background'
            return c_clean.replace(' ', '_')

        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT schema_id, belief_category, current_belief, confidence, last_mutated, evolution_history FROM persona_schemas")
                rows = [dict(r) for r in c.fetchall()]
                if not rows:
                    return 0

                from collections import defaultdict
                grouped = defaultdict(list)
                for r in rows:
                    canon = canonical_category(r["belief_category"])
                    grouped[canon].append(r)

                total_pruned = 0
                for canon_cat, group in grouped.items():
                    if len(group) <= 1:
                        if group and group[0]["belief_category"] != canon_cat:
                            c.execute("UPDATE persona_schemas SET belief_category = ? WHERE schema_id = ?", (canon_cat, group[0]["schema_id"]))
                        continue

                    # Sort by confidence descending, then by length of belief text
                    group.sort(key=lambda x: (x.get("confidence") or 0.0, len(x.get("current_belief") or "")), reverse=True)
                    winner = group[0]
                    losers = group[1:]

                    c.execute("UPDATE persona_schemas SET belief_category = ? WHERE schema_id = ?", (canon_cat, winner["schema_id"]))

                    for loser in losers:
                        c.execute("DELETE FROM persona_schemas WHERE schema_id = ?", (loser["schema_id"],))
                        total_pruned += 1

                conn.commit()
                print(f"[+] Persona Schemas: Deduplicated {len(rows)} down to {len(grouped)} canonical schemas ({total_pruned} redundant schemas pruned).")
                return total_pruned
        except sqlite3.Error as e:
            print(f"[-] Error deduplicating persona schemas: {e}")
            return 0

    # =========================================================================
    # Script Vault & Scratch Code Recall
    # =========================================================================

    def upsert_script(self, script_name: str, code_content: str, docstring_summary: str = "", category: str = "utility", source_session: str = "", scope: str = "GLOBAL") -> dict:
        """
        Inserts or increments usage of a scratch script by SHA-256 hash.
        Scope is either 'GLOBAL' (workstation tool) or 'RECIPE' (target/file-bound recipe).
        Returns dict with status ('inserted' or 'incremented') and script_id.
        """
        import hashlib
        import uuid
        norm_code = code_content.strip()
        if not norm_code:
            return {"status": "error", "error": "empty_code"}

        sha = hashlib.sha256(norm_code.encode("utf-8")).hexdigest()
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT script_id, execution_count FROM script_vault WHERE sha256_hash = ?", (sha,))
                existing = c.fetchone()
                if existing:
                    s_id = existing[0]
                    c.execute("UPDATE script_vault SET execution_count = execution_count + 1, scope = ? WHERE script_id = ?", (scope, s_id))
                    conn.commit()
                    return {"status": "incremented", "script_id": s_id}
                else:
                    s_id = f"scr_{uuid.uuid4().hex[:12]}"
                    c.execute("""
                        INSERT INTO script_vault (script_id, script_name, category, docstring_summary, code_content, sha256_hash, source_session, created_at, execution_count, scope)
                        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 1, ?)
                    """, (s_id, script_name, category, docstring_summary, code_content, sha, source_session, scope))
                    conn.commit()
                    return {"status": "inserted", "script_id": s_id}
        except sqlite3.Error as e:
            print(f"[-] Error upserting script to vault: {e}")
            return {"status": "error", "error": str(e)}

    def search_scripts(self, query: str, limit: int = 5, category: str = "", scope: str = "") -> list:
        """Searches the Script Vault using FTS5 BM25 or LIKE fallback with optional scope filtering."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                # FTS5 search
                try:
                    clean_q = "".join([ch if ch.isalnum() or ch.isspace() else " " for ch in query]).strip()
                    words = [w for w in clean_q.split() if w]
                    if words:
                        fts_query = " OR ".join([f"{w}*" for w in words])
                        conditions = ["script_vault_fts MATCH ?"]
                        params = [fts_query]
                        if category:
                            conditions.append("v.category = ?")
                            params.append(category)
                        if scope:
                            conditions.append("v.scope = ?")
                            params.append(scope)
                        params.append(limit)
                        where_clause = " AND ".join(conditions)

                        c.execute(f"""
                            SELECT v.script_id, v.script_name, v.category, v.scope, v.docstring_summary, v.code_content, v.execution_count, v.source_session, v.created_at
                            FROM script_vault_fts f
                            JOIN script_vault v ON f.script_id = v.script_id
                            WHERE {where_clause}
                            ORDER BY bm25(script_vault_fts) ASC, v.execution_count DESC LIMIT ?
                        """, tuple(params))
                        rows = c.fetchall()
                        if rows:
                            return [dict(r) for r in rows]
                except sqlite3.OperationalError:
                    pass

                # Fallback to standard LIKE
                like_term = f"%{query}%"
                conditions = ["(script_name LIKE ? OR docstring_summary LIKE ? OR code_content LIKE ?)"]
                params = [like_term, like_term, like_term]
                if category:
                    conditions.append("category = ?")
                    params.append(category)
                if scope:
                    conditions.append("scope = ?")
                    params.append(scope)
                params.append(limit)
                where_clause = " AND ".join(conditions)

                c.execute(f"""
                    SELECT script_id, script_name, category, scope, docstring_summary, code_content, execution_count, source_session, created_at
                    FROM script_vault
                    WHERE {where_clause}
                    ORDER BY execution_count DESC LIMIT ?
                """, tuple(params))
                return [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error searching script vault: {e}")
            return []

    def get_script(self, script_id: str) -> dict | None:
        """Retrieves a single script from the vault by script_id."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM script_vault WHERE script_id = ?", (script_id,))
                row = c.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"[-] Error fetching script: {e}")
            return None




    # =========================================================================
    # OPEN LOOPS / PARKED THOUGHTS ENGINE
    # =========================================================================

    def park_thought(self, thought: str, context_project: str = "", priority: str = "normal", source_context: str = "") -> int:
        """Parks a casual thought, reminder, or open loop to revisit later."""
        def _tx(conn):
            c = conn.cursor()
            c.execute("""
                INSERT INTO parked_thoughts (thought, context_project, priority, source_context, created_at, status)
                VALUES (?, ?, ?, ?, datetime('now'), 'parked')
            """, (thought.strip(), context_project.strip(), priority.strip(), source_context.strip()))
            return c.lastrowid
        return self._run_transaction(_tx)

    def get_open_loops(self, context_project: str = "", status: str = "parked", limit: int = 10) -> list[dict]:
        """Retrieves pending parked thoughts / open loops, optionally filtered by project."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                query = "SELECT * FROM parked_thoughts WHERE status = ?"
                params = [status]
                if context_project:
                    query += " AND (context_project = ? OR context_project = '')"
                    params.append(context_project)
                query += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, created_at ASC LIMIT ?"
                params.append(limit)
                c.execute(query, tuple(params))
                return [dict(r) for r in c.fetchall()]
        except sqlite3.Error as e:
            print(f"[-] Error fetching open loops: {e}")
            return []

    def resolve_thought(self, thought_id: int, status: str = "resolved") -> bool:
        """Updates status of a parked thought ('resolved', 'dropped', 'parked')."""
        def _tx(conn):
            c = conn.cursor()
            c.execute("""
                UPDATE parked_thoughts 
                SET status = ?, resolved_at = datetime('now')
                WHERE id = ?
            """, (status, thought_id))
            return c.rowcount > 0
        return self._run_transaction(_tx)

    def touch_thought_reminder(self, thought_id: int) -> bool:
        """Increments reminded_count and updates last_reminded_at timestamp."""
        def _tx(conn):
            c = conn.cursor()
            c.execute("""
                UPDATE parked_thoughts 
                SET reminded_count = reminded_count + 1, last_reminded_at = datetime('now')
                WHERE id = ?
            """, (thought_id,))
            return c.rowcount > 0
        return self._run_transaction(_tx)

    # =========================================================================
    # ULM DIAGNOSTICS & INTEGRITY ENGINE
    # =========================================================================

    def run_diagnostics(self, deep: bool = False) -> dict:
        """Executes a comprehensive, strictly read-only diagnostics suite on the ULM SQLite database.
        
        Args:
            deep: If True, executes PRAGMA integrity_check instead of quick_check.
        """
        results = {
            "status": "HEALTHY",
            "db_path": str(self.db_path),
            "deep_mode": deep,
            "physical_health": {},
            "schema_integrity": {},
            "fts_integrity": {},
            "data_anomalies": {},
            "issues": []
        }
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # 1. Physical health & space allocation
                page_size = c.execute("PRAGMA page_size;").fetchone()[0]
                page_count = c.execute("PRAGMA page_count;").fetchone()[0]
                freelist_count = c.execute("PRAGMA freelist_count;").fetchone()[0]
                wal_mode = c.execute("PRAGMA journal_mode;").fetchone()[0]
                
                total_mb = (page_count * page_size) / (1024 * 1024)
                unused_mb = (freelist_count * page_size) / (1024 * 1024)
                fragmentation_pct = (unused_mb / total_mb * 100.0) if total_mb > 0 else 0.0
                
                check_cmd = "PRAGMA integrity_check;" if deep else "PRAGMA quick_check;"
                sqlite_check = [r[0] for r in c.execute(check_cmd).fetchall()]
                if sqlite_check != ["ok"]:
                    results["status"] = "CORRUPTED"
                    results["issues"].append(f"SQLite {check_cmd} reported: {sqlite_check}")
                
                results["physical_health"] = {
                    "total_size_mb": round(total_mb, 2),
                    "unused_space_mb": round(unused_mb, 2),
                    "fragmentation_pct": round(fragmentation_pct, 2),
                    "journal_mode": wal_mode,
                    "sqlite_check": "ok" if sqlite_check == ["ok"] else sqlite_check
                }
                
                # 2. Foreign key verification
                fk_violations = c.execute("PRAGMA foreign_key_check;").fetchall()
                results["schema_integrity"]["foreign_key_violations"] = len(fk_violations)
                if fk_violations:
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"{len(fk_violations)} foreign key constraint violation(s) found.")
                
                # 3. FTS5 Index Integrity Checks
                fts_tables = ["messages_fts", "facts_fts", "script_vault_fts"]
                fts_status = {}
                for fts in fts_tables:
                    try:
                        # Check table existence first
                        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (fts,)).fetchone()
                        if exists:
                            c.execute(f"INSERT INTO {fts}({fts}) VALUES('integrity-check');")
                            fts_status[fts] = "ok"
                        else:
                            fts_status[fts] = "missing"
                    except Exception as e:
                        fts_status[fts] = f"error: {str(e)}"
                        results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                        results["issues"].append(f"FTS index '{fts}' integrity check failed: {e}")
                results["fts_integrity"] = fts_status
                
                # 4. Data Anomaly & Orphan Detection
                orphaned_messages = c.execute("""
                    SELECT COUNT(*) FROM messages m 
                    LEFT JOIN sessions s ON m.session_id = s.session_id 
                    WHERE s.session_id IS NULL;
                """).fetchone()[0]
                
                orphaned_embeddings = c.execute("""
                    SELECT COUNT(*) FROM fact_embeddings fe 
                    LEFT JOIN facts f ON fe.fact_id = f.fact_id 
                    WHERE f.fact_id IS NULL;
                """).fetchone()[0]
                
                null_fact_hashes = c.execute("""
                    SELECT COUNT(*) FROM facts WHERE fact_id IS NULL OR fact_id = '';
                """).fetchone()[0]
                
                total_sessions = c.execute("SELECT COUNT(*) FROM sessions;").fetchone()[0]
                total_messages = c.execute("SELECT COUNT(*) FROM messages;").fetchone()[0]
                total_facts = c.execute("SELECT COUNT(*) FROM facts;").fetchone()[0]
                facts_fts_count = c.execute("SELECT COUNT(*) FROM facts_fts;").fetchone()[0]
                messages_fts_count = c.execute("SELECT COUNT(*) FROM messages_fts;").fetchone()[0]
                
                results["data_anomalies"] = {
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "total_facts": total_facts,
                    "orphaned_messages": orphaned_messages,
                    "orphaned_embeddings": orphaned_embeddings,
                    "null_fact_hashes": null_fact_hashes,
                    "facts_fts_drift": facts_fts_count - (total_facts - null_fact_hashes),
                    "messages_fts_drift": messages_fts_count - total_messages
                }
                
                if orphaned_messages > 0:
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"Found {orphaned_messages} messages with missing parent session.")
                if orphaned_embeddings > 0:
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"Found {orphaned_embeddings:,} orphaned embedding cache entries.")
                if null_fact_hashes > 0:
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"Found {null_fact_hashes} facts with empty fact_id hashes.")
                if facts_fts_count != (total_facts - null_fact_hashes):
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"FTS5 drift detected in facts_fts ({facts_fts_count} indexed vs {total_facts - null_fact_hashes} valid facts).")
                if messages_fts_count != total_messages:
                    results["status"] = "WARNING" if results["status"] != "CORRUPTED" else results["status"]
                    results["issues"].append(f"FTS5 drift detected in messages_fts ({messages_fts_count:,} indexed vs {total_messages:,} messages).")
                    
        except Exception as e:
            results["status"] = "CRITICAL_ERROR"
            results["issues"].append(f"Diagnostics runner encountered an unhandled error: {str(e)}")
            
        return results
if __name__ == "__main__":
    import sys
    if "--diagnose" in sys.argv:
        deep_flag = "--deep" in sys.argv
        db = ULMDatabase()
        diag = db.run_diagnostics(deep=deep_flag)
        import json
        print(json.dumps(diag, indent=2))
        sys.exit(0)