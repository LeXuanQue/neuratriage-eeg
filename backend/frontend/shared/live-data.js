// Live data adapter: polls the local backend when available. Without backend
// model output it returns a neutral waiting frame, not simulated evidence.
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
      if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
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

  function neutralHistory() {
    return Array.from({ length: 80 }, (_, i) => ({
      t: i - 79,
      NS: 1 / 3,
      IS: 1 / 3,
      HS: 1 / 3,
    }));
  }

  function fallbackFrame(mode) {
    const scenario = normalizeMode(mode);
    const probs = normalizeProbs({ NS: 1, IS: 1, HS: 1 });
    return {
      source: "waiting",
      connection: "waiting",
      timestamp_ms: Date.now(),
      scenario,
      mode: scenario,
      status: "waiting",
      dominant: "NS",
      probs,
      sqi: null,
      timeToAlertSec: null,
      hasModelEvent: false,
      patient: {},
      device: {
        name: "No measured source",
        sample_rate: 256,
        battery: null,
        channels: 0,
        stream: "waiting",
      },
      history: neutralHistory(),
      features: [],
      metrics: {},
    };
  }

  function coerceFrame(payload, requestedMode, connection) {
    payload = unwrapPayload(payload);
    const mode = normalizeMode(payload.mode || payload.scenario || requestedMode);
    const hasProbPayload = !!(payload.probabilities || payload.probs);
    const probs = hasProbPayload ? normalizeProbs(payload.probabilities || payload.probs) : normalizeProbs({ NS: 1, IS: 1, HS: 1 });
    const dominant = payload.dominant || (hasProbPayload ? dominantClass(probs) : "NS");
    const hasModelEvent = payload.hasModelEvent === true || payload.has_model_event === true;
    return {
      ...fallbackFrame(mode),
      ...payload,
      connection,
      mode,
      scenario: mode,
      dominant,
      probs,
      sqi: typeof payload.sqi === "number" ? payload.sqi : null,
      timeToAlertSec: payload.time_to_alert_sec ?? payload.timeToAlertSec ?? null,
      hasModelEvent,
      history: Array.isArray(payload.history) && payload.history.length
        ? payload.history.map((point, i) => ({ t: point.t ?? i - payload.history.length + 1, ...normalizeProbs(point) }))
        : neutralHistory(),
      features: Array.isArray(payload.features) && payload.features.length ? payload.features : [],
      metrics: payload.metrics || {},
    };
  }

  function useLiveData(mode) {
    const scenario = normalizeMode(mode);
    const [frame, setFrame] = React.useState(() => fallbackFrame(scenario));

    React.useEffect(() => {
      setFrame(fallbackFrame(scenario));
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
