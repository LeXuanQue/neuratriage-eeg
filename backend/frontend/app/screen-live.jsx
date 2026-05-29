// Live Monitor — flagship screen
const { useMemo: useM_lm, useState: useS_lm, useEffect: useE_lm, useRef: useR_lm } = React;

window.LiveMonitor = function LiveMonitor({frame, t, lang, channels, animated, accent}) {
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
  const lowSqi = !hasModelEvent || Number(signalSqi || 0) < 0.70;
  const decisionLabel = lowSqi ? (lang === "en" ? "No decision" : "Chưa đủ tín hiệu") : t.severityShort[dom];
  const accentColor = lowSqi ? "var(--ink-3)" : dom === "NS" ? "var(--ns)" : dom === "IS" ? "var(--is)" : "var(--hs)";

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
      return lang === "en"
        ? {title:"Signal not usable yet", body:"SQI is below the detector gate. This usually means too few clean windows, flat/low-variance data, motion/noise, missing channels, or replay data that has not reached the model window length yet.", action:null}
        : {title:"Tín hiệu chưa đủ dùng", body:"SQI thấp hơn ngưỡng của detector. Thường do chưa đủ cửa sổ sạch, dữ liệu phẳng/biên độ thấp, nhiễu chuyển động, thiếu kênh, hoặc replay chưa đủ dài để tạo cửa sổ model.", action:null};
    }
    if (lang === "en") {
      if (dom === "NS") return {title:"No elevated model signal", body:"The current EEG window does not cross the model alert threshold. Continue monitoring; this is not a clinical exclusion.", action:null};
      if (dom === "IS") return {title:"Model output favors IS", body:"The model probability crossed the IS alert threshold on usable EEG windows. Treat this as triage support only and confirm through the standard stroke workflow.", action:"Page MD"};
      return {title:"Model output favors HS", body:"The HS output is exploratory in this prototype. It can be shown for testing, but it is not a validated diagnosis and must be confirmed by standard imaging/workflow.", action:"Page MD"};
    }
    if (dom === "NS") return {title:"Model chưa thấy tín hiệu tăng", body:"Cửa sổ EEG hiện tại chưa vượt ngưỡng cảnh báo của model. Tiếp tục theo dõi; đây không phải kết luận loại trừ lâm sàng.", action:null};
    if (dom === "IS") return {title:"Model nghiêng về IS", body:"Xác suất model vượt ngưỡng IS trên các cửa sổ EEG đủ chất lượng. Chỉ dùng để hỗ trợ triage và phải xác nhận bằng quy trình đột quỵ tiêu chuẩn.", action:"Báo MD"};
    return {title:"Model nghiêng về HS", body:"Đầu ra HS trong prototype này còn exploratory. Có thể dùng để test giao diện, nhưng chưa phải chẩn đoán đã được validation và phải xác nhận bằng hình ảnh/quy trình chuẩn.", action:"Báo MD"};
  }, [dom, lang, lowSqi, hasRawData, hasModelEvent]);
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

  return (
    <div className="nt-live-layout" style={{padding:14, height:"calc(100vh - 54px)"}}>
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
            {hasModelEvent && topSignals.length > 0
              ? <window.FeatureAttribution features={frame.features.slice(0, 5)} color={accentColor}/>
              : <div style={{height:130, display:"grid", placeItems:"center", textAlign:"center", color:"var(--ink-3)", fontSize:11, lineHeight:1.45}}>{lang==="en"?"Feature attribution waits for model events.":"Đóng góp đặc trưng chờ event model."}</div>}
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
            <span className={`tag ${lowSqi ? "" : dom.toLowerCase()}`}><span className={`dot live ${lowSqi ? "" : dom.toLowerCase()}`}/>{decisionLabel}</span>
          </div>
          {hasModelEvent ? (
            <>
              <div style={{display:"flex", justifyContent:"center", marginBottom:16}}>
                <window.RiskGauge size={150} value={lowSqi ? (signalSqi || 0) : frame.probs[dom]} color={accentColor}
                                  label={decisionLabel} sublabel={lowSqi ? "SQI gate" : t.live.currentClass}/>
              </div>
              <window.RiskBars probs={frame.probs} labels={t.severity}/>
            </>
          ) : (
            <div style={{height:190, display:"grid", placeItems:"center", color:"var(--ink-3)", fontSize:12, textAlign:"center", lineHeight:1.5}}>
              {lang==="en"?"No realtime EEG probabilities yet.":"Chưa có xác suất realtime từ raw EEG."}
            </div>
          )}
        </div>

        {/* Recommendation */}
        <div className={`panel sev-bg-${dom.toLowerCase()}`} style={{padding:"16px 18px"}}>
          <div style={{fontSize:10.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", fontWeight:500, marginBottom:10}}>{t.live.recommendation}</div>
          <h3 style={{fontSize:15, fontWeight:600, margin:"0 0 8px", color:accentColor, letterSpacing:"-0.005em"}}>{recommendation.title}</h3>
          <p style={{fontSize:12.5, color:"var(--ink-2)", margin:"0 0 14px", lineHeight:1.55, fontWeight:300}}>{recommendation.body}</p>
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
          <div style={{fontSize:11, color:"var(--ink-3)", marginBottom:7}}>{lang === "en" ? "Top contributing signals" : "Tín hiệu đóng góp chính"}</div>
          {hasModelEvent && topSignals.length > 0 ? topSignals.map((f) => (
            <div key={f.name} style={{display:"grid", gridTemplateColumns:"1fr 46px", gap:8, alignItems:"center", marginBottom:6}}>
              <div className="mono" style={{fontSize:10.5, color:"var(--ink-2)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{f.name}</div>
              <div className="mono" style={{fontSize:10.5, color:accentColor, textAlign:"right"}}>{Number(f.value || 0).toFixed(3)}</div>
            </div>
          )) : (
            <div style={{fontSize:10.5, color:"var(--ink-4)", lineHeight:1.45}}>
              {lang==="en"?"Waiting for model events from raw EEG.":"Đang chờ event model từ raw EEG."}
            </div>
          )}
          <div style={{fontSize:10.5, color:"var(--ink-4)", lineHeight:1.45, marginTop:8}}>
            {lang === "en"
              ? "Research prototype. Not a diagnosis or replacement for CT/MRI."
              : "Prototype nghiên cứu. Không thay thế chẩn đoán hoặc CT/MRI."}
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
            <div className="stat-sub">{hasModelEvent ? "EMA beta=0.3 · hys 0.65/0.55" : (lang==="en"?"No realtime event yet":"Chưa có event realtime")}</div>
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
            <span style={{color:"var(--hs)"}}>● HS</span>
          </div>
        </div>
      </div>
    </div>
  );
};
