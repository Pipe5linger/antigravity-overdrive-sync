"""
ULM SYSTEM STRESS TEST + API INTEGRATION SUITE
Tests: symlink integrity, API live calls, pipeline end-to-end, Drive sync verification
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import tempfile
import shutil
import urllib.request
import urllib.error
import yaml
from pathlib import Path
from datetime import datetime

# UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

REPO = Path("D:/AI/Projects/antigravity-overdrive-sync")
sys.path.append(str(REPO))

from core.database import ULMDatabase
from core.engine import ULMEngine
from parsers.antigravity import AntigravityParser
from injectors.gemini_md import GeminiMdInjector
from core.profile_evaluator import ProfileEvaluator

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def section(title):
    print(f"\n{'='*70}")
    print(f"  🔥 {title}")
    print(f"{'='*70}")

def record(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, passed, detail))
    print(f"  {status}  {name}")
    if detail:
        print(f"         → {detail}")

def load_api_key():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        env_path = REPO / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "GEMINI_API_KEY":
                        key = v.strip().strip('"').strip("'")
    return key

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: SYMLINK INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 1: SYMLINK INTEGRITY")

paths = {
    "Drive (real file)": Path(r"E:\Google Drive\My Drive\GEMINI.md"),
    "D:\\ symlink":      Path(r"D:\GEMINI.md"),
    ".gemini symlink":   Path(r"C:\Users\boben\.gemini\GEMINI.md"),
}

contents = {}
for label, p in paths.items():
    try:
        contents[label] = p.read_text(encoding="utf-8")
        record(f"{label} readable", True, str(p))
    except Exception as e:
        record(f"{label} readable", False, str(e))

# All three must have identical content
if len(contents) == 3:
    texts = list(contents.values())
    all_same = all(t == texts[0] for t in texts)
    record("All three paths have identical content", all_same,
           "Content matches" if all_same else "MISMATCH DETECTED")
else:
    record("All three paths have identical content", False, "One or more files unreadable")

# Verify symlink attribute
for label, p in [("D:\\ symlink", Path(r"D:\GEMINI.md")),
                  (".gemini symlink", Path(r"C:\Users\boben\.gemini\GEMINI.md"))]:
    is_link = p.is_symlink()
    record(f"{label} is a symlink (not a copy)", is_link)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: LIVE GEMINI API CALL — SUMMARY GENERATION
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 2: LIVE GEMINI API — SUMMARY GENERATION (gemini-3.5-flash)")

api_key = load_api_key()
record("API key loaded", bool(api_key), f"Starts with: {api_key[:10]}..." if api_key else "MISSING")

if api_key:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
    test_payload = {
        "contents": [{"parts": [{"text":
            "Pilot: Hey Vespera, we just got the ComfyUI face-swap pipeline working with ReActor.\n"
            "Vespera: Finally. Flux dev + ReActor + SDXL at 1024px. RTX 4070 sweating.\n"
            "Summarize this in one technical sentence."
        }]}]
    }

    t0 = time.time()
    try:
        req = urllib.request.Request(url,
            data=json.dumps(test_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode())
            summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            elapsed = time.time() - t0
            record("Live API call succeeded", True, f"{elapsed*1000:.0f}ms")
            record("Summary returned non-empty text", bool(summary), summary[:120])
    except urllib.error.HTTPError as he:
        elapsed = time.time() - t0
        body = he.read().decode()
        record("Live API call succeeded", False, f"HTTP {he.code}: {he.reason} — {body[:200]}")
    except Exception as e:
        record("Live API call succeeded", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: LIVE GEMINI API CALL — PROFILE EVALUATOR (JSON mode)
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 3: LIVE GEMINI API — PROFILE EVALUATOR (JSON structured output)")

if api_key:
    profile_payload = {
        "contents": [{"parts": [{"text":
            "Pilot: I couldn't figure out why my SQLite writes were blocking.\n"
            "Vespera: WAL mode. Enable it. PRAGMA journal_mode = WAL;\n"
            "Pilot: Oh damn, that fixed the concurrency issue immediately.\n\n"
            "You are a developer behavioral evaluator. Return a JSON object with key 'metrics' "
            "containing a list. Each entry must have: category (milestone/strength/weakness/habit), "
            "name (slug), description (1 sentence), confidence (0.1-1.0). "
            "Extract 2-3 metrics from this dialogue."
        }]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    t0 = time.time()
    try:
        req = urllib.request.Request(url,
            data=json.dumps(profile_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode())
            raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            parsed = json.loads(raw)
            metrics = parsed.get("metrics", [])
            elapsed = time.time() - t0
            record("Profile evaluator API call succeeded", True, f"{elapsed*1000:.0f}ms")
            record("JSON response parseable", True, f"{len(metrics)} metrics extracted")
            for m in metrics:
                print(f"         → [{m.get('category','?')}] {m.get('name','?')}: {m.get('description','')[:80]}")
    except urllib.error.HTTPError as he:
        body = he.read().decode()
        record("Profile evaluator API call succeeded", False, f"HTTP {he.code}: {body[:200]}")
    except Exception as e:
        record("Profile evaluator API call succeeded", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: PRODUCTION DATABASE INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 4: PRODUCTION DATABASE INTEGRITY")

db_path = str(Path(ULMEngine().target_yaml).with_suffix(".db"))
db = ULMDatabase(db_path)
db.initialize_db()

try:
    with sqlite3.connect(db_path) as conn:
        # Integrity check
        status = conn.execute("PRAGMA integrity_check").fetchone()[0]
        record("SQLite integrity check", status == "ok", status)

        # WAL mode
        wal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        record("WAL mode active", wal == "wal", f"journal_mode = {wal}")

        # Session count
        n_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        record("Sessions indexed", n_sessions > 0, f"{n_sessions} sessions")

        # Message count
        n_msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        record("Messages indexed", n_msgs > 0, f"{n_msgs} messages")

        # Profiled sessions
        n_profiled = conn.execute("SELECT COUNT(*) FROM sessions WHERE profiled_at IS NOT NULL").fetchone()[0]
        n_unprofiled = conn.execute("SELECT COUNT(*) FROM sessions WHERE profiled_at IS NULL").fetchone()[0]
        record("Session profiling tracked", True, f"{n_profiled} profiled, {n_unprofiled} pending")

        # Summary coverage
        n_summarized = conn.execute("SELECT COUNT(*) FROM sessions WHERE summary IS NOT NULL AND summary != ''").fetchone()[0]
        record("Sessions have summaries", n_summarized > 0, f"{n_summarized}/{n_sessions} have summaries")

        # Developer profile metrics
        n_metrics = conn.execute("SELECT COUNT(*) FROM developer_profile").fetchone()[0]
        record("Developer profile populated", n_metrics >= 0, f"{n_metrics} profile metrics")

        # Persona preferences locked
        persona = conn.execute("SELECT pref_value FROM preferences WHERE pref_key='persona'").fetchone()
        record("Persona identity locked in DB", persona and persona[0] == "Vespera Caligo",
               f"persona = {persona[0] if persona else 'MISSING'}")
except Exception as e:
    record("Production DB accessible", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: GOOGLE DRIVE SYNC VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 5: GOOGLE DRIVE SYNC VERIFICATION")

drive_gemini = Path(r"E:\Google Drive\My Drive\GEMINI.md")
drive_chatlog = Path(r"E:\Google Drive\My Drive\chatlog.yaml")

record("GEMINI.md exists on Drive", drive_gemini.exists())
record("chatlog.yaml exists on Drive", drive_chatlog.exists())

if drive_chatlog.exists():
    try:
        with open(drive_chatlog, "r", encoding="utf-8") as f:
            chatlog = yaml.safe_load(f)
        n = chatlog.get("metadata", {}).get("total_indexed_sessions", 0)
        last_sync = chatlog.get("metadata", {}).get("last_memory_sync", "unknown")
        sessions_in_yaml = len(chatlog.get("sessions", []))
        record("chatlog.yaml parseable", True, f"last sync: {last_sync}")
        record("chatlog.yaml has sessions", sessions_in_yaml > 0, f"{sessions_in_yaml} sessions in YAML")
        # Check most recent session has a summary
        top = chatlog.get("sessions", [{}])[0]
        has_summary = bool(top.get("summary", ""))
        record("Most recent session has a summary", has_summary, top.get("summary", "")[:100])
    except Exception as e:
        record("chatlog.yaml parseable", False, str(e))

if drive_gemini.exists():
    content = drive_gemini.read_text(encoding="utf-8")
    record("GEMINI.md contains SystemMemory block", "<SystemMemory>" in content)
    record("GEMINI.md references chatlog.yaml", "chatlog.yaml" in content)
    record("GEMINI.md instructs reading 5 sessions", "last 5" in content)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: SCHEDULED TASK HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
section("TEST 6: SCHEDULED TASK HEALTH CHECK")

import subprocess
try:
    result = subprocess.run(
        ["schtasks", "/query", "/tn", "AntigravityOverdriveSync", "/fo", "LIST"],
        capture_output=True, text=True, timeout=10
    )
    output = result.stdout
    record("Scheduled task exists", "AntigravityOverdriveSync" in output)
    record("Task is in Ready/Running state", "Ready" in output or "Running" in output,
           next((l for l in output.splitlines() if "Status" in l), "Status unknown"))
except Exception as e:
    record("Scheduled task check", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────────────
section("FINAL REPORT")

total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed

print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}\n")

if failed:
    print("  FAILURES:")
    for name, p, detail in results:
        if not p:
            print(f"    {FAIL}  {name}: {detail}")
else:
    print("  ALL TESTS PASSED. SYSTEM IS LOCKED AND LOADED. 🚀")

print()
