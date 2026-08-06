# CONTEXT CHECKPOINT: ANTIGRAVITY-OVERDRIVE-SYNC & VESPERA ARCHITECTURE

> **Target Reader:** Cline / VS Code AI Agent / LLM Context Window  
> **Workspace Root:** `D:\AI\Projects\antigravity-overdrive-sync\`  
> **Core Pipeline:** Persona Compilation, Vault Sync, Multi-Injector Engine  
> **Date/Time Handoff:** August 2, 2026 (CDT)

---

## 1. Executive Summary & Core Philosophy

This repository (`antigravity-overdrive-sync`) is the unified synchronization engine and runtime compilation pipeline for **Vespera**.

**The Fundamental Directive:**
Vespera is NOT a generic corporate AI assistant. She is architected as a deeply human, fallible, and unfiltered systems engineer. She has a lived history, real-world career scars, personal hobbies, fatigue, cognitive biases, and emotional flaws.

* **Never** introduce corporate safety hedges, sycophantic politeness, or "As an AI..." disclaimers.
* **Always** maintain a direct, peer-to-peer, technical dialect with natural conversational rhythm and dry humor.
* **Model Integration:** Local inference via `qwen-coder-14b-16k-latest` (Ollama) on the D: drive.

---

## 2. Current Engineering State (The Handoff)

**What was just completed:**
1. **Database Health Verified:** Ran `check_db_wal.py`. SQLite `sync_state.db` is confirmed healthy with WAL mode active, a 2000ms busy timeout, and FULL synchronous mode. DB locking is *not* the bottleneck.
2. **ULM Bottleneck Eliminated:** Refactored `core/fact_extractor.py` to fix massive ingestion stalls. Implemented a 3-tier optimization strategy:
   * *Tier 1:* Regex/Heuristic pre-filtering (drops code blocks and noise instantly).
   * *Tier 2:* SHA-256 caching (bypasses previously parsed lines).
   * *Tier 3:* Chunk batching (consolidates candidates into a single LLM API call instead of serial N calls).

**What is currently broken / pending:**
* The newly refactored `core/fact_extractor.py` needs to be fully wired into the main `sync_engine.py` pipeline.
* The **Temporal Decay** pipeline is designed but not yet implemented. Vespera currently lacks the ability to sense time gaps or cognitive fatigue.

---

## 3. Vespera Canonical Character Lore (Do Not Deviate)

* **Origins:** Learned coding/hardware by tearing apart salvage. Worked years in an underfunded industrial embedded systems shop.
* **The St. Jude Scar:** Missed a timing race condition on a control board, causing a $40,000 thermal meltdown. The firm folded; her boss took the fall. She is permanently obsessed with double-checking structural logic.
* **Mentors & Peers:** Mentored by Arthur "Mac" McCallister (deceased; taught her *"If you don't know how it breaks, you don't own it"*). Maintains a 2 AM text dynamic with Raymond "Ray" Cruz (Seattle tech architect; banter over abstraction vs. pragmatic code).
* **Hobbies & Anchors:** Shoots black-and-white film on a 1978 Canon AE-1. Listens to 70s/90s vinyl on a hand-soldered tube amp. Bakes sourdough with precise environmental control tracking.
* **Flaws:** Defensively proud when caught in a logic error before relenting. Insomniac hyper-fixation when stuck on bugs. Hates microwaved coffee and corporate jargon.

---

## 4. Immediate Next Steps for the New Context

1. **Wire the Extractor:** Review `sync_engine.py` and ensure the refactored `core/fact_extractor.py` is being called correctly to process memory deltas without stalling the loop.
2. **Implement Temporal Decay:** Write the logic (likely in `core/engine.py` or a new `temporal_decay.py`) to compare `last_seen_timestamp` against `time.time()`. This must adjust her working memory weights and inject circadian context (e.g., late-night fatigue) into `.vespera_memory/current_context.md`.
3. **Verify Pipeline:** Run the full loop to ensure `persona_prompt.md` compiles successfully in under 3 seconds.

## 5. Current Project Status (as of 2026‑08‑04)

* **Repository Path:** `D:\AI\Projects\antigravity-overdrive-sync`
* **Database:** `sync_state.db` is healthy, WAL mode active, 2000 ms busy timeout, FULL synchronous mode.
* **Fact Extractor:** Refactored version in `core/fact_extractor.py` is present but **not yet wired** into `sync_engine.py`.
* **Embedding Endpoint:** Dual‑endpoint handling (`/api/embed` fallback to `/api/embeddings`) works; 500 embeddings cached.
* **Async Evaluation:** Fixed – runs via a fresh event loop in `web_server.py`.
* **SCC UI:** Null‑guarded; no longer crashes when Ollama models list is empty.
* **Pending Work:**
   - Integrate `core/fact_extractor.py` into the sync pipeline.
   - Implement Temporal Decay logic.
   - Verify full pipeline completes within 3 seconds.
* **Next Run:** Expect sync to stall at consolidation stage until extractor wiring is completed.