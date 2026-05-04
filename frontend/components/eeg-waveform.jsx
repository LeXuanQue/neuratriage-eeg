// EEG waveform — pseudo real-time generator + SVG renderer
// Generates plausible EEG-looking traces and animates them.

const { useState: useStateEEG, useEffect: useEffectEEG, useRef: useRefEEG, useMemo: useMemoEEG } = React;

// ──────────────────────────────────────────────────────────────────
// Channel naming — 10-20 system subset
const STD_10_20 = [
  "Fp1", "Fp2",
  "F7", "F3", "Fz", "F4", "F8",
  "T3", "C3", "Cz", "C4", "T4",
  "T5", "P3", "Pz", "P4", "T6",
  "O1", "O2",
];

// pick first N channels
window.pickChannels = function(n) {
  return STD_10_20.slice(0, Math.min(n, STD_10_20.length));
};

// ──────────────────────────────────────────────────────────────────
// Synthetic EEG generator: mixture of sine waves at delta/theta/alpha/beta + noise.
// Different "modes" produce different-looking traces (matching NS/IS/HS phenotypes).
function makeSeed(i) {
  return Math.sin((i + 1) * 12.9898) * 43758.5453 % 1;
}

function eegMixture({channelIndex, mode, t, sampleRate}) {
  // mode: "NS" — alpha-rich, balanced
  //       "IS" — slowed: more delta/theta, reduced alpha
  //       "HS" — slowed + asymmetric burst on some channels
  const seed = makeSeed(channelIndex);
  const phase = seed * Math.PI * 2;

  let v = 0;
  // delta 1-3 Hz
  v += (mode === "IS" ? 28 : mode === "HS" ? 32 : 14) * Math.sin(2*Math.PI*1.5*t + phase);
  // theta 4-7 Hz
  v += (mode === "IS" ? 22 : mode === "HS" ? 24 : 12) * Math.sin(2*Math.PI*5.5*t + phase*1.3);
  // alpha 8-12 Hz
  v += (mode === "NS" ? 26 : 10) * Math.sin(2*Math.PI*10*t + phase*0.7);
  // beta 13-25 Hz
  v += (mode === "NS" ? 8 : 6) * Math.sin(2*Math.PI*18*t + phase*1.7);
  // 1/f noise approximation
  v += (Math.random() - 0.5) * 8;
  // hemorrhagic burst — asymmetric on some channels
  if (mode === "HS" && (channelIndex === 5 || channelIndex === 6 || channelIndex === 11)) {
    v += 18 * Math.sin(2*Math.PI*2.2*t + phase) * (0.6 + 0.4*Math.sin(0.4*t));
  }
  return v;
}

// ──────────────────────────────────────────────────────────────────
// One channel trace renderer: keeps a rolling buffer, draws SVG polyline
window.EEGTrace = function EEGTrace({
  channelIndex, label, mode = "NS", height = 38, width = 600,
  speed = 1, animated = true, color
}) {
  const POINTS = 320;
  const sampleRate = 64; // visual sample rate
  const [buffer, setBuffer] = useStateEEG(() => {
    const b = new Array(POINTS).fill(0);
    let t = 0;
    for (let i = 0; i < POINTS; i++) {
      b[i] = eegMixture({channelIndex, mode, t, sampleRate});
      t += 1 / sampleRate;
    }
    return b;
  });

  const tRef = useRefEEG(POINTS / sampleRate);
  useEffectEEG(() => {
    if (!animated) return;
    let frame;
    let last = performance.now();
    const step = (now) => {
      const dt = (now - last) / 1000;
      last = now;
      const samplesToAdd = Math.max(1, Math.round(dt * sampleRate * speed));
      setBuffer(prev => {
        const next = prev.slice(samplesToAdd);
        for (let i = 0; i < samplesToAdd; i++) {
          tRef.current += 1 / sampleRate;
          next.push(eegMixture({channelIndex, mode, t: tRef.current, sampleRate}));
        }
        return next;
      });
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [animated, mode, speed, channelIndex]);

  const path = useMemoEEG(() => {
    const min = -80, max = 80;
    const stepX = width / (POINTS - 1);
    let d = "";
    for (let i = 0; i < POINTS; i++) {
      const x = i * stepX;
      const y = height/2 - (buffer[i] / (max-min)) * height * 0.9;
      d += (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1) + " ";
    }
    return d;
  }, [buffer, width, height]);

  return (
    <div style={{display: "flex", alignItems: "center", gap: 8, height: height + 6}}>
      <div style={{
        width: 36, fontSize: 10, fontFamily: "var(--font-mono)",
        color: "var(--ink-3)", textAlign: "right"
      }}>{label}</div>
      <svg width={width} height={height} style={{display: "block", flex: 1}}>
        {/* baseline */}
        <line x1="0" y1={height/2} x2={width} y2={height/2}
              stroke="var(--line)" strokeWidth="1" strokeDasharray="2 4" />
        <path d={path} fill="none"
              stroke={color || "var(--trace)"}
              strokeWidth="1.1" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────
// Multi-channel stack
window.EEGStack = function EEGStack({channels, mode = "NS", animated = true, traceWidth = 600, traceHeight = 36, speed = 1}) {
  return (
    <div style={{display: "flex", flexDirection: "column", gap: 2}}>
      {channels.map((ch, i) => (
        <EEGTrace key={ch} channelIndex={i} label={ch}
                  mode={mode} animated={animated}
                  width={traceWidth} height={traceHeight} speed={speed} />
      ))}
    </div>
  );
};
