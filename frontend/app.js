// Vespera ULM Control Center SPA JavaScript Engine

let allSessions = [];
let allFacts = [];
let allProfileMetrics = [];

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadDashboardData();
    startLogPolling();
});

// Navigation Tab Switching
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-item');
    const tabViews = document.querySelectorAll('.tab-view');
    const titleEl = document.getElementById('current-view-title');
    const descEl = document.getElementById('current-view-desc');

    const headers = {
        'dashboard': { title: 'Overview Dashboard', desc: 'Live cognitive metrics, session telemetry, and database status.' },
        'sessions': { title: 'Chat Sessions Explorer', desc: 'Browse synced chat session transcripts, message turns, and summaries.' },
        'facts': { title: 'Semantic Facts Core', desc: 'Inspect, search, edit, or add long-term environment and persona facts.' },
        'profile': { title: 'Developer Profile Matrix', desc: 'Cognitive behavioral telemetry (Milestones, Strengths, Weaknesses, Habits).' },
        'settings': { title: 'Preferences & LLM Configurations', desc: 'Manage local Ollama models, cloud credentials, and sync settings.' },
        'actions': { title: 'Pipeline Execution & Event Logs', desc: 'Trigger manual sync workflows and view live event terminal logs.' }
    };

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            navButtons.forEach(b => b.classList.remove('active'));
            tabViews.forEach(v => v.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`view-${targetTab}`).classList.add('active');

            if (headers[targetTab]) {
                titleEl.textContent = headers[targetTab].title;
                descEl.textContent = headers[targetTab].desc;
            }

            // Lazy load tab data
            if (targetTab === 'sessions') loadSessions();
            if (targetTab === 'facts') loadFacts();
            if (targetTab === 'profile') loadProfile();
            if (targetTab === 'settings') loadPreferences();
            if (targetTab === 'actions') loadLogs();
        });
    });
}

// 1. Dashboard Overview Data
async function loadDashboardData() {
    try {
        const res = await fetch('/api/stats');
        const stats = await res.json();

        document.getElementById('sb-journal').textContent = stats.journal_mode;
        document.getElementById('hb-model').textContent = stats.llm_model;
        document.getElementById('hb-facts').textContent = stats.total_facts;
        document.getElementById('hb-metrics').textContent = stats.total_profile_metrics;

        document.getElementById('card-sessions').textContent = stats.total_sessions;
        document.getElementById('card-messages').textContent = stats.total_messages;
        document.getElementById('card-facts').textContent = stats.total_facts;
        document.getElementById('card-profile').textContent = stats.total_profile_metrics;

        document.getElementById('env-db-path').textContent = stats.db_path;
        document.getElementById('env-db-size').textContent = stats.db_size;
        document.getElementById('env-provider').textContent = stats.llm_provider.toUpperCase();
    } catch (e) {
        showToast('Error loading dashboard stats', 'error');
    }
}

// 2. Chat Sessions Explorer
async function loadSessions() {
    try {
        const res = await fetch('/api/sessions?limit=100');
        const data = await res.json();
        allSessions = data.sessions || [];

        // Populate Tag Filter
        const tagFilter = document.getElementById('session-tag-filter');
        const tags = [...new Set(allSessions.map(s => s.project_tag).filter(Boolean))];
        tagFilter.innerHTML = '<option value="">All Project Tags</option>';
        tags.forEach(t => {
            tagFilter.innerHTML += `<option value="${t}">${t}</option>`;
        });

        renderSessionsTable(allSessions);
    } catch (e) {
        showToast('Error loading sessions', 'error');
    }
}

function renderSessionsTable(sessions) {
    const tbody = document.getElementById('sessions-tbody');
    if (!sessions.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No chat sessions found.</td></tr>';
        return;
    }

    tbody.innerHTML = sessions.map(s => {
        const shortId = s.session_id.substring(0, 12);
        const tagBadge = s.project_tag ? `<span class="badge glow-purple">${s.project_tag}</span>` : '<span class="text-muted">None</span>';
        const lastMutated = s.updated_at ? s.updated_at.split('T')[0] : 'N/A';
        const summaryText = s.summary ? s.summary.substring(0, 80) + '...' : '<span class="text-muted">No summary</span>';

        return `
            <tr>
                <td class="code-font">${shortId}...</td>
                <td>${tagBadge}</td>
                <td>${lastMutated}</td>
                <td>${s.topics || 'General'}</td>
                <td>${summaryText}</td>
                <td>
                    <button class="btn btn-outline" style="padding:6px 12px; font-size:11px;" onclick="viewTranscript('${s.session_id}')">
                        💬 Open Transcript
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function filterSessions() {
    const query = document.getElementById('session-search').value.toLowerCase();
    const tag = document.getElementById('session-tag-filter').value;

    const filtered = allSessions.filter(s => {
        const matchTag = !tag || s.project_tag === tag;
        const matchQuery = !query || 
            (s.session_id && s.session_id.toLowerCase().includes(query)) ||
            (s.topics && s.topics.toLowerCase().includes(query)) ||
            (s.summary && s.summary.toLowerCase().includes(query));
        return matchTag && matchQuery;
    });

    renderSessionsTable(filtered);
}

async function viewTranscript(sessionId) {
    const modal = document.getElementById('transcript-modal');
    const body = document.getElementById('modal-transcript-body');
    const title = document.getElementById('modal-session-title');

    title.textContent = `Transcript: ${sessionId.substring(0, 16)}...`;
    body.innerHTML = '<div class="text-center">Loading turns...</div>';
    modal.classList.remove('hidden');

    try {
        const res = await fetch(`/api/sessions/${sessionId}/messages`);
        const data = await res.json();
        const msgs = data.messages || [];

        if (!msgs.length) {
            body.innerHTML = '<div class="text-center">No messages recorded for this session.</div>';
            return;
        }

        body.innerHTML = msgs.map(m => {
            const isPilot = (m.role === 'Pilot' || m.role === 'user');
            const roleClass = isPilot ? 'pilot' : 'vespera';
            const authorName = isPilot ? 'Pilot (Bobby)' : 'Vespera Caligo';

            let cleanContent = m.content.replace(/<USER_REQUEST>/g, '').replace(/<\/USER_REQUEST>/g, '').trim();

            return `
                <div class="transcript-message ${roleClass}">
                    <div class="msg-author">
                        <span>${authorName}</span>
                        <span class="text-muted" style="font-size:11px;">${m.created_at || ''}</span>
                    </div>
                    <div class="msg-text">${escapeHtml(cleanContent)}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        body.innerHTML = '<div class="text-center" style="color:var(--accent-red)">Error loading transcript.</div>';
    }
}

function closeTranscriptModal() {
    document.getElementById('transcript-modal').classList.add('hidden');
}

// 3. Semantic Facts Core
async function loadFacts() {
    try {
        const res = await fetch('/api/facts?limit=200');
        const data = await res.json();
        allFacts = data.facts || [];
        renderFactsTable(allFacts);
    } catch (e) {
        showToast('Error loading facts', 'error');
    }
}

function renderFactsTable(facts) {
    const tbody = document.getElementById('facts-tbody');
    if (!facts.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No facts found.</td></tr>';
        return;
    }

    tbody.innerHTML = facts.map(f => {
        const confPct = (f.confidence * 100).toFixed(0) + '%';
        const tag = f.project_tag || 'Global';
        const lastSeen = f.last_seen ? f.last_seen.split('T')[0] : 'N/A';

        return `
            <tr>
                <td class="code-font">${f.fact_id.substring(0, 10)}...</td>
                <td><span class="badge glow-cyan">${f.category.toUpperCase()}</span></td>
                <td>${escapeHtml(f.fact)}</td>
                <td><strong style="color:var(--accent-green)">${confPct}</strong></td>
                <td>${tag}</td>
                <td>${lastSeen}</td>
                <td>
                    <button class="btn btn-outline" style="padding:4px 8px; font-size:11px; color:var(--accent-red); border-color:rgba(239,68,68,0.3);" onclick="deleteFact('${f.fact_id}')">
                        🗑️ Delete
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function filterFacts() {
    const query = document.getElementById('facts-search').value.toLowerCase();
    const cat = document.getElementById('facts-cat-filter').value;

    const filtered = allFacts.filter(f => {
        const matchCat = !cat || f.category === cat;
        const matchQuery = !query || (f.fact && f.fact.toLowerCase().includes(query));
        return matchCat && matchQuery;
    });

    renderFactsTable(filtered);
}

function openAddFactModal() {
    document.getElementById('fact-modal').classList.remove('hidden');
}

function closeFactModal() {
    document.getElementById('fact-modal').classList.add('hidden');
}

async function submitNewFact() {
    const cat = document.getElementById('new-fact-cat').value;
    const text = document.getElementById('new-fact-text').value.trim();
    const conf = parseFloat(document.getElementById('new-fact-conf').value);

    if (!text) {
        showToast('Please enter a fact description', 'error');
        return;
    }

    try {
        const res = await fetch('/api/facts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fact: text, category: cat, confidence: conf })
        });

        if (res.ok) {
            showToast('Fact added successfully!');
            closeFactModal();
            document.getElementById('new-fact-text').value = '';
            loadFacts();
            loadDashboardData();
        }
    } catch (e) {
        showToast('Failed to add fact', 'error');
    }
}

async function deleteFact(factId) {
    if (!confirm('Are you sure you want to delete this fact from memory?')) return;
    try {
        const res = await fetch(`/api/facts/${factId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Fact deleted.');
            loadFacts();
            loadDashboardData();
        }
    } catch (e) {
        showToast('Failed to delete fact', 'error');
    }
}

// 4. Developer Profile Matrix
async function loadProfile() {
    try {
        const res = await fetch('/api/profile?limit=200');
        const data = await res.json();
        allProfileMetrics = data.profile || [];
        renderProfileTable(allProfileMetrics);
    } catch (e) {
        showToast('Error loading developer profile', 'error');
    }
}

function renderProfileTable(profile) {
    const tbody = document.getElementById('profile-tbody');
    if (!profile.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No profile metrics found.</td></tr>';
        return;
    }

    tbody.innerHTML = profile.map(p => {
        const confPct = p.confidence ? (p.confidence * 100).toFixed(0) + '%' : 'N/A';
        const tag = p.project_tag || 'Global';
        const lastObserved = p.last_seen ? p.last_seen.split('T')[0] : 'N/A';

        return `
            <tr>
                <td><span class="badge glow-purple">${p.category.toUpperCase()}</span></td>
                <td class="code-font" style="color:var(--accent-yellow);">${escapeHtml(p.name)}</td>
                <td>${escapeHtml(p.description)}</td>
                <td><strong style="color:var(--accent-green)">${confPct}</strong></td>
                <td><span class="badge glow-cyan">${p.frequency}</span></td>
                <td>${tag}</td>
                <td>${lastObserved}</td>
            </tr>
        `;
    }).join('');
}

function filterProfile() {
    const query = document.getElementById('profile-search').value.toLowerCase();
    const cat = document.getElementById('profile-cat-filter').value;

    const filtered = allProfileMetrics.filter(p => {
        const matchCat = !cat || p.category === cat;
        const matchQuery = !query || 
            (p.name && p.name.toLowerCase().includes(query)) ||
            (p.description && p.description.toLowerCase().includes(query));
        return matchCat && matchQuery;
    });

    renderProfileTable(filtered);
}

// 5. Preferences & Settings
async function loadPreferences() {
    try {
        const res = await fetch('/api/preferences');
        const data = await res.json();
        const prefs = data.preferences || {};

        if (prefs.llm_provider) document.getElementById('pref-provider').value = prefs.llm_provider;
        if (prefs.llm_model) document.getElementById('pref-model').value = prefs.llm_model;
        if (prefs.ollama_endpoint) document.getElementById('pref-endpoint').value = prefs.ollama_endpoint;
        if (prefs.gemini_api_key) document.getElementById('pref-gemini-key').value = prefs.gemini_api_key;
        if (prefs.google_docs_webhook_url) document.getElementById('pref-webhook-url').value = prefs.google_docs_webhook_url;
    } catch (e) {
        showToast('Error loading preferences', 'error');
    }
}

async function savePreferences() {
    const provider = document.getElementById('pref-provider').value;
    const model = document.getElementById('pref-model').value.trim();
    const endpoint = document.getElementById('pref-endpoint').value.trim();
    const geminiKey = document.getElementById('pref-gemini-key').value.trim();
    const webhookUrl = document.getElementById('pref-webhook-url').value.trim();

    const pairs = [
        { key: 'llm_provider', value: provider },
        { key: 'llm_model', value: model },
        { key: 'ollama_endpoint', value: endpoint },
        { key: 'gemini_api_key', value: geminiKey },
        { key: 'google_docs_webhook_url', value: webhookUrl }
    ];

    try {
        for (const p of pairs) {
            await fetch('/api/preferences', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(p)
            });
        }
        showToast('Preferences saved successfully!');
        loadDashboardData();
    } catch (e) {
        showToast('Failed to save preferences', 'error');
    }
}

async function scanOllamaModels() {
    const container = document.getElementById('ollama-models-dropdown');
    container.innerHTML = 'Scanning Ollama...';
    container.classList.remove('hidden');

    try {
        const res = await fetch('/api/ollama/models');
        const data = await res.json();

        if (data.status === 'online' && data.models.length) {
            container.innerHTML = data.models.map(m => `
                <div class="model-chip" onclick="selectModel('${m}')">${m}</div>
            `).join('');
        } else {
            container.innerHTML = `<span style="color:var(--accent-red);">Ollama Offline or No Models (${data.error || ''})</span>`;
        }
    } catch (e) {
        container.innerHTML = '<span style="color:var(--accent-red);">Failed to connect to Ollama.</span>';
    }
}

function selectModel(modelName) {
    document.getElementById('pref-model').value = modelName;
    document.getElementById('ollama-models-dropdown').classList.add('hidden');
    showToast(`Selected model: ${modelName}`);
}

// 6. Pipeline Action Drivers
async function triggerAction(actionType) {
    showToast(`Launching ${actionType} action...`);

    try {
        const res = await fetch(`/api/actions/${actionType}`, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
            showToast(`${actionType.toUpperCase()} completed!`);
            loadDashboardData();
            loadLogs();
        } else {
            showToast(`Action failed: ${data.detail}`, 'error');
        }
    } catch (e) {
        showToast(`Execution error for ${actionType}`, 'error');
    }
}

// Live Log Terminal Polling
async function loadLogs() {
    try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        const consoleEl = document.getElementById('log-console');

        if (data.logs && data.logs.length) {
            consoleEl.innerHTML = data.logs.map(l => `<div class="log-entry">${escapeHtml(l)}</div>`).join('');
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }
    } catch (e) {}
}

function startLogPolling() {
    setInterval(() => {
        loadLogs();
    }, 3000);
}

// Helper Utilities
function showToast(msg, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.style.background = type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(16, 185, 129, 0.9)';
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
