// Live Monitor — Variant C: Data-dense research console
// 3-column layout, more numbers, MFDFA spectrum visible

window.LiveMonitorC = function LiveMonitorC({mode = "HS", channels}) {
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

  const metrics = [
    {l: "ApEn̄", v: "0.842", d: "+0.12"},
    {l: "FuEn̄", v: "0.917", d: "+0.18"},
    {l: "h(2)", v: "0.71", d: "−0.04"},
    {l: "Δα", v: "0.55", d: "+0.21"},
    {l: "BSI δ", v: "0.34", d: "+0.09"},
    {l: "θ/α", v: "1.82", d: "+0.42"},
  ];

  return (
    <div style={{padding: 14, display: "grid", gridTemplateColumns: "1fr 1.4fr 1fr", gap: 12, height: "100%"}}>
      {/* Left: metrics + topomap */}
      <div style={{display: "flex", flexDirection: "column", gap: 12, minHeight: 0}}>
        <div className="panel" style={{padding: 14}}>
          <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4}}>{t.live.currentClass}</div>
          <div style={{display: "flex", alignItems: "baseline", gap: 8}}>
            <span style={{fontSize: 36, fontWeight: 700, color: color, fontFamily: "var(--font-mono)", letterSpacing: "-0.02em"}}>{(dominant[1]*100).toFixed(1)}<span style={{fontSize: 16, color: "var(--ink-3)"}}>%</span></span>
            <span style={{color: color, fontWeight: 600, fontSize: 14}}>{t.severityShort[dominant[0]]}</span>
          </div>
          <div style={{marginTop: 12}}>
            <window.RiskBars probs={probs} labels={t.severity} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span>Live metrics</span><span className="mono" style={{fontSize: 10, textTransform: "none"}}>per-window mean</span></div>
          <div style={{padding: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10}}>
            {metrics.map(m => (
              <div key={m.l} style={{padding: "8px 10px", background: "var(--bg-2)", borderRadius: 4}}>
                <div style={{fontSize: 10, color: "var(--ink-3)"}}>{m.l}</div>
                <div className="mono" style={{fontSize: 16, fontWeight: 600, marginTop: 2}}>{m.v}</div>
                <div className="mono" style={{fontSize: 10, color: m.d.startsWith("+") ? "var(--hs)" : "var(--ns)"}}>{m.d}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel" style={{flex: 1}}>
          <div className="panel-header"><span>Topomap · δ-band</span></div>
          <div style={{padding: 8, display: "grid", placeItems: "center"}}>
            <window.BrainTopomap channels={channels.slice(0, 19)} mode={mode} size={180} />
          </div>
        </div>
      </div>

      {/* Center: EEG */}
      <div className="panel" style={{display: "flex", flexDirection: "column", minHeight: 0}}>
        <div className="panel-header">
          <span>EEG · {channels.length}ch · 256Hz</span>
          <span style={{display: "flex", gap: 8}}>
            <span className="tag"><span className="dot live"/>STREAM</span>
            <span className="kbd">100µV</span>
          </span>
        </div>
        <div style={{padding: "8px 12px", flex: 1, overflow: "auto"}}>
          <window.EEGStack channels={channels} mode={mode} animated={true} traceWidth={500} traceHeight={26} />
        </div>
        <div style={{borderTop: "1px solid var(--line)", padding: "8px 12px", display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--ink-3)"}}>
          <span className="mono">epoch 1842 · t = 30:42.18</span>
          <span className="mono">SQI 0.91 · 0 rejected</span>
        </div>
      </div>

      {/* Right: features + spectrum */}
      <div style={{display: "flex", flexDirection: "column", gap: 12, minHeight: 0}}>
        <div className="panel">
          <div className="panel-header"><span>{t.live.multifractal}</span><span className="mono" style={{fontSize: 10, textTransform: "none"}}>q ∈ [−5,5]</span></div>
          <div style={{padding: 8, display: "grid", placeItems: "center"}}>
            <window.MultifractalSpectrum width={280} height={140} mode={mode} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span>{t.live.bandPower}</span></div>
          <div style={{padding: 8, display: "grid", placeItems: "center"}}>
            <window.BandPower mode={mode} width={280} height={110} />
          </div>
        </div>
        <div className="panel" style={{flex: 1, minHeight: 0, display: "flex", flexDirection: "column"}}>
          <div className="panel-header"><span>{t.live.featureImportance}</span></div>
          <div style={{padding: 10, overflow: "auto", flex: 1}}>
            <window.FeatureAttribution features={features} color={color} />
          </div>
          <div style={{borderTop: "1px solid var(--line)", padding: "8px 12px", display: "flex", gap: 8}}>
            <button className="btn" style={{flex: 1, fontSize: 11}}>{t.live.acknowledge}</button>
            <button className="btn btn-primary" style={{flex: 1, background: color, borderColor: color, fontSize: 11}}>{t.live.escalate}</button>
          </div>
        </div>
      </div>
    </div>
  );
};
