import pytest
from core.database import ULMDatabase
from core.mcp_server import expand_conversational_query, ulm_recall, ulm_pin_fact

def test_expand_conversational_query():
    raw = "can you please show me the facial parity sweep settings from Phase 2?"
    exp = expand_conversational_query(raw)
    
    tokens = exp["meaningful_tokens"]
    assert "facial" in tokens
    assert "parity" in tokens
    assert "sweep" in tokens
    assert "phase" in tokens
    assert "can" not in tokens
    assert "please" not in tokens
    assert "the" not in tokens
    assert "from" not in tokens
    
    assert '"facial"*' in exp["fts_query"]
    assert '"parity"*' in exp["fts_query"]

def test_pin_and_recall_with_source_pointer(tmp_path):
    test_db_path = str(tmp_path / "test_sync.db")
    db = ULMDatabase(test_db_path)
    db.initialize_db()
    
    # Verify table has source_pointer column
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info(facts)")
        cols = [col[1] for col in c.fetchall()]
        assert "source_pointer" in cols
        
    # Pin fact with source pointer
    db.upsert_fact(
        fact="Phase 2 facial parity runs with tolerance 0.045 on script scripts/facial_parity.py",
        category="Technical",
        confidence=1.0,
        project_tag="test-proj",
        pinned=1,
        source_pointer="scripts/facial_parity.py:L45"
    )
    
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT fact, source_pointer, pinned FROM facts WHERE project_tag = 'test-proj'")
        row = c.fetchone()
        assert row is not None
        assert row[1] == "scripts/facial_parity.py:L45"
        assert row[2] == 1
    db.close_connection()

def test_upsert_dedup_and_embedding_retention(tmp_path):
    """Verifies Claude's bugfix: upserting a fact multiple times does NOT duplicate FTS5 rows and does NOT wipe cached embeddings."""
    test_db_path = str(tmp_path / "test_dedup.db")
    db = ULMDatabase(test_db_path)
    db.initialize_db()
    
    fact_text = "NVIDIA RTX 4070 VRAM ceiling is 12GB strictly enforced"
    fid = db.make_fact_id(fact_text)
    
    # 1. Upsert fact first time
    db.upsert_fact(fact=fact_text, category="Hardware", confidence=1.0)
    
    # Add a mock embedding for this fact
    dummy_blob = b"\x00" * 128
    with db.get_connection() as conn:
        conn.execute("INSERT INTO fact_embeddings (fact_id, embedding, model_id, created_at) VALUES (?, ?, ?, ?)", (fid, dummy_blob, "test-model", "now"))
        conn.commit()
        
    # 2. Upsert fact 3 more times
    for _ in range(3):
        db.upsert_fact(fact=fact_text, category="Hardware", confidence=1.0)
        
    with db.get_connection() as conn:
        c = conn.cursor()
        # Assert exactly 1 row in facts
        c.execute("SELECT COUNT(*) FROM facts WHERE fact_id = ?", (fid,))
        assert c.fetchone()[0] == 1
        
        # Assert exactly 1 row in facts_fts (NO trigger duplicate bloat)
        c.execute("SELECT COUNT(*) FROM facts_fts WHERE fact_id = ?", (fid,))
        assert c.fetchone()[0] == 1
        
        # Assert embedding was NOT cascade-deleted by INSERT OR REPLACE
        c.execute("SELECT COUNT(*) FROM fact_embeddings WHERE fact_id = ?", (fid,))
        assert c.fetchone()[0] == 1
        
    db.close_connection()
