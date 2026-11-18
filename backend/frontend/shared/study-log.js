// Study 1 mode (docs/user_study_protocol.md).
//
// Active only when the URL carries a pseudonymous participant code AND an explicit
// condition, e.g.  app.html?participant=P07&condition=B&trial=1&source=device
// (a missing condition is a facilitator typo, not a silent default to G).
// It then locks the interface (sidebar and tweaks hidden), logs events to
// POST /api/study/events, and gives the facilitator hotkeys:
//   Ctrl+Shift+S  trial start        Ctrl+Shift+E  trial end (next trial number)
//   Ctrl+Shift+A  operator action    Ctrl+Shift+R  fault resolved
// The corner badge shows the participant and trial only, never the condition.
// &source=device (or replay for pilots) opens the live screen and starts that stream.
// The trial number is written back into the URL, so a reload does not reuse it; events that
// fail to post are queued and retried with the next one.
(function () {
  const CODE = /^P[0-9]{2,3}$/;
  const HOTKEYS = { S: "trial_start", E: "trial_end", A: "operator_action", R: "fault_resolved" };

  function parseParams(search) {
    const q = new URLSearchParams(search || "");
    const participant = q.get("participant") || "";
    const rawCondition = (q.get("condition") || "").toUpperCase();
    const condition = rawCondition === "B" || rawCondition === "G" ? rawCondition : "";
    const trial = Math.max(1, parseInt(q.get("trial") || "1", 10) || 1);
    const active = CODE.test(participant) && condition !== "";
    const source = (q.get("source") || "").toLowerCase();
    const startSource = active && (source === "device" || source === "replay") ? source : "";
    return { active, participant, condition, trial, startSource };
  }

  const state = parseParams(location.search);
  const pending = [];
  let badge = null;
  let notRecording = false;

  function utcNow() {
    return new Date().toISOString();
  }

  function renderBadge() {
    if (!badge) return;
    badge.textContent = `${state.participant} · T${state.trial}` + (notRecording ? " · NOT RECORDING" : "");
    badge.style.background = notRecording || pending.length ? "var(--hs, #c33)" : "";
  }

  function persistTrial() {
    try {
      const q = new URLSearchParams(location.search);
      q.set("trial", String(state.trial));
      history.replaceState(null, "", `${location.pathname}?${q.toString()}${location.hash || ""}`);
    } catch (e) {
      /* URL persistence is best effort; the event log still has the trial number */
    }
  }

  function post(body) {
    return window.NTApi.post("/api/study/events", body);
  }

  let flushing = false;

  // One flush at a time: a second call while a post is in flight would resend pending[0].
  async function flush() {
    if (flushing) return null;
    flushing = true;
    try {
      while (pending.length) {
        try {
          await post(pending[0]);
          pending.shift();
        } catch (e) {
          return false;
        }
      }
      return true;
    } finally {
      flushing = false;
      renderBadge();
    }
  }

  function log(type, payload) {
    if (!state.active || !window.NTApi) return Promise.resolve(null);
    pending.push({
      participant: state.participant,
      condition: state.condition,
      trial: state.trial,
      type,
      client_ts: utcNow(),
      payload: payload || {},
    });
    // A failed post must never break the live screen: keep it queued, retry with the next
    // event, and show the facilitator a red badge while anything is unsent.
    return flush();
  }

  function markNotRecording() {
    notRecording = true;
    renderBadge();
  }

  function onKey(e) {
    if (!(e.ctrlKey && e.shiftKey)) return;
    const type = HOTKEYS[String(e.key).toUpperCase()];
    if (!type) return;
    e.preventDefault();
    log(type, {});
    if (type === "trial_end") {
      state.trial += 1;
      persistTrial();
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
    markNotRecording,
    parseParams,
  };
})();
