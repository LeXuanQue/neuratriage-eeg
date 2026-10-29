// Live data adapter: polls the local backend when available, otherwise
// generates a browser-side realtime demo stream with the same shape.
(function () {
  const CLASS_KEYS = ["NS", "IS", "HS"];
  const API_KEY = "neuratriage_api_base";
  const DEFAULT_API_BASE = "http://127.0.0.1:8501";

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function getApiBase() {
    try {
      if (window.API_BASE_URL !== undefined) return window.API_BASE_URL;
      const saved = localStorage.getItem(API_KEY);
      if (saved !== null) return saved;
      if ((location.hostname === "127.0.0.1" || location.hostname === "localhost") && location.port === "8000") {
        return DEFAULT_API_BASE;
      }
      return "";
    } catch (e) {
      return DEFAULT_API_BASE;
    }
  }

  function normalizeMode(mode) {
    const next = String(mode || "HS").toUpperCase();
    return CLASS_KEYS.includes(next) ? next : "HS";
  }

  function normalizeProbs(probs) {
    const raw = probs || {};
    const values = CLASS_KEYS.map((key) => Math.max(0.01, Number(raw[key] ?? raw[key.toLowerCase()] ?? 0.01)));
    const sum = values.reduce((a, b) => a + b, 0) || 1;
    return Object.fromEntries(CLASS_KEYS.map((key, i) => [key, values[i] / sum]));
  }

  function dominantClass(probs) {
    return CLASS_KEYS.slice().sort((a, b) => probs[b] - probs[a])[0];
  }

  function unwrapPayload(payload) {
    if (payload && payload.success === true && payload.data && typeof payload.data === "object") {
      return payload.data;
    }
    return payload || {};
  }

  function scenarioProbs(mode, now) {
    const scenario = normalizeMode(mode);
    const wave = Math.sin(now * 0.72);
    const slow = Math.sin(now * 0.18);
    const ripple = Math.sin(now * 1.31);
    if (scenario === "NS") {
      return normalizeProbs({ NS: 0.80 + 0.04 * wave, IS: 0.13 + 0.025 * slow, HS: 0.07 + 0.015 * ripple });
    }
    if (scenario === "IS") {
      const ramp = 0.5 + 0.5 * Math.sin(now * 0.22);
      return normalizeProbs({ NS: 0.20 - 0.04 * ramp, IS: 0.64 + 0.12 * ramp + 0.03 * wave, HS: 0.13 + 0.02 * ripple });
    }
    const ramp = 0.5 + 0.5 * Math.sin(now * 0.20);
    return normalizeProbs({ NS: 0.06 + 0.025 * slow, IS: 0.17 + 0.035 * wave, HS: 0.70 + 0.12 * ramp + 0.025 * ripple });
  }

  function historyFor(mode, now) {
    return Array.from({ length: 80 }, (_, i) => ({
      t: i - 79,
      ...scenarioProbs(mode, now - (79 - i)),
    }));
  }

  function featuresFor(mode, now) {
    const scale = mode === "HS" ? 1 : mode === "IS" ? 0.78 : 0.42;
    const wobble = Math.sin(now * 0.55) * 0.012;
    return [
      { name: "FuEn (T4)", value: 0.135 * scale + wobble },
      { name: "delta_h MFDFA (Fp2)", value: 0.118 * scale - wobble * 0.6 },
      { name: "alpha-power (O1)", value: -0.096 * scale + wobble * 0.4 },
      { name: "ApEn (C3)", value: 0.082 * scale + wobble * 0.8 },
      { name: "Hurst H(2) (P4)", value: 0.068 * scale - wobble * 0.3 },
      { name: "theta/alpha ratio (Fz)", value: 0.061 * scale + wobble * 0.5 },
    ];
  }

  function metricsFor(now) {
    return {
      apen_mean: 0.84 + 0.04 * Math.sin(now * 0.33),
      fuen_mean: 0.91 + 0.035 * Math.sin(now * 0.29),
      h2: 0.71 + 0.025 * Math.sin(now * 0.41),
      delta_alpha: 0.55 + 0.05 * Math.sin(now * 0.24),
      bsi_delta: 0.34 + 0.04 * Math.sin(now * 0.37),
      theta_alpha: 1.82 + 0.12 * Math.sin(now * 0.31),
    };
  }

  function fallbackFrame(mode) {
    const now = Date.now() / 1000;
    const scenario = normalizeMode(mode);
    const probs = scenarioProbs(scenario, now);
    const dominant = dominantClass(probs);
    return {
      source: "browser-sim",
      connection: "demo",
      timestamp_ms: Date.now(),
      scenario,
      mode: scenario,
      status: dominant === "NS" ? "monitor" : "alert-hold",
      dominant,
      probs,
      sqi: clamp(0.90 + 0.045 * Math.sin(now * 0.27), 0.74, 0.98),
      timeToAlertSec: dominant === "NS" ? null : 4.2,
      patient: {
        name: "Nguyen Van T.",
        initials: "NV",
        mrn: "MRN-2026-04812",
        age: 67,
        sex: "M",
        bed: "ED-04",
        onset_min: 42,
      },
      device: {
        name: "g.tec g.HIamp",
        sample_rate: 256,
        battery: Math.round(clamp(87 + 4 * Math.sin(now * 0.08), 78, 94)),
        channels: 19,
        stream: "demo",
      },
      history: historyFor(scenario, now),
      features: featuresFor(scenario, now),
      metrics: metricsFor(now),
    };
  }

  function coerceFrame(payload, requestedMode, connection) {
    payload = unwrapPayload(payload);
    const now = Date.now() / 1000;
    const mode = normalizeMode(payload.mode || payload.scenario || requestedMode);
    const probs = normalizeProbs(payload.probabilities || payload.probs || scenarioProbs(mode, now));
    const dominant = payload.dominant || dominantClass(probs);
    return {
      ...fallbackFrame(mode),
      ...payload,
      connection,
      mode,
      scenario: mode,
      dominant,
      probs,
      sqi: Number(payload.sqi ?? 0.9),
      timeToAlertSec: payload.time_to_alert_sec ?? payload.timeToAlertSec ?? null,
      history: Array.isArray(payload.history) && payload.history.length
        ? payload.history.map((point, i) => ({ t: point.t ?? i - payload.history.length + 1, ...normalizeProbs(point) }))
        : historyFor(mode, now),
      features: Array.isArray(payload.features) && payload.features.length ? payload.features : featuresFor(mode, now),
      metrics: payload.metrics || metricsFor(now),
    };
  }

  function useLiveData(mode) {
    const scenario = normalizeMode(mode);
    const [frame, setFrame] = React.useState(() => fallbackFrame(scenario));

    React.useEffect(() => {
      let alive = true;
      let timer = null;

      async function poll() {
        const apiBase = getApiBase().replace(/\/$/, "");
        try {
          const url = `${apiBase}/api/live?scenario=${encodeURIComponent(scenario)}&ts=${Date.now()}`;
          const response = await fetch(url, { cache: "no-store" });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const payload = await response.json();
          if (alive) setFrame(coerceFrame(payload, scenario, "backend"));
        } catch (e) {
          if (alive) setFrame(fallbackFrame(scenario));
        } finally {
          if (alive) timer = setTimeout(poll, 1000);
        }
      }

      poll();
      return () => {
        alive = false;
        if (timer) clearTimeout(timer);
      };
    }, [scenario]);

    return frame;
  }

  window.LiveData = {
    DEFAULT_API_BASE,
    API_KEY,
    getApiBase,
    fallbackFrame,
    normalizeMode,
    normalizeProbs,
    dominantClass,
    unwrapPayload,
    useLiveData,
  };
  window.useLiveData = useLiveData;
})();
