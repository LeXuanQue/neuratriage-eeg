// Live Monitor — Variant A (default): split layout
// Left: EEG waveform stack + brain topomap
// Right: big risk gauge + 3-class bars + recommendation + feature importance
// Top strip: patient summary + SQI + time-to-alert

window.LiveMonitorA = function LiveMonitorA({mode = "HS", channels, accent}) {
  const t = window.useT();
  const probs = mode === "NS" ? {NS: 0.82, IS: 0.12, HS: 0.06}
              : mode === "IS" ? {NS: 0.18, IS: 0.71, HS: 0.11}
              : {NS: 0.04, IS: 0.18, HS: 0.78};
  const dominant = Object.entries(probs).sort((a,b)=>b[1]-a[1])[0];
  const color = dominant[0] === "NS" ? "var(--ns)" : dominant[0] === "IS" ? "var(--is)" : "var(--hs)";

  const features = [
    {name: "FuEn (T4)", value: 0.184},
    {name: "Δh MFDFA (Fp2)", value: 0.142},
    {name: "α-power (O1)", value: -0.118},
    {name: "ApEn (C3)", value: 0.097},
    {name: "Hurst H(2) (P4)", value: 0.082},
    {name: "θ/α ratio (Fz)", value: 0.071},
    {name: "BSI δ-band", value: 0.064},
    {name: "Width Δα (T4)", value: 0.052},
  ];

  const history = window.useM2 ? null : null;
  const histArr = React.useMemo(() => {
    const arr = [];
    for (let i = 0; i < 80; i++) {
      const ramp = Math.max(0, (i - 50) / 30);
      const noise = () => (Math.random() - 0.5) * 0.06;
      let NS, IS, HS;
      if (mode === "HS") {
        NS = Math.max(0.02, 0.7 - ramp * 0.7 + noise());
        IS = 0.15 + ramp * 0.05 + noise();
        HS = Math.min(0.95, 0.10 + ramp * 0.78 + noise());
      } else if (mode === "IS") {
        NS = Math.max(0.05, 0.6 - ramp * 0.5 + noise());
        IS = 0.20 + ramp * 0.55 + noise();
        HS = 0.10 + noise();
      } else {
        NS = 0.78 + noise(); IS = 0.14 + noise(); HS = 0.08 + noise();
      }
      const sum = NS + IS + HS;
      arr.push({t: i, NS: NS/sum, IS: IS/sum, HS: HS/sum});
    }
    return arr;
  }, [mode]);

  return (
    <div style={{padding: 18, display: "flex", flexDirection: "column", gap: 14, minHeight: "100%"}}>
      {/* Patient strip */}
      <div className="panel" style={{
        padding: "12px 16px",
        display: "grid",
        gridTemplateColumns: "1.4fr 1fr 1fr 1fr 1fr",
        gap: 18,
        alignItems: "center",
      }}>
        <div>
          <div style={{display: "flex", alignItems: "center", gap: 10}}>
            <div style={{
              width: 38, height: 38, borderRadius: 19, background: "var(--bg-3)",
              display: "grid", placeItems: "center", fontWeight: 600, fontSize: 13,
              color: "var(--ink-2)",
            }}>NV</div>
            <div>
              <div style={{fontSize: 13.5, fontWeight: 600, letterSpacing: "-0.01em"}}>Nguyễn Văn T.</div>
              <div className="mono" style={{fontSize: 11, color: "var(--ink-3)", marginTop: 2}}>
                MRN-2026-04812 · 67{t.live.male === "M" ? "M" : "y · " + t.live.male}
              </div>
            </div>
          </div>
        </div>
        <Stat label={t.live.onsetSymptoms} value="42" unit={t.live.minsAgo} accent="var(--hs)" />
        <Stat label={t.live.sqi} value="0.91" unit="/ 1.0" sub={<span style={{color: "var(--ns)"}}>● {t.live.sqiGood}</span>} />
        <Stat label={t.live.windowSec} value="1.0" unit="s" sub={t.live.bufferLong + " 30s"} />
        <Stat label={t.live.modelAccuracy} value="96.8" unit="%" sub="ApFu-MFDFA · macro-F1 0.967" />
      </div>

      {/* Main grid */}
      <div style={{display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 14, flex: 1, minHeight: 0}}>
        {/* Left column */}
        <div style={{display: "flex", flexDirection: "column", gap: 14, minHeight: 0}}>
          <div className="panel" style={{display: "flex", flexDirection: "column", minHeight: 0, flex: 1}}>
            <div className="panel-header">
              <span>EEG · {channels.length} {t.live.channels} · 256 {t.live.hz}</span>
              <span style={{display: "flex", gap: 8, alignItems: "center"}}>
                <span className="tag"><span className="dot live"/>Streaming</span>
                <span className="kbd">100 µV</span>
              </span>
            </div>
            <div style={{padding: "10px 14px", flex: 1, overflow: "auto"}}>
              <window.EEGStack channels={channels} mode={mode} animated={true} traceWidth={760} traceHeight={28} />
            </div>
          </div>
          <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14}}>
            <div className="panel">
              <div className="panel-header"><span>{t.live.bandPower}</span><span className="mono" style={{textTransform: "none", fontSize: 10}}>relative power</span></div>
              <div style={{padding: 12, display: "grid", placeItems: "center"}}>
                <window.BandPower mode={mode} width={300} height={120} />
              </div>
            </div>
            <div className="panel">
              <div className="panel-header"><span>Topomap · δ band</span><span className="mono" style={{textTransform: "none", fontSize: 10}}>asymmetry index 0.34</span></div>
              <div style={{padding: 8, display: "grid", placeItems: "center"}}>
                <window.BrainTopomap channels={channels.slice(0, 19)} mode={mode} size={170} />
              </div>
            </div>
          </div>
        </div>
        {/* Right column */}
        <div style={{display: "flex", flexDirection: "column", gap: 14, minHeight: 0}}>
          <div className="panel" style={{padding: "16px 20px"}}>
            <div style={{display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10}}>
              <div style={{fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.06em", textTransform: "uppercase"}}>{t.live.currentClass}</div>
              <span className="mono" style={{fontSize: 10, color: "var(--ink-3)"}}>{t.live.lastUpdate} 0.8s {t.live.ago}</span>
            </div>
            <div style={{display: "flex", gap: 18, alignItems: "center"}}>
              <window.RiskGauge size={150} value={dominant[1]} color={color}
                                label={t.severityShort[dominant[0]]} sublabel={t.live.riskScore} />
              <div style={{flex: 1}}>
                <window.RiskBars probs={probs} labels={t.severity} />
              </div>
            </div>
            <div style={{
              marginTop: 14, padding: "10px 12px",
              background: mode === "HS" ? "var(--hs-soft)" : mode === "IS" ? "var(--is-soft)" : "var(--ns-soft)",
              borderRadius: 6, borderLeft: `3px solid ${color}`,
              fontSize: 12, lineHeight: 1.5, color: "var(--ink-2)",
            }}>
              <div style={{fontWeight: 600, color: color, fontSize: 11.5, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4}}>
                {t.live.recommendation}
              </div>
              {mode === "HS" && t.live.title === "Theo dõi trực tiếp"
                ? "Nghi xuất huyết não. Báo bác sĩ, ưu tiên chuyển CT không cản quang. Không dùng tiêu sợi huyết trước khi loại trừ."
                : mode === "HS"
                ? "Hemorrhagic pattern detected. Page MD, prioritize non-contrast CT. Withhold thrombolysis until ruled out."
                : mode === "IS" && t.live.title === "Theo dõi trực tiếp"
                ? "Nghi thiếu máu cục bộ. Đánh giá NIHSS, chuẩn bị CT/CTA, xem xét cửa sổ tiêu sợi huyết."
                : mode === "IS"
                ? "Ischemic pattern detected. Score NIHSS, prepare CT/CTA, evaluate thrombolysis window."
                : "Pattern within normal range. Continue passive monitoring."}
            </div>
            <div style={{display: "flex", gap: 8, marginTop: 12}}>
              <button className="btn" style={{flex: 1}}><window.Icon name="ack" size={13}/>{t.live.acknowledge}</button>
              <button className="btn btn-primary" style={{flex: 1, background: color, borderColor: color}}>
                <window.Icon name="page" size={13}/>{t.live.escalate}
              </button>
            </div>
          </div>

          <div className="panel" style={{flex: 1, minHeight: 0, display: "flex", flexDirection: "column"}}>
            <div className="panel-header">
              <span>{t.live.featureImportance}</span>
              <span className="mono" style={{textTransform: "none", fontSize: 10}}>{t.live.explainShort}</span>
            </div>
            <div style={{padding: 12, overflow: "auto", flex: 1}}>
              <window.FeatureAttribution features={features} color={color} />
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <span>Risk timeline · last 80s</span>
              <span style={{display: "flex", gap: 10, fontSize: 10, color: "var(--ink-3)"}}>
                <span><span className="dot ns" style={{marginRight: 4}}/>NS</span>
                <span><span className="dot is" style={{marginRight: 4}}/>IS</span>
                <span><span className="dot hs" style={{marginRight: 4}}/>HS</span>
              </span>
            </div>
            <div style={{padding: "8px 10px"}}>
              <window.RiskTimeline width={400} height={86} history={histArr}
                                   alerts={mode === "HS" ? [{idx: 65, value: 0.78}] : []} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

function Stat({label, value, unit, sub, accent}) {
  return (
    <div>
      <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4}}>{label}</div>
      <div style={{display: "flex", alignItems: "baseline", gap: 4}}>
        <span className="mono" style={{fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em", color: accent || "var(--ink)"}}>{value}</span>
        <span style={{fontSize: 11, color: "var(--ink-3)"}} className="mono">{unit}</span>
      </div>
      {sub && <div style={{fontSize: 10.5, color: "var(--ink-3)", marginTop: 2}}>{sub}</div>}
    </div>
  );
}
window.LiveStat = Stat;
