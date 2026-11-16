// Study 1 mode (docs/user_study_protocol.md).
//
// Active only when the URL carries a pseudonymous participant code, e.g.
//   app.html?participant=P07&condition=B&trial=1
// It then locks the interface (sidebar and tweaks hidden), logs events to
// POST /api/study/events, and gives the facilitator hotkeys:
//   Ctrl+Shift+S  trial start        Ctrl+Shift+E  trial end (next trial number)
//   Ctrl+Shift+A  operator action    Ctrl+Shift+R  fault resolved
// The corner badge shows the participant and trial only, never the condition.
// &source=device (or replay for pilots) opens the live screen and starts that stream.
(function () {
  const CODE = /^P\d{2,3}$/;
  const HOTKEYS = { S: "trial_start", E: "trial_end", A: "operator_action", R: "fault_resolved" };

  function parseParams(search) {
    const q = new URLSearchParams(search || "");
    const participant = q.get("participant") || "";
    const condition = (q.get("condition") || "G").toUpperCase() === "B" ? "B" : "G";
    const trial = Math.max(1, parseInt(q.get("trial") || "1", 10) || 1);
    const active = CODE.test(participant);
    const source = (q.get("source") || "").toLowerCase();
    const startSource = active && (source === "device" || source === "replay") ? source : "";
    return { active, participant, condition, trial, startSource };
  }

  const state = parseParams(location.search);
  let badge = null;

  function utcNow() {
    return new Date().toISOString();
  }

  function renderBadge() {
    if (!badge) return;
    badge.textContent = `${state.participant} · T${state.trial}`;
  }

  function log(type, payload) {
    if (!state.active || !window.NTApi) return Promise.resolve(null);
    const body = {
      participant: state.participant,
      condition: state.condition,
      trial: state.trial,
      type,
      client_ts: utcNow(),
      payload: payload || {},
    };
    // A failed log must never break the live screen; the facilitator sees the badge turn red.
    return window.NTApi.post("/api/study/events", body).catch(() => {
      if (badge) badge.style.background = "var(--hs, #c33)";
      return null;
    });
  }

  function onKey(e) {
    if (!(e.ctrlKey && e.shiftKey)) return;
    const type = HOTKEYS[String(e.key).toUpperCase()];
    if (!type) return;
    e.preventDefault();
    log(type, {});
    if (type === "trial_end") {
      state.trial += 1;
      renderBadge();
    }
  }

  if (state.active) {
    document.body.classList.add("nt-study");
    badge = document.createElement("div");
    badge.setAttribute("aria-hidden", "true");
    badge.className = "nt-study-badge";
    renderBadge();
    document.body.appendChild(badge);
    window.addEventListener("keydown", onKey);
  }

  window.NTStudy = {
    get active() { return state.active; },
    get participant() { return state.participant; },
    get condition() { return state.condition; },
    get trial() { return state.trial; },
    // "device" | "replay" | "" — app.html starts it when its nt:nav listener is ready
    get startSource() { return state.startSource; },
    log,
    parseParams,
  };
})();
