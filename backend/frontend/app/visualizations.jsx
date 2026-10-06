// EEG Stroke — Visualization library (dark themed)
// All output is small inline SVG — no external libs. Continuous animations.
const { useMemo: useM_v, useState: useS_v, useEffect: useE_v, useRef: useR_v } = React;

// ──────────────────────────────────────────────────────────────────
// Channel positions on a unit circle (10-20 system)
window.ELECTRODES = {
  Fp1:[-0.30,-0.85], Fp2:[0.30,-0.85],
  F7:[-0.75,-0.55], F3:[-0.40,-0.45], Fz:[0,-0.45], F4:[0.40,-0.45], F8:[0.75,-0.55],
  T3:[-0.95,0], C3:[-0.45,0], Cz:[0,0], C4:[0.45,0], T4:[0.95,0],
  T5:[-0.75,0.55], P3:[-0.40,0.45], Pz:[0,0.45], P4:[0.40,0.45], T6:[0.75,0.55],
  O1:[-0.30,0.85], O2:[0.30,0.85],
};
window.STD_10_20 = ["Fp1","Fp2","F7","F3","Fz","F4","F8","T3","C3","Cz","C4","T4","T5","P3","Pz","P4","T6","O1","O2"];
window.pickChannels = function(n){return window.STD_10_20.slice(0, Math.min(n, window.STD_10_20.length))};

// ──────────────────────────────────────────────────────────────────
// EEG synthesis — mixture of sines per band
function ntEegSample({channelIndex, mode, t}) {
  return 0;
}

// ──────────────────────────────────────────────────────────────────
// EEG Trace — animated rolling buffer
window.EEGTrace = function EEGTrace({channelIndex, label, mode="IS", height=28, width="100%", animated=true, color}) {
  const POINTS = 280, sr = 64;
  const [buffer, setBuffer] = useS_v(() => {
    const b = new Array(POINTS).fill(0);
    let t = 0;
    for (let i = 0; i < POINTS; i++) { b[i] = ntEegSample({channelIndex, mode, t}); t += 1/sr; }
    return b;
  });
  const tRef = useR_v(POINTS / sr);
  useE_v(() => {
    if (!animated) return;
    let frame, last = performance.now();
    const step = (now) => {
      const dt = (now - last) / 1000; last = now;
      const samples = Math.max(1, Math.round(dt * sr));
      setBuffer(prev => {
        const next = prev.slice(samples);
        for (let i = 0; i < samples; i++) {
          tRef.current += 1/sr;
          next.push(ntEegSample({channelIndex, mode, t: tRef.current}));
        }
        return next;
      });
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [animated, mode, channelIndex]);

  const W = 100, H = height; // viewBox-relative
  const path = useM_v(() => {
    const stepX = W / (POINTS - 1);
    let d = "";
    for (let i = 0; i < POINTS; i++) {
      const x = i * stepX;
      const y = H/2 - (buffer[i] / 160) * H * 0.85;
      d += (i===0?"M":"L") + x.toFixed(2) + "," + y.toFixed(2) + " ";
    }
    return d;
  }, [buffer, H]);

  return (
    <div style={{display:"flex", alignItems:"center", gap:8, height:H+4}}>
      <div style={{width:32, fontSize:10, fontFamily:"var(--font-mono)", color:"var(--ink-3)", textAlign:"right", flex:"none"}}>{label}</div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} style={{display:"block", flex:1, minWidth:0}}>
        <line x1="0" y1={H/2} x2={W} y2={H/2} stroke="var(--line)" strokeWidth="0.3" strokeDasharray="0.6 1.2" vectorEffect="non-scaling-stroke"/>
        <path d={path} fill="none" stroke={color || "var(--trace)"} strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      </svg>
    </div>
  );
};

// EEG Trace from raw sample buffer (A2: renders actual WS data)
window.EEGTraceRaw = function EEGTraceRaw({data, label, height=28, color}) {
  const W = 100, H = height;
  if (!data || data.length < 2) {
    return (
      <div style={{display:"flex", alignItems:"center", gap:8, height:H+4}}>
        <div style={{width:32, fontSize:10, fontFamily:"var(--font-mono)", color:"var(--ink-3)", textAlign:"right", flex:"none"}}>{label}</div>
        <div style={{flex:1, height:H, display:"flex", alignItems:"center"}}>
          <div style={{width:"100%", height:1, background:"var(--line)"}}/>
        </div>
      </div>
    );
  }
  const n = data.length;
  const stepX = W / (n - 1);
  // Clean the trace so it reads like clinical EEG instead of a tangled raw dump:
  //  1) high-pass by subtracting a slow EMA baseline (kills DC offset + drift),
  //  2) robust scale from the 95th-pct amplitude (ignores spikes),
  //  3) clamp into the lane so channels never bleed into each other.
  const clean = new Array(n);
  let baseline = data[0];
  const BETA = 0.02; // slow baseline tracker (high-pass corner)
  for (let i = 0; i < n; i++) {
    baseline = BETA * data[i] + (1 - BETA) * baseline;
    clean[i] = data[i] - baseline;
  }
  const absSorted = clean.map(Math.abs).sort((a, b) => a - b);
  const p95 = absSorted[Math.min(n - 1, Math.floor(n * 0.95))] || 1e-9;
  const scale = (p95 < 1e-9 ? 1e-9 : p95) * 2.4;
  let d = "";
  for (let i = 0; i < n; i++) {
    const x = i * stepX;
    const y = Math.max(0, Math.min(H, H / 2 - (clean[i] / scale) * H * 0.85));
    d += (i === 0 ? "M" : "L") + x.toFixed(2) + "," + y.toFixed(2) + " ";
  }
  return (
    <div style={{display:"flex", alignItems:"center", gap:8, height:H+4}}>
      <div style={{width:32, fontSize:10, fontFamily:"var(--font-mono)", color:"var(--ink-3)", textAlign:"right", flex:"none"}}>{label}</div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} style={{display:"block", flex:1, minWidth:0}}>
        <line x1="0" y1={H/2} x2={W} y2={H/2} stroke="var(--line)" strokeWidth="0.3" strokeDasharray="0.6 1.2" vectorEffect="non-scaling-stroke"/>
        <path d={d} fill="none" stroke={color || "var(--trace)"} strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke"/>
      </svg>
    </div>
  );
};

// rawData: optional array of per-channel sample arrays from WS/replay stream.
// Missing channel data is rendered as an empty trace, never as synthetic EEG.
window.EEGStack = function EEGStack({channels, mode="IS", animated=true, traceHeight=28, color, rawData}) {
  return (
    <div style={{display:"flex", flexDirection:"column", gap:1}}>
      {channels.map((ch, i) => {
        const chData = rawData && rawData[i] && rawData[i].length > 1 ? rawData[i] : null;
        return chData
          ? <window.EEGTraceRaw key={ch} data={chData} label={ch} height={traceHeight} color={color}/>
          : <window.EEGTraceRaw key={ch} data={null} label={ch} height={traceHeight} color={color}/>;
      })}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Risk gauge — circular ring with center value
window.RiskGauge = function RiskGauge({size=180, value, label, sublabel, color}) {
  const stroke = 10;
  const r = (size - stroke - 6) / 2;
  const c = 2 * Math.PI * r;
  const dash = c * value;
  return (
    <div style={{position:"relative", width:size, height:size}}>
      <svg width={size} height={size}>
        <defs>
          <filter id="gaugeGlow"><feGaussianBlur stdDeviation="3"/></filter>
        </defs>
        <circle cx={size/2} cy={size/2} r={r} stroke="var(--bg-3)" strokeWidth={stroke} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth={stroke} fill="none"
                strokeDasharray={`${dash} ${c-dash}`} strokeDashoffset={c*0.25}
                strokeLinecap="round"
                style={{transition:"stroke-dasharray 0.4s, stroke 0.4s", filter:"drop-shadow(0 0 6px "+color+")"}}/>
      </svg>
      <div style={{position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center"}}>
        <div className="mono" style={{fontSize:size*0.25, fontWeight:600, color:"var(--ink)", lineHeight:1, letterSpacing:"-0.02em"}}>
          {(value*100).toFixed(0)}<span style={{fontSize:size*0.13, color:"var(--ink-3)"}}>%</span>
        </div>
        <div style={{fontSize:9.5, textTransform:"uppercase", letterSpacing:"0.10em", color:"var(--ink-3)", marginTop:4}}>{sublabel}</div>
        <div style={{fontSize:13, fontWeight:600, color:color, marginTop:2, fontFamily:"var(--font-mono)"}}>{label}</div>
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Risk bars: binary NS / IS only.
window.RiskBars = function RiskBars({probs, labels}) {
  const items = [
    {key:"NS", value:probs.NS, color:"var(--ns)", soft:"var(--ns-soft)"},
    {key:"IS", value:probs.IS, color:"var(--is)", soft:"var(--is-soft)"},
  ];
  return (
    <div style={{display:"flex", flexDirection:"column", gap:11}}>
      {items.map(it => (
        <div key={it.key}>
          <div style={{display:"flex", justifyContent:"space-between", fontSize:11.5, marginBottom:5, alignItems:"center"}}>
            <span style={{display:"flex", alignItems:"center", gap:7}}>
              <span className="dot" style={{background:it.color, width:7, height:7}}/>
              <span style={{color:"var(--ink-2)"}}>{labels[it.key]}</span>
            </span>
            <span className="mono" style={{fontWeight:600, fontSize:13, color:"var(--ink)"}}>
              {(it.value*100).toFixed(1)}<span style={{color:"var(--ink-3)", fontWeight:400, fontSize:10.5}}>%</span>
            </span>
          </div>
          <div style={{height:6, background:it.soft, borderRadius:3, overflow:"hidden", position:"relative"}}>
            <div style={{position:"absolute", inset:0, width:(it.value*100)+"%", background:it.color, transition:"width 0.4s ease", borderRadius:3, boxShadow:`0 0 8px ${it.color}`}}/>
          </div>
        </div>
      ))}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Feature attribution (SHAP-style)
window.FeatureAttribution = function FeatureAttribution({features, color}) {
  const max = Math.max(...features.map(f => Math.abs(f.value)));
  return (
    <div style={{display:"flex", flexDirection:"column", gap:7}}>
      {features.map((f, i) => {
        const pct = Math.abs(f.value) / max;
        const positive = f.value > 0;
        return (
          <div key={i} style={{display:"grid", gridTemplateColumns:"130px 1fr 50px", alignItems:"center", gap:10, fontSize:11}}>
            <span className="mono" style={{color:"var(--ink-2)"}}>{f.name}</span>
            <div style={{position:"relative", height:14, background:"var(--bg-3)", borderRadius:2, overflow:"hidden"}}>
              <div style={{
                position:"absolute",
                left: positive ? "50%" : `${50 - pct*50}%`,
                width: `${pct*50}%`,
                top:0, bottom:0,
                background: positive ? color : "var(--ink-4)",
                boxShadow: positive ? `0 0 6px ${color}` : "none",
              }}/>
              <div style={{position:"absolute", left:"50%", top:0, bottom:0, width:1, background:"var(--line-3)"}}/>
            </div>
            <span className="mono" style={{color:positive?color:"var(--ink-3)", textAlign:"right", fontSize:10.5}}>
              {positive?"+":""}{f.value.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Brain Topomap with optional heat blob
window.BrainTopomap = function BrainTopomap({size=200, channels, valuesByChan={}, mode="IS", showLabels=true}) {
  const values = useM_v(() => {
    if (Object.keys(valuesByChan).length) return valuesByChan;
    return {};
  }, [valuesByChan, channels.join(",")]);

  const cx = size/2, cy = size/2, r = size*0.42;
  const colorFor = (v) => {
    // dark-friendly: cool dim blue → vivid hot
    const L = (0.35 + v*0.35).toFixed(3);
    const C = (0.04 + v*0.20).toFixed(3);
    const H = (240 - v*215).toFixed(0);
    return `oklch(${L} ${C} ${H})`;
  };

  return (
    <svg width={size} height={size} style={{display:"block"}}>
      <defs>
        <radialGradient id={`topomapBg-${mode}`}>
          <stop offset="0%" stopColor="oklch(0.18 0.04 250)" stopOpacity="1"/>
          <stop offset="100%" stopColor="oklch(0.10 0.02 250)" stopOpacity="1"/>
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r} fill={`url(#topomapBg-${mode})`} stroke="var(--line-2)" strokeWidth="1"/>
      <path d={`M ${cx-7} ${cy-r+2} L ${cx} ${cy-r-7} L ${cx+7} ${cy-r+2} Z`} fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1"/>
      <ellipse cx={cx-r} cy={cy} rx="5" ry="11" fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1"/>
      <ellipse cx={cx+r} cy={cy} rx="5" ry="11" fill="var(--bg-2)" stroke="var(--line-2)" strokeWidth="1"/>
      {channels.map(ch => {
        const pos = window.ELECTRODES[ch];
        if (!pos) return null;
        const ex = cx + pos[0]*r*0.85, ey = cy + pos[1]*r*0.85;
        const hasValue = typeof values[ch] === "number" && Number.isFinite(values[ch]);
        const v = hasValue ? values[ch] : 0;
        return (
          <g key={ch}>
            <circle cx={ex} cy={ey} r={size*0.05} fill={hasValue ? colorFor(v) : "var(--bg-3)"} stroke="oklch(1 0 0 / 0.15)" strokeWidth="0.7"
                    style={{filter: hasValue && v > 0.6 ? `drop-shadow(0 0 4px ${colorFor(v)})` : "none"}}/>
            {showLabels && (
              <text x={ex} y={ey+2.5} fontSize={size*0.038} textAnchor="middle"
                    fill={hasValue && v>0.5?"#fff":"var(--ink-3)"} fontFamily="var(--font-mono)">{ch}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Risk timeline: NS / IS trends with alert markers.
window.RiskTimeline = function RiskTimeline({width=400, height=90, history, alerts=[], live=false}) {
  const xAt = (i) => (i / (history.length-1)) * (width-20) + 10;
  const yAt = (v) => height - 12 - v * (height - 22);
  const pathFor = (key) => history.map((h, i) => (i===0?"M":"L") + xAt(i).toFixed(1) + "," + yAt(h[key]).toFixed(1)).join(" ");
  return (
    <svg width={width} height={height} style={{display:"block"}}>
      {[0.25, 0.5, 0.75].map(g => (
        <line key={g} x1={10} x2={width-10} y1={yAt(g)} y2={yAt(g)} stroke="var(--line)" strokeDasharray="2 4"/>
      ))}
      <path d={pathFor("NS")} fill="none" stroke="var(--ns)" strokeWidth="1.2" opacity="0.85"/>
      <path d={pathFor("IS")} fill="none" stroke="var(--is)" strokeWidth="1.2" opacity="0.85"/>
      {alerts.map((a, i) => (
        <g key={i}>
          <line x1={xAt(a.idx)} x2={xAt(a.idx)} y1={6} y2={height-10} stroke="var(--hs)" strokeDasharray="3 3" opacity="0.6"/>
          <circle cx={xAt(a.idx)} cy={yAt(a.value)} r="3" fill="var(--hs)" style={{filter:"drop-shadow(0 0 4px var(--hs))"}}/>
        </g>
      ))}
      {live && (
        <circle cx={xAt(history.length-1)} cy={yAt(history[history.length-1].IS)} r="3.5" fill="var(--is)">
          <animate attributeName="r" values="3.5;6;3.5" dur="1.4s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="1;0.3;1" dur="1.4s" repeatCount="indefinite"/>
        </circle>
      )}
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Band power bars
window.BandPower = function BandPower({mode="IS", width=280, height=120, rawData=null, fs=256}) {
  let bands = [];
  bands = useM_v(() => {
    function goertzelPower(samples, freq, sampleRate) {
      const n = samples.length;
      if (n < 8) return 0;
      const k = Math.max(1, Math.round((n * freq) / sampleRate));
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
    if (!Array.isArray(rawData) || !rawData.some(ch => Array.isArray(ch) && ch.length > 32)) return [];
    const centers = [{name:"δ", freq:2}, {name:"θ", freq:6}, {name:"α", freq:10}, {name:"β", freq:20}, {name:"γ", freq:35}];
    const powers = centers.map(({name, freq}) => {
      let sum = 0, count = 0;
      rawData.forEach((ch) => {
        if (!Array.isArray(ch) || ch.length < 32) return;
        const sampleRate = Number(fs || 256);
        const slice = ch.slice(-Math.min(ch.length, Math.round(sampleRate * 2)));
        const mean = slice.reduce((a, b) => a + Number(b || 0), 0) / slice.length;
        const centered = slice.map(v => Number(v || 0) - mean);
        sum += goertzelPower(centered, freq, sampleRate);
        count += 1;
      });
      return {name, raw: count ? sum / count : 0};
    });
    const max = Math.max(...powers.map(b => b.raw), 1e-9);
    return powers.map(b => ({name:b.name, v:Math.max(0.04, Math.min(1, b.raw / max))}));
  }, [mode, rawData, fs]);
  const pad = 24;
  const barW = (width - pad*2) / bands.length - 8;
  const color = mode==="NS"?"var(--ns)":"var(--is)";
  return (
    <svg width={width} height={height}>
      <line x1={pad} y1={height-22} x2={width-pad} y2={height-22} stroke="var(--line-2)"/>
      {bands.length === 0 && (
        <text x={width/2} y={height/2} fontSize="10" textAnchor="middle" fill="var(--ink-3)">waiting raw EEG</text>
      )}
      {bands.map((b, i) => {
        const x = pad + i*(barW+8);
        const h = b.v*(height - 40);
        return (
          <g key={b.name}>
            <rect x={x} y={height-22-h} width={barW} height={h} fill={color} fillOpacity="0.82" rx="2"
                  style={{filter:`drop-shadow(0 0 4px ${color})`}}/>
            <text x={x+barW/2} y={height-7} fontSize="11" textAnchor="middle" fill="var(--ink-2)" fontStyle="italic">{b.name}</text>
            <text x={x+barW/2} y={height-22-h-4} fontSize="9" textAnchor="middle" fill="var(--ink-3)" fontFamily="var(--font-mono)">{(b.v*100).toFixed(0)}</text>
          </g>
        );
      })}
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Multifractal spectrum f(α) - inverted U
window.MultifractalSpectrum = function MultifractalSpectrum({width=300, height=160, mode="IS"}) {
  const params = {
    NS: {center:1.0, w:0.45, h:1.0, color:"var(--ns)"},
    IS: {center:1.15, w:0.30, h:0.92, color:"var(--is)"},
  }[mode] || {center:1.15, w:0.30, h:0.92, color:"var(--is)"};
  const xMin=0.4, xMax=1.7, pad=28;
  const xAt = a => pad + (a-xMin)/(xMax-xMin) * (width-pad-12);
  const yAt = f => height-pad+4 - f * (height-pad-18);
  const points = [];
  for (let a=xMin; a<=xMax; a+=0.02) {
    points.push([a, params.h * Math.exp(-Math.pow((a-params.center)/params.w, 2)*2)]);
  }
  const path = points.map(([a,f],i) => (i===0?"M":"L") + xAt(a).toFixed(1) + "," + yAt(f).toFixed(1)).join(" ");
  return (
    <svg width={width} height={height} style={{display:"block"}}>
      <line x1={pad} y1={height-pad+4} x2={width-8} y2={height-pad+4} stroke="var(--line-2)"/>
      <line x1={pad} y1={8} x2={pad} y2={height-pad+4} stroke="var(--line-2)"/>
      {[0.6,0.9,1.2,1.5].map(a => (
        <g key={a}>
          <line x1={xAt(a)} y1={height-pad+4} x2={xAt(a)} y2={height-pad+8} stroke="var(--ink-4)"/>
          <text x={xAt(a)} y={height-6} fontSize="9" fill="var(--ink-3)" textAnchor="middle" fontFamily="var(--font-mono)">{a.toFixed(1)}</text>
        </g>
      ))}
      <text x={width/2} y={height-pad+22} fontSize="9" fill="var(--ink-3)" textAnchor="middle" fontStyle="italic">α (singularity)</text>
      <text x={6} y={20} fontSize="9" fill="var(--ink-3)" fontStyle="italic">f(α)</text>
      <path d={path} fill={params.color} fillOpacity="0.18" stroke={params.color} strokeWidth="1.5" style={{filter:`drop-shadow(0 0 4px ${params.color})`}}/>
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Confusion matrix
window.ConfusionMatrix = function ConfusionMatrix({size=200, matrix, labels}) {
  const cell = size / Math.max(1, labels.length);
  const max = Math.max(...matrix.flat());
  return (
    <svg width={size+50} height={size+30}>
      {matrix.map((row, i) => row.map((v, j) => {
        const intensity = v / max;
        return (
          <g key={`${i}-${j}`}>
            <rect x={50+j*cell} y={i*cell} width={cell} height={cell}
                  fill={`oklch(${0.16 + intensity*0.50} ${0.04 + intensity*0.16} 220)`}
                  stroke="var(--bg)" strokeWidth="2"/>
            <text x={50+j*cell+cell/2} y={i*cell+cell/2+4} textAnchor="middle" fontSize="13"
                  fill={intensity>0.55?"#fff":"var(--ink-2)"} fontFamily="var(--font-mono)" fontWeight="500">{v}</text>
          </g>
        );
      }))}
      {labels.map((l, i) => (
        <g key={"l"+i}>
          <text x={45} y={i*cell+cell/2+4} fontSize="11" textAnchor="end" fill="var(--ink-2)" fontFamily="var(--font-mono)">{l}</text>
          <text x={50+i*cell+cell/2} y={size+18} fontSize="11" textAnchor="middle" fill="var(--ink-2)" fontFamily="var(--font-mono)">{l}</text>
        </g>
      ))}
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// Spark line (small trend chart, single series)
window.Sparkline = function Sparkline({data, width=120, height=32, color="var(--brand-2)", fill=true}){
  const min=Math.min(...data), max=Math.max(...data);
  const range = max-min || 1;
  const xAt = i => (i/(data.length-1))*width;
  const yAt = v => height - 4 - ((v-min)/range)*(height-8);
  const pts = data.map((v,i)=>`${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
  const path = "M"+pts.replace(/,/g," ").split(" ").map((s,i)=>i%2===0?(i===0?"":"L")+s:s).join(" ");
  const area = `M0,${height} L`+pts.split(" ").join(" L")+` L${width},${height} Z`;
  return (
    <svg width={width} height={height} style={{display:"block"}}>
      {fill && <path d={area} fill={color} fillOpacity="0.15"/>}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.4"/>
    </svg>
  );
};

// ──────────────────────────────────────────────────────────────────
// SQI dial — small horizontal bar
window.SQIBar = function SQIBar({value, width=140}) {
  const hasValue = typeof value === "number" && Number.isFinite(value);
  const shown = hasValue ? Math.max(0, Math.min(1, value)) : 0;
  const color = !hasValue ? "var(--ink-4)" : shown >= 0.85 ? "var(--ns)" : shown >= 0.7 ? "var(--is)" : "var(--hs)";
  return (
    <div style={{display:"flex", alignItems:"center", gap:10}}>
      <div style={{position:"relative", height:5, background:"var(--bg-3)", borderRadius:3, width:width, overflow:"hidden"}}>
        <div style={{position:"absolute", inset:0, width:(shown*100)+"%", background:color, borderRadius:3, boxShadow:hasValue ? `0 0 6px ${color}` : "none", transition:"width 0.3s, background 0.3s"}}/>
        {[0.7, 0.85].map(t => (
          <div key={t} style={{position:"absolute", left:(t*100)+"%", top:-1, bottom:-1, width:1, background:"var(--bg)"}}/>
        ))}
      </div>
      <span className="mono" style={{fontSize:11, color, minWidth:32, fontWeight:600}}>{hasValue ? shown.toFixed(2) : "--"}</span>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Animated probability sweep — single channel (used in dashboard cards)
window.ProbAreaChart = function ProbAreaChart({history, width=300, height=80, classKey="IS"}) {
  const color = classKey==="NS"?"var(--ns)":"var(--is)";
  const xAt = i => (i/(history.length-1))*width;
  const yAt = v => height - 6 - v*(height-12);
  const pts = history.map((h,i)=>`${xAt(i).toFixed(1)},${yAt(h[classKey]).toFixed(1)}`);
  const line = "M"+pts.join(" L");
  const area = `M0,${height} L`+pts.join(" L")+` L${width},${height} Z`;
  return (
    <svg width={width} height={height} style={{display:"block"}}>
      <defs>
        <linearGradient id={`pa-${classKey}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.4"/>
          <stop offset="1" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#pa-${classKey})`}/>
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" style={{filter:`drop-shadow(0 0 3px ${color})`}}/>
    </svg>
  );
};
