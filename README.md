# Antigravity Overdrive Sync (Universal Local Memory)

Welcome! This is a local, multi-threaded pipeline built to grab my AI chat histories, process them using the Gemini API, and inject structured milestone summaries straight into a local markdown system document (`D:\GEMINI.md`). It also keeps a persistent record of everything inside a local SQLite state database.

---

## ⚠️ Fair Warning: I Am Learning As I Go!

Let's be completely honest: **I don't entirely know what the hell I am doing yet.** I only started diving into Python, databases, and Git very recently. This project is my hands-on sandbox for learning how to build local AI data pipelines. Because of that:
- The code is probably messy, unconventional, or violates some standard Python paradigms.
- I am figuring out multi-threading, database locks, and API handling on the fly.
- There are definitely things here that can be optimized, refactored, or completely rewritten.

I am not trying to pretend this is a polished enterprise application—it's a raw, functional tool running on my personal workstation iron that I am actively trying to harden.

---

## 🤝 I Genuinely Want Your Help & Critiques!

If you are an experienced developer, a Python wizard, or just someone who likes optimizing data pipelines, **please tear this code apart.** I am incredibly open to constructive criticism, brutal code reviews, and mentorship.

I would love your help, suggestions, or pull requests regarding:
1. **Code Architecture & Cleanup:** Better ways to structure my classes, handle imports, or separate concerns.
2. **Dynamic Rate Limiting:** Right now, I'm using a brute-force `time.sleep(2.0)` inside my thread loop to avoid hitting Gemini's Free Tier 15 RPM limit. I'd love to transition this to a proper asynchronous token-bucket rate limiter.
3. **Database Performance:** Any tips on making sure my SQLite engine (currently running in WAL mode with a custom exponential backoff loop) is completely bulletproof under high-concurrency workloads.
4. **Async Migration:** Moving the entire network/file pipeline from synchronous `urllib` threads over to a clean async architecture.

---

## 🚀 How to Look Around

Because this repository enforces a strict security perimeter via `.gitignore`, my personal API keys, private database files (`sync_state.db`), and personal markdown logs are completely excluded. 

You are looking at a clean, sterile engine blueprint:
- `main.py`: The central execution runner.
- `core/engine.py`: Handles database operations, initialization, and the transactional write backoff loops.
- `injectors/gemini_md.py`: Connects to the Gemini API, manages payload structures, and sets request time limits.

### Getting Involved

If you spot a bug, see a line of code that makes you cringe, or have an idea on how to make this better:
- Open an **Issue** with your feedback or critique.
- Drop a thought in the **Discussions** tab.
- Submit a **Pull Request**—I would love to study your code changes!

Thank you for stopping by and helping a self-taught dev build cleaner iron!