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
  const CLASS_KEYS = ["NS", "IS"];
  const PRED_TO_KEY = {
    "non-stroke": "NS",
    nonstroke: "NS",
    ischemic: "IS",
  };
  const HISTORY_LEN = 80;
  const FS = 256;
  const CHUNK_SECONDS = 0.5;
  const CHUNK_SAMPLES = Math.round(FS * CHUNK_SECONDS);
  const DEFAULT_DEVICE_CHANNELS = [
    "C3", "C4", "Cz", "F3", "F4", "F7", "F8", "Fz", "Fp1",
    "Fp2", "O1", "O2", "P3", "P4", "T3", "T4", "T5", "T6",
  ];

  // Most-recent open stream socket, so a UI control (the demo artifact toggle)
  // can send a message without the hook exposing an imperative React API.
  let currentSocket = null;

  function setArtifact(on, intensity) {
    if (currentSocket && currentSocket.readyState === WebSocket.OPEN) {
      const m = { type: "artifact", on: !!on };
      if (intensity != null) m.intensity = Number(intensity);
      try {
        currentSocket.send(JSON.stringify(m));
        return true;
      } catch (e) {
        return false;
      }
    }
    return false;
  }

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
      NS: 0.5,
      IS: 0.5,
    }));
  }

  function eventToProbs(event) {
    const ps = event.probabilities_smooth;
    if (!Array.isArray(ps) || ps.length < 2) return null;
    const sum = ps[0] + ps[1] || 1;
    return { NS: ps[0] / sum, IS: ps[1] / sum };
  }

  function buildFrame(scenario, lastEvent, history, source, connection, deviceChannels) {
    const fallback =
      window.LiveData && window.LiveData.fallbackFrame
        ? window.LiveData.fallbackFrame(scenario)
        : { patient: {}, device: {}, features: [], metrics: {} };

    let probs = fallback.probs || { NS: 0.5, IS: 0.5 };
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
  // runId (optional) — bump it to force a fresh connection with the same
  // arguments. Demo mode uses it for "run this scenario again".
  // artifactOn (optional) — arm the artifact injector as soon as the socket
  // opens. It is deliberately not a dependency: changing it must not reconnect,
  // and live toggling still goes through setArtifact().
  function useWSStream(scenarioInput, replayNpz, patientId, requestedChannels, deviceStream, runId, artifactOn, loopReplay) {
    const scenario = String(scenarioInput || "IS").toUpperCase();
    const deviceMode = !!deviceStream;
    const replay = deviceMode ? null : (replayNpz ? String(replayNpz) : null);
    // loop lives in the init message, so changing it has to reopen the socket.
    const loop = !!loopReplay;
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
    const artifactOnRef = React.useRef(false);
    const initialArtifactRef = React.useRef(false);
    initialArtifactRef.current = !!artifactOn;

    React.useEffect(() => {
      let alive = true;
      const sessionId = uuidHex();
      let ws = null;

      const history = emptyHistory();
      let lastEvent = null;
      let opened = false;
      rawBufferRef.current = null;
      artifactOnRef.current = false;
      deviceChannelsRef.current = cleanChannels(requestedChannels);
      // Replay mode: server reads a stored .npz and pumps chunks itself, so
      // the FE just listens. No client-side synthetic generator runs.
      const useReplay = !!replay;

      function attachHandlers(socket) {
      socket.addEventListener("open", () => {
        if (!alive) return;
        opened = true;
        currentSocket = socket;
        const initMsg = deviceMode
          ? { type: "init", source: "device", fs: FS }
          : { type: "init", device_channels: deviceChannelsRef.current, fs: FS };
        // A1: link session to patient on the backend
        if (patientId) {
          initMsg.patient_id = String(patientId);
        }
        if (!deviceMode && useReplay) {
          initMsg.replay_npz = replay;
          initMsg.realtime = true;
          if (loop) initMsg.loop = true;
        }
        socket.send(JSON.stringify(initMsg));
        // A demo scenario that wants a corrupted signal has to arm the injector
        // on *this* socket. Doing it from a React effect races the reconnect:
        // setArtifact() drops the message when the previous socket is closing.
        if (initialArtifactRef.current) {
          artifactOnRef.current = true;
          try {
            socket.send(JSON.stringify({ type: "artifact", on: true }));
          } catch (e) {
            /* the close handler will surface the dead socket */
          }
        }
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
            artifactOn: artifactOnRef.current,
          });
        } else if (payload.type === "ready") {
          const readyChannels = cleanChannels(payload.device_channels || payload.mapped_channels || deviceChannelsRef.current);
          deviceChannelsRef.current = readyChannels;
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            source: "backend-ws",
            connection: "backend",
            streamError: null,
            rawBuffer: rawBufferRef.current ? rawBufferRef.current.map((ch) => ch.slice()) : null,
            deviceChannels: readyChannels,
            rawSource: useReplay ? "replay" : "none",
            hasModelEvent: false,
            replayDone: false,
            replayLap: 0,
            deviceStatus: null,
            device: {
              ...((prev && prev.device) || fallbackFrame.device || {}),
              channels: readyChannels.length,
            },
          }));
        } else if (payload.type === "device_status") {
          // BLE link state. Surfacing this is what separates "headset is off"
          // from "the app is broken" — the backend otherwise retries silently.
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            deviceStatus: {
              state: String(payload.state || ""),
              message: String(payload.message || ""),
              retryInSec: payload.retry_in_sec == null ? null : Number(payload.retry_in_sec),
            },
          }));
        } else if (payload.type === "replay_loop") {
          // Looping playback reached the end and restarted — keep the screen
          // alive and show which lap we are on.
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            replayLap: Number(payload.lap) || 0,
            replayDone: false,
          }));
        } else if (payload.type === "replay_done") {
          // The stored recording ran out. Keep the last frame on screen and
          // flag it, so the UI can offer "run again" instead of looking hung.
          setFrame((prev) => ({ ...(prev || fallbackFrame), replayDone: true }));
        } else if (payload.type === "artifact_state") {
          artifactOnRef.current = !!payload.on;
          setFrame((prev) => ({ ...(prev || fallbackFrame), artifactOn: !!payload.on }));
        } else if (payload.type === "error") {
          // Backend refused/aborted the stream (device not configured, replay
          // file missing, detector crash, …). Surface it instead of silently
          // dropping — the operator must see "cannot start / stream error".
          setFrame((prev) => ({
            ...(prev || fallbackFrame),
            source: "backend-ws-error",
            connection: "error",
            streamError: String(payload.message || "Stream error"),
            hasModelEvent: false,
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
            rawSource: useReplay ? "replay" : "raw",
            // A raw chunk says nothing about the model. Clearing hasModelEvent
            // here made the risk score, SQI and recommendation blink out twice a
            // second — once per chunk — between the events that set it true.
            hasModelEvent: prev ? !!prev.hasModelEvent : false,
            device: {
              ...((prev && prev.device) || fallbackFrame.device || {}),
              channels: incomingChannels.length,
            },
          }));
        }
      });

      socket.addEventListener("close", () => {
        if (!alive) return;
        if (currentSocket === socket) currentSocket = null;
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
          if (ws) ws.close();
        } catch (e) {
          /* noop */
        }
      };
    }, [scenario, replay, patientId, requestedChannelKey, deviceMode, runId, loop]);

    return frame;
  }

  window.WSStream = {
    useWSStream,
    setArtifact,
    DEFAULT_DEVICE_CHANNELS,
    FS,
    CHUNK_SECONDS,
  };
  window.useWSStream = useWSStream;
})();
