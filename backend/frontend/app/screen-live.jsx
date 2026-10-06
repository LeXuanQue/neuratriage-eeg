// Live Monitor — flagship screen
const { useMemo: useM_lm, useState: useS_lm, useEffect: useE_lm, useRef: useR_lm } = React;

// Active real-time model + its honest held-out numbers (GET /api/model/info).
// Cached for the page: the active model only changes when the server restarts.
let _ntModelInfoCache = null;
window.useModelInfo = function useModelInfo() {
  const [info, setInfo] = useS_lm(_ntModelInfoCache);
  const [error, setError] = useS_lm(null);
  useE_lm(() => {
    if (_ntModelInfoCache || !window.NTApi) return undefined;
    let alive = true;
    window.NTApi.get("/api/model/info")
      .then(d => { _ntModelInfoCache = d; if (alive) setInfo(d); })
      .catch(e => { if (alive) setError(e); });
    return () => { alive = false; };
  }, []);
  return {info, error};
};

// "Which model is scoring, and what do we honestly know about it."
window.ModelInfoCard = function ModelInfoCard({t, info, error, compact}) {
  const m = t.modelInfo;
  if (error) return <div style={{fontSize:10.5, color:"var(--hs)"}}>{m.unavailable}</div>;
  if (!info) return <div style={{fontSize:10.5, color:"var(--ink-4)"}}>{m.loading}</div>;
  const kind = info.realtime_model === "riemann" ? "riemann" : "features";
  const r = info.riemann || {};
  const aucs = (r.eye_matched_patient_auc || []).map(v => Number(v).toFixed(2));
  const sources = Object.entries(r.train_sources || {});
  return (
    <div style={{display:"grid", gap:6, fontSize:11}}>
      <div style={{display:"flex", justifyContent:"space-between", gap:10, alignItems:"baseline"}}>
        <span style={{color:"var(--ink-3)"}}>{m.label}</span>
        <span className="mono" style={{color:"var(--ink)", textAlign:"right"}}>{m[kind]}</span>
      </div>
      {kind === "riemann" && !r.available && (
        <div style={{color:"var(--hs)"}}>{m.riemannMissing}</div>
      )}
      {kind === "riemann" && r.available && aucs.length > 0 && (
        <div style={{display:"flex", justifyContent:"space-between", gap:10}}>
          <span style={{color:"var(--ink-3)"}}>{m.heldout}</span>
          <span className="mono" style={{color:"var(--ink)"}}>{aucs.join(" / ")}</span>
        </div>
      )}
      {kind === "features" && <div style={{color:"var(--ink-3)", lineHeight:1.45}}>{m.featuresNote}</div>}
      {!compact && kind === "riemann" && sources.length > 0 && (
        <div style={{color:"var(--ink-3)", lineHeight:1.45}}>
          {m.trainedOn}: {sources.map(([k, v]) => `${k} (${v.patients} ${m.patients})`).join(", ")}
        </div>
      )}
      {!compact && kind === "riemann" && (r.known_limits || []).length > 0 && (
        <div>
          <div style={{color:"var(--ink-3)", marginBottom:3}}>{m.limitsTitle}</div>
          <ul style={{margin:0, paddingLeft:16, color:"var(--ink-2)", lineHeight:1.45}}>
            {r.known_limits.map(x => <li key={x}>{x}</li>)}
          </ul>
        </div>
      )}
      <div style={{color:"var(--ink-4)", lineHeight:1.45}}>{m.notDiagnostic}</div>
    </div>
  );
};

window.LiveMonitor = function LiveMonitor({frame, t, lang, channels, animated, accent, demo}) {
  // A2: use device channels + raw WS buffer when stream is connected
  const hasRawData = !!(frame.rawBuffer && frame.rawBuffer.length > 0);
  const hasModelEvent = hasRawData && frame.hasModelEvent === true;
  const rawSource = frame.rawSource || (hasRawData ? "raw" : "none");
  const sourceLabel = rawSource === "replay"
    ? "replay"
    : rawSource === "raw"
    ? "raw"
    : "no raw stream";
  const displayChannels = frame.deviceChannels || channels;
  const mode = frame.mode;
  const dom = frame.dominant;
  const signalSqi = hasModelEvent && typeof frame.sqi === "number" ? frame.sqi : null;
  // Trust the detector's own gate instead of re-deriving one. The backend gates
  // at sqi_threshold=0.55 and reports `no-decision` when it refuses; the UI used
  // to re-test at 0.70, so for SQI in [0.55, 0.70) it hid a decision the model
  // had actually made — and flickered whenever SQI wobbled across that line.
  const lowSqi = !hasModelEvent || frame.status === "no-decision";
  const displayMode = dom === "NS" ? "NS" : "IS";
  const decisionLabel = lowSqi ? (lang === "en" ? "No decision" : "Chưa đủ tín hiệu") : t.severityShort[displayMode];
  const accentColor = lowSqi ? "var(--ink-3)" : displayMode === "NS" ? "var(--ns)" : "var(--is)";
  // An abstention must never borrow the green "NS" styling (Jabbour et al. 2025:
  // clinicians under-diagnose when the AI abstains), nor the panel's colour while
  // nothing has been measured yet.
  const recommendationClass = !hasModelEvent ? "panel"
    : lowSqi ? "panel sev-bg-nd" : `panel sev-bg-${displayMode.toLowerCase()}`;
  const modelInfo = window.useModelInfo();

  // Alert action state
  const [currentAlertId, setCurrentAlertId] = useS_lm(null);
  const [ackState, setAckState] = useS_lm(null); // null | "loading" | "done"
  const [pageState, setPageState] = useS_lm(null); // null | "sent"
  const prevStatus = useR_lm(null);

  // When status transitions into an alert, fetch the latest open alert ID from backend
  useE_lm(() => {
    if (!hasModelEvent) {
      setCurrentAlertId(null);
      setAckState(null);
      prevStatus.current = null;
      return;
    }
    const isAlert = frame.status && frame.status.startsWith("alert");
    const wasAlert = prevStatus.current && prevStatus.current.startsWith("alert");
    prevStatus.current = frame.status;
    if (isAlert && !wasAlert && window.NTApi) {
      window.NTApi.get("/api/alerts?only_open=true&limit=1").then(items => {
        const arr = Array.isArray(items) ? items : (items?.items || []);
        if (arr.length > 0) setCurrentAlertId(arr[0].id);
      }).catch(() => {});
    }
    if (!isAlert) {
      setCurrentAlertId(null);
      setAckState(null);
    }
  }, [frame.status, hasModelEvent]);

  // Auto-clear page toast after 4s
  useE_lm(() => {
    if (pageState !== "sent") return;
    const t = setTimeout(() => setPageState(null), 4000);
    return () => clearTimeout(t);
  }, [pageState]);

  async function handleAck() {
    if (!currentAlertId || ackState === "loading") return;
    setAckState("loading");
    try {
      await window.NTApi.post(`/api/alerts/${currentAlertId}/ack`);
      setAckState("done");
    } catch (e) {
      setAckState(null);
    }
  }

  async function handleDismiss() {
    if (!currentAlertId) return;
    try {
      await window.NTApi.post(`/api/alerts/${currentAlertId}/dismiss`);
      setAckState("done");
    } catch (e) {}
  }

  function handlePageMD() {
    setPageState("sent");
  }
  const recommendation = useM_lm(() => {
    if (!hasRawData) {
      return lang === "en"
        ? {title:"Waiting for measured EEG", body:"No raw EEG chunk has arrived yet. The app is not showing simulated probabilities as realtime evidence.", action:null}
        : {title:"Đang chờ EEG đo được", body:"Chưa nhận được raw EEG chunk. Ứng dụng không hiển thị xác suất mô phỏng như bằng chứng realtime.", action:null};
    }
    if (!hasModelEvent) {
      return lang === "en"
        ? {title:"Waiting for model event", body:"Raw/replay EEG is available, but the detector has not emitted a model event yet. Probabilities and alerts are hidden until they come from the backend.", action:null}
        : {title:"Đang chờ event model", body:"Đã có EEG raw/replay, nhưng detector chưa trả event model. Xác suất và cảnh báo sẽ ẩn cho đến khi có dữ liệu từ backend.", action:null};
    }
    if (lowSqi) {
      return {title: t.nd.title, body: t.nd.body, action: null, nd: true};
    }
    if (lang === "en") {
      if (dom === "NS") return {title:"No elevated model signal", body:"The current EEG window does not cross the model alert threshold. Continue monitoring; this is not a clinical exclusion.", action:null};
      if (dom === "IS") return {title:"Model output favors IS", body:"The model probability crossed the IS alert threshold on usable EEG windows. Treat this as binary triage support only and confirm through the standard stroke workflow.", action:"Page MD"};
      return {title:"Outside binary scope", body:"The app is configured for NS-vs-IS triage. Other model outputs are not presented as validated clinical classes.", action:null};
    }
    if (dom === "NS") return {title:"Model chưa thấy tín hiệu tăng", body:"Cửa sổ EEG hiện tại chưa vượt ngưỡng cảnh báo của model. Tiếp tục theo dõi; đây không phải kết luận loại trừ lâm sàng.", action:null};
    if (dom === "IS") return {title:"Model nghiêng về IS", body:"Xác suất model vượt ngưỡng IS trên các cửa sổ EEG đủ chất lượng. Chỉ dùng để hỗ trợ triage và phải xác nhận bằng quy trình đột quỵ tiêu chuẩn.", action:"Báo MD"};
    return {title:"Ngoài phạm vi binary", body:"App đang cấu hình cho triage NS-vs-IS. Các đầu ra khác không được trình bày như class lâm sàng đã validation.", action:null};
  }, [dom, lang, lowSqi, hasRawData, hasModelEvent, t]);
  const whyTitle = lang === "en" ? "Why is this shown?" : "Vì sao hệ thống hiển thị?";
  const whyRows = [
    [lang === "en" ? "Signal state" : "Trạng thái tín hiệu", !hasRawData ? "Waiting for raw EEG" : !hasModelEvent ? "Raw EEG only - waiting for detector" : lowSqi ? "SQI gate blocks model decision" : "Usable EEG window"],
    [lang === "en" ? "Model output" : "Đầu ra model", !hasModelEvent || lowSqi ? "No clinical class shown" : `${(frame.probs[dom] * 100).toFixed(1)}% ${t.severityShort[dom]}`],
    [lang === "en" ? "SQI" : "SQI", signalSqi == null ? "not measured by detector" : `${signalSqi.toFixed(2)} ${signalSqi >= 0.85 ? "(good)" : signalSqi >= 0.7 ? "(usable)" : "(low)"}`],
    [lang === "en" ? "Backend status" : "Trạng thái backend", !hasModelEvent ? "waiting-for-model-event" : lowSqi ? "no-decision / low-sqi" : String(frame.status || "monitor")],
    [lang === "en" ? "Channels shown" : "Kênh đang hiển thị", hasRawData ? `${displayChannels.length} measured/replay channels` : "No raw stream - placeholder hidden"],
  ];
  const topSignals = (frame.features || []).slice(0, 3);
  const topomapValues = useM_lm(() => {
    if (!hasRawData || !Array.isArray(frame.rawBuffer)) return {};
    const fs = Number(frame.device?.sample_rate || 256);
    function goertzel(samples, freq) {
      const n = samples.length;
      if (n < 32) return 0;
      const k = Math.max(1, Math.round((n * freq) / fs));
      const w = (2 * Math.PI * k) / n;
      const coeff = 2 * Math.cos(w);
      let s0 = 0, s1 = 0, s2 = 0;
      for (let i = 0; i < n; i++) {
        s0 = Number(samples[i] || 0) + coeff * s1 - s2;
        s2 = s1;
        s1 = s0;
      }
      return Math.max(0, s1 * s1 + s2 * s2 - coeff * s1 * s2);
    }
    const raw = displayChannels.map((ch, i) => {
      const samples = Array.isArray(frame.rawBuffer[i]) ? frame.rawBuffer[i].slice(-Math.min(frame.rawBuffer[i].length, Math.round(fs * 2))) : [];
      const mean = samples.length ? samples.reduce((a, b) => a + Number(b || 0), 0) / samples.length : 0;
      return [ch, goertzel(samples.map(v => Number(v || 0) - mean), 2)];
    });
    const max = Math.max(...raw.map(([,v]) => v), 1e-9);
    return Object.fromEntries(raw.map(([ch, v]) => [ch, Math.max(0.05, Math.min(1, v / max))]));
  }, [hasRawData, frame.rawBuffer, frame.device?.sample_rate, displayChannels.join(",")]);

  const streamError = frame.streamError || null;

  // Demo mode context — which stored recording is running and what to watch for.
  const demoScenario = (demo && demo.scenario) || null;
  const demoTitle = demoScenario ? (demoScenario.title[lang] || demoScenario.title.en) : "";
  const demoExpect = demoScenario ? (demoScenario.expect[lang] || demoScenario.expect.en) : "";
  const demoActive = !!(demo && demo.activeId);

  // Live-device link state (BLE). Only meaningful before real samples arrive.
  const deviceStatus = frame.deviceStatus || null;
  const showDeviceStatus = !!deviceStatus && !hasRawData
    && deviceStatus.state !== "connected" && deviceStatus.state !== "stopped";
  const deviceSearching = deviceStatus && deviceStatus.state === "searching";
  const deviceStatusColor = deviceSearching ? "var(--brand-2)" : "var(--is)";

  return (
    <div className="nt-live-layout" style={{padding:14, height:"calc(100vh - 54px)"}}>
      {demoActive && (
        <div style={{
          gridColumn:"1 / -1", marginBottom:10, padding:"11px 14px",
          border:"1px solid " + (frame.replayDone ? "var(--line-2)" : "var(--brand-2)"),
          borderRadius:9,
          background:"color-mix(in oklab, var(--brand-2) 7%, transparent)",
        }}>
          <div style={{display:"flex", alignItems:"center", gap:10, flexWrap:"wrap", marginBottom:9}}>
            <span className="tag mono" style={{fontSize:9.5, color:"var(--brand-2)", borderColor:"var(--brand-2)"}}>
              {!frame.replayDone && <span className="dot live"/>}
              {frame.replayDone ? t.demo.replayDone : t.demo.banner}
            </span>
            <span style={{fontSize:13, fontWeight:600}}>{demoTitle}</span>
            {frame.replayLap > 0 && (
              <span className="tag mono" style={{fontSize:9.5, color:"var(--ink-3)"}}>
                {t.demo.lap} {frame.replayLap}
              </span>
            )}
            <span style={{fontSize:11.5, color:"var(--ink-3)", flex:"1 1 200px", minWidth:0}}>{t.demo.bannerHint}</span>
            <div style={{display:"flex", gap:7, flexWrap:"wrap"}}>
              <button className="btn btn-sm" onClick={() => demo.rerun()}>
                <window.NTIcon name="play" size={11}/>{t.demo.rerun}
              </button>
              <button className="btn btn-sm" onClick={() => demo.toggleLoop && demo.toggleLoop()}
                      title={t.demo.loopHint}
                      style={{borderColor: demo.loop ? "var(--brand-2)" : "var(--line-2)",
                              color: demo.loop ? "var(--brand-2)" : "var(--ink-2)"}}>
                {t.demo.loop}: {demo.loop ? t.demo.on : t.demo.off}
              </button>
              <button className="btn btn-sm" onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"demo"}}))}>
                {t.demo.change}
              </button>
              <button className="btn-ghost btn btn-sm" onClick={() => demo.stop()}>{t.demo.stop}</button>
            </div>
          </div>
          {window.DemoPipelineStrip && <window.DemoPipelineStrip t={t} frame={frame}/>}
          {demoExpect && (
            <div style={{marginTop:9, fontSize:11.5, color:"var(--ink-2)", lineHeight:1.5}}>
              <span style={{color:"var(--ink-3)"}}>{t.demo.expectLabel}: </span>{demoExpect}
            </div>
          )}
        </div>
      )}
      {showDeviceStatus && (
        <div role="status" style={{
          gridColumn:"1 / -1", marginBottom:10, padding:"12px 15px",
          border:"1px solid " + deviceStatusColor, borderRadius:9,
          background:"color-mix(in oklab, " + deviceStatusColor + " 8%, transparent)",
          display:"flex", alignItems:"center", gap:13, flexWrap:"wrap",
        }}>
          <window.NTIcon name="bt" size={16} color={deviceStatusColor}/>
          <div style={{flex:"1 1 300px", minWidth:0}}>
            <div style={{fontSize:13.5, fontWeight:600, color:deviceStatusColor, marginBottom:3}}>
              {deviceSearching ? t.deviceLink.searching
                : deviceStatus.state === "blocked" ? t.deviceLink.blocked
                : t.deviceLink.error}
              {deviceStatus.retryInSec != null && (
                <span className="mono" style={{fontWeight:400, fontSize:11, color:"var(--ink-3)", marginLeft:8}}>
                  {t.deviceLink.retryIn} {deviceStatus.retryInSec}{lang === "vi" ? " " : ""}{t.deviceLink.seconds}
                </span>
              )}
            </div>
            <div style={{fontSize:12, color:"var(--ink-3)", lineHeight:1.5}}>
              {deviceSearching ? t.deviceLink.searchingHint : t.deviceLink.errorHint}
            </div>
            {deviceStatus.message && (
              <div className="mono" style={{fontSize:10.5, color:"var(--ink-4)", marginTop:4}}>
                {deviceStatus.message}
              </div>
            )}
          </div>
          <button className="btn btn-sm"
                  onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"demo"}}))}>
            <window.NTIcon name="play" size={11}/>{t.deviceLink.openDemo}
          </button>
        </div>
      )}
      {demo && !demoActive && !hasRawData && !showDeviceStatus && (
        <div style={{
          gridColumn:"1 / -1", marginBottom:10, padding:"14px 16px",
          border:"1px dashed var(--line-2)", borderRadius:9, background:"var(--bg-2)",
          display:"flex", alignItems:"center", gap:14, flexWrap:"wrap",
        }}>
          <div style={{flex:"1 1 320px", minWidth:0}}>
            <div style={{fontSize:14, fontWeight:600, marginBottom:4}}>{t.demo.ctaTitle}</div>
            <div style={{fontSize:12, color:"var(--ink-3)", lineHeight:1.55}}>{t.demo.ctaBody}</div>
          </div>
          <button className="btn btn-primary btn-sm"
                  onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"demo"}}))}>
            <window.NTIcon name="play" size={11}/>{t.demo.cta}
          </button>
        </div>
      )}
      {streamError && (
        <div
          role="alert"
          style={{
            gridColumn:"1 / -1",
            display:"flex", alignItems:"center", gap:10,
            padding:"10px 14px", marginBottom:10,
            border:"1px solid var(--hs)",
            background:"rgba(220,70,70,0.12)",
            borderRadius:8, color:"var(--hs)",
            fontFamily:"var(--font-mono)", fontSize:13,
          }}>
          <window.NTIcon name="alerts" size={15} color="var(--hs)"/>
          <span>
            <b>{lang==="en" ? "Cannot start stream" : "Không thể bắt đầu luồng"}:</b>{" "}
            {streamError}
          </span>
        </div>
      )}
      {/* LEFT — EEG + topomap + features */}
      <div className="nt-live-main">
        {/* EEG strip */}
        <div className="panel" style={{display:"flex", flexDirection:"column", minHeight:0}}>
          <div className="panel-header">
            <div className="title">
              <window.NTIcon name="live" size={13} color="var(--brand-2)"/>
              <span>EEG · {hasRawData ? displayChannels.length : 0} {t.live.channels} · {frame.device?.sample_rate || 256} {t.live.hz}</span>
            </div>
            <div style={{display:"flex", gap:8, alignItems:"center"}}>
              <button
                type="button"
                onClick={() => { if (window.WSStream && window.WSStream.setArtifact) window.WSStream.setArtifact(!frame.artifactOn); }}
                disabled={!hasRawData}
                title={lang==="en"
                  ? "Demo: inject a signal artifact so SQI drops and the interface enters No-Decision"
                  : "Demo: chèn nhiễu để SQI tụt và giao diện vào trạng thái No-Decision"}
                className="tag"
                style={{
                  cursor: hasRawData ? "pointer" : "not-allowed",
                  fontFamily:"var(--font-mono)",
                  opacity: hasRawData ? 1 : 0.5,
                  border:"1px solid " + (frame.artifactOn ? "var(--hs)" : "var(--ink-4)"),
                  background: frame.artifactOn ? "rgba(220,70,70,0.14)" : "transparent",
                  color: frame.artifactOn ? "var(--hs)" : "var(--ink-3)",
                }}>
                {frame.artifactOn
                  ? (lang==="en" ? "⚠ Artifact ON" : "⚠ Nhiễu BẬT")
                  : (lang==="en" ? "Inject artifact" : "Chèn nhiễu")}
              </button>
              {hasRawData
                ? <span className="tag" style={{fontFamily:"var(--font-mono)", color:"var(--brand-2)"}}>{sourceLabel} · {displayChannels.length}ch</span>
                : <span className="tag" style={{fontFamily:"var(--font-mono)"}}>no raw stream</span>
              }
              <span style={{display:"flex", alignItems:"center", gap:5, fontSize:10.5, color:"var(--ink-3)"}}>
                <span className="dot live" style={{background:hasRawData?"var(--brand-2)":"var(--ink-4)"}}/>
                <span className="mono">{hasRawData ? sourceLabel : "waiting"}</span>
              </span>
            </div>
          </div>
          <div style={{flex:1, padding:"10px 12px", overflowY:"auto", minHeight:0}}>
            {hasRawData ? (
              <window.EEGStack
                channels={displayChannels}
                mode={mode}
                animated={false}
                traceHeight={32}
                rawData={frame.rawBuffer || null}
              />
            ) : (
              <div style={{height:"100%", minHeight:180, display:"grid", placeItems:"center", color:"var(--ink-3)", fontSize:12, textAlign:"center", padding:18}}>
                {lang === "en"
                  ? "Waiting for measured EEG samples. The app no longer draws synthetic traces as if they were live data."
                  : "Đang chờ mẫu EEG đo được. Ứng dụng không vẽ sóng giả như dữ liệu realtime."}
              </div>
            )}
          </div>
        </div>

        {/* Bottom row: topomap + features + bandpower */}
        <div className="nt-live-bottom-grid">
          <div className="panel" style={{padding:12, display:"flex", flexDirection:"column", alignItems:"center", minWidth:0}}>
            <div style={{alignSelf:"stretch", display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
              <div style={{fontSize:10, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500}}>Topomap · δ</div>
            </div>
            {hasRawData
              ? <window.BrainTopomap size={150} channels={displayChannels} mode={mode} showLabels={true} valuesByChan={topomapValues}/>
              : <div style={{height:150, display:"grid", placeItems:"center", textAlign:"center", color:"var(--ink-3)", fontSize:11, lineHeight:1.45}}>{lang==="en"?"Topomap waits for raw EEG.":"Topomap chờ raw EEG."}</div>}
          </div>

          <div className="panel" style={{padding:12, overflow:"hidden", minWidth:0}}>
            <div style={{fontSize:10, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500, marginBottom:12}}>{t.live.explainShort}</div>
            {/* Nothing in the backend computes attributions yet, so never draw bars. */}
            {hasModelEvent && topSignals.length > 0
              ? <window.FeatureAttribution features={frame.features.slice(0, 5)} color={accentColor}/>
              : <div style={{height:130, display:"grid", placeItems:"center", textAlign:"center", color:"var(--ink-3)", fontSize:11, lineHeight:1.45, padding:"0 6px"}}>{t.modelInfo.explainUnavailable}</div>}
          </div>

          <div className="panel" style={{padding:"12px 12px 4px", minWidth:0}}>
            <div style={{fontSize:10, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500, marginBottom:4}}>{t.live.bandPower}</div>
            {hasRawData
              ? <window.BandPower mode={mode} width={196} height={130} rawData={frame.rawBuffer || null} fs={frame.device?.sample_rate || 256}/>
              : <div style={{height:130, display:"grid", placeItems:"center", textAlign:"center", color:"var(--ink-3)", fontSize:11, lineHeight:1.45}}>{lang==="en"?"Band power waits for measured samples.":"Phổ năng lượng chờ mẫu đo được."}</div>}
          </div>
        </div>
      </div>

      {/* RIGHT — risk + recommendation + sqi + history */}
      <div className="nt-live-side">
        {/* Risk gauge */}
        <div className="panel" style={{padding:18}}>
          <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:14}}>
            <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500}}>{t.live.riskScore}</div>
            <span className={`tag ${lowSqi ? "" : displayMode.toLowerCase()}`}><span className={`dot live ${lowSqi ? "" : displayMode.toLowerCase()}`}/>{decisionLabel}</span>
          </div>
          {hasModelEvent ? (
            <>
              <div style={{display:"flex", justifyContent:"center", marginBottom:16}}>
                <window.RiskGauge size={150} value={lowSqi ? (signalSqi || 0) : frame.probs[displayMode]} color={accentColor}
                                  label={decisionLabel} sublabel={lowSqi ? t.nd.gaugeSub : t.live.currentClass}/>
              </div>
              {/* Under No-Decision the bars are not a result: grey them out so a
                  50/50 or green NS bar is not read as "normal". */}
              <div style={lowSqi ? {opacity:0.3, filter:"grayscale(1)"} : undefined} aria-hidden={lowSqi || undefined}>
                <window.RiskBars probs={frame.probs} labels={t.severity}/>
              </div>
            </>
          ) : (
            <div style={{height:190, display:"grid", placeItems:"center", color:"var(--ink-3)", fontSize:12, textAlign:"center", lineHeight:1.5}}>
              {lang==="en"?"No realtime EEG probabilities yet.":"Chưa có xác suất realtime từ raw EEG."}
            </div>
          )}
          <div style={{marginTop:12, paddingTop:10, borderTop:"1px solid var(--line)"}}>
            <window.ModelInfoCard t={t} info={modelInfo.info} error={modelInfo.error} compact={true}/>
          </div>
        </div>

        {/* Recommendation */}
        <div className={recommendationClass} style={{padding:"16px 18px"}} role={recommendation.nd ? "alert" : undefined}>
          <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500, marginBottom:10}}>{t.live.recommendation}</div>
          <h3 style={{fontSize:15, fontWeight:600, margin:"0 0 8px", color: recommendation.nd ? "var(--ink)" : accentColor, letterSpacing:"-0.005em"}}>{recommendation.title}</h3>
          <p style={{fontSize:12.5, color:"var(--ink-2)", margin:"0 0 14px", lineHeight:1.55, fontWeight:300}}>{recommendation.body}</p>
          {recommendation.nd && (
            <div style={{margin:"0 0 14px"}}>
              <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-2)", fontWeight:600, marginBottom:6}}>{t.nd.actionsTitle}</div>
              <ol style={{margin:0, paddingLeft:18, fontSize:12.5, color:"var(--ink)", lineHeight:1.55}}>
                {t.nd.actions.map(a => <li key={a}>{a}</li>)}
              </ol>
            </div>
          )}
          <div style={{display:"flex", gap:8, flexWrap:"wrap"}}>
            {recommendation.action && (
              <button
                className="btn btn-primary btn-sm"
                style={{background:accentColor, boxShadow:`0 2px 12px -4px ${accentColor}`, opacity: pageState === "sent" ? 0.7 : 1}}
                onClick={handlePageMD}
                disabled={pageState === "sent"}
                title={lang === "en"
                  ? "Simulated escalation — this prototype has no real paging/notification integration."
                  : "Escalation mô phỏng — prototype chưa tích hợp paging/thông báo thật."}
              >
                <window.NTIcon name="page" size={12}/>
                {pageState === "sent" ? (lang === "en" ? "Paged (demo) ✓" : "Đã báo (demo) ✓") : recommendation.action}
              </button>
            )}
            <button
              className="btn btn-sm"
              onClick={handleAck}
              disabled={lowSqi || !currentAlertId || ackState === "loading" || ackState === "done"}
              title={!currentAlertId ? "No backend alert id available" : lowSqi ? "Blocked by low SQI" : ""}
              style={{opacity: ackState === "done" || lowSqi || !currentAlertId ? 0.55 : 1}}
            >
              <window.NTIcon name="ack" size={12}/>
              {ackState === "loading" ? "…" : ackState === "done" ? (lang === "en" ? "Acknowledged ✓" : "Đã xác nhận ✓") : t.live.acknowledge}
            </button>
            {dom !== "NS" && (
              <button
                className="btn-ghost btn btn-sm"
                onClick={handleDismiss}
                disabled={lowSqi || !currentAlertId || ackState === "done"}
                style={{opacity: ackState === "done" || lowSqi || !currentAlertId ? 0.4 : 1}}
              >
                {t.live.dismiss}
              </button>
            )}
          </div>
        </div>

        {/* Why this alert */}
        <div className="panel" style={{padding:14}}>
          <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500, marginBottom:10}}>{whyTitle}</div>
          <div style={{display:"grid", gap:7, marginBottom:12}}>
            {whyRows.map(([k, v]) => (
              <div key={k} style={{display:"flex", justifyContent:"space-between", gap:12, fontSize:11.5}}>
                <span style={{color:"var(--ink-3)"}}>{k}</span>
                <span className="mono" style={{color:"var(--ink-1)", textAlign:"right"}}>{v}</span>
              </div>
            ))}
          </div>
          {/* Was "Top contributing signals": the backend never sends attributions, so
              this slot now states which model is scoring and its known limits. */}
          <window.ModelInfoCard t={t} info={modelInfo.info} error={modelInfo.error} compact={false}/>
          <div style={{fontSize:10.5, color:"var(--ink-4)", lineHeight:1.45, marginTop:8}}>
            {lang === "en"
              ? "Not a replacement for CT/MRI."
              : "Không thay thế CT/MRI."}
          </div>
          {(lowSqi || !currentAlertId) && (
            <div style={{fontSize:10.5, color:lowSqi ? "var(--is)" : "var(--ink-4)", lineHeight:1.45, marginTop:8}}>
              {lowSqi
                ? (lang === "en" ? "Actions are disabled until SQI returns to usable range." : "Tác vụ được khóa đến khi SQI đạt ngưỡng sử dụng.")
                : (lang === "en" ? "Ack/dismiss is disabled until a backend alert is available." : "Ack/dismiss bị khóa vì chưa có alert id từ backend.")}
            </div>
          )}
        </div>

        {/* SQI + Timing */}
        <div className="panel nt-two-grid" style={{padding:14}}>
          <div>
            <div className="stat-lbl">{t.live.sqi}</div>
            <window.SQIBar value={signalSqi} width={130}/>
            <div className="stat-sub">
              {!hasRawData
                ? (lang === "en" ? "Waiting for raw EEG" : "Đang chờ raw EEG")
                : !hasModelEvent ? (lang === "en" ? "Waiting for detector SQI" : "Đang chờ SQI từ detector")
                : signalSqi >= 0.85 ? t.live.sqiGood : signalSqi >= 0.7 ? t.live.sqiOk
                : (lang === "en" ? "Low - model decision gated" : "Thấp - model chưa kết luận")}
            </div>
          </div>
          <div>
            <div className="stat-lbl">{t.live.timeToAlert}</div>
            <div className="stat-val">
              {!hasModelEvent || frame.timeToAlertSec === null ? "—" : frame.timeToAlertSec.toFixed(1)}
              <span className="unit">{t.live.seconds}</span>
            </div>
            <div className="stat-sub">{hasModelEvent ? "EMA beta=0.35 · hys 0.80/0.60" : (lang==="en"?"No realtime event yet":"Chưa có event realtime")}</div>
          </div>
        </div>

        {/* History */}
        <div className="panel" style={{padding:14}}>
          <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10}}>
            <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500}}>{lang==="vi"?"Xác suất 80 giây":"80-second probability"}</div>
            <span className="mono" style={{fontSize:10, color:"var(--ink-3)"}}>−80s → now</span>
          </div>
          {hasModelEvent
            ? <window.RiskTimeline width={310} height={84} history={frame.history} alerts={[]} live={true}/>
            : <div style={{height:84, display:"grid", placeItems:"center", color:"var(--ink-3)", fontSize:11}}>{lang==="en"?"Waiting for backend events.":"Đang chờ event từ backend."}</div>}
          <div style={{display:"flex", justifyContent:"space-between", marginTop:8, fontSize:10.5, fontFamily:"var(--font-mono)"}}>
            <span style={{color:"var(--ns)"}}>● NS</span>
            <span style={{color:"var(--is)"}}>● IS</span>
          </div>
        </div>
      </div>
    </div>
  );
};
