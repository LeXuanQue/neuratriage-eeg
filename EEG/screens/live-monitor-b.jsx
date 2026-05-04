// Live Monitor — Variant B: Risk-first hero
// Massive risk panel taking 60% of screen, EEG and topomap below

window.LiveMonitorB = function LiveMonitorB({mode = "HS", channels}) {
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
  ];

  const histArr = React.useMemo(() => {
    const arr = [];
    for (let i = 0; i < 80; i++) {
      const ramp = Math.max(0, (i - 50) / 30);
      const noise = () => (Math.random() - 0.5) * 0.06;
      let NS, IS, HS;
      if (mode === "HS") { NS = Math.max(0.02, 0.7 - ramp*0.7 + noise()); IS = 0.15 + ramp*0.05 + noise(); HS = Math.min(0.95, 0.10 + ramp*0.78 + noise()); }
      else if (mode === "IS") { NS = Math.max(0.05, 0.6 - ramp*0.5 + noise()); IS = 0.20 + ramp*0.55 + noise(); HS = 0.10 + noise(); }
      else { NS = 0.78 + noise(); IS = 0.14 + noise(); HS = 0.08 + noise(); }
      const sum = NS + IS + HS;
      arr.push({t: i, NS: NS/sum, IS: IS/sum, HS: HS/sum});
    }
    return arr;
  }, [mode]);

  return (
    <div style={{padding: 18, display: "flex", flexDirection: "column", gap: 14}}>
      {/* Hero risk panel */}
      <div className="panel" style={{padding: 0, overflow: "hidden", borderColor: color}}>
        <div style={{
          padding: "20px 28px",
          background: mode === "HS" ? "var(--hs-soft)" : mode === "IS" ? "var(--is-soft)" : "var(--ns-soft)",
          display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 28, alignItems: "center",
          borderBottom: `1px solid ${color}`,
        }}>
          <div>
            <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6}}>
              {t.live.currentClass}
            </div>
            <div style={{fontSize: 56, fontWeight: 700, lineHeight: 1, color: color, letterSpacing: "-0.03em", fontFamily: "var(--font-mono)"}}>
              {(dominant[1]*100).toFixed(1)}<span style={{fontSize: 24, color: "var(--ink-3)", fontWeight: 500}}>%</span>
            </div>
            <div style={{fontSize: 16, fontWeight: 600, color: color, marginTop: 6}}>
              {t.severity[dominant[0]]}
            </div>
            <div className="mono" style={{fontSize: 11, color: "var(--ink-3)", marginTop: 4}}>
              {t.live.timeToAlert} 4.2s · {t.live.lastUpdate} 0.8s {t.live.ago}
            </div>
          </div>
          <div style={{flex: 1, maxWidth: 460}}>
            <window.RiskBars probs={probs} labels={t.severity} />
          </div>
          <div style={{display: "flex", flexDirection: "column", gap: 8, minWidth: 180}}>
            <button className="btn btn-primary" style={{background: color, borderColor: color, padding: "10px 14px", fontSize: 13}}>
              <window.Icon name="page" size={14}/>{t.live.escalate}
            </button>
            <button className="btn" style={{padding: "10px 14px", fontSize: 13}}>
              <window.Icon name="ack" size={14}/>{t.live.acknowledge}
            </button>
          </div>
        </div>
        <div style={{padding: "10px 28px", display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--ink-2)"}}>
          <span><b style={{color: "var(--ink)"}}>Nguyễn Văn T.</b> · MRN-2026-04812 · 67y · {t.live.onsetSymptoms} 42 {t.live.minsAgo}</span>
          <span className="mono" style={{color: "var(--ink-3)"}}>SQI 0.91 · {channels.length}ch · 256Hz · ApFu-MFDFA</span>
        </div>
      </div>

      {/* EEG + supporting */}
      <div style={{display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 14}}>
        <div className="panel">
          <div className="panel-header">
            <span>EEG · {channels.length} {t.live.channels}</span>
            <span className="tag"><span className="dot live"/>Streaming</span>
          </div>
          <div style={{padding: "8px 14px", maxHeight: 360, overflow: "auto"}}>
            <window.EEGStack channels={channels} mode={mode} animated={true} traceWidth={520} traceHeight={22} />
          </div>
        </div>
        <div style={{display: "flex", flexDirection: "column", gap: 14}}>
          <div className="panel">
            <div className="panel-header"><span>Risk timeline · 80s</span></div>
            <div style={{padding: "6px 8px"}}>
              <window.RiskTimeline width={380} height={80} history={histArr}
                                   alerts={mode === "HS" ? [{idx: 65, value: 0.78}] : []} />
            </div>
          </div>
          <div className="panel" style={{flex: 1}}>
            <div className="panel-header"><span>{t.live.featureImportance}</span></div>
            <div style={{padding: 12}}>
              <window.FeatureAttribution features={features} color={color} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
