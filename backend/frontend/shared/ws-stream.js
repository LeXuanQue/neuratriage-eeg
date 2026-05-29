// NeuraTriage live streaming via WebSocket.
// =========================================
// Public API:
//   window.WSStream.useWSStream(scenario)  // React hook returning a frame
//                                           // with the same shape as
//                                           // window.useLiveData(scenario).
//
// Behaviour:
//   1. Generates a session_id (UUID-like hex) client-side.
//   2. Opens WS to ${apiBase}/ws/stream/${session_id}.
//   3. Sends {type:"init", device_channels, fs}.
//   4. In replay mode, the server streams stored dataset chunks.
//      Without replay or a real device bridge, no raw EEG is generated.
//   5. Drains {type:"event", ...} messages from the server, converts them
//      into the live-data frame shape, and exposes the latest frame.
//
// Fallback:
//   If WS fails or no replay/device source is available, the hook returns a
//   neutral waiting frame. It does not generate client-side EEG.
(function () {
  if (typeof window === "undefined") return;
  const CLASS_KEYS = ["NS", "IS", "HS"];
  const PRED_TO_KEY = {
    "non-stroke": "NS",
    nonstroke: "NS",
    ischemic: "IS",
    hemorrhagic: "HS",
  };
  const HISTORY_LEN = 80;
  const FS = 256;
  const CHUNK_SECONDS = 0.5;
  const CHUNK_SAMPLES = Math.round(FS * CHUNK_SECONDS);
  const DEFAULT_DEVICE_CHANNELS = [
    "C3", "C4", "Cz", "F3", "F4", "F7", "F8", "Fz", "Fp1",
    "Fp2", "O1", "O2", "P3", "P4", "T3", "T4", "T5", "T6",
  ];

  function uuidHex() {
    const bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }

  function getApiBase() {
    if (window.LiveData && window.LiveData.getApiBase) {
      return window.LiveData.getApiBase().replace(/\/$/, "");
    }
    return "";
  }

  function wsUrlFromApiBase(apiBase, path) {
    if (!apiBase) {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${location.host}${path}`;
    }
    let url;
    try {
      url = new URL(apiBase);
    } catch (e) {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${location.host}${path}`;
    }
    const wsProto = url.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${url.host}${path}`;
  }

  function withToken(url, token) {
    if (!token) return url;
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}token=${encodeURIComponent(token)}`;
  }

  function cleanChannels(channels) {
    const arr = Array.isArray(channels) ? channels.map(String).filter(Boolean) : [];
    return arr.length ? arr : DEFAULT_DEVICE_CHANNELS;
  }

  // Box-Muller standard normal — pipeline's SQI gate likes broadband noise,
  // pure deterministic sines fail flatline/HF checks (sqi_total → 0).
  // ── Frame helpers ─────────────────────────────────────────────────────
  function emptyHistory() {
    return Array.from({ length: HISTORY_LEN }, (_, i) => ({
      t: i - (HISTORY_LEN - 1),
      NS: 1 / 3,
      IS: 1 / 3,
      HS: 1 / 3,
    }));
  }

  function eventToProbs(event) {
    const ps = event.probabilities_smooth;
    if (!Array.isArray(ps) || ps.length < 3) return null;
    const sum = ps[0] + ps[1] + ps[2] || 1;
    return { NS: ps[0] / sum, IS: ps[1] / sum, HS: ps[2] / sum };
  }

  function buildFrame(scenario, lastEvent, history, source, connection, deviceChannels) {
    const fallback =
      window.LiveData && window.LiveData.fallbackFrame
        ? window.LiveData.fallbackFrame(scenario)
        : { patient: {}, device: {}, features: [], metrics: {} };

    let probs = fallback.probs || { NS: 1 / 3, IS: 1 / 3, HS: 1 / 3 };
    let dominant = "NS";
    let sqi = null;
    let status = "waiting";
    if (lastEvent) {
      const evProbs = eventToProbs(lastEvent);
      if (evProbs) probs = evProbs;
      const predKey = PRED_TO_KEY[lastEvent.predicted_class] || null;
      dominant =
        predKey ||
        (probs ? CLASS_KEYS.slice().sort((a, b) => probs[b] - probs[a])[0] : scenario);
      if (typeof lastEvent.sqi_total === "number") sqi = lastEvent.sqi_total;
      if (lastEvent.status) status = lastEvent.status;
    }

    return {
      ...fallback,
      source,
      connection,
      scenario,
      mode: scenario,
      timestamp_ms: Date.now(),
      probs,
      dominant,
      sqi,
      status,
      timeToAlertSec: lastEvent && status && status.startsWith("alert") ? 4.2 : null,
      hasModelEvent: !!lastEvent,
      history:
        history.length === HISTORY_LEN ? history.slice() : emptyHistory(),
      device: {
        ...(fallback.device || {}),
        channels: cleanChannels(deviceChannels).length,
      },
    };
  }

  // ── Rolling EEG buffer (A2: expose sent chunks to UI) ────────────────
  const RAW_BUFFER_SEC = 4;
  const RAW_BUFFER_SAMPLES = Math.round(FS * RAW_BUFFER_SEC);

  // ── React hook ────────────────────────────────────────────────────────
  // patientId (optional) — passed in WS init so the backend links the
  // EEGSession row to the correct patient automatically (A1).
  function useWSStream(scenarioInput, replayNpz, patientId, requestedChannels) {
    const scenario = String(scenarioInput || "HS").toUpperCase();
    const replay = replayNpz ? String(replayNpz) : null;
    const requestedChannelKey = cleanChannels(requestedChannels).join(",");
    const fallbackFrame =
      window.LiveData && window.LiveData.fallbackFrame
        ? window.LiveData.fallbackFrame(scenario)
        : null;

    const [frame, setFrame] = React.useState(
      fallbackFrame ||
        buildFrame(scenario, null, emptyHistory(), "waiting", "waiting", cleanChannels(requestedChannels))
    );

    // A2: rolling buffer of raw chunks being sent, exposed as rawBuffer in frame
    const rawBufferRef = React.useRef(null);
    const deviceChannelsRef = React.useRef(DEFAULT_DEVICE_CHANNELS);

    React.useEffect(() => {
      let alive = true;
      const sessionId = uuidHex();
      let ws = null;

      const history = emptyHistory();
      let lastEvent = null;
      let opened = false;
      rawBufferRef.current = null;
      deviceChannelsRef.current = cleanChannels(requestedChannels);
      // Replay mode: server reads a stored .npz and pumps chunks itself, so
      // the FE just listens. No client-side synthetic generator runs.
      const useReplay = !!replay;

      function attachHandlers(socket) {
      socket.addEventListener("open", () => {
        if (!alive) return;
        opened = true;
        const initMsg = {
          type: "init",
          device_channels: deviceChannelsRef.current,
          fs: FS,
        };
        // A1: link session to patient on the backend
        if (patientId) {
          initMsg.patient_id = String(patientId);
        }
        if (useReplay) {
          initMsg.replay_npz = replay;
          initMsg.realtime = true;
        }
        socket.send(JSON.stringify(initMsg));
        // No client-side synthetic pumping. Dataset replay is handled by the
        // server; real devices need a real bridge before data appears here.
      });

      socket.addEventListener("message", (msg) => {
        if (!alive) return;
        let payload;
        try {
          payload = JSON.parse(msg.data);
        } catch (e) {
          return;
        }
        if (payload.type === "event") {
          lastEvent = payload;
          const probs = eventToProbs(payload);
          if (probs) {
            history.push({ t: history.length, ...probs });
            while (history.length > HISTORY_LEN) history.shift();
            for (let i = 0; i < history.length; i++) {
              history[i].t = i - (history.length - 1);
            }
          }
          // A2: snapshot current rawBuffer into frame so live screen can render it
          const rawSnap = rawBufferRef.current
            ? rawBufferRef.current.map((ch) => ch.slice())
            : null;
          setFrame({
            ...buildFrame(scenario, lastEvent, history, "backend-ws", "backend", deviceChannelsRef.current),
            rawBuffer: rawSnap,
            deviceChannels: deviceChannelsRef.current,
            rawSource: useReplay ? "replay" : "raw",
            hasModelEvent: true,
          });
        } else if (payload.type === "ready") {
          const readyChannels = cleanChannels(payload.device_channels || payload.mapped_channels || deviceChannelsRef.current);
          deviceChannelsRef.current = readyChannels;
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            source: "backend-ws",
            connection: "backend",
            rawBuffer: rawBufferRef.current ? rawBufferRef.current.map((ch) => ch.slice()) : null,
            deviceChannels: readyChannels,
            rawSource: useReplay ? "replay" : "none",
            hasModelEvent: false,
            device: {
              ...((prev && prev.device) || fallbackFrame.device || {}),
              channels: readyChannels.length,
            },
          }));
        } else if (payload.type === "raw_chunk" && Array.isArray(payload.chunk)) {
          const incomingChannels = cleanChannels(payload.device_channels || payload.channels || deviceChannelsRef.current);
          deviceChannelsRef.current = incomingChannels;
          const chunk = payload.chunk;
          if (!rawBufferRef.current || rawBufferRef.current.length !== chunk.length) {
            rawBufferRef.current = chunk.map((ch) => Array.isArray(ch) ? ch.slice(-RAW_BUFFER_SAMPLES) : []);
          } else {
            rawBufferRef.current = rawBufferRef.current.map((buf, i) => {
              const next = buf.concat(Array.isArray(chunk[i]) ? chunk[i] : []);
              return next.length > RAW_BUFFER_SAMPLES
                ? next.slice(next.length - RAW_BUFFER_SAMPLES)
                : next;
            });
          }
          const rawSnap = rawBufferRef.current.map((ch) => ch.slice());
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            source: "backend-ws",
            connection: "backend",
            rawBuffer: rawSnap,
            deviceChannels: incomingChannels,
            rawSource: "replay",
            hasModelEvent: false,
            device: {
              ...((prev && prev.device) || fallbackFrame.device || {}),
              channels: incomingChannels.length,
            },
          }));
        }
      });

      socket.addEventListener("close", () => {
        if (!alive) return;
        setFrame((prev) => ({
          ...(prev || fallbackFrame),
          source: opened ? "backend-ws-closed" : "waiting",
          connection: "waiting",
          rawBuffer: null,
          hasModelEvent: false,
        }));
      });
      }

      async function connect() {
        try {
          if (window.NTApi) await window.NTApi.ensureAuth();
        } catch (e) {
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            source: "auth-unavailable",
            connection: "waiting",
            rawBuffer: null,
            hasModelEvent: false,
          }));
          return;
        }
        if (!alive) return;
        const apiBase = getApiBase();
        const token = window.NTApi?.getToken?.() || "";
        const wsUrl = withToken(wsUrlFromApiBase(apiBase, `/ws/stream/${sessionId}`), token);
        try {
          ws = new WebSocket(wsUrl);
        } catch (e) {
          return;
        }
        attachHandlers(ws);
      }

      connect();

      return () => {
        alive = false;
        try {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "close" }));
          }
        } catch (e) {
          /* noop */
        }
        try {
          ws.close();
        } catch (e) {
          /* noop */
        }
      };
    }, [scenario, replay, patientId, requestedChannelKey]);

    return frame;
  }

  window.WSStream = {
    useWSStream,
    DEFAULT_DEVICE_CHANNELS,
    FS,
    CHUNK_SECONDS,
  };
  window.useWSStream = useWSStream;
})();
