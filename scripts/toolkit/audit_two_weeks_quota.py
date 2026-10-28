import sqlite3
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_audit():
    print("=" * 60)
    print(" 🔮 VESPERA 14-DAY TOKEN & QUOTA AUDIT (2026-09-26 -> 2026-10-10)")
    print("=" * 60)

    # 1. Audit db/sync_state.db
    conn = sqlite3.connect("db/sync_state.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT session_id, role, content, created_at "
        "FROM messages "
        "WHERE created_at >= '2026-09-26' "
        "ORDER BY session_id, created_at ASC"
    )
    db_messages = cursor.fetchall()

    sessions_db = {}
    for sess_id, role, content, ts in db_messages:
        if sess_id not in sessions_db:
            sessions_db[sess_id] = []
        toks = int(len((content or "").split()) * 1.3)
        sessions_db[sess_id].append(toks)

    db_total_turns = sum(len(v) for v in sessions_db.values())
    db_raw_tokens = sum(sum(v) for v in sessions_db.values())

    # Standard unmanaged cumulative context accumulation
    db_standard_cumulative = 0
    for s_id, turns in sessions_db.items():
        hist = 0
        for t in turns:
            hist += t
            db_standard_cumulative += hist

    # ULM Bounded context (rolling window capped at 4500)
    db_ulm_cumulative = 0
    for s_id, turns in sessions_db.items():
        for i in range(len(turns)):
            win_start = max(0, i - 3)
            win_toks = sum(turns[win_start:i+1])
            db_ulm_cumulative += min(4500, 1500 + win_toks)

    # 2. Audit Antigravity Local Brain Transcripts
    brain_dir = Path(r"C:\Users\boben\.gemini\antigravity\brain")
    brain_sessions = 0
    brain_total_turns = 0
    brain_raw_tokens = 0
    brain_standard_cumulative = 0
    brain_ulm_cumulative = 0

    two_weeks_ago = datetime(2026, 9, 26).timestamp()

    if brain_dir.exists():
        for sess_folder in brain_dir.iterdir():
            if not sess_folder.is_dir():
                continue
            transcript = sess_folder / ".system_generated" / "logs" / "transcript.jsonl"
            if not transcript.exists():
                continue
            
            mtime = transcript.stat().st_mtime
            if mtime < two_weeks_ago:
                continue

            turns_toks = []
            try:
                with open(transcript, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            step = json.loads(line)
                            c = step.get("content", "")
                            if c:
                                turns_toks.append(int(len(c.split()) * 1.3))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

            if not turns_toks:
                continue

            brain_sessions += 1
            brain_total_turns += len(turns_toks)
            brain_raw_tokens += sum(turns_toks)

            # Standard cumulative
            hist = 0
            for t in turns_toks:
                hist += t
                brain_standard_cumulative += hist

            # ULM bounded
            for i in range(len(turns_toks)):
                win_start = max(0, i - 3)
                win_toks = sum(turns_toks[win_start:i+1])
                brain_ulm_cumulative += min(4500, 1500 + win_toks)

    print(f"\n[1] SYNC_STATE.DB AUDIT (Persistent Conversations):")
    print(f"  - Sessions active in last 14 days: {len(sessions_db):,}")
    print(f"  - Conversational messages processed: {db_total_turns:,}")
    print(f"  - Raw isolated content tokens: {db_raw_tokens:,}")
    print(f"  - Without ULM (Unbounded quadratic resends): {db_standard_cumulative:,} tokens")
    print(f"  - With ULM (Bounded 4.5k rolling window): {db_ulm_cumulative:,} tokens")
    if db_standard_cumulative > 0:
        db_saved = db_standard_cumulative - db_ulm_cumulative
        db_pct = (db_saved / db_standard_cumulative) * 100
        print(f"  -> Tokens saved on DB chats: {db_saved:,} ({db_pct:.1f}% reduction)")

    print(f"\n[2] ANTIGRAVITY BRAIN TRANSCRIPTS AUDIT (Live Workstation Sessions):")
    print(f"  - Sessions active in last 14 days: {brain_sessions:,}")
    print(f"  - Total trajectory steps/turns: {brain_total_turns:,}")
    print(f"  - Raw generated tokens: {brain_raw_tokens:,}")
    print(f"  - Without ULM (Naive cumulative history): {brain_standard_cumulative:,} tokens")
    print(f"  - With ULM (Bounded rolling context): {brain_ulm_cumulative:,} tokens")
    if brain_standard_cumulative > 0:
        brain_saved = brain_standard_cumulative - brain_ulm_cumulative
        brain_pct = (brain_saved / brain_standard_cumulative) * 100
        print(f"  -> Tokens saved on Brain sessions: {brain_saved:,} ({brain_pct:.1f}% reduction)")

    # Aggregate Total
    grand_standard = db_standard_cumulative + brain_standard_cumulative
    grand_ulm = db_ulm_cumulative + brain_ulm_cumulative
    grand_saved = grand_standard - grand_ulm
    grand_pct = (grand_saved / grand_standard) * 100 if grand_standard > 0 else 0

    # Pricing & Quota Equivalent
    # Gemini 1.5/2.5/Pro pricing ~ $1.25 / 1M tokens (input prompt tokens)
    # Gemini Pro Free / Pro Tier limit: 50 requests/day or quota buckets
    dollar_equivalent = (grand_saved / 1_000_000) * 1.25

    print("\n" + "=" * 60)
    print(" 🏆 GRAND TOTAL 14-DAY SAVINGS REPORT:")
    print("=" * 60)
    print(f"  - Total tokens that WOULD have been billed: {grand_standard:,}")
    print(f"  - Actual bounded tokens billed under ULM:   {grand_ulm:,}")
    print(f"  - TOTAL TOKENS SAVED:                      {grand_saved:,}")
    print(f"  - Overall Quota Compression Ratio:         {grand_pct:.1f}% SAVED")
    print(f"  - Est. Cloud API Value Conserved:          ~${dollar_equivalent:.2f} USD")
    print("=" * 60)

if __name__ == "__main__":
    run_audit()
