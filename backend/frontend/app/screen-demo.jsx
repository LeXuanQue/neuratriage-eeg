// Demo mode — guided scenarios that run the whole system without a headset.
// The screen only *picks* a stored recording; every number shown afterwards on
// the live screen comes from the backend detector, not from this file.
const { useMemo: useM_dm, useState: useS_dm, useRef: useR_dm } = React;

const DEMO_ACCENTS = {is: "var(--is)", ns: "var(--ns)", warn: "var(--hs)"};

window.DEMO_PIPELINE_STEPS = ["source", "raw", "sqi", "model", "alert"];

// Maps a live frame onto the five pipeline steps so the same vocabulary is used
// on the demo screen and on the live monitor.
window.demoStepStates = function demoStepStates(frame) {
  const connected = frame && frame.connection === "backend";
  const hasRaw = !!(frame && frame.rawBuffer && frame.rawBuffer.length > 0);
  const hasEvent = hasRaw && frame && frame.hasModelEvent === true;
  const status = (frame && frame.status) || "";
  const blockedBySqi = hasEvent && status === "no-decision";
  const decided = hasEvent && !blockedBySqi;
  const alerting = decided && String(status).startsWith("alert");

  return {
    source: connected ? "done" : "active",
    raw: hasRaw ? "done" : connected ? "active" : "waiting",
    sqi: blockedBySqi ? "blocked" : decided ? "done" : hasRaw ? "active" : "waiting",
    model: decided ? "done" : blockedBySqi ? "blocked" : hasRaw ? "active" : "waiting",
    alert: alerting ? "done" : decided ? "active" : "waiting",
  };
};

const STATE_COLORS = {
  done: "var(--ns)",
  active: "var(--brand-2)",
  blocked: "var(--hs)",
  waiting: "var(--ink-4)",
};

// One step of the pipeline strip. `state` is done | active | blocked | waiting.
window.DemoStep = function DemoStep({index, label, hint, state, compact}) {
  const color = STATE_COLORS[state] || STATE_COLORS.waiting;
  const dim = state === "waiting";
  return (
    <div style={{
      flex:"1 1 0", minWidth: compact ? 108 : 140,
      padding: compact ? "8px 10px" : "12px 14px",
      borderRadius:8,
      border:"1px solid " + (dim ? "var(--line)" : color),
      background: dim ? "transparent" : "color-mix(in oklab, " + color + " 12%, transparent)",
      opacity: dim ? 0.62 : 1,
      transition:"border-color 0.2s, background 0.2s, opacity 0.2s",
    }}>
      <div style={{display:"flex", alignItems:"center", gap:7, marginBottom: compact ? 2 : 5}}>
        <span className="mono" style={{
          width:17, height:17, borderRadius:"50%", flex:"none",
          display:"grid", placeItems:"center",
          fontSize:9.5, color: dim ? "var(--ink-3)" : color,
          border:"1px solid " + (dim ? "var(--ink-4)" : color),
        }}>{index}</span>
        <span style={{fontSize: compact ? 11.5 : 13, fontWeight:500, color: dim ? "var(--ink-3)" : "var(--ink)"}}>{label}</span>
      </div>
      {!compact && (
        <div style={{fontSize:11.5, color:"var(--ink-3)", lineHeight:1.45, paddingLeft:24}}>{hint}</div>
      )}
    </div>
  );
};

// Compact strip shown on the live monitor while a demo scenario is streaming.
window.DemoPipelineStrip = function DemoPipelineStrip({t, frame}) {
  const states = window.demoStepStates(frame);
  return (
    <div style={{display:"flex", gap:7, flexWrap:"wrap"}}>
      {window.DEMO_PIPELINE_STEPS.map((key, i) => (
        <window.DemoStep key={key} index={i + 1} compact={true}
          label={t.demo.steps[key]} hint={t.demo.steps[key + "Hint"]} state={states[key]}/>
      ))}
    </div>
  );
};

window.DemoScreen = function DemoScreen({t, lang, frame, demo}) {
  const scenarios = (demo && demo.scenarios) || [];
  const activeId = demo && demo.activeId;
  const states = useM_dm(() => window.demoStepStates(frame), [frame]);
  // Declared above every use (Babel-in-browser turns a later const into undefined).
  const modelInfo = window.useModelInfo ? window.useModelInfo() : {info: null, error: null};
  const activeModel = modelInfo.info ? modelInfo.info.realtime_model : null;

  // ── Your own recording ────────────────────────────────────────────────────
  const fileRef = useR_dm(null);
  const [uploading, setUploading] = useS_dm(false);
  const [uploaded, setUploaded] = useS_dm(null);
  const [uploadError, setUploadError] = useS_dm(null);
  const uploadPlaying = typeof activeId === "string" && activeId.indexOf("upload:") === 0;

  // An uploaded file is a scenario with no promised outcome — the shape matches
  // the API scenarios so the live banner and pipeline strip work unchanged.
  function uploadScenario(up) {
    const name = up.original_name || up.upload_id;
    return {
      id: "upload:" + up.upload_id,
      title: {vi: name, en: name},
      summary: {vi: t.demo.uploadUnknown, en: t.demo.uploadUnknown},
      expect: {vi: "", en: ""},
      replay_case: up.upload_id,
      dataset: "upload",
      class_hint: "unknown",
      artifact: false,
      expected_status: "unknown",
      accent: "brand",
      duration_sec: 0,
      expect_at_sec: null,
    };
  }

  async function handleUpload(file) {
    if (!file || !window.NTApi) return;
    setUploadError(null);
    setUploading(true);
    setUploaded(null);
    try {
      await window.NTApi.ensureAuth();
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(window.NTApi.baseUrl() + "/api/upload", {
        method: "POST",
        headers: {"Authorization": "Bearer " + window.NTApi.getToken()},
        body: form,
      });
      const j = await r.json();
      if (!r.ok || !j.success) throw new Error((j.error && j.error.message) || t.demo.uploadError);
      setUploaded(j.data);
      if (demo) demo.start(uploadScenario(j.data));   // stream it straight away
    } catch (e) {
      setUploadError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  }

  function fmtDuration(sec) {
    const s = Math.round(Number(sec) || 0);
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  }

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      <div style={{display:"flex", flexDirection:"column", gap:16, maxWidth:960, margin:"0 auto"}}>

        {/* Intro */}
        <div className="panel" style={{padding:"20px 22px"}}>
          <div style={{display:"flex", alignItems:"center", gap:9, marginBottom:6}}>
            <window.NTIcon name="play" size={15} color="var(--brand-2)"/>
            <h2 style={{margin:0, fontSize:19, fontWeight:600, letterSpacing:"-0.01em"}}>{t.demo.title}</h2>
          </div>
          <div style={{fontSize:13, color:"var(--ink-2)", marginBottom:10}}>{t.demo.subtitle}</div>
          <p style={{margin:0, fontSize:12.5, color:"var(--ink-3)", lineHeight:1.6, maxWidth:640, fontWeight:300}}>
            {t.demo.intro}
          </p>
        </div>

        {/* Pipeline explainer — also reflects the running stream */}
        <div className="panel" style={{padding:"16px 18px"}}>
          <div className="stat-lbl" style={{marginBottom:12}}>{t.demo.pipelineTitle}</div>
          <div style={{display:"flex", gap:9, flexWrap:"wrap"}}>
            {window.DEMO_PIPELINE_STEPS.map((key, i) => (
              <window.DemoStep key={key} index={i + 1}
                label={t.demo.steps[key]} hint={t.demo.steps[key + "Hint"]}
                state={activeId ? states[key] : "waiting"}/>
            ))}
          </div>
        </div>

        {/* Scenarios */}
        <div>
          <div className="stat-lbl" style={{marginBottom:10}}>{t.demo.scenariosTitle}</div>

          {demo && demo.loading && (
            <div className="panel" style={{padding:24, color:"var(--ink-3)", fontSize:12.5}}>{t.demo.loading}</div>
          )}
          {demo && demo.error && (
            <div className="panel" style={{padding:24, color:"var(--hs)", fontSize:12.5}}>
              {t.demo.error}: {demo.error.message || String(demo.error)}
            </div>
          )}
          {demo && !demo.loading && !demo.error && scenarios.length === 0 && (
            <div className="panel" style={{padding:24, color:"var(--ink-3)", fontSize:12.5}}>{t.demo.empty}</div>
          )}

          <div style={{display:"grid", gap:12}}>
            {scenarios.map(sc => {
              const color = DEMO_ACCENTS[sc.accent] || "var(--brand-2)";
              const isActive = sc.id === activeId;
              return (
                <div key={sc.id} className="panel" style={{
                  padding:"16px 18px",
                  border:"1px solid " + (isActive ? color : "var(--line)"),
                  boxShadow: isActive ? `0 0 0 1px ${color}, 0 6px 24px -18px ${color}` : "none",
                }}>
                  <div style={{display:"flex", alignItems:"flex-start", gap:14, flexWrap:"wrap"}}>
                    <div style={{flex:"1 1 340px", minWidth:0}}>
                      <div style={{display:"flex", alignItems:"center", gap:8, flexWrap:"wrap", marginBottom:5}}>
                        <h3 style={{margin:0, fontSize:15, fontWeight:600, color, letterSpacing:"-0.005em"}}>
                          {sc.title[lang] || sc.title.en}
                        </h3>
                        <span className="tag mono" style={{fontSize:9.5, color, borderColor:color}}>{sc.expected_status}</span>
                        {sc.loop && (
                          <span className="tag mono" style={{fontSize:9.5, color:"var(--brand-2)", borderColor:"var(--brand-2)"}}>
                            {t.demo.loop}
                          </span>
                        )}
                        {sc.stitched && (
                          <span className="tag mono" style={{fontSize:9.5}}>{t.demo.stitchedTag}</span>
                        )}
                        {sc.artifact && (
                          <span className="tag mono" style={{fontSize:9.5, color:"var(--hs)", borderColor:"var(--hs)"}}>
                            {t.demo.artifactOn}
                          </span>
                        )}
                        {sc.failure_mode && (
                          <span className="tag mono" style={{fontSize:9.5, color:"var(--hs)", borderColor:"var(--hs)"}}>
                            {t.modelInfo.failureTag}
                          </span>
                        )}
                        {isActive && (
                          <span className="tag mono" style={{fontSize:9.5, color:"var(--brand-2)", borderColor:"var(--brand-2)"}}>
                            <span className="dot live"/> {t.demo.running}
                          </span>
                        )}
                      </div>
                      <p style={{margin:"0 0 10px", fontSize:12.5, color:"var(--ink-2)", lineHeight:1.55, fontWeight:300}}>
                        {sc.summary[lang] || sc.summary.en}
                      </p>
                      <div style={{
                        padding:"9px 11px", borderRadius:7,
                        background:"var(--bg-3)", borderLeft:"2px solid " + color,
                      }}>
                        <div style={{fontSize:10, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", marginBottom:4}}>
                          {t.demo.expectLabel}
                        </div>
                        <div style={{fontSize:12, color:"var(--ink-2)", lineHeight:1.5}}>
                          {sc.expect[lang] || sc.expect.en}
                        </div>
                        {sc.expect_at_sec ? (
                          <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginTop:6}}>
                            {t.demo.watchAt} {sc.expect_at_sec}
                          </div>
                        ) : null}
                        {Array.isArray(sc.expect_models) && sc.expect_models.length > 0 && (
                          <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginTop:4}}>
                            {t.modelInfo.measuredWith}: {sc.expect_models.join(" + ")}
                          </div>
                        )}
                        {activeModel && Array.isArray(sc.expect_models) && sc.expect_models.indexOf(activeModel) < 0 && (
                          <div style={{fontSize:11, color:"var(--hs)", marginTop:6, lineHeight:1.45}}>
                            {t.modelInfo.expectModelMismatch}
                          </div>
                        )}
                        {activeModel === "riemann" && sc.in_riemann_training && (
                          <div style={{fontSize:11, color:"var(--ink-3)", marginTop:6, lineHeight:1.45}}>
                            {t.modelInfo.inTraining}
                          </div>
                        )}
                      </div>
                    </div>

                    <div style={{flex:"0 0 auto", display:"flex", flexDirection:"column", gap:8, minWidth:170}}>
                      <div style={{display:"grid", gap:4, fontSize:11}}>
                        <div style={{display:"flex", justifyContent:"space-between", gap:10}}>
                          <span style={{color:"var(--ink-3)"}}>{t.demo.caseLabel}</span>
                          <span className="mono" style={{color:"var(--ink-2)"}}>{sc.replay_case}</span>
                        </div>
                        <div style={{display:"flex", justifyContent:"space-between", gap:10}}>
                          <span style={{color:"var(--ink-3)"}}>{t.demo.durationLabel}</span>
                          <span className="mono" style={{color:"var(--ink-2)"}}>{fmtDuration(sc.duration_sec)}</span>
                        </div>
                      </div>
                      <button className={"btn btn-sm " + (isActive ? "" : "btn-primary")}
                        onClick={() => demo && demo.start(sc)}
                        style={isActive ? {} : {background:color, boxShadow:`0 2px 12px -6px ${color}`}}>
                        <window.NTIcon name="play" size={11}/>
                        {isActive ? t.demo.rerun : t.demo.run}
                      </button>
                      {isActive && (
                        <>
                          <button className="btn btn-sm" onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"live"}}))}>
                            <window.NTIcon name="live" size={11}/>{t.demo.openLive}
                          </button>
                          <button className="btn-ghost btn btn-sm" onClick={() => demo && demo.stop()}>
                            {t.demo.stop}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Your own recording */}
        <div className="panel" style={{
          padding:"16px 18px",
          border:"1px solid " + (uploadPlaying ? "var(--brand-2)" : "var(--line)"),
        }}>
          <div style={{display:"flex", alignItems:"flex-start", gap:14, flexWrap:"wrap"}}>
            <div style={{flex:"1 1 340px", minWidth:0}}>
              <div style={{display:"flex", alignItems:"center", gap:8, flexWrap:"wrap", marginBottom:5}}>
                <window.NTIcon name="download" size={14} color="var(--brand-2)"/>
                <h3 style={{margin:0, fontSize:15, fontWeight:600, letterSpacing:"-0.005em"}}>{t.demo.uploadTitle}</h3>
                {uploadPlaying && (
                  <span className="tag mono" style={{fontSize:9.5, color:"var(--brand-2)", borderColor:"var(--brand-2)"}}>
                    <span className="dot live"/> {t.demo.uploadPlaying}
                  </span>
                )}
              </div>
              <p style={{margin:"0 0 8px", fontSize:12.5, color:"var(--ink-2)", lineHeight:1.55, fontWeight:300}}>
                {t.demo.uploadBody}
              </p>
              <div style={{fontSize:11, color:"var(--ink-4)", lineHeight:1.45}}>{t.demo.uploadHint}</div>
              {uploaded && (
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginTop:7}}>
                  {uploaded.original_name} · {(Number(uploaded.size_bytes || 0) / (1024 * 1024)).toFixed(1)} MB
                </div>
              )}
              {uploadError && (
                <div style={{marginTop:8, fontSize:11.5, color:"var(--hs)"}}>
                  {t.demo.uploadError}: {uploadError}
                </div>
              )}
            </div>
            <div style={{flex:"0 0 auto", display:"flex", flexDirection:"column", gap:8, minWidth:170}}>
              <input type="file" ref={fileRef} accept=".npz,.npy" style={{display:"none"}}
                     onChange={e => { const f = e.target.files && e.target.files[0]; e.target.value = ""; handleUpload(f); }}/>
              <button className="btn btn-sm btn-primary" disabled={uploading}
                      onClick={() => fileRef.current && fileRef.current.click()}>
                <window.NTIcon name="download" size={11}/>
                {uploading ? t.demo.uploading : uploaded ? t.demo.uploadAnother : t.demo.uploadPick}
              </button>
              {uploaded && !uploading && (
                <button className="btn btn-sm" onClick={() => demo && demo.start(uploadScenario(uploaded))}>
                  <window.NTIcon name="play" size={11}/>{uploadPlaying ? t.demo.rerun : t.demo.uploadPlay}
                </button>
              )}
            </div>
          </div>
        </div>

        <div style={{fontSize:11, color:"var(--ink-4)", lineHeight:1.5, paddingBottom:8}}>
          {lang === "vi"
            ? "Prototype nghiên cứu. Bản ghi dùng cho demo là dữ liệu đã ẩn danh, không phải bệnh nhân thời gian thực, và kết quả không thay thế chẩn đoán hay CT/MRI."
            : "Research prototype. Demo recordings are de-identified data, not real-time patients, and the output does not replace a diagnosis or CT/MRI."}
        </div>
      </div>
    </div>
  );
};
