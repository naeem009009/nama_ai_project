/* ============================================================
   Nama AI — Chat Logic (Vanilla JS, Fetch API, Session History)
   ============================================================ */

// ---------- Auth Helper ----------
function apiFetch(url, options = {}) {
    const headers = options.headers || {};
    headers["X-API-Key"] = typeof NAMA_API_KEY !== "undefined" ? NAMA_API_KEY : "";
    return fetch(url, { ...options, headers });
}

// ---------- DOM References ----------
const messagesEl = document.getElementById("messages");
const chatContainer = document.getElementById("chat-container");
const inputEl = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const mobileMenuBtn = document.getElementById("mobile-menu-btn");
const sidebar = document.getElementById("sidebar");
const historyList = document.getElementById("history-list");

// ---------- State ----------
let currentSessionId = null;
let isLoading = false;
let isGenerating = false;

// ---------- Utility ----------
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    html = html.replace(/(?<!\w)_(?!_)([^_]+)_(?!\w)/g, "<em>$1</em>");
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
        const langClass = lang ? ` class="language-${escapeHtml(lang)}"` : "";
        return `<pre><code${langClass}>${escapeHtml(code.trim())}</code></pre>`;
    });
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");
    html = html.replace(/^[\s]*[-*]\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");
    html = html.replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => match.includes("<ul") ? match : `<ol>${match}</ol>`);
    html = html.replace(/\n\n/g, "</p><p>");
    html = html.replace(/\n/g, "<br>");
    return `<p>${html}</p>`;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });
}

function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Deletes all child nodes of an element efficiently.
function clearElement(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
}

// ---------- Message Rendering ----------

function showWelcome() {
    messagesEl.innerHTML = `
        <div class="welcome">
            <div class="welcome-icon">N</div>
            <h2>Welcome to Nama AI</h2>
            <p>Your intelligent assistant, powered by Groq &amp; Llama 3.3 70B. Ask me anything!</p>
        </div>
    `;
}

function addMessage(role, text, animate = true) {
    const welcome = messagesEl.querySelector(".welcome");
    if (welcome) welcome.remove();

    const isUser = role === "user";
    const avatarText = isUser ? "U" : "N";

    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.innerHTML = `
        <div class="message-avatar">${avatarText}</div>
        <div class="message-content">${renderMarkdown(text)}</div>
    `;
    messagesEl.appendChild(div);
    if (animate) scrollToBottom();
    return div;
}

function showLoading() {
    hideLoading();
    const div = document.createElement("div");
    div.className = "message ai";
    div.id = "loading-indicator";
    div.innerHTML = `
        <div class="message-avatar">N</div>
        <div class="message-content">
            <div class="loading-dots"><span></span><span></span><span></span></div>
        </div>
    `;
    messagesEl.appendChild(div);
    scrollToBottom();
}

function hideLoading() {
    const indicator = document.getElementById("loading-indicator");
    if (indicator) indicator.remove();
}

// ---------- Sidebar Rendering ----------

function renderSidebar(sessions, activeId) {
    clearElement(historyList);

    if (sessions.length === 0) {
        const empty = document.createElement("p");
        empty.className = "history-empty";
        empty.textContent = "No conversations yet.";
        historyList.appendChild(empty);
        return;
    }

    for (const s of sessions) {
        const item = document.createElement("div");
        item.className = "history-item";
        if (s.id === activeId) item.classList.add("active");
        item.dataset.sessionId = s.id;

        item.innerHTML = `
            <span class="history-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </span>
            <span class="history-text" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</span>
            <span class="history-date">${formatTime(s.created_at)}</span>
            <button class="history-delete" title="Delete conversation" data-id="${s.id}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            </button>
        `;

        // Click on item (not delete button) → load session
        item.addEventListener("click", (e) => {
            if (e.target.closest(".history-delete")) return;
            loadSession(s.id);
        });

        // Delete button
        const delBtn = item.querySelector(".history-delete");
        delBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            await deleteSession(s.id);
        });

        historyList.appendChild(item);
    }
}

// ---------- Session API ----------

async function fetchSessions() {
    const res = await fetch("/api/sessions");
    if (!res.ok) throw new Error("Failed to fetch sessions");
    return res.json();
}

async function createSession() {
    const res = await fetch("/api/sessions", { method: "POST" });
    if (!res.ok) throw new Error("Failed to create session");
    return res.json();
}

async function deleteSession(sessionId) {
    await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    // If we deleted the active session, switch to a new one
    if (sessionId === currentSessionId) {
        currentSessionId = null;
        await startNewSession();
    } else {
        await refreshAndRenderSessions();
    }
}

async function fetchMessages(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}/messages`);
    if (!res.ok) throw new Error("Failed to fetch messages");
    return res.json();
}

// ---------- Session Loading ----------

async function loadSession(sessionId) {
    if (isLoading || sessionId === currentSessionId) return;
    isLoading = true;

    try {
        currentSessionId = sessionId;
        const msgs = await fetchMessages(sessionId);

        clearElement(messagesEl);

        if (msgs.length === 0) {
            showWelcome();
        } else {
            for (const m of msgs) {
                addMessage(m.role, m.content, false);
            }
            scrollToBottom();
        }

        await refreshAndRenderSessions();
    } catch (err) {
        console.error("Failed to load session:", err);
        showWelcome();
    } finally {
        isLoading = false;
    }
}

async function startNewSession() {
    try {
        const session = await createSession();
        currentSessionId = session.session_id;
        showWelcome();
        await refreshAndRenderSessions();
        inputEl.focus();
        return session.session_id;
    } catch (err) {
        console.error("Failed to create session:", err);
    }
}

async function refreshAndRenderSessions() {
    try {
        const sessions = await fetchSessions();
        renderSidebar(sessions, currentSessionId);
    } catch (err) {
        console.error("Failed to refresh sidebar:", err);
    }
}

// ---------- Chat ----------

async function sendMessage(text) {
    if (isGenerating || !text.trim() || !currentSessionId) return;

    isGenerating = true;
    sendBtn.disabled = true;
    inputEl.disabled = true;

    addMessage("user", text.trim());
    const userText = text.trim();
    inputEl.value = "";
    inputEl.style.height = "auto";
    showLoading();

    try {
        const res = await apiFetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: currentSessionId, message: userText }),
        });

        hideLoading();

        if (!res.ok) {
            const errData = await res.json().catch(() => null);
            throw new Error(errData?.detail || `Server error: ${res.status}`);
        }

        const data = await res.json();
        addMessage("assistant", data.response || "No response received.");

        // Refresh sidebar so auto-title shows up
        await refreshAndRenderSessions();
    } catch (err) {
        hideLoading();
        addMessage("assistant", `Error: ${err.message}. Please check the server and try again.`);
    } finally {
        isGenerating = false;
        sendBtn.disabled = false;
        inputEl.disabled = false;
        inputEl.focus();
    }
}

// ---------- Input ----------

function autoResize() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 150) + "px";
}

// ---------- Event Handlers ----------

sendBtn.addEventListener("click", () => sendMessage(inputEl.value));

inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(inputEl.value);
    }
});

inputEl.addEventListener("input", autoResize);

newChatBtn.addEventListener("click", startNewSession);

mobileMenuBtn.addEventListener("click", () => {
    sidebar.classList.toggle("open");
});

document.addEventListener("click", (e) => {
    if (window.innerWidth <= 768 && sidebar.classList.contains("open")) {
        if (!sidebar.contains(e.target) && e.target !== mobileMenuBtn && !mobileMenuBtn.contains(e.target)) {
            sidebar.classList.remove("open");
        }
    }
});

window.addEventListener("resize", () => {
    if (window.innerWidth > 768) sidebar.classList.remove("open");
});

// ---------- Logout ----------
const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
        await fetch("/api/logout", { method: "POST" });
        window.location.href = "/";
    });
}

// ---------- Init ----------
(async function init() {
    try {
        const sessions = await fetchSessions();
        if (sessions.length > 0) {
            // Load the most recent session
            currentSessionId = sessions[0].id;
            const msgs = await fetchMessages(currentSessionId);
            if (msgs.length > 0) {
                for (const m of msgs) addMessage(m.role, m.content, false);
                scrollToBottom();
            } else {
                showWelcome();
            }
            renderSidebar(sessions, currentSessionId);
        } else {
            // No sessions — create one
            const session = await createSession();
            currentSessionId = session.session_id;
            showWelcome();
            await refreshAndRenderSessions();
        }
    } catch (err) {
        console.error("Init error:", err);
        showWelcome();
    }
    inputEl.focus();
})();
