// All non-live screens

window.DashboardScreen = function DashboardScreen() {
  const t = window.useT();
  const patients = [
    {name: "Nguyễn Văn T.", mrn: "MRN-2026-04812", age: 67, sex: "M", risk: "HS", score: 0.78, trend: "↑", onset: 42, sqi: 0.91, bed: "ED-04"},
    {name: "Trần Thị H.", mrn: "MRN-2026-04795", age: 58, sex: "F", risk: "IS", score: 0.71, trend: "↑", onset: 88, sqi: 0.86, bed: "ED-02"},
    {name: "Lê Quốc B.", mrn: "MRN-2026-04760", age: 71, sex: "M", risk: "NS", score: 0.18, trend: "↓", onset: null, sqi: 0.94, bed: "NICU-7"},
    {name: "Phạm Mai L.", mrn: "MRN-2026-04733", age: 49, sex: "F", risk: "NS", score: 0.12, trend: "→", onset: null, sqi: 0.88, bed: "OBS-3"},
    {name: "Đỗ Hoàng K.", mrn: "MRN-2026-04701", age: 62, sex: "M", risk: "IS", score: 0.55, trend: "→", onset: 120, sqi: 0.72, bed: "ED-09"},
    {name: "Vũ Thanh N.", mrn: "MRN-2026-04680", age: 55, sex: "F", risk: "NS", score: 0.21, trend: "↓", onset: null, sqi: 0.93, bed: "NICU-3"},
  ];
  return (
    <div style={{padding: 18}}>
      <div style={{display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 14}}>
        {[
          {l: "Active monitoring", v: 6, sub: "+1 last hour"},
          {l: "High-risk active", v: 2, sub: "1 HS · 1 IS", c: "var(--hs)"},
          {l: "Alerts today", v: 14, sub: "3 acknowledged"},
          {l: "Avg time-to-alert", v: "5.4s", sub: "p95 8.1s"},
        ].map(k => (
          <div className="panel" key={k.l} style={{padding: 14}}>
            <div style={{fontSize: 10.5, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{k.l}</div>
            <div className="mono" style={{fontSize: 24, fontWeight: 600, marginTop: 6, color: k.c || "var(--ink)"}}>{k.v}</div>
            <div style={{fontSize: 10.5, color: "var(--ink-3)", marginTop: 2}}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="panel-header">
          <span>Patients under monitoring</span>
          <div style={{display: "flex", gap: 6}}>
            <button className="btn btn-ghost" style={{fontSize: 11}}>{t.actions.filter}</button>
            <button className="btn" style={{fontSize: 11}}>{t.actions.newSession}</button>
          </div>
        </div>
        <table style={{width: "100%", borderCollapse: "collapse", fontSize: 12}}>
          <thead>
            <tr style={{textAlign: "left", color: "var(--ink-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.06em"}}>
              <th style={{padding: "10px 14px", fontWeight: 500}}>Patient</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>Bed</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>Class</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>Risk</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>Trend</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>Onset</th>
              <th style={{padding: "10px 8px", fontWeight: 500}}>SQI</th>
              <th style={{padding: "10px 14px", fontWeight: 500}}></th>
            </tr>
          </thead>
          <tbody>
            {patients.map(p => {
              const c = p.risk === "HS" ? "var(--hs)" : p.risk === "IS" ? "var(--is)" : "var(--ns)";
              return (
                <tr key={p.mrn} style={{borderTop: "1px solid var(--line)"}}>
                  <td style={{padding: "10px 14px"}}>
                    <div style={{fontWeight: 500}}>{p.name}</div>
                    <div className="mono" style={{fontSize: 10.5, color: "var(--ink-3)"}}>{p.mrn} · {p.age}{p.sex}</div>
                  </td>
                  <td style={{padding: "10px 8px"}} className="mono">{p.bed}</td>
                  <td style={{padding: "10px 8px"}}>
                    <span className="tag" style={{borderColor: c, color: c}}>
                      <span className="dot" style={{background: c}}/>{p.risk}
                    </span>
                  </td>
                  <td style={{padding: "10px 8px"}} className="mono">
                    <span style={{color: c, fontWeight: 600}}>{(p.score*100).toFixed(0)}%</span>
                  </td>
                  <td style={{padding: "10px 8px", color: p.trend === "↑" ? "var(--hs)" : p.trend === "↓" ? "var(--ns)" : "var(--ink-3)"}} className="mono">{p.trend}</td>
                  <td style={{padding: "10px 8px"}} className="mono">{p.onset ? p.onset + "m" : "—"}</td>
                  <td style={{padding: "10px 8px"}} className="mono">{p.sqi.toFixed(2)}</td>
                  <td style={{padding: "10px 14px", textAlign: "right"}}>
                    <button className="btn btn-ghost" style={{fontSize: 11}}>{t.actions.seeDetail} →</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

window.PatientScreen = function PatientScreen({channels}) {
  const t = window.useT();
  const events = [
    {time: "14:42:18", level: "HS", text: "Hemorrhagic risk crossed 0.75", ack: false},
    {time: "14:38:02", level: "IS", text: "Ischemic probability rising", ack: true, by: "Dr. Lan"},
    {time: "14:30:00", level: "INFO", text: "Recording started · 19ch · ZJU4H montage", ack: true},
    {time: "14:28:44", level: "INFO", text: "Impedance check passed (all < 10 kΩ)", ack: true},
  ];
  return (
    <div style={{padding: 18, display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 14}}>
      <div className="panel" style={{padding: 18, height: "fit-content"}}>
        <div style={{display: "flex", gap: 14, alignItems: "center"}}>
          <div style={{width: 56, height: 56, borderRadius: 28, background: "var(--bg-3)", display: "grid", placeItems: "center", fontSize: 18, fontWeight: 600, color: "var(--ink-2)"}}>NV</div>
          <div>
            <div style={{fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em"}}>Nguyễn Văn T.</div>
            <div className="mono" style={{fontSize: 11.5, color: "var(--ink-3)"}}>MRN-2026-04812</div>
          </div>
        </div>
        <div style={{marginTop: 18, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, fontSize: 12}}>
          {[
            ["Age / Sex", "67 / M"], ["Bed", "ED-04"],
            ["Admitted", "14:24, 04 May"], ["Onset", "13:42 · 42m ago"],
            ["BP", "168 / 96"], ["HR", "92 bpm"],
            ["NIHSS", "8"], ["Glucose", "6.1 mmol/L"],
            ["Allergies", "—"], ["Anticoag.", "Warfarin"],
          ].map(([l, v]) => (
            <div key={l}>
              <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{l}</div>
              <div className="mono" style={{fontSize: 13, marginTop: 2}}>{v}</div>
            </div>
          ))}
        </div>
        <div style={{borderTop: "1px solid var(--line)", marginTop: 18, paddingTop: 14}}>
          <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8}}>Past medical history</div>
          <div style={{fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6}}>
            HTN (2018), AF on warfarin, prior TIA (2024), dyslipidemia.
          </div>
        </div>
      </div>

      <div style={{display: "flex", flexDirection: "column", gap: 14}}>
        <div className="panel">
          <div className="panel-header">
            <span>Risk timeline · last 30 minutes</span>
            <span style={{fontSize: 10.5, color: "var(--ink-3)"}}>4 events</span>
          </div>
          <div style={{padding: "10px 12px"}}>
            <window.RiskTimeline width={620} height={120}
              history={Array.from({length: 80}, (_, i) => {
                const ramp = Math.max(0, (i - 50) / 30);
                const NS = Math.max(0.05, 0.7 - ramp*0.6);
                const IS = 0.20 + ramp*0.05;
                const HS = 0.10 + ramp*0.7;
                const sum = NS+IS+HS;
                return {NS: NS/sum, IS: IS/sum, HS: HS/sum};
              })}
              alerts={[{idx: 65, value: 0.78}]} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span>Event log</span><button className="btn btn-ghost" style={{fontSize: 11}}>{t.actions.export}</button></div>
          <div>
            {events.map((e, i) => {
              const c = e.level === "HS" ? "var(--hs)" : e.level === "IS" ? "var(--is)" : "var(--ink-3)";
              return (
                <div key={i} style={{padding: "10px 14px", borderTop: i ? "1px solid var(--line)" : "none", display: "grid", gridTemplateColumns: "80px 60px 1fr auto", gap: 12, alignItems: "center", fontSize: 12}}>
                  <span className="mono" style={{color: "var(--ink-3)"}}>{e.time}</span>
                  <span className="tag" style={{borderColor: c, color: c, justifyContent: "center"}}>{e.level}</span>
                  <span>{e.text}</span>
                  <span style={{fontSize: 10.5, color: "var(--ink-3)"}}>{e.ack ? `✓ ${e.by || "ack"}` : "pending"}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

window.AlertReviewScreen = function AlertReviewScreen({channels}) {
  const t = window.useT();
  const features = [
    {name: "FuEn (T4)", value: 0.184},
    {name: "Δh MFDFA (Fp2)", value: 0.142},
    {name: "α-power (O1)", value: -0.118},
    {name: "ApEn (C3)", value: 0.097},
    {name: "Hurst H(2) (P4)", value: 0.082},
    {name: "θ/α ratio (Fz)", value: 0.071},
  ];
  return (
    <div style={{padding: 18, display: "grid", gridTemplateColumns: "260px 1fr", gap: 14}}>
      <div className="panel" style={{padding: 0}}>
        <div className="panel-header"><span>Alert log</span></div>
        {[
          {t: "14:42:18", n: "Nguyễn V.T.", c: "HS", s: 0.78, sel: true},
          {t: "14:38:02", n: "Trần T.H.", c: "IS", s: 0.71},
          {t: "14:11:53", n: "Đỗ H.K.", c: "IS", s: 0.62},
          {t: "13:48:09", n: "Lê Q.B.", c: "IS", s: 0.55},
          {t: "13:22:31", n: "Vũ T.N.", c: "HS", s: 0.69},
        ].map((a, i) => {
          const c = a.c === "HS" ? "var(--hs)" : "var(--is)";
          return (
            <div key={i} style={{
              padding: "12px 14px", borderTop: i ? "1px solid var(--line)" : "none",
              background: a.sel ? "var(--bg-2)" : "transparent",
              borderLeft: a.sel ? `3px solid ${c}` : "3px solid transparent",
              cursor: "pointer",
            }}>
              <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
                <span style={{fontSize: 12, fontWeight: 500}}>{a.n}</span>
                <span className="tag" style={{borderColor: c, color: c, fontSize: 10}}><span className="dot" style={{background: c}}/>{a.c}</span>
              </div>
              <div className="mono" style={{fontSize: 10.5, color: "var(--ink-3)", marginTop: 4, display: "flex", justifyContent: "space-between"}}>
                <span>{a.t}</span><span style={{color: c, fontWeight: 600}}>{(a.s*100).toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{display: "flex", flexDirection: "column", gap: 14}}>
        <div className="panel" style={{padding: "14px 18px"}}>
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-start"}}>
            <div>
              <div style={{fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{t.live.explainability}</div>
              <div style={{fontSize: 18, fontWeight: 600, marginTop: 4}}>Hemorrhagic alert · 14:42:18</div>
              <div className="mono" style={{fontSize: 11.5, color: "var(--ink-3)", marginTop: 4}}>
                Nguyễn Văn T. · MRN-2026-04812 · ApFu-MFDFA-TPELGBM v0.4.2 · epoch 1842
              </div>
            </div>
            <div style={{textAlign: "right"}}>
              <div className="mono" style={{fontSize: 28, fontWeight: 600, color: "var(--hs)"}}>78%</div>
              <div style={{fontSize: 11, color: "var(--ink-3)"}}>HS probability</div>
            </div>
          </div>
        </div>

        <div style={{display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 14}}>
          <div className="panel">
            <div className="panel-header"><span>EEG at alert moment ± 5s</span></div>
            <div style={{padding: "8px 14px", maxHeight: 320, overflow: "auto"}}>
              <window.EEGStack channels={channels.slice(0, 12)} mode="HS" animated={true} traceWidth={420} traceHeight={22} speed={0.6} />
            </div>
          </div>
          <div style={{display: "flex", flexDirection: "column", gap: 14}}>
            <div className="panel">
              <div className="panel-header"><span>{t.live.featureImportance}</span></div>
              <div style={{padding: 12}}>
                <window.FeatureAttribution features={features} color="var(--hs)" />
              </div>
            </div>
            <div className="panel">
              <div className="panel-header"><span>Topomap · δ asymmetry</span></div>
              <div style={{padding: 8, display: "grid", placeItems: "center"}}>
                <window.BrainTopomap channels={channels.slice(0, 19)} mode="HS" size={160} />
              </div>
            </div>
          </div>
        </div>

        <div className="panel" style={{padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center"}}>
          <div style={{fontSize: 12, color: "var(--ink-2)"}}>
            <b>Outcome confirmation:</b> CT confirmed deep ICH at 15:08 · confirmed by Dr. Lan
          </div>
          <div style={{display: "flex", gap: 8}}>
            <button className="btn">Mark TP</button>
            <button className="btn">Mark FP</button>
            <button className="btn btn-primary">{t.actions.export}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

window.SetupScreen = function SetupScreen({channels}) {
  const t = window.useT();
  return (
    <div style={{padding: 18, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14}}>
      <div className="panel">
        <div className="panel-header"><span>1. Patient & device</span></div>
        <div style={{padding: 18, display: "flex", flexDirection: "column", gap: 14}}>
          {[
            {l: "Patient MRN", v: "MRN-2026-04812", mono: true},
            {l: "Operator", v: "KTV Trần V.A."},
            {l: "Device", v: "g.tec g.HIamp · S/N 4421"},
            {l: "Montage", v: "10-20, 19 channels, ref Cz"},
            {l: "Sample rate", v: "256 Hz"},
            {l: "Notch", v: "50 Hz"},
            {l: "Bandpass", v: "0.5 – 45 Hz"},
          ].map(f => (
            <div key={f.l} style={{display: "grid", gridTemplateColumns: "140px 1fr", alignItems: "center", gap: 12}}>
              <span style={{fontSize: 11.5, color: "var(--ink-3)"}}>{f.l}</span>
              <div style={{padding: "7px 10px", border: "1px solid var(--line)", borderRadius: 5, background: "var(--bg-2)", fontSize: 12.5}} className={f.mono ? "mono" : ""}>{f.v}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span>2. Impedance & SQI check</span>
          <span className="tag" style={{borderColor: "var(--ns)", color: "var(--ns)"}}><span className="dot ns"/>All passing</span>
        </div>
        <div style={{padding: 16, display: "grid", placeItems: "center"}}>
          <window.BrainTopomap channels={channels.slice(0, 19)} mode="NS" size={250} />
        </div>
        <div style={{padding: "12px 18px", borderTop: "1px solid var(--line)", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, fontSize: 11.5}}>
          <div>
            <div style={{color: "var(--ink-3)"}}>Impedance</div>
            <div className="mono" style={{fontSize: 16, fontWeight: 600, color: "var(--ns)"}}>4.2 kΩ avg</div>
          </div>
          <div>
            <div style={{color: "var(--ink-3)"}}>SQI</div>
            <div className="mono" style={{fontSize: 16, fontWeight: 600, color: "var(--ns)"}}>0.91</div>
          </div>
          <div>
            <div style={{color: "var(--ink-3)"}}>Bad ch.</div>
            <div className="mono" style={{fontSize: 16, fontWeight: 600}}>0 / {channels.length}</div>
          </div>
        </div>
      </div>

      <div className="panel" style={{gridColumn: "1 / -1"}}>
        <div className="panel-header">
          <span>3. Channel status — {channels.length} channels</span>
          <button className="btn btn-primary" style={{fontSize: 11.5}}>Start recording →</button>
        </div>
        <div style={{padding: 14, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8}}>
          {channels.map((ch, i) => {
            const imp = 2 + (i * 1.7) % 8;
            const ok = imp < 8;
            return (
              <div key={ch} style={{
                border: "1px solid var(--line)", borderRadius: 5,
                padding: "8px 10px", display: "flex", justifyContent: "space-between",
                background: ok ? "var(--ns-soft)" : "var(--is-soft)",
                borderColor: ok ? "var(--ns)" : "var(--is)",
              }}>
                <span className="mono" style={{fontSize: 12, fontWeight: 600}}>{ch}</span>
                <span className="mono" style={{fontSize: 11, color: ok ? "var(--ns)" : "var(--is)"}}>{imp.toFixed(1)} kΩ</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

window.InsightsScreen = function InsightsScreen({channels}) {
  return (
    <div style={{padding: 18, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14}}>
      <div className="panel" style={{gridColumn: "1 / -1", padding: 18, display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 14}}>
        {[
          {l: "Accuracy", v: "0.9689", s: "test"},
          {l: "Macro F1", v: "0.9672", s: "5-fold"},
          {l: "AUC OVR", v: "0.991", s: "HS vs rest"},
          {l: "Brier", v: "0.041", s: "calibrated"},
          {l: "ECE", v: "0.022", s: "after Platt"},
          {l: "Recall HS", v: "0.972", s: "priority"},
        ].map(k => (
          <div key={k.l}>
            <div style={{fontSize: 10.5, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{k.l}</div>
            <div className="mono" style={{fontSize: 22, fontWeight: 600, marginTop: 4}}>{k.v}</div>
            <div style={{fontSize: 10.5, color: "var(--ink-3)"}}>{k.s}</div>
          </div>
        ))}
      </div>
      <div className="panel">
        <div className="panel-header"><span>Confusion matrix</span><span className="mono" style={{fontSize: 10, textTransform: "none"}}>n = 4218</span></div>
        <div style={{padding: 16, display: "grid", placeItems: "center"}}>
          <window.ConfusionMatrix size={220} matrix={[[1402, 18, 5], [22, 1389, 19], [4, 12, 1347]]} labels={["NS", "IS", "HS"]} />
        </div>
      </div>
      <div className="panel">
        <div className="panel-header"><span>Calibration</span><span className="mono" style={{fontSize: 10, textTransform: "none"}}>reliability</span></div>
        <div style={{padding: 16, display: "grid", placeItems: "center"}}>
          <window.CalibrationPlot width={280} height={210} />
        </div>
      </div>
      <div className="panel">
        <div className="panel-header"><span>Multifractal · per class</span></div>
        <div style={{padding: 12, display: "grid", placeItems: "center", gap: 6}}>
          <window.MultifractalSpectrum width={260} height={130} mode="NS" />
          <window.MultifractalSpectrum width={260} height={130} mode="HS" />
        </div>
      </div>
      <div className="panel" style={{gridColumn: "1 / -1"}}>
        <div className="panel-header"><span>Global feature importance · ApFu-MFDFA-TPELGBM</span></div>
        <div style={{padding: 14}}>
          <window.FeatureAttribution color="var(--brand)" features={[
            {name: "FuEn̄ all", value: 0.218},
            {name: "Δh MFDFĀ", value: 0.182},
            {name: "ApEn̄ all", value: 0.151},
            {name: "Width Δᾱ", value: 0.122},
            {name: "α relative power", value: -0.108},
            {name: "BSI δ", value: 0.094},
            {name: "θ/α ratio", value: 0.087},
            {name: "Hurst h(2)", value: -0.069},
            {name: "MFDFAI corr.", value: 0.058},
            {name: "γ-band power", value: 0.041},
          ]}/>
        </div>
      </div>
    </div>
  );
};

window.ReportsScreen = function ReportsScreen() {
  const reports = [
    {date: "04/05/2026", n: "Nguyễn Văn T.", type: "Alert summary", outcome: "TP · Hemorrhagic", id: "R-04812-A"},
    {date: "04/05/2026", n: "Trần Thị H.", type: "Session report", outcome: "Pending", id: "R-04795-S"},
    {date: "03/05/2026", n: "Lê Quốc B.", type: "Session report", outcome: "NS confirmed", id: "R-04760-S"},
    {date: "03/05/2026", n: "Phạm Mai L.", type: "Alert summary", outcome: "FP · benign artifact", id: "R-04733-A"},
    {date: "02/05/2026", n: "Đỗ Hoàng K.", type: "Session report", outcome: "TP · Ischemic", id: "R-04701-S"},
  ];
  return (
    <div style={{padding: 18, display: "flex", flexDirection: "column", gap: 14}}>
      <div className="panel">
        <div className="panel-header">
          <span>Generated reports</span>
          <div style={{display: "flex", gap: 6}}>
            <button className="btn btn-ghost" style={{fontSize: 11}}>Filter by date</button>
            <button className="btn">+ New report</button>
          </div>
        </div>
        <table style={{width: "100%", borderCollapse: "collapse", fontSize: 12.5}}>
          <thead style={{textAlign: "left", color: "var(--ink-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.06em"}}>
            <tr><th style={{padding: "10px 14px", fontWeight: 500}}>Date</th><th style={{padding: "10px 8px", fontWeight: 500}}>Patient</th><th style={{padding: "10px 8px", fontWeight: 500}}>Type</th><th style={{padding: "10px 8px", fontWeight: 500}}>Outcome</th><th style={{padding: "10px 8px", fontWeight: 500}}>ID</th><th></th></tr>
          </thead>
          <tbody>
            {reports.map(r => (
              <tr key={r.id} style={{borderTop: "1px solid var(--line)"}}>
                <td style={{padding: "11px 14px"}} className="mono">{r.date}</td>
                <td style={{padding: "11px 8px", fontWeight: 500}}>{r.n}</td>
                <td style={{padding: "11px 8px", color: "var(--ink-2)"}}>{r.type}</td>
                <td style={{padding: "11px 8px", color: "var(--ink-2)"}}>{r.outcome}</td>
                <td style={{padding: "11px 8px"}} className="mono">{r.id}</td>
                <td style={{padding: "11px 14px", textAlign: "right"}}>
                  <button className="btn btn-ghost" style={{fontSize: 11}}>PDF</button>
                  <button className="btn btn-ghost" style={{fontSize: 11}}>CSV</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

window.SettingsScreen = function SettingsScreen() {
  const t = window.useT();
  const Row = ({label, sub, children}) => (
    <div style={{display: "grid", gridTemplateColumns: "260px 1fr", padding: "16px 0", borderTop: "1px solid var(--line)", gap: 24, alignItems: "center"}}>
      <div>
        <div style={{fontSize: 13, fontWeight: 500}}>{label}</div>
        <div style={{fontSize: 11.5, color: "var(--ink-3)", marginTop: 2}}>{sub}</div>
      </div>
      <div>{children}</div>
    </div>
  );
  const Slider = ({value, unit}) => (
    <div style={{display: "flex", alignItems: "center", gap: 12}}>
      <div style={{flex: 1, height: 4, background: "var(--bg-3)", borderRadius: 2, position: "relative"}}>
        <div style={{position: "absolute", left: 0, top: 0, bottom: 0, width: value+"%", background: "var(--brand)", borderRadius: 2}}/>
        <div style={{position: "absolute", left: `calc(${value}% - 7px)`, top: -5, width: 14, height: 14, background: "var(--bg)", border: "2px solid var(--brand)", borderRadius: 7}}/>
      </div>
      <span className="mono" style={{fontSize: 12, color: "var(--ink-2)", minWidth: 60, textAlign: "right"}}>{value}{unit}</span>
    </div>
  );
  return (
    <div style={{padding: 24, maxWidth: 880}}>
      <div className="panel" style={{padding: "8px 24px"}}>
        <div style={{padding: "16px 0 4px"}}>
          <div style={{fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)"}}>Alert policy</div>
        </div>
        <Row label={t.live.threshold + " · HS"} sub="Risk score above which a hemorrhagic alert fires.">
          <Slider value={75} unit="%"/>
        </Row>
        <Row label={t.live.threshold + " · IS"} sub="Risk score above which an ischemic alert fires.">
          <Slider value={70} unit="%"/>
        </Row>
        <Row label={t.live.hysteresis} sub="Score must stay above threshold for this duration before firing.">
          <Slider value={40} unit=" s"/>
        </Row>
        <Row label={t.live.cooldown} sub="Suppress repeat alerts on the same patient within this window.">
          <Slider value={60} unit=" s"/>
        </Row>
        <Row label="EMA smoothing" sub="Exponential moving average over per-second probabilities.">
          <Slider value={30} unit=" α"/>
        </Row>
        <Row label="SQI gating" sub="Suppress decisions below this signal-quality threshold (no-decision state).">
          <Slider value={60} unit=" /1.0"/>
        </Row>
      </div>
    </div>
  );
};
