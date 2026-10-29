// NeuraTriage REST helper for app.html.
// =====================================
// Public API:
//   await window.NTApi.get(path)
//   await window.NTApi.post(path, body)
//   await window.NTApi.put(path, body)
//   await window.NTApi.del(path)
//
//   await window.NTApi.ensureAuth()   // requires an existing token
//   window.NTApi.useApi(fn, deps)     // tiny React helper: fetch on mount + on deps
//
// All helpers unwrap the {success,data} envelope and throw an ApiError on
// {success:false} or HTTP error.
(function () {
  if (typeof window === "undefined") return;

  const TOKEN_KEY = "neuratriage_token";
  const TOKEN_EXP_KEY = "neuratriage_token_exp";

  function baseUrl() {
    if (window.LiveData && window.LiveData.getApiBase) {
      return window.LiveData.getApiBase().replace(/\/$/, "");
    }
    return "";
  }

  function getToken() {
    try {
      const exp = Number(localStorage.getItem(TOKEN_EXP_KEY) || 0);
      if (exp && Date.now() / 1000 > exp - 30) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(TOKEN_EXP_KEY);
        return null;
      }
      return localStorage.getItem(TOKEN_KEY);
    } catch (e) {
      return null;
    }
  }

  function setToken(token, expiresAt) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      if (expiresAt) localStorage.setItem(TOKEN_EXP_KEY, String(expiresAt));
    } catch (e) {
      /* noop */
    }
  }

  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
    } catch (e) {
      /* noop */
    }
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

  async function login(email, password) {
    const r = await fetch(baseUrl() + "/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email, password }),
    });
    let json = null;
    try {
      json = await r.json();
    } catch (e) {
      /* ignore */
    }
    if (!r.ok || !json || json.success === false) {
      const code = (json && json.error && json.error.code) || "HTTP_" + r.status;
      const msg = (json && json.error && json.error.message) || "Login failed";
      throw new ApiError(msg, code, r.status, json);
    }
    setToken(json.data.access_token, json.data.expires_at);
    return json.data;
  }

  async function ensureAuth() {
    if (getToken()) return;
    throw new ApiError("Sign in required", "MISSING_TOKEN", 401, null);
  }

  async function request(path, { method = "GET", body, retried = false } = {}) {
    await ensureAuth();
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const tok = getToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;

    let r;
    try {
      r = await fetch(baseUrl() + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError("Network error: " + e.message, "NETWORK_ERROR", 0, e);
    }

    let json = null;
    try {
      json = await r.json();
    } catch (e) {
      /* allow null */
    }

    if (r.status === 401 && !retried) {
      clearToken();
      return request(path, { method, body, retried: true });
    }

    if (!r.ok || !json || json.success === false) {
      const code = (json && json.error && json.error.code) || "HTTP_" + r.status;
      const msg = (json && json.error && json.error.message) || r.statusText || "Request failed";
      throw new ApiError(msg, code, r.status, json);
    }
    return json.data;
  }

  // Tiny convenience hook for app screens. Re-runs whenever any value in
  // `deps` changes; `intervalMs` (optional) re-fetches periodically.
  function useApi(fn, deps, intervalMs) {
    const [state, setState] = React.useState({
      data: null,
      error: null,
      loading: true,
    });

    React.useEffect(() => {
      let alive = true;
      let timer = null;

      async function run() {
        if (!alive) return;
        try {
          const data = await fn();
          if (alive) setState({ data, error: null, loading: false });
        } catch (err) {
          if (alive) setState({ data: null, error: err, loading: false });
        }
      }

      run();
      if (intervalMs && intervalMs > 0) {
        timer = setInterval(run, intervalMs);
      }
      return () => {
        alive = false;
        if (timer) clearInterval(timer);
      };
    }, deps || []);

    return state;
  }

  window.NTApi = {
    ApiError,
    baseUrl,
    getToken,
    clearToken,
    ensureAuth,
    login,
    get: (path) => request(path),
    post: (path, body) => request(path, { method: "POST", body: body || {} }),
    put: (path, body) => request(path, { method: "PUT", body: body || {} }),
    del: (path) => request(path, { method: "DELETE" }),
    useApi,
  };
})();
