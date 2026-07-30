import os
import sys
import json
import sqlite3
import datetime
import requests
import uvicorn
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from core.engine import ULMEngine
from core.database import ULMDatabase
from core.assembler import DynamicPromptAssembler

app = FastAPI(title="Vespera ULM Control Center", version="2.0.0")

# System Paths & Engine Setup
engine = ULMEngine()
db_path = str(Path(engine.target_yaml).with_suffix(".db"))
db = ULMDatabase(db_path)
db.initialize_db()

frontend_dir = Path(__file__).resolve().parent / "frontend"

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
        "llm_model": db.get_preference("llm_model", "qwen2.5-coder-vespera:latest"),
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
            query = "SELECT fact_id, fact, category, confidence, first_seen, last_seen, project_tag FROM facts WHERE 1=1"
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

@app.get("/api/preferences")
def get_preferences():
    try:
        with db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT pref_key, pref_value, updated_at FROM preferences")
            prefs = {r["pref_key"]: r["pref_value"] for r in c.fetchall()}
            return {"preferences": prefs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/preferences")
def set_preference(payload: PreferencePayload):
    try:
        db.set_preference(payload.key, payload.value)
        add_web_log(f"Preference updated: {payload.key} = {payload.value}")
        return {"status": "success", "key": payload.key, "value": payload.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ollama/models")
def get_ollama_models():
    endpoint = db.get_preference("ollama_endpoint", "http://localhost:11434")
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
        from parsers.antigravity import AntigravityParser
        from injectors.gemini_md import GeminiMdInjector
        from core.profile_evaluator import ProfileEvaluator
        from core.consolidator import MemoryConsolidator
        
        log_parser = AntigravityParser()
        memory_injector = GeminiMdInjector()
        evaluator = ProfileEvaluator()
        
        new_logs = log_parser.fetch_new_logs(force_ingest=True)
        if new_logs:
            synced_s, synced_m = db.import_raw_logs(new_logs)
            add_web_log(f"ETL Ingested: {synced_s} sessions, {synced_m} messages.")
            
        unprofiled = db.get_unprofiled_sessions()
        if unprofiled:
            add_web_log(f"Evaluating {len(unprofiled)} unprofiled sessions in background worker thread...")
            count = 0
            total = len(unprofiled)
            for s_id in unprofiled:
                count += 1
                if evaluator.evaluate_session(db, s_id):
                    db.mark_session_profiled(s_id)
                if count % 5 == 0 or count == total:
                    add_web_log(f"Profile Progress: Evaluated {count}/{total} sessions...")
        
        consolidator = MemoryConsolidator(db)
        consolidator.consolidate()
            
        memory_injector.inject(db, dry_run=False)
        add_web_log("[+] ULM Sync & Reinjection completed successfully!")
    except Exception as e:
        add_web_log(f"[-] ULM Sync Error: {e}")

import threading
_sync_thread_running = False

@app.post("/api/actions/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    global _sync_thread_running
    if _sync_thread_running:
        add_web_log("[*] Sync task already running in background.")
        return {"status": "running", "message": "ULM Sync task already in progress."}

    def _async_sync():
        global _sync_thread_running
        _sync_thread_running = True
        try:
            run_sync_task()
        finally:
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

# Mount Frontend static files
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

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
