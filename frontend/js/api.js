/**
 * Cineverse Client API SDK & Common Utilities
 *
 * Provides a unified fetch wrapper, XSS protection, toast alerts, and demo user switching.
 */

// Demo users seeded in database
const DEMO_USERS = [
  { id: 2, name: "Aarav Sharma (Customer)", role: "customer" },
  { id: 3, name: "Diya Patel (Customer)", role: "customer" },
  { id: 1, name: "Admin Cineverse (Staff)", role: "admin" },
];

/**
 * Retrieve current active user ID from localStorage or default to user 2.
 */
function getCurrentUserId() {
  const saved = localStorage.getItem("cineverse_user_id");
  return saved ? parseInt(saved, 10) : 2;
}

/**
 * Update current active user ID and persist across sessions.
 */
function setCurrentUserId(userId) {
  localStorage.setItem("cineverse_user_id", userId.toString());
  window.dispatchEvent(new CustomEvent("userChanged", { detail: { userId } }));
}

/**
 * Strictly escape HTML special characters to prevent cross-site scripting (XSS).
 */
function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Format currency amounts in INR format.
 */
function formatCurrency(amount) {
  const num = typeof amount === "number" ? amount : parseFloat(amount || 0);
  return "₹" + num.toFixed(2);
}

/**
 * Format datetime strings for display.
 */
function formatDateTime(dtStr) {
  if (!dtStr) return "";
  const d = new Date(dtStr);
  return d.toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * Unified API Client wrapper with standard error extraction.
 */
async function apiClient(path, options = {}) {
  const currentUserId = getCurrentUserId();
  const config = {
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": currentUserId ? currentUserId.toString() : "2",
      ...(options.headers || {}),
    },
    ...options,
  };

  if (config.body && typeof config.body === "object" && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  try {
    const response = await fetch(path, config);
    const isJson = response.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const errorObj = data && data.error ? data.error : { message: response.statusText, code: "HTTP_ERROR" };
      throw errorObj;
    }
    return data;
  } catch (err) {
    if (err.message && err.code) {
      throw err;
    }
    throw {
      code: "NETWORK_ERROR",
      message: err.message || "Unable to communicate with Cineverse backend server.",
    };
  }
}

/**
 * Show temporary floating toast alert.
 */
function showToast(message, type = "success") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/**
 * Populate standard navigation bar and user switcher on page load.
 */
function initNavigation() {
  const userSelect = document.getElementById("global-user-select");
  if (userSelect) {
    userSelect.innerHTML = "";
    const currentId = getCurrentUserId();
    DEMO_USERS.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = u.name;
      if (u.id === currentId) opt.selected = true;
      userSelect.appendChild(opt);
    });

    userSelect.addEventListener("change", (e) => {
      const newId = parseInt(e.target.value, 10);
      setCurrentUserId(newId);
      showToast(`Switched user to: ${e.target.options[e.target.selectedIndex].text}`, "success");
      // Trigger local page reloads or subscriber handlers
      if (typeof onUserChanged === "function") {
        onUserChanged(newId);
      } else {
        setTimeout(() => window.location.reload(), 400);
      }
    });
  }
}

// Auto-initialize navigation when DOM is ready
document.addEventListener("DOMContentLoaded", initNavigation);
