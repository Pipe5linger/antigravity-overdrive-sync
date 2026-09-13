# 📊 ULM Performance & Telemetry Benchmark

This document details the stress-testing parameters, database optimization history, and telemetry results for the **Universal Local Memory (ULM)** modular pipeline. 

A primary goal of this framework is to provide high-performance conversation synchronization while maintaining an extremely small, predictable resource footprint on the host system.

---

## 📈 SQLite vs. YAML Monolithic Benchmark (Commit `442fec9`)

To prove the architectural advantage of our SQLite-backed context cache, we ran a telemetry stress test against the legacy YAML monolithic approach using **1,000 distinct chat sessions, 10,000 message logs, and 5,000 duplicate injection attempts**:

| Telemetry Metric | Legacy YAML Monolith | **New SQLite Database Engine 🚀** | Performance Verdict |
| :--- | :--- | :--- | :--- |
| **Peak Memory Allocation** | `248.811 MB` | **`0.155 MB`** (159 KB) | **99.9% Memory Reduction** (Indexed SQLite prevents in-RAM key merges) |
| **Context Query Latency** | `37,524 ms` (37s) | **`7.517 ms`** | **99.9% Latency Speedup** (Retrieval is mathematically instantaneous) |
| **Storage Footprint** | `11.30 MB` (Raw text files) | **`2.63 MB`** (Indexed binary) | **76% Disk Space Compression** (Highly normalized relational indexing) |
| **Deduplication Strategy** | Manual key scans | **Deterministic SHA-256 Hashing** | **Idempotent** (skipped 5,000 identical items silently at DB level) |

---

## 🛠️ The Stress Test Setup

The benchmarks are executed using our local test harness scripts inside the `/benchmark` directory:

1. **`benchmark/stress_test.py` (Legacy YAML):** Generates 99 standard sessions and a MONSTER 100k line transcript, parsing it in a single stream to measure high-water memory bounds.
2. **`benchmark/stress_test_sqlite.py` (New Database):** Generates 10,000 raw message rows, hammers the SQLite `INSERT OR IGNORE` deduplication code with 5,000 immediate duplicates, injects 500 profile preferences/facts, and runs a sub-10ms context join query to measure production latency.

---

## 🧠 Why ULM’s Relational Database Cache Wins

Traditional AI context engines load entire log directories or transcripts directly into RAM to parse them (e.g. `json.load()`). Under heavy usage, this creates a massive spike in memory overhead, leading to extensive paging, system lag, and eventual **OOM (Out Of Memory)** crashes.

ULM completely eliminates this single point of failure (SPOF) using **Layered Memory Storage**:
* **Layer 1: Lossless Raw Archive (Messages Table)** - Stores every single message turn on disk, queryable on demand, with a flat memory footprint of **159 KB**.
* **Layer 2: Distilled Working Memory (Facts & Preferences Tables)** - Holds high-density, semantic context summaries that are injected into active LLM system prompts without token bloating or persona drift.

---

## 🚀 Running the Benchmarks Locally

You can replicate these exact telemetry measurements on your own machine.

1. Navigate to the benchmark directory:
   ```bash
   cd benchmark
   ```

2. Run the SQLite telemetry test suite:
   ```bash
   python stress_test_sqlite.py
   ```

3. Upon completion, the harness will output your active execution time, peak memory usage, and clean up the temporary test database automatically.
