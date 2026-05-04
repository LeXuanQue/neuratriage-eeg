// Visualization helpers for EEG Stroke app
// All output is small inline SVG — no external libs.

const { useMemo: useM2, useState: useS2, useEffect: useE2 } = React;

// ──────────────────────────────────────────────────────────────────
// Risk score 3-class horizontal bar
window.RiskBars = function RiskBars({probs, labels, t}) {
  const items = [
    {key: "NS", value: probs.NS, color: "var(--ns)", soft: "var(--ns-soft)"},
    {key: "IS", value: probs.IS, color: "var(--is)", soft: "var(--is-soft)"},
    {key: "HS", value: probs.HS, color: "var(--hs)", soft: "var(--hs-soft)"},
  ];
  return (
    <div style={{display: "flex", flexDirection: "column", gap: 14}}>
      {items.map(it => (
        <div key={it.key}>
          <div style={{display: "flex", justifyContent: "space-between",
                       fontSize: 12, marginBottom: 6, alignItems: "center"}}>
            <span style={{display: "flex", alignItems: "center", gap: 8}}>
              <span className="dot" style={{background: it.color, width: 8, height: 8}} />
              <span style={{color: "var(--ink-2)"}}>{labels[it.key]}</span>
            </span>
            <span className="mono" style={{fontWeight: 600, fontSize: 14, color: "var(--ink)"}}>
              {(it.value * 100).toFixed(1)}<span style={{color: "var(--ink-3)", fontWeight: 400, fontSize: 11}}>%</span>
            </span>
          </div>
          <div style={{height: 8, background: it.soft, borderRadius: 4, overflow: "hidden", position: "relative"}}>
            <div style={{
              position: "absolute", inset: 0, width: (it.value*100)+"%",
              background: it.color, transition: "width 0.4s ease",
              borderRadius: 4,
            }}/>
          </div>
        </div>
      ))}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Big circular risk gauge
window.RiskGauge = function RiskGauge({size = 200, value, label, sublabel, color}) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = c * value;
  return (
    <div style={{position: "relative", width: size, height: size}}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r}
                stroke="var(--bg-3)" strokeWidth={stroke} fill="none" />
        <circle cx={size/2} cy={size/2} r={r}
                stroke={color} strokeWidth={stroke} fill="none"
                strokeDasharray={`${dash} ${c-dash}`}
                strokeDashoffset={c * 0.25}
                strokeLinecap="round"
                style={{transition: "stroke-dasharray 0.4s ease, stroke 0.4s ease"}} />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        gap: 2,
      }}>
        <div className="mono" style={{fontSize: size * 0.27, fontWeight: 600, color: "var(--ink)", lineHeight: 1, letterSpacing: "-0.02em"}}>
          {(value * 100).toFixed(0)}<span style={{fontSize: size * 0.13, color: "var(--ink-3)"}}>%</span>
        </div>
        <div style={{fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-3)", marginTop: 4}}>
          {sublabel}
        </div>
        <div style={{fontSize: 13, fontWeight: 500, color: color, marginTop: 2}}>{label}</div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// SHAP-style feature attribution bars (positive/negative)
window.FeatureAttribution = function FeatureAttribution({features, color}) {
  const max = Math.max(...features.map(f => Math.abs(f.value)));
  return (
    <div style={{display: "flex", flexDirection: "column", gap: 8}}>
      {features.map((f, i) => {
        const pct = Math.abs(f.value) / max;
        const positive = f.value > 0;
        return (
          <div key={i} style={{display: "grid", gridTemplateColumns: "120px 1fr 60px", alignItems: "center", gap: 10, fontSize: 11.5}}>
            <span className="mono" style={{color: "var(--ink-2)"}}>{f.name}</span>
            <div style={{position: "relative", height: 16, background: "var(--bg-3)", borderRadius: 2, overflow: "hidden"}}>
              <div style={{
                position: "absolute",
                left: positive ? "50%" : `${50 - pct*50}%`,
                width: `${pct*50}%`,
                top: 0, bottom: 0,
                background: positive ? color : "var(--ink-4)",
              }}/>
              <div style={{position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--line-2)"}}/>
            </div>
            <span className="mono" style={{
              color: positive ? color : "var(--ink-3)",
              textAlign: "right",
              fontVariantNumeric: "tabular-nums",
              fontSize: 11,
            }}>{positive ? "+" : ""}{f.value.toFixed(3)}</span>
          </div>
        );
      })}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Multifractal spectrum f(α) inverted-U curve
window.MultifractalSpectrum = function MultifractalSpectrum({width = 280, height = 140, mode = "NS"}) {
  const params = {
    NS: {center: 1.0, width: 0.45, height: 1.0, color: "var(--ns)"},
    IS: {center: 1.15, width: 0.30, height: 0.92, color: "var(--is)"},
    HS: {center: 1.25, width: 0.55, height: 0.95, color: "var(--hs)"},
  }[mode];
  const points = useM2(() => {
    const pts = [];
    for (let a = 0.4; a <= 1.7; a += 0.02) {
      const f = params.height * Math.exp(-Math.pow((a - params.center) / params.width, 2) * 2);
      pts.push([a, f]);
    }
    return pts;
  }, [mode]);

  const xMin = 0.4, xMax = 1.7;
  const yMin = 0, yMax = 1.05;
  const pad = 26;
  const xAt = a => pad + (a - xMin) / (xMax - xMin) * (width - pad - 12);
  const yAt = f => height - pad + 4 - (f - yMin) / (yMax - yMin) * (height - pad - 18);

  const path = points.map(([a, f], i) => (i === 0 ? "M" : "L") + xAt(a).toFixed(1) + "," + yAt(f).toFixed(1)).join(" ");

  return (
    <svg width={width} height={height} style={{display: "block"}}>
      {/* axes */}
      <line x1={pad} y1={height - pad + 4} x2={width - 8} y2={height - pad + 4} stroke="var(--line-2)" />
      <line x1={pad} y1={8} x2={pad} y2={height - pad + 4} stroke="var(--line-2)" />
      {[0.6, 0.9, 1.2, 1.5].map(a => (
        <g key={a}>
          <line x1={xAt(a)} y1={height-pad+4} x2={xAt(a)} y2={height-pad+8} stroke="var(--ink-4)" />
          <text x={xAt(a)} y={height-6} fontSize="9" fill="var(--ink-3)" textAnchor="middle" fontFamily="var(--font-mono)">{a.toFixed(1)}</text>
        </g>
      ))}
      <text x={width/2} y={height-pad+22} fontSize="9" fill="var(--ink-3)" textAnchor="middle" fontStyle="italic">α (singularity)</text>
      <text x={6} y={20} fontSize="9" fill="var(--ink-3)" fontStyle="italic">f(α)</text>
      <path d={path} fill={params.color} fillOpacity="0.12" stroke={params.color} strokeWidth="1.5" />
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Mini brain topomap — circle with electrode positions; colored by value
const ELECTRODE_POSITIONS = {
  // approximate 10-20 layout on a unit circle (cx, cy in [-1, 1])
  Fp1: [-0.30, -0.85], Fp2: [0.30, -0.85],
  F7: [-0.75, -0.55], F3: [-0.40, -0.45], Fz: [0, -0.45], F4: [0.40, -0.45], F8: [0.75, -0.55],
  T3: [-0.95, 0], C3: [-0.45, 0], Cz: [0, 0], C4: [0.45, 0], T4: [0.95, 0],
  T5: [-0.75, 0.55], P3: [-0.40, 0.45], Pz: [0, 0.45], P4: [0.40, 0.45], T6: [0.75, 0.55],
  O1: [-0.30, 0.85], O2: [0.30, 0.85],
};

window.BrainTopomap = function BrainTopomap({size = 200, channels, valuesByChan = {}, mode = "NS", title}) {
  // pseudo-random per-channel intensity if not provided
  const values = useM2(() => {
    if (Object.keys(valuesByChan).length) return valuesByChan;
    const v = {};
    channels.forEach((ch, i) => {
      let base;
      if (mode === "NS") base = 0.2 + 0.1 * Math.sin(i*1.7);
      else if (mode === "IS") base = 0.5 + 0.2 * Math.sin(i*0.9);
      else base = 0.4 + 0.3 * Math.sin(i*1.1) + (i === 5 || i === 11 ? 0.4 : 0);
      v[ch] = Math.max(0, Math.min(1, base));
    });
    return v;
  }, [mode, channels.join(",")]);

  const cx = size/2, cy = size/2, r = size * 0.42;
  const colorFor = (v) => {
    // map 0->cool blue, 1-> warm red via oklch
    return `oklch(${(0.85 - v*0.4).toFixed(3)} ${(0.05 + v*0.15).toFixed(3)} ${(240 - v*215).toFixed(0)})`;
  };

  return (
    <div style={{display: "flex", flexDirection: "column", alignItems: "center", gap: 6}}>
      {title && <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{title}</div>}
      <svg width={size} height={size} style={{display: "block"}}>
        {/* head */}
        <circle cx={cx} cy={cy} r={r} fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1.5" />
        {/* nose */}
        <path d={`M ${cx-7} ${cy-r+2} L ${cx} ${cy-r-7} L ${cx+7} ${cy-r+2} Z`} fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1.5" />
        {/* ears */}
        <ellipse cx={cx-r} cy={cy} rx="5" ry="11" fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1.2" />
        <ellipse cx={cx+r} cy={cy} rx="5" ry="11" fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1.2" />
        {/* electrodes */}
        {channels.map((ch) => {
          const pos = ELECTRODE_POSITIONS[ch];
          if (!pos) return null;
          const ex = cx + pos[0] * r * 0.85;
          const ey = cy + pos[1] * r * 0.85;
          const v = values[ch] ?? 0.2;
          return (
            <g key={ch}>
              <circle cx={ex} cy={ey} r={size * 0.045} fill={colorFor(v)} stroke="var(--ink)" strokeOpacity="0.15" strokeWidth="0.7" />
              <text x={ex} y={ey + 2.5} fontSize={size * 0.04} textAnchor="middle"
                    fill={v > 0.55 ? "white" : "var(--ink-2)"}
                    fontFamily="var(--font-mono)">{ch}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Risk-over-time sparkline w/ class regions
window.RiskTimeline = function RiskTimeline({width = 600, height = 90, history, alerts = []}) {
  // history: array of {t, NS, IS, HS}
  const xAt = (i) => (i / (history.length - 1)) * (width - 20) + 10;
  const yAt = (v) => height - 12 - v * (height - 22);
  const pathFor = (key) => history.map((h, i) => (i === 0 ? "M" : "L") + xAt(i).toFixed(1) + "," + yAt(h[key]).toFixed(1)).join(" ");
  return (
    <svg width={width} height={height} style={{display: "block"}}>
      {/* gridlines */}
      {[0.25, 0.5, 0.75].map(g => (
        <line key={g} x1={10} x2={width-10} y1={yAt(g)} y2={yAt(g)} stroke="var(--line)" strokeDasharray="2 4" />
      ))}
      <path d={pathFor("NS")} fill="none" stroke="var(--ns)" strokeWidth="1.2" />
      <path d={pathFor("IS")} fill="none" stroke="var(--is)" strokeWidth="1.2" />
      <path d={pathFor("HS")} fill="none" stroke="var(--hs)" strokeWidth="1.8" />
      {alerts.map((a, i) => (
        <g key={i}>
          <line x1={xAt(a.idx)} x2={xAt(a.idx)} y1={6} y2={height-10} stroke="var(--hs)" strokeDasharray="3 3" />
          <circle cx={xAt(a.idx)} cy={yAt(a.value)} r="3" fill="var(--hs)" />
        </g>
      ))}
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Calibration plot
window.CalibrationPlot = function CalibrationPlot({width = 280, height = 200}) {
  const pad = 32;
  const ideal = [];
  const observed = [
    [0.05, 0.04], [0.15, 0.12], [0.25, 0.27], [0.35, 0.39],
    [0.45, 0.46], [0.55, 0.59], [0.65, 0.68], [0.75, 0.74],
    [0.85, 0.83], [0.95, 0.91],
  ];
  const xAt = v => pad + v * (width - pad - 12);
  const yAt = v => height - pad - v * (height - pad - 12);
  return (
    <svg width={width} height={height}>
      {/* axes */}
      <line x1={pad} y1={height-pad} x2={width-12} y2={height-pad} stroke="var(--line-2)" />
      <line x1={pad} y1={12} x2={pad} y2={height-pad} stroke="var(--line-2)" />
      {/* perfect line */}
      <line x1={xAt(0)} y1={yAt(0)} x2={xAt(1)} y2={yAt(1)} stroke="var(--ink-4)" strokeDasharray="3 3" />
      {/* observed */}
      <path d={observed.map(([x,y],i)=>(i===0?"M":"L")+xAt(x)+","+yAt(y)).join(" ")} fill="none" stroke="var(--brand)" strokeWidth="1.5"/>
      {observed.map(([x,y],i)=>(<circle key={i} cx={xAt(x)} cy={yAt(y)} r="3" fill="var(--brand)" />))}
      <text x={width/2} y={height-6} fontSize="9" fill="var(--ink-3)" textAnchor="middle">Predicted probability</text>
      <text x={10} y={height/2} fontSize="9" fill="var(--ink-3)" transform={`rotate(-90 10 ${height/2})`} textAnchor="middle">Observed frequency</text>
    </svg>
  );
};

// Confusion matrix
window.ConfusionMatrix = function ConfusionMatrix({size = 200, matrix, labels}) {
  const cell = size / 3;
  const max = Math.max(...matrix.flat());
  return (
    <svg width={size + 50} height={size + 30}>
      {matrix.map((row, i) => row.map((v, j) => {
        const intensity = v / max;
        return (
          <g key={`${i}-${j}`}>
            <rect x={50 + j*cell} y={i*cell} width={cell} height={cell}
                  fill={`oklch(${0.97 - intensity*0.45} ${0.04 + intensity*0.10} 245)`}
                  stroke="var(--bg)" strokeWidth="2" />
            <text x={50 + j*cell + cell/2} y={i*cell + cell/2 + 4}
                  textAnchor="middle" fontSize="13"
                  fill={intensity > 0.55 ? "white" : "var(--ink)"}
                  fontFamily="var(--font-mono)" fontWeight="500">{v}</text>
          </g>
        );
      }))}
      {labels.map((l, i) => (
        <g key={"l"+i}>
          <text x={45} y={i*cell + cell/2 + 4} fontSize="11" textAnchor="end" fill="var(--ink-2)" fontFamily="var(--font-mono)">{l}</text>
          <text x={50 + i*cell + cell/2} y={size + 18} fontSize="11" textAnchor="middle" fill="var(--ink-2)" fontFamily="var(--font-mono)">{l}</text>
        </g>
      ))}
    </svg>
  );
};

// Spectral / band-power bars
window.BandPower = function BandPower({mode = "NS", width = 280, height = 110}) {
  const bands = mode === "NS"
    ? [{name: "δ", v: 0.35}, {name: "θ", v: 0.30}, {name: "α", v: 0.85}, {name: "β", v: 0.55}, {name: "γ", v: 0.20}]
    : mode === "IS"
    ? [{name: "δ", v: 0.85}, {name: "θ", v: 0.72}, {name: "α", v: 0.30}, {name: "β", v: 0.25}, {name: "γ", v: 0.12}]
    : [{name: "δ", v: 0.92}, {name: "θ", v: 0.78}, {name: "α", v: 0.35}, {name: "β", v: 0.40}, {name: "γ", v: 0.18}];
  const pad = 24;
  const barW = (width - pad*2) / bands.length - 8;
  const color = mode === "NS" ? "var(--ns)" : mode === "IS" ? "var(--is)" : "var(--hs)";
  return (
    <svg width={width} height={height}>
      <line x1={pad} y1={height-22} x2={width-pad} y2={height-22} stroke="var(--line-2)" />
      {bands.map((b, i) => {
        const x = pad + i * (barW + 8);
        const h = b.v * (height - 40);
        return (
          <g key={b.name}>
            <rect x={x} y={height-22 - h} width={barW} height={h} fill={color} fillOpacity="0.85" rx="2" />
            <text x={x + barW/2} y={height-7} fontSize="11" textAnchor="middle" fill="var(--ink-2)" fontStyle="italic">{b.name}</text>
            <text x={x + barW/2} y={height-22-h-4} fontSize="9" textAnchor="middle" fill="var(--ink-3)" fontFamily="var(--font-mono)">{(b.v*100).toFixed(0)}</text>
          </g>
        );
      })}
    </svg>
  );
};
