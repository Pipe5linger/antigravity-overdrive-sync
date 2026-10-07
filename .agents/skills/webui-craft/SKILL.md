---
name: webui-craft
description: Comprehensive engineering guide for crafting, debugging, and maintaining lightweight, high-performance WebUI interfaces, FastAPI server endpoints, and vanilla modern ES6+ frontend scripts.
---

# WebUI Engineering & Script Crafting Guide

## Overview
This skill provides architectural patterns, code templates, and debugging strategies for building responsive, reliable WebUIs without bloated build pipelines (e.g. no `npm`/`webpack` overhead). It is specifically tailored for local AI control centers, dashboards, and tooling interfaces (FastAPI + Vanilla ES6 + Glassmorphic CSS).

---

## 1. Backend Architecture (FastAPI & Async Endpoints)

### A. Non-Blocking Long Operations
Never run blocking CPU-bound or external I/O tasks directly inside async route handlers. Use `BackgroundTasks` or thread pools:
```python
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Control Center")

@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    # Offload execution to avoid blocking event loop
    background_tasks.add_task(run_heavy_sync)
    return {"status": "started", "message": "Sync queued in background"}
```

### B. Real-Time Telemetry & Log Streaming (SSE)
Instead of hammering the server with rapid 100ms HTTP polling, use Server-Sent Events (SSE) or a capped ring buffer:
```python
import asyncio
from fastapi.responses import StreamingResponse

@app.get("/api/logs/stream")
async def stream_logs():
    async def event_generator():
        while True:
            # Yield new logs if available
            log = await get_next_log()
            yield f"data: {json.dumps(log)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 2. Frontend Engineering (Modern Vanilla ES6+ Patterns)

### A. Clean State & API Client Pattern
Avoid spaghetti DOM manipulation. Encapsulate API communication and state management into dedicated modules:

```javascript
// Centralized state container
const AppState = {
    stats: {},
    logs: [],
    activeTab: 'overview',
    subscribers: new Set(),
    
    update(patch) {
        Object.assign(this, patch);
        this.notify();
    },
    subscribe(callback) {
        this.subscribers.add(callback);
    },
    notify() {
        this.subscribers.forEach(cb => cb(this));
    }
};

// Robust API Client with unified error handling
const API = {
    async request(url, options = {}) {
        try {
            const res = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                ...options
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `HTTP ${res.status}: ${res.statusText}`);
            }
            return await res.json();
        } catch (err) {
            UI.showToast(`API Error: ${err.message}`, 'error');
            throw err;
        }
    },
    getStats() { return this.request('/api/stats'); },
    addFact(payload) {
        return this.request('/api/facts', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }
};
```

### B. Event Delegation & Memory Safety
* Never attach anonymous event listeners inside loops. Use event delegation on parent containers.
* Clear all `setInterval` / `setTimeout` references when tearing down views or switching tabs to avoid CPU leaks.

```javascript
// Efficient event delegation on parent container
document.querySelector('#fact-list').addEventListener('click', (event) => {
    const deleteBtn = event.target.closest('[data-action="delete-fact"]');
    if (!deleteBtn) return;
    const factId = deleteBtn.dataset.id;
    confirmDeleteFact(factId);
});
```

---

## 3. Glassmorphic UI & Cybernetic Styling Principles

Modern, high-contrast dark themes should prioritize visual clarity, smooth micro-interactions, and responsive layout grids:

```css
:root {
    --bg-base: #0d0f14;
    --card-bg: rgba(22, 27, 34, 0.75);
    --card-border: rgba(255, 255, 255, 0.08);
    --accent-primary: #8a2be2;
    --accent-glow: rgba(138, 43, 226, 0.35);
    --text-main: #f0f6fc;
    --text-dim: #8b949e;
}

.glass-card {
    background: var(--card-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--card-border);
    border-radius: 10px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    transition: transform 0.2s ease, border-color 0.2s ease;
}

.glass-card:hover {
    border-color: var(--accent-glow);
    transform: translateY(-2px);
}
```

---

## 4. Debugging & Common WebUI Pitfalls

1. **Stale Cache / 304 Not Modified**:
   * When modifying `frontend/app.js` or `frontend/styles.css`, browsers often aggressively cache static assets.
   * *Fix*: Append a cache-buster query parameter in `index.html` during rapid development:
     `<script src="/static/app.js?v=2.0.1"></script>`.
2. **CORS Pitfalls with Separate Dev Ports**:
   * If serving FastAPI on `:8000` and testing through another port, always configure `CORSMiddleware`.
3. **Encoding Crashes in JSON Payloads**:
   * Always verify that text containing emojis, accents, or special symbols is handled with UTF-8 encoding in both FastAPI responses and `fetch()` requests.
4. **Uncaught Async Exceptions**:
   * Wrap top-level async controller calls in try/catch or an async error boundary so the UI never freezes silently in a loading state.
