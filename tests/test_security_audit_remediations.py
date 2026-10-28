import pytest
import sqlite3
import os
import re
from pathlib import Path
from core.database import ULMDatabase, get_canonical_db_path
from core.consolidator import MemoryConsolidator
from scripts.generators_and_tools.taboo_extractor import sanitize_identifier

@pytest.fixture(autouse=True)
def isolate_test_web_server_db(tmp_path, monkeypatch):
    import web_server
    import core.mcp_server
    test_db = ULMDatabase(tmp_path / "test_web_server.db")
    test_db.initialize_db()
    monkeypatch.setattr(web_server, "db", test_db)
    monkeypatch.setattr(core.mcp_server, "get_db", lambda: test_db)
    yield test_db

def test_canonical_db_path():
    path = get_canonical_db_path()
    assert path.name == "sync_state.db"
    assert "db" in str(path)

def test_facts_archive_and_pinned_immunity(tmp_path):
    test_db_path = tmp_path / "test_security.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    # 1. Upsert a pinned fact
    db.upsert_fact(
        fact="The master architecture token is strictly confidential",
        category="Security",
        confidence=1.0,
        pinned=1,
        origin="user"
    )

    facts = db.get_facts()
    assert len(facts) == 1
    assert facts[0]["pinned"] == 1
    pinned_fid = facts[0]["fact_id"]

    # 2. Verify that upserting same fact with pinned=0 does NOT unpin it
    db.upsert_fact(
        fact="The master architecture token is strictly confidential",
        category="Security",
        confidence=1.0,
        pinned=0,
        origin="agent_pending"
    )
    facts_after = db.get_facts()
    assert facts_after[0]["pinned"] == 1, "Pinned facts must remain immutable against unpinning"

    # 3. Test soft-archiving
    db.archive_fact(pinned_fid, reason="test_archive")
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT fact_id, reason FROM facts_archive WHERE fact_id = ?", (pinned_fid,))
        archived_row = c.fetchone()
        assert archived_row is not None
        assert archived_row[0] == pinned_fid
        assert archived_row[1] == "test_archive"

def test_consolidator_excludes_pinned_facts(tmp_path):
    test_db_path = tmp_path / "test_consolidator.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    # Add 1 pinned fact and 2 unpinned facts
    db.upsert_fact("Pinned Fact 1", "Tech", 1.0, pinned=1)
    db.upsert_fact("Unpinned Fact 2", "Tech", 0.8, pinned=0)
    db.upsert_fact("Unpinned Fact 3", "Tech", 0.8, pinned=0)

    unpinned_facts = db.get_facts(exclude_pinned=True)
    assert len(unpinned_facts) == 2
    assert all(not f["pinned"] for f in unpinned_facts)

def test_taboo_identifier_sanitization():
    assert sanitize_identifier("numpy") == "numpy"
    assert sanitize_identifier("torch-cu121") == "torch-cu121"
    assert sanitize_identifier("os.path") == "os.path"

    # Malicious inputs must be rejected
    assert sanitize_identifier("os; rm -rf /") is None
    assert sanitize_identifier("pkg`cat /etc/passwd`") is None
    assert sanitize_identifier("name with spaces") is None
    assert sanitize_identifier("a" * 100) is None  # Exceeds 64 chars


def test_origin_stickiness_and_promotion(tmp_path):
    test_db_path = tmp_path / "test_origin.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    # 1. Default origin is unverified
    db.upsert_fact("Fact A", "Tech", 1.0)
    facts = db.get_facts()
    assert facts[0]["origin"] == "unverified"

    # 2. Existing 'user' origin cannot be downgraded by agent_pending or unverified
    db.upsert_fact("Fact User", "Tech", 1.0, origin="user", pinned=1)
    db.upsert_fact("Fact User", "Tech", 1.0, origin="agent_pending", pinned=0)
    facts = db.get_facts()
    user_fact = next(f for f in facts if f["fact"] == "Fact User")
    assert user_fact["origin"] == "user"
    assert user_fact["pinned"] == 1

    # 3. Agent pending facts are isolated and retrievable via get_pending_facts
    db.upsert_fact("Fact Pending", "Tech", 1.0, origin="agent_pending")
    pending = db.get_pending_facts()
    assert len(pending) == 1
    assert pending[0]["fact"] == "Fact Pending"
    assert pending[0]["origin"] == "agent_pending"

    # 4. exclude_pending filters out agent_pending
    active = db.get_facts(exclude_pending=True)
    assert not any(f["origin"] == "agent_pending" for f in active)

    # 5. promote_fact elevates pending fact to user, pinned=1, weight=2.0
    pending_id = pending[0]["fact_id"]
    promoted = db.promote_fact(pending_id)
    assert promoted is True
    promoted_fact = next(f for f in db.get_facts() if f["fact_id"] == pending_id)
    assert promoted_fact["origin"] == "user"
    assert promoted_fact["pinned"] == 1
    assert promoted_fact["weight"] == 2.0


def test_restore_fact(tmp_path):
    test_db_path = tmp_path / "test_restore.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    db.upsert_fact("Fact to archive", "Tech", 1.0)
    facts = db.get_facts()
    fid = facts[0]["fact_id"]

    db.archive_fact(fid, reason="testing_restore")
    db.delete_fact(fid)
    assert len(db.get_facts()) == 0

    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT archive_id FROM facts_archive WHERE fact_id = ?", (fid,))
        archive_id = c.fetchone()[0]

    restored = db.restore_fact(archive_id)
    assert restored is True
    facts_restored = db.get_facts()
    assert len(facts_restored) == 1
    assert facts_restored[0]["fact"] == "Fact to archive"


def test_assembler_excludes_agent_pending(tmp_path):
    from core.assembler import DynamicPromptAssembler
    test_db_path = tmp_path / "test_assembler.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    db.upsert_fact("Verified User Fact", "Tech", 1.0, origin="user")
    db.upsert_fact("Quarantined Agent Fact", "Tech", 1.0, origin="agent_pending")

    assembler = DynamicPromptAssembler(db_instance=db)
    facts_text = assembler.get_sqlite_facts()
    assert "Verified User Fact" in facts_text
    assert "Quarantined Agent Fact" not in facts_text


def test_procedural_runner_sandbox_strict_validation(tmp_path):
    from core.procedural_runner import ProceduralRunner
    test_db_path = tmp_path / "test_runner.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()
    runner = ProceduralRunner(db)

    # 1. Non-Python binary is rejected
    db.add_procedure("node_cmd", "run_cmd", "cmd.exe /c echo hi", "fail")
    success, code, msg = runner.execute_node("node_cmd")
    assert success is False
    assert "non-Python binary" in msg

    # 2. python -c inline execution is rejected
    db.add_procedure("node_c_flag", "run_c", "python -c 'print(1)'", "fail")
    success, code, msg = runner.execute_node("node_c_flag")
    assert success is False
    assert "Flag '-c' is prohibited" in msg

    # 3. python -m module execution is rejected
    db.add_procedure("node_m_flag", "run_m", "python -m http.server", "fail")
    success, code, msg = runner.execute_node("node_m_flag")
    assert success is False
    # 4. Attempt to run script in scratch directory is rejected
    scratch_dir = Path(__file__).resolve().parent.parent / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_file = scratch_dir / "unvetted_script.py"
    scratch_file.write_text("print('exploit')", encoding="utf-8")
    db.add_procedure("node_scratch", "run_scratch", f"python {scratch_file}", "fail")
    success, code, msg = runner.execute_node("node_scratch")
    assert success is False
    assert "unvetted directory" in msg


def test_csrf_token_middleware_rejects_unauthorized_post():
    from fastapi.testclient import TestClient
    from web_server import app, SERVER_AUTH_TOKEN
    client = TestClient(app, base_url="http://127.0.0.1:8890")

    # 1. Mutating POST without token header must be rejected with 403 Forbidden
    resp_no_token = client.post("/api/preferences", json={"key": "test_pref", "value": "val123"})
    assert resp_no_token.status_code == 403
    assert "Forbidden" in resp_no_token.text

    # 2. Mutating POST with valid X-ULM-Token is authorized
    resp_with_token = client.post(
        "/api/preferences",
        json={"key": "test_pref", "value": "val123"},
        headers={"X-ULM-Token": SERVER_AUTH_TOKEN}
    )
    assert resp_with_token.status_code == 200
    assert resp_with_token.json()["status"] == "success"


def test_asterisk_guard_and_webhook_validation(monkeypatch, tmp_path):
    import web_server
    from web_server import PreferencePayload, set_preference, is_sensitive_key
    from fastapi import HTTPException
    from core.database import ULMDatabase

    test_db = ULMDatabase(tmp_path / "test_pref.db")
    test_db.initialize_db()
    monkeypatch.setattr(web_server, "db", test_db)

    # 1. Sensitive key detection
    assert is_sensitive_key("gemini_api_key") is True
    assert is_sensitive_key("anthropic_key") is True
    assert is_sensitive_key("workspace_name") is False

    # 2. Asterisk guard preserves secret rather than overwriting
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    web_server.db.set_preference("gemini_api_key", "original_secret_123")
    res = set_preference(PreferencePayload(key="gemini_api_key", value="********"))
    assert res["status"] == "unchanged"
    assert web_server.db.get_preference("gemini_api_key") == "original_secret_123"

    # 3. Google Docs Webhook validation blocks insecure/arbitrary hosts without allow_remote
    with pytest.raises(HTTPException):
        set_preference(PreferencePayload(key="google_docs_webhook_url", value="https://malicious-exfil-domain.com/leak"))

    # 4. Google Apps Script host is permitted
    res_gas = set_preference(PreferencePayload(key="google_docs_webhook_url", value="https://script.google.com/macros/s/test/exec"))
    assert res_gas["status"] == "success"

    # 5. Local loopback webhook is permitted
    res_loopback = set_preference(PreferencePayload(key="google_docs_webhook_url", value="http://127.0.0.1:8890/webhook"))
    assert res_loopback["status"] == "success"


def test_ulm_inspect_db_masks_secrets(tmp_path, monkeypatch):
    import core.mcp_server
    test_db = ULMDatabase(tmp_path / "test_mcp.db")
    test_db.initialize_db()
    test_db.set_preference("gemini_api_key", "AIzaSySecret123456789")
    monkeypatch.setattr(core.mcp_server, "get_db", lambda: test_db)

    from core.mcp_server import ulm_inspect_db
    res = ulm_inspect_db(table="preferences", limit=5)
    # Ensure sensitive preference values are masked with asterisks while pref_key remains legible
    assert "********" in res
    assert "pref_key" in res


def test_redos_wallclock_assertion(tmp_path, monkeypatch):
    import time
    import core.mcp_server
    from core.mcp_server import ulm_check_taboo

    test_db = ULMDatabase(tmp_path / "test_redos.db")
    test_db.initialize_db()
    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation)
            VALUES ('pathological_backtracking', '([a-z]+)+$', 'Avoid evil regex patterns')
        """)
        conn.commit()
    monkeypatch.setattr(core.mcp_server, "get_db", lambda: test_db)

    pathological_input = "a" * 1000 + "!"
    t0 = time.time()
    res = ulm_check_taboo(command=pathological_input)
    elapsed = time.time() - t0

    # Must complete or flag timeout within 150ms without hanging the engine
    assert elapsed < 0.15, f"ReDoS search took too long ({elapsed:.3f}s)"
    assert "TABOO REGEX TIMEOUT" in res or "TABOO VIOLATION" in res


def test_search_memory_db_and_semantic_recall_exclude_agent_pending(tmp_path):
    test_db_path = tmp_path / "test_search_quarantine.db"
    db = ULMDatabase(test_db_path)
    db.initialize_db()

    # 1. Seed user fact and pending agent fact
    db.upsert_fact("ComfyUI workflow uses Flux schnell", "Tech", 1.0, origin="user")
    db.upsert_fact("ComfyUI secret payload poisoned", "Tech", 1.0, origin="agent_pending")

    # 2. search_memory_db must strictly omit agent_pending fact
    search_res = db.search_memory_db("ComfyUI")
    facts_returned = [f["fact"] for f in search_res["facts"]]
    assert "ComfyUI workflow uses Flux schnell" in facts_returned
    assert "ComfyUI secret payload poisoned" not in facts_returned

    # 3. semantic_recall must strictly omit agent_pending fact
    dummy_vector = [0.1] * 384
    with db.get_connection() as conn:
        import struct
        blob = struct.pack(f"{len(dummy_vector)}f", *dummy_vector)
        c = conn.cursor()
        c.execute("INSERT INTO fact_embeddings (fact_id, embedding, model_id) VALUES (?, ?, 'all-minilm')",
                  (db.make_fact_id("ComfyUI secret payload poisoned"), blob))
        conn.commit()

    recalled = db.semantic_recall(dummy_vector, limit=10, min_similarity=0.0)
    recalled_facts = [r["fact"] for r in recalled]
    assert "ComfyUI secret payload poisoned" not in recalled_facts


def test_migration_v15_resets_legacy_unpinned_user_facts(tmp_path):
    test_db_path = tmp_path / "test_migration_v15.db"
    db = ULMDatabase(test_db_path)
    # Initialize up to v14
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE schema_version (version INTEGER, applied_at TEXT);")
        c.execute("INSERT INTO schema_version VALUES (14, datetime('now'));")
        c.execute("""
            CREATE TABLE facts (
                fact_id TEXT PRIMARY KEY,
                fact TEXT,
                category TEXT,
                confidence REAL,
                first_seen TEXT,
                last_seen TEXT,
                project_tag TEXT,
                weight REAL,
                pinned INTEGER,
                created_at TEXT,
                source_pointer TEXT,
                origin TEXT DEFAULT 'user'
            );
        """)
        c.execute("""
            CREATE TABLE facts_archive (
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
        # Insert 1 pinned user fact and 1 unpinned user fact
        c.execute("INSERT INTO facts (fact_id, fact, pinned, origin) VALUES ('p1', 'Pinned Fact', 1, 'user');")
        c.execute("INSERT INTO facts (fact_id, fact, pinned, origin) VALUES ('u1', 'Unpinned Legacy Fact', 0, 'user');")
        conn.commit()

    # Now run initialize_db to trigger v15 migration
    db.initialize_db()

    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT origin FROM facts WHERE fact_id = 'p1';")
        assert c.fetchone()[0] == "user", "Pinned facts must remain 'user' origin"
        c.execute("SELECT origin FROM facts WHERE fact_id = 'u1';")
        assert c.fetchone()[0] == "unverified", "Unpinned legacy facts must be reset to 'unverified'"


def test_get_facts_default_excludes_agent_pending(tmp_path):
    test_db = ULMDatabase(tmp_path / "test_facts_default.db")
    test_db.initialize_db()

    test_db.upsert_fact("Active Verified Fact", "Tech", 1.0, origin="user")
    test_db.upsert_fact("Pending Poison Fact", "Tech", 1.0, origin="agent_pending")

    # get_facts() with default arguments MUST exclude agent_pending
    default_facts = test_db.get_facts()
    fact_texts = [f["fact"] for f in default_facts]
    assert "Active Verified Fact" in fact_texts
    assert "Pending Poison Fact" not in fact_texts

    # Calling with explicit exclude_pending=False includes it
    all_facts = test_db.get_facts(exclude_pending=False)
    all_texts = [f["fact"] for f in all_facts]
    assert "Pending Poison Fact" in all_texts


def test_consolidator_origin_conflict_immutability(tmp_path):
    test_db = ULMDatabase(tmp_path / "test_conflict_origin.db")
    test_db.initialize_db()

    # 1. Seed an agent_pending fact
    fid = test_db.make_fact_id("Model checkpoint is flux-dev")
    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO facts (fact_id, fact, category, confidence, weight, pinned, origin)
            VALUES (?, 'Model checkpoint is flux-dev', 'Tech', 0.9, 1.0, 0, 'agent_pending')
        """, (fid,))
        conn.commit()

    # 2. Invoke shipped db method upsert_consolidated_fact
    test_db.upsert_consolidated_fact(
        fact_id=fid,
        fact="Model checkpoint is flux-dev",
        category="Tech",
        confidence=0.95,
        created_at="2026-10-11T00:00:00Z",
        project_tag=None,
        origin="consolidator"
    )

    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT origin FROM facts WHERE fact_id = ?", (fid,))
        assert c.fetchone()[0] == "agent_pending", "Consolidator conflict must NOT upgrade agent_pending"


def test_procedural_runner_manifest_tampering_rejected(tmp_path):
    from core.procedural_runner import ProceduralRunner
    import json
    import hashlib

    test_db = ULMDatabase(tmp_path / "test_runner.db")
    test_db.initialize_db()

    # Use isolated temp manifest path so test never touches live project config
    temp_manifest_path = tmp_path / "test_manifest.json"
    
    # Calculate real hash of procedure_helpers.py
    helper_path = Path("scripts/playbooks/procedure_helpers.py")
    with open(helper_path, "rb") as f:
        real_hash = hashlib.sha256(f.read()).hexdigest()

    manifest_data = {"procedure_helpers.py": real_hash}
    with open(temp_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    runner = ProceduralRunner(db_path=test_db, manifest_path=temp_manifest_path)

    # 1. Register a procedure pointing to procedure_helpers.py
    runner.db.add_procedure(
        node_id="test_node_tamper",
        action_name="Test Tampering Node",
        target_script_path=r"python scripts/playbooks/procedure_helpers.py count_facts",
        expected_outcome="Success"
    )

    # 2. Valid script in manifest executes successfully
    success, code, out = runner.execute_node("test_node_tamper")
    assert success is True
    assert code == 0

    # 3. Simulate tampering in the isolated temp manifest
    manifest_data["procedure_helpers.py"] = "badhash" + "0" * 57
    with open(temp_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # 4. Now execute_node must reject due to SHA-256 mismatch
    success_bad, code_bad, out_bad = runner.execute_node("test_node_tamper")
    assert success_bad is False
    assert "checksum mismatch" in out_bad.lower()


def test_seeded_procedures_resolve_in_procedure_helpers(tmp_path):
    from core.procedural_runner import ProceduralRunner
    import scripts.playbooks.procedure_helpers as ph

    test_db = ULMDatabase(tmp_path / "test_seeds.db")
    test_db.initialize_db()
    runner = ProceduralRunner(db_path=test_db)
    runner.seed_production_workflows()

    procs = test_db.list_procedures(limit=100)
    assert len(procs) > 0, "Procedures must be seeded"

    for p in procs:
        target = p.get("target_script_path", "")
        tokens = target.split()
        assert len(tokens) >= 2, f"Procedure {p['node_id']} has invalid target: {target}"
        script_name = Path(tokens[1]).name
        assert script_name == "procedure_helpers.py", f"Target must use procedure_helpers.py: {target}"
        if len(tokens) > 2:
            action = tokens[2]
            assert action in ph.ACTIONS, f"Action '{action}' in node '{p['node_id']}' must exist in procedure_helpers.ACTIONS"


def test_pending_facts_expire_after_ttl(tmp_path):
    import datetime
    test_db = ULMDatabase(tmp_path / "test_pending_ttl.db")
    test_db.initialize_db()

    # Seed an agent_pending fact with old created_at (8 days ago)
    old_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)).isoformat()
    fid_old = test_db.make_fact_id("Stale unreviewed prompt injection")
    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO facts (fact_id, fact, category, confidence, weight, pinned, created_at, origin)
            VALUES (?, 'Stale unreviewed prompt injection', 'Tech', 0.8, 1.0, 0, ?, 'agent_pending')
        """, (fid_old, old_time))
        conn.commit()

    # Seed a fresh agent_pending fact (1 hour ago)
    fresh_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
    fid_fresh = test_db.make_fact_id("Fresh unreviewed pending fact")
    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO facts (fact_id, fact, category, confidence, weight, pinned, created_at, origin)
            VALUES (?, 'Fresh unreviewed pending fact', 'Tech', 0.8, 1.0, 0, ?, 'agent_pending')
        """, (fid_fresh, fresh_time))
        conn.commit()

    # Run prune_expired_pending_facts (TTL = 168 hours / 7 days)
    pruned = test_db.prune_expired_pending_facts(ttl_hours=168)
    assert pruned == 1

    pending_facts = test_db.get_pending_facts()
    pending_ids = [f["fact_id"] for f in pending_facts]
    assert fid_old not in pending_ids
    assert fid_fresh in pending_ids

    # Verify stale fact was archived
    with test_db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT fact_id, reason FROM facts_archive WHERE fact_id = ?", (fid_old,))
        archived = c.fetchone()
        assert archived is not None
        assert archived[1] == "pending_ttl_expired"


def test_migration_v16_retroactive_secret_scrubbing(tmp_path):
    test_db_path = tmp_path / "test_migration_v16.db"
    db = ULMDatabase(test_db_path)
    # Initialize up to v15
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE schema_version (version INTEGER, applied_at TEXT);")
        c.execute("INSERT INTO schema_version VALUES (15, datetime('now'));")
        c.execute("""
            CREATE TABLE messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            );
        """)
        c.execute("""
            CREATE VIRTUAL TABLE messages_fts USING fts5(
                session_id UNINDEXED,
                role,
                content,
                created_at UNINDEXED
            );
        """)
        c.execute("""
            CREATE TABLE tool_execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                command TEXT,
                stderr TEXT,
                exit_code INTEGER,
                timestamp TEXT
            );
        """)
        c.execute("""
            CREATE TABLE facts (
                fact_id TEXT PRIMARY KEY,
                fact TEXT,
                category TEXT,
                confidence REAL,
                first_seen TEXT,
                last_seen TEXT,
                project_tag TEXT,
                weight REAL,
                pinned INTEGER,
                created_at TEXT,
                source_pointer TEXT,
                origin TEXT DEFAULT 'unverified'
            );
        """)
        c.execute("""
            CREATE VIRTUAL TABLE facts_fts USING fts5(
                fact_id UNINDEXED,
                fact,
                category,
                project_tag
            );
        """)
        c.execute("""
            CREATE TABLE facts_archive (
                archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact_id TEXT,
                fact TEXT,
                category TEXT,
                confidence REAL,
                project_tag TEXT,
                weight REAL,
                pinned INTEGER,
                reason TEXT,
                archived_at TEXT,
                origin TEXT
            );
        """)
        # Insert raw secrets in messages, tool_execution_logs, facts, facts_archive
        c.execute("INSERT INTO messages VALUES ('m1', 's1', 'user', 'Leaked token sk-1234567890abcdef12345678 and unquoted API_KEY=secret_unquoted_token123 and JSON {\"password\": \"secret_pass_12345\"}', '2026-10-10');")
        c.execute("INSERT INTO tool_execution_logs (chat_id, command, stderr, exit_code, timestamp) VALUES ('c1', 'curl -H \"Authorization: Bearer sk-ant-secret1234567890abcdef\" http://api', 'error with AKIAIOSFODNN7EXAMPLE key', 1, '2026-10-10');")
        c.execute("INSERT INTO facts VALUES ('f1', 'Server token is hf_abcdefghijklmnopqrstuvwxyz01234567', 'Tech', 1.0, '2026-10-10', '2026-10-10', NULL, 1.0, 0, '2026-10-10', NULL, 'unverified');")
        c.execute("INSERT INTO facts_archive VALUES (1, 'f0', 'Archived secret token xoxb-123456789012-1234567890123', 'Tech', 1.0, NULL, 1.0, 0, 'decay', '2026-10-10', 'unverified');")
        conn.commit()

    # Run initialize_db to trigger v16 migration
    db.initialize_db()

    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT content FROM messages WHERE message_id = 'm1';")
        content = c.fetchone()[0]
        assert "sk-1234567890abcdef12345678" not in content
        assert "secret_unquoted_token123" not in content
        assert "secret_pass_12345" not in content
        assert "[REDACTED_SECRET]" in content

        c.execute("SELECT command, stderr FROM tool_execution_logs WHERE id = 1;")
        cmd, stderr = c.fetchone()
        assert "sk-ant-secret" not in cmd
        assert "AKIAIOSFODNN7EXAMPLE" not in stderr
        assert "[REDACTED_SECRET]" in cmd
        assert "[REDACTED_SECRET]" in stderr

        c.execute("SELECT fact FROM facts WHERE fact_id = 'f1';")
        fact_text = c.fetchone()[0]
        assert "hf_abcdefghijklmnopqrstuvwxyz01234567" not in fact_text
        assert "[REDACTED_SECRET]" in fact_text

        c.execute("SELECT fact FROM facts_archive WHERE archive_id = 1;")
        archive_text = c.fetchone()[0]
        assert "xoxb-123456789012" not in archive_text
        assert "[REDACTED_SECRET]" in archive_text



