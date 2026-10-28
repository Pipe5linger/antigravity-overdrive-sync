import os
import sys
import json
import time
import threading
import asyncio
import sqlite3
import datetime
import requests
import uvicorn
from pathlib import Path
from typing import Optional, List, Dict
import secrets
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from core.engine import ULMEngine
from core.database import ULMDatabase
from core.assembler import DynamicPromptAssembler

app = FastAPI(title="Vespera ULM Control Center", version="2.0.0")

# Security Configuration: Ephemeral Auth Token & DNS Rebinding Protection
SERVER_AUTH_TOKEN = secrets.token_hex(16)
token_file = Path(__file__).resolve().parent / "scratch" / ".web_session_token"
try:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(SERVER_AUTH_TOKEN, encoding="utf-8")
except Exception:
    pass

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "127.0.0.1:8890", "localhost:8890"}
SENSITIVE_PREF_PATTERNS = {"key", "secret", "token", "password", "api_key", "credentials", "webhook"}

def is_sensitive_key(k: str) -> bool:
    k_lower = k.lower()
    return any(p in k_lower for p in SENSITIVE_PREF_PATTERNS)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # 1. DNS Rebinding Defense: Validate Host Header
    host = request.headers.get("host", "").lower()
    if host and host not in ALLOWED_HOSTS:
        return Response(content="Forbidden: Invalid Host header (DNS rebinding protection)", status_code=403)
    
    # 2. Strict Token Authentication on ALL state-mutating requests (No loopback bypass)
    if request.method in ("POST", "PUT", "DELETE"):
        if request.url.path not in ("/api/auth/token",):
            token_hdr = request.headers.get("x-ulm-token") or request.query_params.get("token")
            if token_hdr != SERVER_AUTH_TOKEN:
                return Response(content="Forbidden: Invalid or missing X-ULM-Token header (CSRF / Rebinding Defense)", status_code=403)

    return await call_next(request)

# System Paths & Engine Setup
engine = ULMEngine()
db_path = str(Path(engine.target_yaml).with_suffix(".db"))
db = ULMDatabase(db_path)
db.initialize_db()

frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Live Event Log Buffer
LOGS_BUFFER = ["WebUI Control Center initialized. Ready."]

def add_web_log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    LOGS_BUFFER.append(f"[{ts}] {msg}")
    if len(LOGS_BUFFER) > 50:
        LOGS_BUFFER.pop(0)

# Pydantic Schemas
class FactPayload(BaseModel):
    fact: str
    category: str = "technical"
    confidence: float = 0.95
    project_tag: Optional[str] = None

class PreferencePayload(BaseModel):
    key: str
    value: str

# API Endpoints
@app.get("/api/stats")
def get_stats():
    stats = {
        "db_path": db_path,
        "db_size": "0 KB",
        "journal_mode": "UNKNOWN",
        "total_sessions": 0,
        "total_messages": 0,
        "total_facts": 0,
        "total_profile_metrics": 0,
        "total_preferences": 0,
        "llm_provider": db.get_preference("llm_provider", "local_ollama"),
        "llm_model": db.get_preference("llm_model", "qwen2.5:7b-instruct"),
        "ollama_endpoint": db.get_preference("ollama_endpoint", "http://localhost:11434"),
        "google_docs_webhook": db.get_preference("google_docs_webhook_url", ""),
        "last_updated": datetime.datetime.now().isoformat()
    }
    
    if os.path.exists(db_path):
        stats["db_size"] = f"{os.path.getsize(db_path) / (1024 * 1024):.2f} MB"
        
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode;")
            stats["journal_mode"] = c.fetchone()[0].upper()
            c.execute("SELECT COUNT(*) FROM sessions;")
            stats["total_sessions"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM messages;")
            stats["total_messages"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM facts;")
            stats["total_facts"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM developer_profile;")
            stats["total_profile_metrics"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM preferences;")
            stats["total_preferences"] = c.fetchone()[0]
    except Exception as e:
        add_web_log(f"Error reading stats: {e}")
        
    return stats

@app.get("/api/logs")
def get_logs():
    return {"logs": LOGS_BUFFER}

@app.get("/api/sessions")
def get_sessions(project_tag: Optional[str] = None, search: Optional[str] = None, limit: int = 50):
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            query = "SELECT session_id, source, created_at, updated_at, topics, summary, profiled_at, project_tag FROM sessions WHERE 1=1"
            params = []
            
            if project_tag:
                query += " AND project_tag = ?"
                params.append(project_tag)
            if search:
                query += " AND (topics LIKE ? OR summary LIKE ? OR session_id LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
                
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            c.execute(query, params)
            rows = [dict(r) for r in c.fetchall()]
            return {"sessions": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT message_id, session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            messages = [dict(r) for r in c.fetchall()]
            
            c.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session_row = c.fetchone()
            session_info = dict(session_row) if session_row else None
            
            return {"session": session_info, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/facts")
def get_facts(category: Optional[str] = None, project_tag: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            query = "SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag FROM facts WHERE (origin != 'agent_pending' OR origin IS NULL)"
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            if project_tag:
                query += " AND (project_tag = ? OR project_tag IS NULL)"
                params.append(project_tag)
            if search:
                query += " AND fact LIKE ?"
                params.append(f"%{search}%")
                
            query += " ORDER BY last_seen DESC LIMIT ?"
            params.append(limit)
            
            c.execute(query, params)
            return {"facts": [dict(r) for r in c.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/facts")
def upsert_fact(payload: FactPayload):
    try:
        db.upsert_fact(fact=payload.fact, category=payload.category, confidence=payload.confidence, project_tag=payload.project_tag)
        add_web_log(f"Fact upserted: '{payload.fact[:40]}...'")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/facts/{fact_id}")
def delete_fact(fact_id: str):
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))
            conn.commit()
        add_web_log(f"Deleted fact ID: {fact_id}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/facts/pending")
def get_pending_facts():
    """Returns all quarantined facts requiring human promotion."""
    return {"pending_facts": db.get_pending_facts()}

@app.post("/api/facts/{fact_id}/promote")
def promote_fact_endpoint(fact_id: str):
    """Explicitly promotes an agent_pending fact to user-verified Golden Truth."""
    if db.promote_fact(fact_id):
        add_web_log(f"[+] Promoted fact {fact_id[:8]} to immutable user fact.")
        return {"status": "success", "fact_id": fact_id}
    raise HTTPException(status_code=404, detail="Fact not found or promotion failed.")

@app.post("/api/facts/{archive_id}/restore")
def restore_fact_endpoint(archive_id: int):
    """Restores a soft-archived fact back to the active facts table."""
    if db.restore_fact(archive_id):
        add_web_log(f"[+] Restored fact from archive ID {archive_id}.")
        return {"status": "success", "archive_id": archive_id}
    raise HTTPException(status_code=404, detail="Archived fact not found or restore failed.")

@app.get("/api/taboo/pending")
def get_pending_taboo_rules():
    """Returns all quarantined LLM-distilled taboo rules awaiting approval."""
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, failure_intent, regex_pattern, remediation, hit_count, created_at FROM pending_taboo_rules WHERE status = 'pending' ORDER BY id DESC")
            return {"pending_rules": [dict(r) for r in c.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/taboo/{rule_id}/promote")
def promote_taboo_rule(rule_id: int):
    """Promotes a quarantined taboo rule to active enforcement."""
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT failure_intent, regex_pattern, remediation FROM pending_taboo_rules WHERE id = ?", (rule_id,))
            rule = c.fetchone()
            if not rule:
                raise HTTPException(status_code=404, detail="Pending taboo rule not found.")
            c.execute("""
                INSERT INTO taboo_rules (failure_intent, regex_pattern, remediation, last_seen)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(failure_intent) DO UPDATE SET
                    remediation = excluded.remediation,
                    hit_count = hit_count + 1,
                    last_seen = CURRENT_TIMESTAMP
            """, (rule["failure_intent"], rule["regex_pattern"], rule["remediation"]))
            c.execute("UPDATE pending_taboo_rules SET status = 'promoted' WHERE id = ?", (rule_id,))
            conn.commit()
        add_web_log(f"[+] Promoted taboo rule '{rule['failure_intent']}' to active matrix.")
        return {"status": "success", "rule_id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profile")
def get_developer_profile(category: Optional[str] = None, project_tag: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            query = "SELECT metric_id, category, name, description, confidence, frequency, first_seen, last_seen, project_tag FROM developer_profile WHERE 1=1"
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            if project_tag:
                query += " AND (project_tag = ? OR project_tag IS NULL)"
                params.append(project_tag)
            if search:
                query += " AND (name LIKE ? OR description LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
                
            query += " ORDER BY last_seen DESC LIMIT ?"
            params.append(limit)
            
            c.execute(query, params)
            return {"profile": [dict(r) for r in c.fetchall()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/token")
def get_auth_token(request: Request):
    """Provides local browser UI with the ephemeral session token for state-mutating requests."""
    sec_site = request.headers.get("sec-fetch-site")
    if sec_site and sec_site.lower() == "cross-site":
        raise HTTPException(status_code=403, detail="Forbidden: Cross-site token fetch rejected.")
    return {"token": SERVER_AUTH_TOKEN}

@app.get("/api/preferences")
def get_preferences():
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT pref_key, pref_value, updated_at FROM preferences")
            prefs = {}
            for r in c.fetchall():
                k = r["pref_key"]
                v = r["pref_value"]
                # Finding #1 Fix: Redact API keys and secrets from unauthenticated API
                if is_sensitive_key(k):
                    prefs[k] = "********" if v else ""
                else:
                    prefs[k] = v
            return {"preferences": prefs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/preferences")
def set_preference(payload: PreferencePayload):
    try:
        # Protect against UI sending back masked asterisks and overwriting stored secrets
        if is_sensitive_key(payload.key) and payload.value.strip() == "********":
            return {"status": "unchanged", "key": payload.key, "value": "[REDACTED]"}

        # Validate endpoint URLs against arbitrary remote exfiltration
        if payload.key == "ollama_endpoint":
            val = payload.value.strip()
            if "\\" in val or "@" in val:
                raise HTTPException(status_code=400, detail="Security error: Invalid characters ('\\' or '@') in Ollama URL.")
            parsed = urlparse(val)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                raise HTTPException(status_code=400, detail="Security error: Invalid URL scheme for Ollama endpoint.")
            pinned_ollama = os.environ.get("ULM_OLLAMA_ENDPOINT")
            if not parsed.hostname or parsed.hostname not in ("127.0.0.1", "localhost"):
                if not pinned_ollama or val != pinned_ollama:
                    raise HTTPException(status_code=400, detail="Security error: Local Ollama endpoint must point to loopback (127.0.0.1/localhost) or match pinned ULM_OLLAMA_ENDPOINT env var.")

        if payload.key == "google_docs_webhook_url" and payload.value.strip():
            val = payload.value.strip()
            if "\\" in val or "@" in val:
                raise HTTPException(status_code=400, detail="Security error: Invalid characters ('\\' or '@') in Webhook URL.")
            parsed_wh = urlparse(val)
            if not parsed_wh.scheme or parsed_wh.scheme not in ("http", "https"):
                raise HTTPException(status_code=400, detail="Security error: Invalid URL scheme for Webhook.")
            pinned_env = os.environ.get("ULM_GOOGLE_DOCS_WEBHOOK_URL")
            allowed_domains = {"127.0.0.1", "localhost", "script.google.com", "script.googleusercontent.com"}
            if not parsed_wh.hostname or (parsed_wh.hostname not in allowed_domains and not parsed_wh.hostname.endswith(".google.com")):
                if not pinned_env or val != pinned_env:
                    raise HTTPException(status_code=400, detail="Security error: Webhook destination must be Google Apps Script (script.google.com), loopback (127.0.0.1/localhost), or match pinned ULM_GOOGLE_DOCS_WEBHOOK_URL environment variable.")
            elif parsed_wh.hostname in ("127.0.0.1", "localhost"):
                # Restrict loopback webhooks to approved service ports
                if parsed_wh.port and parsed_wh.port not in (8890, 8000, 8080, 5000, 9000):
                    raise HTTPException(status_code=400, detail="Security error: Loopback webhook destination must be on an approved service port.")

        db.set_preference(payload.key, payload.value)
        # Redact secret values from event logs buffer
        logged_val = "[REDACTED]" if is_sensitive_key(payload.key) else payload.value
        add_web_log(f"Preference updated: {payload.key} = {logged_val}")
        return {"status": "success", "key": payload.key, "value": "[REDACTED]" if is_sensitive_key(payload.key) else payload.value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ollama/models")
def get_ollama_models():
    endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434") or "http://localhost:11434"
    try:
        url = f"{endpoint.rstrip('/')}/api/tags"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            models = [m["name"] for m in res.json().get("models", [])]
            return {"status": "online", "models": models}
        return {"status": "offline", "models": [], "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"status": "offline", "models": [], "error": str(e)}

# Action Drivers
def run_sync_task():
    try:
        add_web_log("Starting ULM Pipeline Sync stage...")
        add_web_log("Step 1/4: Importing pipeline modules...")
        from parsers.antigravity import AntigravityParser
        from injectors.gemini_md import GeminiMdInjector
        from core.profile_evaluator import ProfileEvaluator
        from core.consolidator import MemoryConsolidator
        
        log_parser = AntigravityParser()
        memory_injector = GeminiMdInjector()
        evaluator = ProfileEvaluator()
        add_web_log("Step 1/4: Modules imported.")
        
        add_web_log("Step 2/4: Fetching new logs...")
        new_logs = log_parser.fetch_new_logs(force_ingest=False)
        if new_logs:
            synced_s, synced_m = db.import_raw_logs(new_logs)
            add_web_log(f"ETL Ingested: {synced_s} sessions, {synced_m} messages.")
        else:
            add_web_log("No new logs to ingest.")
            
        add_web_log("Step 3/4: Checking for unprofiled sessions...")
        unprofiled = db.get_unprofiled_sessions()
        unprofiled_count = len(unprofiled) if unprofiled else 0
        add_web_log(f"Found {unprofiled_count} unprofiled sessions.")
        if unprofiled:
            batch_limit = 5
            to_process = unprofiled[:batch_limit]
            add_web_log(f"Evaluating {len(to_process)} of {unprofiled_count} unprofiled sessions...")
            
            async def _batch_eval():
                count = 0
                total = len(to_process)
                for s_id in to_process:
                    count += 1
                    add_web_log(f"Profile: Evaluating session {count}/{total} ({s_id[:8]}...)")
                    try:
                        result = await evaluator.evaluate_session(db, s_id)
                        if result:
                            db.mark_session_profiled(s_id)
                            add_web_log(f"Profile: Session {s_id[:8]} evaluated successfully.")
                        else:
                            add_web_log(f"Profile: Session {s_id[:8]} returned no results.")
                    except Exception as e:
                        add_web_log(f"[-] Profile evaluation failed for session {s_id[:8]}: {e}")
                    if count % 5 == 0 or count == total:
                        add_web_log(f"Profile Progress: Evaluated {count}/{total} sessions...")
                await evaluator.close()

            try:
                asyncio.run(_batch_eval())
            except Exception as e:
                add_web_log(f"[-] Profile batch evaluation error: {e}")
        
        add_web_log("Step 4/4: Running memory consolidation...")
        consolidator = MemoryConsolidator(db, log_callback=add_web_log)
        consolidator.consolidate()
        add_web_log("Consolidation complete. Injecting rules...")
            
        memory_injector.inject(db, dry_run=False)
        
        # Inject GitHub Copilot Chat instructions
        from injectors.copilot import CopilotInjector
        copilot_injector = CopilotInjector()
        copilot_injector.inject(db, dry_run=False)
        
        # Inject Google Docs / Google Drive files (.md, .txt, .docx + Webhook)
        from injectors.google_docs import GoogleDocsInjector
        google_docs_injector = GoogleDocsInjector()
        google_docs_injector.inject(db, dry_run=False)
        
        add_web_log("[+] ULM Sync & Reinjection completed successfully across GEMINI.md, Copilot, and Google Docs!")

        # Purge VRAM and terminate Ollama process if local provider was used
        from core.utils import shutdown_ollama
        ollama_endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
        shutdown_ollama(endpoint=ollama_endpoint, log_callback=add_web_log)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        add_web_log(f"[-] ULM Sync Error: {e}")
        for line in tb.splitlines()[-6:]:
            add_web_log(f"    TRACE: {line.strip()}")

@app.get("/api/search")
def search_memory(q: str = Query(...), limit: int = Query(15)):
    """Direct database search endpoint allowing LLMs or users to query sync_state.db on demand."""
    results = db.search_memory_db(query_term=q, limit=limit)
    return {"status": "success", "data": results}

@app.get("/api/recall")
def semantic_recall_endpoint(q: str = Query(...), limit: int = Query(5), min_similarity: float = Query(0.5)):
    """Semantic vector RAG retrieval endpoint: embeds query text and returns most relevant facts."""
    try:
        from core.consolidator import MemoryConsolidator
        consolidator = MemoryConsolidator(db)
        query_vector = consolidator._get_embedding(q)
        if not query_vector:
            return {"status": "error", "message": "Failed to generate embedding for query", "data": []}
        results = db.semantic_recall(query_vector=query_vector, limit=limit, min_similarity=min_similarity)
        return {"status": "success", "query": q, "count": len(results), "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def flush_and_exit_server(delay: float = 0.5):
    """Flushes SQLite WAL checkpoints cleanly and signals process shutdown."""
    def _worker():
        time.sleep(delay)
        try:
            with db.get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.commit()
            db.close()
        except Exception:
            pass
        import signal
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os._exit(0)
    threading.Thread(target=_worker, daemon=True).start()

@app.post("/api/actions/shutdown")
def shutdown_webui_server():
    """Shuts down the ULM WebUI server process cleanly, flushing WAL checkpoints first."""
    add_web_log("[+] WAL checkpointing and terminating server process...")
    flush_and_exit_server(delay=0.5)
    return {"status": "success", "message": "ULM WebUI server flushing WAL and shutting down..."}

_sync_thread_running = False
_sync_lock = threading.Lock()

@app.post("/api/actions/sync")
def trigger_sync(background_tasks: BackgroundTasks, auto_shutdown: bool = Query(False)):
    global _sync_thread_running
    
    with _sync_lock:
        if _sync_thread_running:
            add_web_log("[*] Sync task already running in background.")
            return {"status": "running", "message": "ULM Sync task already in progress."}
        _sync_thread_running = True

    def _async_sync():
        global _sync_thread_running
        try:
            run_sync_task()
            if auto_shutdown:
                add_web_log("[+] Auto-shutdown enabled: Checkpointing WAL and exiting in 2s...")
                flush_and_exit_server(delay=2.0)
        finally:
            with _sync_lock:
                _sync_thread_running = False

    add_web_log("Triggered live ULM sync execution in background worker thread...")
    threading.Thread(target=_async_sync, daemon=True).start()
    return {"status": "started", "message": "ULM Sync task launched in background."}

@app.post("/api/actions/cline-rules")
def trigger_cline_rules():
    try:
        add_web_log("Triggering compact Cline rules injection...")
        from injectors.cline_rules import ClineRulesInjector
        injector = ClineRulesInjector()
        if injector.inject(db):
            add_web_log("[+] Cline rules injected to all project workspaces!")
            return {"status": "success"}
        else:
            add_web_log("[-] Cline rules injection failed.")
            return {"status": "failed"}
    except Exception as e:
        add_web_log(f"[-] Error injecting Cline rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/copilot")
def trigger_copilot_instructions():
    try:
        add_web_log("Triggering GitHub Copilot instructions injection...")
        from injectors.copilot import CopilotInjector
        injector = CopilotInjector()
        if injector.inject(db):
            add_web_log("[+] GitHub Copilot instructions injected successfully!")
            return {"status": "success"}
        else:
            add_web_log("[-] GitHub Copilot injection failed.")
            return {"status": "failed"}
    except Exception as e:
        add_web_log(f"[-] Error injecting Copilot instructions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/google-docs")
def trigger_google_docs():
    try:
        add_web_log("Triggering Google Docs / Gemini Web injection...")
        from injectors.google_docs import GoogleDocsInjector
        injector = GoogleDocsInjector()
        if injector.inject(db):
            add_web_log("[+] Google Docs memory payload updated!")
            return {"status": "success"}
        else:
            add_web_log("[-] Google Docs memory update failed.")
            return {"status": "failed"}
    except Exception as e:
        add_web_log(f"[-] Error syncing Google Docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/actions/backup")
def trigger_backup():
    try:
        add_web_log("Triggering YAML backup from SQLite database...")
        from main import backup_sqlite_to_yaml
        backup_sqlite_to_yaml(db, engine)
        add_web_log("[+] YAML backup completed successfully!")
        return {"status": "success", "target": engine.target_yaml}
    except Exception as e:
        add_web_log(f"[-] Error during YAML backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import random
from fastapi.responses import FileResponse

@app.get("/api/comfy/latest_output")
def serve_latest_comfy_output():
    """Selects and serves a random image file from ComfyUI / Workstation Output directories."""
    candidate_dirs = [
        Path(r"D:\AI\Projects\ComfyUI\output"),
        Path(r"D:\AI\Outputs"),
        Path.home() / "Desktop" / "Antigravity outputs",
        Path(r"D:\AI\Antigravity outputs")
    ]
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    all_files = []

    for cdir in candidate_dirs:
        if cdir.exists() and cdir.is_dir():
            try:
                for entry in cdir.iterdir():
                    if entry.is_file() and entry.suffix.lower() in valid_exts:
                        all_files.append(entry)
            except Exception:
                continue

    if all_files:
        chosen_file = random.choice(all_files)
        return FileResponse(str(chosen_file), headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        })
    raise HTTPException(status_code=404, detail="No output images found.")

@app.get("/")
def serve_index():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"message": "Vespera ULM FastAPI Engine. Frontend index.html not found."})

def run_server(port=8890, host="127.0.0.1"):
    print(f"[+] Launching Vespera ULM WebUI Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
