#!/usr/bin/env python3
"""
Antigravity Overdrive :: Archaeological Chat Log Ingestion & Deduplication Engine
Sweeps C:, D:, E:, G: for historical chat logs (Perplexity, Browser Exports, Cline tasks, Downloads),
deduplicates supersets, compiles sessions into ULM SQLite database (db/sync_state.db) with FTS5 indexing,
and consolidates raw files into D:\\AI\\Memory_Archive\\Ingested_Chats.
"""

import os
import sys
import json
import re
import shutil
import hashlib
import sqlite3
import argparse
import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Enforce UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import ULMDatabase, DEFAULT_DB_PATH
from core.utils import scrub_secrets

ARCHIVE_DIR = Path(r"D:\AI\Memory_Archive\Ingested_Chats")

# Targeted discovery paths
DISCOVERY_PATHS = [
    {
        "path": Path(os.path.expanduser(r"~\Downloads")),
        "type": "downloads",
        "action": "move"
    },
    {
        "path": Path(r"G:\My Drive\ULM_Browser_Exports"),
        "type": "browser_exports",
        "action": "copy"
    },
    {
        "path": Path(r"E:\_Sanctuary_Backups\Lore_and_Worldbuilding\Notes\Vera"),
        "type": "vera_lore",
        "action": "copy_keep_original"
    },
    {
        "path": Path(r"D:\AI\Vesperas tips"),
        "type": "vespera_tips",
        "action": "move"
    },
    {
        "path": Path(r"E:\Notepad saves"),
        "type": "notepad_saves",
        "action": "move"
    },
    {
        "path": Path(os.path.expanduser(r"~\AppData\Roaming\Code\User\globalStorage\saoudrizwan.cline-nightly\tasks")),
        "type": "cline_tasks",
        "action": "copy_keep_original"
    }
]


def clean_text(s: str) -> str:
    """Normalize text and strip trailing whitespace and citations."""
    if not s:
        return ""
    # Strip perplexity footnote references like [^1_1], [^1_2], etc.
    s = re.sub(r'\[\^\d+_\d+\]', '', s)
    s = re.sub(r'\[cite:\s*[^\]]+\]', '', s)
    return s.strip()


def compute_turn_fingerprint(role: str, text: str) -> str:
    """Normalized turn hash for deduplication matching."""
    norm = re.sub(r'\s+', ' ', clean_text(text)).lower()
    return hashlib.sha256(f"{role.lower()}:{norm[:200]}".encode('utf-8')).hexdigest()[:16]


def parse_browser_json(filepath: Path) -> List[Dict[str, Any]]:
    """Parses exported chat JSON format (Gemini Exporter, Perplexity Flash, etc.)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        for enc in ['cp1252', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    data = json.load(f)
                break
            except Exception:
                continue
        else:
            return []

    if not isinstance(data, dict):
        return []

    metadata = data.get("metadata", {})
    raw_title = metadata.get("title", filepath.stem)
    dates = metadata.get("dates", {})
    created_at = dates.get("created") or dates.get("exported") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    updated_at = dates.get("updated") or dates.get("exported") or created_at

    messages = []
    raw_msgs = data.get("messages", [])
    for msg in raw_msgs:
        # Check standard role
        role = msg.get("role") or "unknown"
        if role in ["Prompt", "user", "User"]:
            norm_role = "Pilot"
        elif role in ["Response", "assistant", "model", "Assistant"]:
            norm_role = "Vespera"
        else:
            norm_role = role

        # Extract text
        text = msg.get("say") or msg.get("text") or ""
        if not text and "contents" in msg:
            text_parts = []
            for c in msg["contents"]:
                if isinstance(c, dict) and c.get("type") == "text":
                    text_parts.append(c.get("content", ""))
                elif isinstance(c, str):
                    text_parts.append(c)
            text = "\n".join(text_parts)

        cleaned = clean_text(text)
        if cleaned:
            msg_time = msg.get("time") or created_at
            messages.append({
                "role": norm_role,
                "text": cleaned,
                "time": msg_time
            })

    if not messages:
        return []

    session_id = f"export_{hashlib.sha256(str(filepath.name).encode('utf-8')).hexdigest()[:12]}"
    return [{
        "session_id": session_id,
        "title": raw_title,
        "source": "browser_export",
        "created_at": created_at,
        "updated_at": updated_at,
        "filepath": filepath,
        "messages": messages
    }]


def parse_perplexity_collection_md(filepath: Path) -> List[Dict[str, Any]]:
    """Splits the massive 5,482-line master Perplexity collection markdown into granular sessions."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()

    # Sections are delimited by '---'
    sections = re.split(r'\n---\n', content)
    parsed_sessions = []
    
    for idx, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue
            
        # Match prompt heading: # <Prompt text>
        lines = sec.split('\n')
        prompt_text = ""
        response_lines = []
        is_response = False
        
        for line in lines:
            if not is_response and line.startswith('# '):
                prompt_text = line[2:].strip()
                is_response = True
            elif is_response:
                response_lines.append(line)
                
        if not prompt_text:
            # Check if this is the introduction block
            if "That's the VERA collection link" in sec:
                prompt_text = "What is the VERA space and master collection link?"
                response_lines = lines
            else:
                continue
                
        response_text = clean_text('\n'.join(response_lines))
        # Strip trailing footnote reference links from Perplexity markdown
        response_text = re.split(r'\n\[\^1_\d+\]:', response_text)[0].strip()
        response_text = re.split(r'\n\[\^2_\d+\]:', response_text)[0].strip()
        response_text = re.split(r'\n\[\^\d+_\d+\]:', response_text)[0].strip()
        
        if not response_text:
            continue
            
        session_id = f"pplx_col_{idx:03d}_{hashlib.sha256(prompt_text.encode('utf-8')).hexdigest()[:8]}"
        title = prompt_text[:60]
        
        parsed_sessions.append({
            "session_id": session_id,
            "title": f"Perplexity Collection: {title}",
            "source": "perplexity_collection",
            "created_at": "2026-01-07T00:08:00Z",
            "updated_at": "2026-01-07T00:08:00Z",
            "filepath": filepath,
            "messages": [
                {"role": "Pilot", "text": prompt_text, "time": "2026-01-07T00:08:00Z"},
                {"role": "Vespera", "text": response_text, "time": "2026-01-07T00:08:05Z"}
            ]
        })
        
    return parsed_sessions


def parse_perplexity_standalone_md(filepath: Path) -> List[Dict[str, Any]]:
    """Parses individual Perplexity chat markdown files from Downloads and other folders."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        with open(filepath, 'r', encoding='latin-1') as f:
            content = f.read()

    lines = content.split('\n')
    title = filepath.stem
    if lines and lines[0].startswith('# '):
        title = lines[0][2:].strip()

    # Perplexity markdown structure: user questions usually header 1 or 2, followed by answers
    messages = []
    current_role = "Pilot"
    current_buffer = []

    for line in lines:
        if line.startswith('# ') or line.startswith('## '):
            if current_buffer:
                msg_text = clean_text('\n'.join(current_buffer))
                if msg_text:
                    messages.append({"role": current_role, "text": msg_text, "time": ""})
                current_buffer = []
            
            heading = line.lstrip('#').strip()
            # If heading looks like a query
            if len(heading) > 10 and not heading.lower().startswith(('recent', 'core files', 'options', 'sources', 'citations')):
                current_role = "Pilot"
                messages.append({"role": "Pilot", "text": heading, "time": ""})
                current_role = "Vespera"
            else:
                current_buffer.append(line)
        else:
            current_buffer.append(line)

    if current_buffer:
        msg_text = clean_text('\n'.join(current_buffer))
        if msg_text:
            messages.append({"role": current_role, "text": msg_text, "time": ""})

    if not messages:
        # Fallback: treat entire content as single note/transcript turn
        cleaned = clean_text(content)
        if cleaned:
            messages = [
                {"role": "Pilot", "text": f"Context inquiry on {title}", "time": ""},
                {"role": "Vespera", "text": cleaned, "time": ""}
            ]

    session_id = f"pplx_{hashlib.sha256(str(filepath.name).encode('utf-8')).hexdigest()[:12]}"
    mtime = datetime.datetime.fromtimestamp(filepath.stat().st_mtime, tz=datetime.timezone.utc).isoformat()
    return [{
        "session_id": session_id,
        "title": title,
        "source": "perplexity",
        "created_at": mtime,
        "updated_at": mtime,
        "filepath": filepath,
        "messages": messages
    }]


def parse_cline_task(task_dir: Path) -> List[Dict[str, Any]]:
    """Parses a Cline/Roo-Cline task directory."""
    ui_log = task_dir / "ui_messages.json"
    api_log = task_dir / "api_conversation_history.json"
    target_file = ui_log if ui_log.exists() else (api_log if api_log.exists() else None)
    if not target_file:
        return []

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    messages = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Extract turn based on ui_messages format
        say_type = item.get("say")
        text = item.get("text") or ""
        ts = item.get("ts")
        time_str = datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).isoformat() if ts else ""

        if say_type in ["user_feedback", "task"]:
            role = "Pilot"
        elif say_type in ["text", "say", "browser_action_launch", "completion_result"]:
            role = "Vespera"
        elif item.get("role") == "user":
            role = "Pilot"
        elif item.get("role") == "assistant":
            role = "Vespera"
        else:
            continue

        cleaned = clean_text(text)
        if cleaned:
            messages.append({"role": role, "text": cleaned, "time": time_str})

    if not messages:
        return []

    mtime = datetime.datetime.fromtimestamp(target_file.stat().st_mtime, tz=datetime.timezone.utc).isoformat()
    return [{
        "session_id": f"cline_{task_dir.name}",
        "title": f"Cline Task {task_dir.name[:8]}",
        "source": "cline",
        "created_at": mtime,
        "updated_at": mtime,
        "filepath": target_file,
        "messages": messages
    }]


class ArchaeologicalHunter:
    def __init__(self, db: ULMDatabase, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.discovered_files = 0
        self.parsed_sessions = []
        self.existing_session_ids = set()
        self.existing_message_fingerprints = set()
        self.stats = {
            "discovered": 0,
            "parsed": 0,
            "exact_duplicates": 0,
            "branch_subsets_dropped": 0,
            "already_in_db": 0,
            "to_ingest_sessions": 0,
            "to_ingest_messages": 0,
            "files_moved": 0,
            "files_copied": 0
        }

    def load_existing_db_state(self):
        """Loads existing session_ids and message fingerprints from SQLite."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT session_id FROM sessions")
            self.existing_session_ids = {row[0] for row in c.fetchall()}

            # Sample first 200 chars of messages to identify already ingested conversations
            c.execute("SELECT role, SUBSTR(content, 1, 150) FROM messages")
            for r, c_sample in c.fetchall():
                if c_sample:
                    norm = re.sub(r'\s+', ' ', c_sample).lower()
                    self.existing_message_fingerprints.add(f"{r.lower()}:{norm}")

        print(f"[+] Loaded {len(self.existing_session_ids)} existing sessions from ULM database.")

    def scan_all_targets(self):
        """Scans all registered directory paths and routes files to appropriate parsers."""
        for target in DISCOVERY_PATHS:
            base_dir = target["path"]
            source_type = target["type"]
            action = target["action"]

            if not base_dir.exists():
                print(f"[-] Directory not found: {base_dir}")
                continue

            print(f"[*] Scanning {source_type}: {base_dir}")

            if source_type == "cline_tasks":
                # Scan subdirectories
                for item in base_dir.iterdir():
                    if item.is_dir():
                        self.stats["discovered"] += 1
                        sessions = parse_cline_task(item)
                        for s in sessions:
                            s["action"] = action
                            self.parsed_sessions.append(s)
                continue

            # Standard file scanner
            for file_path in base_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                # Filter relevant files
                name_lower = file_path.name.lower()
                suffix_lower = file_path.suffix.lower()

                if suffix_lower not in [".json", ".md", ".txt"]:
                    continue

                # Check if it looks like a chat or perplexity export
                is_candidate = False
                if source_type in ["browser_exports", "vera_lore"]:
                    is_candidate = True
                elif "perplexity" in name_lower or "chat" in name_lower or "gemini" in name_lower or "conversation" in name_lower:
                    is_candidate = True
                elif source_type == "vespera_tips" and suffix_lower == ".md":
                    is_candidate = True

                if not is_candidate:
                    continue

                self.stats["discovered"] += 1

                # Route to parser
                sessions = []
                if "collections_vera" in name_lower:
                    sessions = parse_perplexity_collection_md(file_path)
                elif suffix_lower == ".json":
                    sessions = parse_browser_json(file_path)
                elif suffix_lower in [".md", ".txt"]:
                    sessions = parse_perplexity_standalone_md(file_path)

                for s in sessions:
                    s["action"] = action
                    self.parsed_sessions.append(s)

        self.stats["parsed"] = len(self.parsed_sessions)
        print(f"[+] Total discovered candidate files: {self.stats['discovered']}")
        print(f"[+] Total raw parsed session streams: {self.stats['parsed']}")

    def deduplicate(self) -> List[Dict[str, Any]]:
        """Deduplicates sessions via message sequence fingerprints and superset selection."""
        # 1. Group by title stem or fingerprint prefix to identify branched sets
        seen_exact_hashes = {}
        unique_sessions = []

        for s in self.parsed_sessions:
            msgs = s["messages"]
            if not msgs:
                continue

            # Compute session content hash
            combined_text = "".join(f"{m['role']}:{m['text'][:100]}" for m in msgs)
            content_hash = hashlib.sha256(combined_text.encode('utf-8')).hexdigest()

            if content_hash in seen_exact_hashes:
                self.stats["exact_duplicates"] += 1
                continue
            seen_exact_hashes[content_hash] = s
            unique_sessions.append(s)

        # 2. Superset Resolution: Drop partial branch subsets (e.g. if conversation A is prefix of conversation B)
        # Sort by turn count descending so largest superset comes first
        unique_sessions.sort(key=lambda x: len(x["messages"]), reverse=True)
        final_valid_sessions = []
        known_conversations = []

        for s in unique_sessions:
            msgs = s["messages"]
            turn_signatures = [compute_turn_fingerprint(m["role"], m["text"]) for m in msgs]
            sig_str = "|".join(turn_signatures)

            # Check if this signature is an existing subset of any already kept session
            is_subset = False
            for parent_sig in known_conversations:
                if sig_str in parent_sig and len(sig_str) < len(parent_sig):
                    is_subset = True
                    break

            if is_subset:
                self.stats["branch_subsets_dropped"] += 1
                continue

            known_conversations.append(sig_str)

            # Check if session is already present in DB
            if s["session_id"] in self.existing_session_ids:
                self.stats["already_in_db"] += 1
                continue

            # Check if majority of turns are already in DB
            match_count = 0
            for m in msgs:
                norm_sample = re.sub(r'\s+', ' ', m['text'][:150]).lower()
                if f"{m['role'].lower()}:{norm_sample}" in self.existing_message_fingerprints:
                    match_count += 1
            if len(msgs) > 2 and (match_count / len(msgs)) > 0.8:
                self.stats["already_in_db"] += 1
                continue

            final_valid_sessions.append(s)

        self.stats["to_ingest_sessions"] = len(final_valid_sessions)
        self.stats["to_ingest_messages"] = sum(len(s["messages"]) for s in final_valid_sessions)
        return final_valid_sessions

    def execute_ingestion(self, valid_sessions: List[Dict[str, Any]]):
        """Commits deduplicated sessions and messages directly into SQLite ULM DB with FTS5."""
        if not valid_sessions:
            print("[*] No new sessions to ingest.")
            return

        print(f"\n[*] Committing {len(valid_sessions)} sessions ({self.stats['to_ingest_messages']} messages) into SQLite...")

        if self.dry_run:
            print("[+] DRY-RUN active: skipping SQLite write transactions.")
            return

        with self.db.get_connection() as conn:
            c = conn.cursor()

            for s in valid_sessions:
                session_id = s["session_id"]
                source = s["source"]
                created_at = s["created_at"]
                updated_at = s["updated_at"]
                title = s["title"]
                messages = s["messages"]

                # 1. Insert session
                c.execute("""
                    INSERT OR REPLACE INTO sessions (session_id, source, created_at, updated_at, topics, summary, project_tag)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, source, created_at, updated_at, "Historical/Lore", title, "origin_transcripts"))

                # 2. Insert messages
                msg_rows = []
                fts_rows = []
                for idx, m in enumerate(messages):
                    role = m["role"]
                    raw_text = m["text"]
                    clean_text = scrub_secrets(raw_text)
                    msg_time = m["time"] or created_at
                    msg_id = f"{session_id}_m{idx:04d}_{hashlib.sha256(clean_text[:50].encode('utf-8')).hexdigest()[:8]}"
                    
                    msg_rows.append((msg_id, session_id, role, clean_text, msg_time))
                    fts_rows.append((session_id, role, clean_text, msg_time))

                c.executemany("""
                    INSERT OR REPLACE INTO messages (message_id, session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, msg_rows)

                # 3. Insert into FTS5 index
                try:
                    c.executemany("""
                        INSERT INTO messages_fts (session_id, role, content, created_at)
                        VALUES (?, ?, ?, ?)
                    """, fts_rows)
                except Exception as e:
                    pass

            conn.commit()

        print(f"[+] Successfully committed {len(valid_sessions)} sessions to db/sync_state.db!")

    def execute_archival(self, sessions_processed: List[Dict[str, Any]]):
        """Consolidates source files into D:\\AI\\Memory_Archive\\Ingested_Chats."""
        print(f"\n[*] Consolidating raw files into {ARCHIVE_DIR}...")
        
        if not self.dry_run:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        handled_files = set()

        for s in self.parsed_sessions:
            fpath = s.get("filepath")
            if not fpath or not fpath.exists() or fpath in handled_files:
                continue

            handled_files.add(fpath)
            action = s.get("action", "copy")
            dest_file = ARCHIVE_DIR / fpath.name

            # Resolve name conflicts in archive if needed
            if dest_file.exists() and dest_file != fpath:
                dest_file = ARCHIVE_DIR / f"{fpath.stem}_{hashlib.sha256(str(fpath).encode('utf-8')).hexdigest()[:6]}{fpath.suffix}"

            if self.dry_run:
                print(f"[DRY-RUN] {action.upper()}: {fpath} -> {dest_file}")
                if action == "move":
                    self.stats["files_moved"] += 1
                else:
                    self.stats["files_copied"] += 1
                continue

            try:
                if action == "move":
                    shutil.move(str(fpath), str(dest_file))
                    self.stats["files_moved"] += 1
                elif action in ["copy", "copy_keep_original"]:
                    shutil.copy2(str(fpath), str(dest_file))
                    self.stats["files_copied"] += 1
            except Exception as e:
                print(f"[-] Archival error on {fpath.name}: {e}")

        print(f"[+] Archival complete: {self.stats['files_moved']} files moved, {self.stats['files_copied']} files copied.")


def main():
    parser = argparse.ArgumentParser(description="Archaeological Chat Log Ingest & Deduplication Engine")
    parser.add_argument("--dry-run", action="store_true", help="Simulate run without writing to DB or moving files")
    args = parser.parse_args()

    print("=" * 70)
    print("🏺 ANTIGRAVITY OVERDRIVE :: HISTORICAL CHAT LOG ARCHAEOLOGY & INGEST")
    print(f"[*] Target SQLite DB: {DEFAULT_DB_PATH}")
    print(f"[*] Mode: {'DRY RUN (NO DISK / DB MUTATIONS)' if args.dry_run else 'LIVE PRODUCTION INGEST'}")
    print("=" * 70)

    db = ULMDatabase(DEFAULT_DB_PATH)
    hunter = ArchaeologicalHunter(db, dry_run=args.dry_run)
    
    hunter.load_existing_db_state()
    hunter.scan_all_targets()
    valid_sessions = hunter.deduplicate()
    
    print("\n" + "=" * 70)
    print("📊 DEDUPLICATION & VALIDATION SUMMARY")
    print(f" - Discovered Files: {hunter.stats['discovered']}")
    print(f" - Raw Sessions Parsed: {hunter.stats['parsed']}")
    print(f" - Exact Duplicate Sessions Dropped: {hunter.stats['exact_duplicates']}")
    print(f" - Branch Subsets Dropped: {hunter.stats['branch_subsets_dropped']}")
    print(f" - Already In Database (Skipped): {hunter.stats['already_in_db']}")
    print(f" - Sessions To Ingest: {hunter.stats['to_ingest_sessions']}")
    print(f" - Messages To Ingest: {hunter.stats['to_ingest_messages']}")
    print("=" * 70)

    hunter.execute_ingestion(valid_sessions)
    hunter.execute_archival(valid_sessions)

    print("\n[+] Archaeological sweep completed successfully.")


if __name__ == "__main__":
    main()
