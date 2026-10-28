
import pytest
from core.database import ULMDatabase
from core.mcp_server import ulm_park_thought, ulm_get_open_loops, ulm_resolve_thought

def test_parked_thoughts_lifecycle():
    db = ULMDatabase()
    # Test DB insertion
    tid = db.park_thought("Test open loop reminder", context_project="test_proj", priority="high")
    assert tid > 0

    loops = db.get_open_loops(context_project="test_proj")
    assert any(item["id"] == tid for item in loops)

    # Touch reminder
    assert db.touch_thought_reminder(tid) is True

    # Resolve
    assert db.resolve_thought(tid, "resolved") is True
    remaining = db.get_open_loops(context_project="test_proj")
    assert not any(item["id"] == tid for item in remaining)

def test_mcp_tools():
    res_park = ulm_park_thought("MCP test reminder", project_tag="test_suite")
    assert "Successfully parked thought" in res_park

    res_loops = ulm_get_open_loops(project_tag="test_suite")
    assert "Found 1 open loop" in res_loops

    # Extract ID
    import re
    match = re.search(r"#(\d+):", res_loops)
    assert match is not None
    tid = int(match.group(1))

    res_resolve = ulm_resolve_thought(tid, "resolved")
    assert "Successfully updated" in res_resolve
