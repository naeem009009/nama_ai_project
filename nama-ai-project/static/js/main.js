/* ============================================================
   Nama AI — Auth / Landing Page Logic
   ============================================================ */

// ---------- Utilities ----------

function getEl(id) {
    return document.getElementById(id);
}

function showToast(message, type) {
    const toast = getEl("auth-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.className = "auth-toast " + type;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 4000);
}

function setLoading(form, loading) {
    const btn = form.querySelector(".btn-auth-submit");
    const spinner = btn.querySelector(".btn-spinner");
    btn.disabled = loading;
    if (spinner) spinner.classList.toggle("hidden", !loading);
}

// ---------- Tab Switching ----------

function initTabs() {
    const tabs = document.querySelectorAll(".auth-tab");
    const forms = {
        login: getEl("login-form"),
        signup: getEl("signup-form"),
    };

    function switchTab(tabId) {
        tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === tabId));
        Object.entries(forms).forEach(([id, form]) => {
            if (!form) return;
            form.classList.toggle("active-form", id === tabId);
        });
        // Clear any toast on tab switch
        const toast = getEl("auth-toast");
        if (toast) toast.classList.add("hidden");
    }

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });

    // Links inside form redirect text
    document.querySelectorAll(".auth-redirect a[data-tab]").forEach((link) => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            switchTab(link.dataset.tab);
        });
    });
}

// ---------- API calls ----------

async function apiPost(url, data) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    const json = await res.json();
    return { ok: res.ok, status: res.status, data: json };
}

// ---------- Login ----------

function initLogin() {
    const form = getEl("login-form");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = getEl("login-username").value.trim();
        const password = getEl("login-password").value;

        if (!username || !password) {
            showToast("Please fill in all fields.", "error");
            return;
        }

        setLoading(form, true);
        const { ok, data } = await apiPost("/api/login", { username, password });
        setLoading(form, false);

        if (ok) {
            window.location.href = "/chat";
        } else {
            showToast(data.detail || "Login failed. Please try again.", "error");
        }
    });
}

// ---------- Sign Up ----------

function initSignup() {
    const form = getEl("signup-form");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = getEl("signup-username").value.trim();
        const email = getEl("signup-email").value.trim();
        const password = getEl("signup-password").value;
        const confirm = getEl("signup-confirm").value;

        // Client-side validation
        if (!username || !email || !password || !confirm) {
            showToast("All fields are required.", "error");
            return;
        }
        if (username.length < 3) {
            showToast("Username must be at least 3 characters.", "error");
            return;
        }
        if (password.length < 6) {
            showToast("Password must be at least 6 characters.", "error");
            return;
        }
        if (password !== confirm) {
            showToast("Passwords do not match.", "error");
            return;
        }

        setLoading(form, true);
        const { ok, data } = await apiPost("/api/register", {
            username,
            email,
            password,
            confirm_password: confirm,
        });
        setLoading(form, false);

        if (ok) {
            showToast("Account created! Redirecting...", "success");
            setTimeout(() => {
                window.location.href = "/chat";
            }, 800);
        } else {
            showToast(data.detail || "Registration failed.", "error");
        }
    });
}

// ---------- Logout (chat page) ----------

function initLogout() {
    const btn = getEl("logout-btn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
        await apiPost("/api/logout", {});
        window.location.href = "/";
    });
}

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initLogin();
    initSignup();
    initLogout();
});
