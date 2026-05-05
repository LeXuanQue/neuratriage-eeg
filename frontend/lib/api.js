// NeuraTriage API client (browser).
// =================================
// Wraps fetch() with JWT, error envelope, and a single source of truth
// for the backend base URL.
//
// Usage:
//   await window.api.login(email, password)        -> { access_token, user, ... }
//   await window.api.me()                          -> user
//   await window.api.health()                      -> { status, version }
//   await window.api.infer({ eeg_path, patient_id, label })
//   window.api.logout()                            // local clear + audit
//
// Env switching:
//   - Vercel deploy: same-origin "/api/*" (relative). Just works.
//   - Cross-origin (e.g. frontend localhost:8000 → API localhost:8501):
//        <script>window.API_BASE_URL = "http://localhost:8501";</script>
//     placed BEFORE this file in index.html.
(function () {
  const TOKEN_KEY = "neuratriage_token";
  const TOKEN_EXP_KEY = "neuratriage_token_exp";

  function baseUrl() {
    return (typeof window !== "undefined" && window.API_BASE_URL) || "";
  }

  function getToken() {
    try {
      const exp = Number(localStorage.getItem(TOKEN_EXP_KEY) || 0);
      if (exp && Date.now() / 1000 > exp) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(TOKEN_EXP_KEY);
        return null;
      }
      return localStorage.getItem(TOKEN_KEY);
    } catch (e) { return null; }
  }

  function setToken(token, expiresAt) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      if (expiresAt) localStorage.setItem(TOKEN_EXP_KEY, String(expiresAt));
    } catch (e) {}
  }

  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
    } catch (e) {}
  }

  class ApiError extends Error {
    constructor(message, code, status, raw) {
      super(message);
      this.name = "ApiError";
      this.code = code;
      this.status = status;
      this.raw = raw;
    }
  }

  async function request(path, { method = "GET", body, auth = true, timeoutMs = 15000 } = {}) {
    const headers = { "Accept": "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth) {
      const t = getToken();
      if (t) headers["Authorization"] = "Bearer " + t;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let res;
    try {
      res = await fetch(baseUrl() + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        credentials: "omit",
      });
    } catch (e) {
      clearTimeout(timer);
      throw new ApiError(
        e.name === "AbortError" ? "Request timeout" : "Network error",
        e.name === "AbortError" ? "TIMEOUT" : "NETWORK_ERROR",
        0, e
      );
    }
    clearTimeout(timer);

    let json = null;
    try { json = await res.json(); } catch (e) { /* allow null */ }

    if (!res.ok || !json || json.success === false) {
      const code = (json && json.error && json.error.code) || ("HTTP_" + res.status);
      const msg = (json && json.error && json.error.message) || res.statusText || "Request failed";
      if (code === "TOKEN_EXPIRED" || code === "INVALID_TOKEN" || res.status === 401) {
        clearToken();
      }
      throw new ApiError(msg, code, res.status, json);
    }
    return json.data;
  }

  const api = {
    ApiError,
    getToken,
    clearToken,

    health() {
      return request("/api/health", { auth: false });
    },

    disclaimer() {
      return request("/api/disclaimer", { auth: false });
    },

    async login(email, password) {
      const data = await request("/api/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      setToken(data.access_token, data.expires_at);
      return data;
    },

    me() {
      return request("/api/auth/me");
    },

    async logout() {
      try { await request("/api/auth/logout", { method: "POST" }); } catch (e) {}
      clearToken();
    },

    infer({ eeg_path, patient_id, label }) {
      return request("/api/infer", {
        method: "POST",
        body: { eeg_path, patient_id, label },
        timeoutMs: 60000,
      });
    },
  };

  window.api = api;
})();
