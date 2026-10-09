import os
import tempfile
import pytest
from pathlib import Path
from core.database import ULMDatabase
from scripts.toolkit.harvest_scratch_vault import extract_script_metadata

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = ULMDatabase(db_path)
    db.initialize_db()
    yield db
    # Cleanup
    for p in [Path(db_path), Path(db_path + "-wal"), Path(db_path + "-shm")]:
        if p.exists():
            try:
                os.remove(p)
            except Exception:
                pass

def test_script_vault_upsert_and_deduplication(temp_db):
    code_1 = """def inspect_vram():\n    print('Checking RTX 4070 VRAM')\n"""
    
    # 1. Insert new script
    res1 = temp_db.upsert_script(
        script_name="check_vram.py",
        code_content=code_1,
        docstring_summary="Inspects RTX 4070 VRAM",
        category="vram_gpu",
        source_session="sess_test_1"
    )
    assert res1["status"] == "inserted"
    script_id = res1["script_id"]

    # 2. Insert same script again (deduplication)
    res2 = temp_db.upsert_script(
        script_name="duplicate_vram.py",
        code_content=code_1,
        docstring_summary="Different summary but same code",
        category="vram_gpu",
        source_session="sess_test_2"
    )
    assert res2["status"] == "incremented"
    assert res2["script_id"] == script_id

    # 3. Verify execution_count was incremented
    record = temp_db.get_script(script_id)
    assert record is not None
    assert record["execution_count"] == 2
    assert record["script_name"] == "check_vram.py"

def test_script_vault_search_fts5(temp_db):
    temp_db.upsert_script(
        script_name="parse_transcripts.py",
        code_content="import json\ndef parse_jsonl(): pass",
        docstring_summary="Extracts token burn from brain transcripts",
        category="telemetry_logs"
    )
    temp_db.upsert_script(
        script_name="inspect_sqlite_schema.py",
        code_content="import sqlite3\ndef pragma_table(): pass",
        docstring_summary="Dumps table columns and pragma stats",
        category="database"
    )

    # Search for sqlite
    matches_db = temp_db.search_scripts("sqlite columns", limit=5)
    assert len(matches_db) >= 1
    assert matches_db[0]["script_name"] == "inspect_sqlite_schema.py"

    # Search for transcript
    matches_logs = temp_db.search_scripts("transcript token", limit=5)
    assert len(matches_logs) >= 1
    assert matches_logs[0]["script_name"] == "parse_transcripts.py"

def test_ast_metadata_extraction():
    sample_code = '''"""Tool to inspect active database WAL state."""
import sqlite3
from pathlib import Path

class LedgerAuditor:
    def audit_wal(self):
        return True
'''
    summary, category = extract_script_metadata(sample_code, "test_auditor.py")
    assert "inspect active database WAL state" in summary
    assert "Classes: LedgerAuditor" in summary
    assert "Functions: audit_wal" in summary
    assert category == "database"

def test_sanitize_and_classify_recipe(temp_db):
    from scripts.toolkit.harvest_scratch_vault import sanitize_and_classify_script
    
    # 1. Global script
    global_code = "import torch\nprint('VRAM free:', torch.cuda.is_available())"
    code_g, summary_g, cat_g, scope_g = sanitize_and_classify_script(global_code, "gpu_check.py")
    assert scope_g == "GLOBAL"
    assert "sys.argv" not in code_g

    # 2. Recipe script with hardcoded session path
    recipe_code = 'target = r"C:\\Users\\boben\\.gemini\\antigravity\\brain\\206635a9-dc5b-4e12-a078-4e4a895eba9b\\logs\\transcript.jsonl"\nwith open(target): pass'
    code_r, summary_r, cat_r, scope_r = sanitize_and_classify_script(recipe_code, "parse_target.py")
    assert scope_r == "RECIPE"
    assert "sys.argv[1]" in code_r

    # Insert both and search by scope
    temp_db.upsert_script("gpu_check.py", code_g, summary_g, cat_g, scope=scope_g)
    temp_db.upsert_script("parse_target.py", code_r, summary_r, cat_r, scope=scope_r)

    globals_found = temp_db.search_scripts("VRAM", scope="GLOBAL")
    assert len(globals_found) >= 1
    assert globals_found[0]["scope"] == "GLOBAL"

    recipes_found = temp_db.search_scripts("transcript", scope="RECIPE")
    assert len(recipes_found) >= 1
    assert recipes_found[0]["scope"] == "RECIPE"

