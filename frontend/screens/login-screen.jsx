// Login / splash screen — painterly nebula × EEG
// Rich pink-violet nebula clouds, sparkle stars with cross-flares, drifting EEG ribbons.

const { useState: useS_L, useEffect: useE_L, useMemo: useM_L, useRef: useR_L } = React;

// ──────────────────────────────────────────────────────────────────
// Sparkle star with cross-flare (4-point) — like the reference image
function SparkleStar({cx, cy, size = 1, hue = 270, delay = 0, dur = 4}) {
  const armLen = size * 14;
  const coreR = size * 1.6;
  return (
    <g style={{animation: `sparkle ${dur}s ease-in-out ${delay}s infinite`, transformOrigin: `${cx}px ${cy}px`}}>
      {/* soft halo */}
      <circle cx={cx} cy={cy} r={size * 6} fill={`oklch(0.92 0.10 ${hue})`} opacity="0.18"/>
      <circle cx={cx} cy={cy} r={size * 3} fill={`oklch(0.96 0.08 ${hue})`} opacity="0.45"/>
      {/* cross flare */}
      <line x1={cx - armLen} y1={cy} x2={cx + armLen} y2={cy}
            stroke={`oklch(0.98 0.05 ${hue})`} strokeWidth={size * 0.5} opacity="0.85" strokeLinecap="round"/>
      <line x1={cx} y1={cy - armLen} x2={cx} y2={cy + armLen}
            stroke={`oklch(0.98 0.05 ${hue})`} strokeWidth={size * 0.5} opacity="0.85" strokeLinecap="round"/>
      {/* shorter diagonal flare */}
      <line x1={cx - armLen * 0.45} y1={cy - armLen * 0.45} x2={cx + armLen * 0.45} y2={cy + armLen * 0.45}
            stroke={`oklch(0.98 0.05 ${hue})`} strokeWidth={size * 0.3} opacity="0.55" strokeLinecap="round"/>
      <line x1={cx + armLen * 0.45} y1={cy - armLen * 0.45} x2={cx - armLen * 0.45} y2={cy + armLen * 0.45}
            stroke={`oklch(0.98 0.05 ${hue})`} strokeWidth={size * 0.3} opacity="0.55" strokeLinecap="round"/>
      {/* bright core */}
      <circle cx={cx} cy={cy} r={coreR} fill="white"/>
    </g>
  );
}

// ──────────────────────────────────────────────────────────────────
// Painterly nebula background, multi-layered
function CosmicBG() {
  const tinyStars = useM_L(() => {
    const arr = [];
    for (let i = 0; i < 240; i++) {
      arr.push({
        x: Math.random() * 800,
        y: Math.random() * 1000,
        r: Math.random() * 1.1 + 0.2,
        o: Math.random() * 0.7 + 0.25,
        tw: Math.random() * 5 + 2,
        delay: Math.random() * 5,
      });
    }
    return arr;
  }, []);

  const sparkles = useM_L(() => ([
    {cx: 130, cy: 90,  s: 2.0, h: 230, d: 0,   t: 4.0},
    {cx: 410, cy: 60,  s: 2.4, h: 270, d: 1.2, t: 5.2},
    {cx: 660, cy: 130, s: 1.6, h: 320, d: 0.8, t: 4.4},
    {cx: 90,  cy: 480, s: 2.2, h: 290, d: 2.0, t: 5.0},
    {cx: 720, cy: 380, s: 1.4, h: 320, d: 0.4, t: 3.8},
    {cx: 540, cy: 540, s: 1.2, h: 260, d: 1.6, t: 4.6},
    {cx: 240, cy: 720, s: 1.8, h: 300, d: 0.9, t: 5.4},
    {cx: 600, cy: 820, s: 1.5, h: 250, d: 2.4, t: 4.2},
    {cx: 360, cy: 920, s: 1.3, h: 230, d: 1.0, t: 3.6},
    {cx: 760, cy: 660, s: 1.7, h: 310, d: 1.8, t: 5.6},
  ]), []);

  // EEG-shaped flowing ribbons that drift slowly through nebula
  const eegRibbons = useM_L(() => {
    const paths = [];
    const seeds = [0.7, 1.5, 2.3, 3.1];
    seeds.forEach((seed, idx) => {
      const y = 220 + idx * 180;
      let d = `M -40 ${y}`;
      for (let x = -40; x <= 840; x += 5) {
        const v = Math.sin(x * 0.035 + seed) * 14
                + Math.sin(x * 0.12 + seed * 1.7) * 6
                + Math.sin(x * 0.30 + seed) * 2.5
                + (Math.sin(x * 0.5 + seed * 2) > 0.6 ? 16 : 0);
        d += ` L ${x} ${(y + v).toFixed(1)}`;
      }
      paths.push({d, idx});
    });
    return paths;
  }, []);

  return (
    <div style={{position: "absolute", inset: 0, overflow: "hidden"}}>
      <svg style={{position: "absolute", inset: 0, width: "100%", height: "100%"}}
           viewBox="0 0 800 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          {/* Deep space base */}
          <radialGradient id="bgBase" cx="0.5" cy="0.5" r="0.85">
            <stop offset="0%" stopColor="oklch(0.18 0.10 280)"/>
            <stop offset="50%" stopColor="oklch(0.10 0.07 270)"/>
            <stop offset="100%" stopColor="oklch(0.05 0.04 265)"/>
          </radialGradient>

          {/* Magenta-pink core nebula */}
          <radialGradient id="nebPink" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%"  stopColor="oklch(0.88 0.20 350)" stopOpacity="0.95"/>
            <stop offset="20%" stopColor="oklch(0.78 0.24 0)"   stopOpacity="0.85"/>
            <stop offset="55%" stopColor="oklch(0.55 0.25 340)" stopOpacity="0.55"/>
            <stop offset="100%" stopColor="oklch(0.35 0.18 320)" stopOpacity="0"/>
          </radialGradient>

          {/* Violet bloom */}
          <radialGradient id="nebViolet" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%"  stopColor="oklch(0.85 0.22 295)" stopOpacity="0.85"/>
            <stop offset="40%" stopColor="oklch(0.55 0.22 290)" stopOpacity="0.55"/>
            <stop offset="100%" stopColor="oklch(0.30 0.16 280)" stopOpacity="0"/>
          </radialGradient>

          {/* Cyan accent */}
          <radialGradient id="nebCyan" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%"  stopColor="oklch(0.85 0.16 220)" stopOpacity="0.55"/>
            <stop offset="60%" stopColor="oklch(0.55 0.18 235)" stopOpacity="0.20"/>
            <stop offset="100%" stopColor="oklch(0.30 0.14 250)" stopOpacity="0"/>
          </radialGradient>

          {/* Dust silhouettes (dark filaments inside nebula) */}
          <radialGradient id="nebDust" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stopColor="oklch(0.05 0.04 280)" stopOpacity="0.70"/>
            <stop offset="100%" stopColor="oklch(0.05 0.04 280)" stopOpacity="0"/>
          </radialGradient>

          {/* Turbulence to break up the gradient blobs into wispy clouds */}
          <filter id="cloud" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.012 0.022" numOctaves="3" seed="7"/>
            <feDisplacementMap in="SourceGraphic" scale="80"/>
            <feGaussianBlur stdDeviation="6"/>
          </filter>
          <filter id="cloud2" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.018 0.028" numOctaves="2" seed="3"/>
            <feDisplacementMap in="SourceGraphic" scale="60"/>
            <feGaussianBlur stdDeviation="4"/>
          </filter>
          <filter id="cloudDust" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.025 0.04" numOctaves="3" seed="11"/>
            <feDisplacementMap in="SourceGraphic" scale="50"/>
          </filter>

          <linearGradient id="eegGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor="oklch(0.95 0.12 320)" stopOpacity="0"/>
            <stop offset="30%" stopColor="oklch(0.95 0.18 320)" stopOpacity="0.7"/>
            <stop offset="70%" stopColor="oklch(0.95 0.18 270)" stopOpacity="0.7"/>
            <stop offset="100%" stopColor="oklch(0.95 0.12 270)" stopOpacity="0"/>
          </linearGradient>
          <filter id="eegGlow">
            <feGaussianBlur stdDeviation="2.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* base space */}
        <rect width="800" height="1000" fill="url(#bgBase)"/>

        {/* faint outer violet wash, large */}
        <ellipse cx="400" cy="500" rx="600" ry="700" fill="url(#nebViolet)" opacity="0.45" filter="url(#cloud)"/>

        {/* MAIN PINK/MAGENTA cloud — upper-left to mid */}
        <g style={{animation: "neb1Drift 60s ease-in-out infinite alternate"}}>
          <ellipse cx="280" cy="320" rx="380" ry="280" fill="url(#nebPink)" filter="url(#cloud)"/>
          <ellipse cx="350" cy="260" rx="200" ry="160" fill="url(#nebPink)" opacity="0.85" filter="url(#cloud2)"/>
        </g>

        {/* SECONDARY pink/magenta cloud — lower-center, brighter core */}
        <g style={{animation: "neb2Drift 75s ease-in-out infinite alternate"}}>
          <ellipse cx="380" cy="640" rx="340" ry="260" fill="url(#nebPink)" filter="url(#cloud)"/>
          <ellipse cx="320" cy="600" rx="160" ry="120" fill="url(#nebPink)" opacity="0.95" filter="url(#cloud2)"/>
        </g>

        {/* Violet wrap on right side */}
        <g style={{animation: "neb3Drift 90s ease-in-out infinite alternate"}}>
          <ellipse cx="560" cy="450" rx="280" ry="380" fill="url(#nebViolet)" filter="url(#cloud)"/>
          <ellipse cx="620" cy="780" rx="220" ry="280" fill="url(#nebViolet)" opacity="0.7" filter="url(#cloud2)"/>
        </g>

        {/* Cyan accent (cooler highlight tucked into pink) */}
        <ellipse cx="240" cy="380" rx="120" ry="80" fill="url(#nebCyan)" filter="url(#cloud2)" opacity="0.85"/>
        <ellipse cx="500" cy="520" rx="100" ry="70" fill="url(#nebCyan)" filter="url(#cloud2)" opacity="0.6"/>

        {/* Dark dust filaments inside the bright clouds */}
        <ellipse cx="300" cy="350" rx="160" ry="80" fill="url(#nebDust)" filter="url(#cloudDust)" opacity="0.75"/>
        <ellipse cx="400" cy="680" rx="140" ry="70" fill="url(#nebDust)" filter="url(#cloudDust)" opacity="0.65"/>
        <ellipse cx="560" cy="430" rx="100" ry="60" fill="url(#nebDust)" filter="url(#cloudDust)" opacity="0.55"/>

        {/* Tiny stars sprinkled throughout */}
        {tinyStars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="white" opacity={s.o}
                  style={{animation: `twinkle ${s.tw}s ease-in-out ${s.delay}s infinite`}}/>
        ))}

        {/* Big sparkle stars with cross flares */}
        {sparkles.map((s, i) => (
          <SparkleStar key={i} cx={s.cx} cy={s.cy} size={s.s} hue={s.h} delay={s.d} dur={s.t}/>
        ))}

        {/* EEG signal ribbons that drift through the nebula */}
        {eegRibbons.map((p, i) => (
          <g key={i} style={{
            animation: `eegDrift${i % 2} ${20 + i * 3}s ease-in-out infinite alternate`,
            mixBlendMode: "screen",
          }} opacity="0.55">
            <path d={p.d} stroke="url(#eegGrad)" strokeWidth="1.4"
                  fill="none" filter="url(#eegGlow)"/>
          </g>
        ))}

        {/* Shooting EEG pulse traveling across */}
        <circle r="3.5" fill="oklch(0.98 0.18 320)" filter="url(#eegGlow)">
          <animateMotion dur="7s" repeatCount="indefinite"
                         path="M -40 480 Q 200 420 400 510 T 840 470"/>
        </circle>
        <circle r="2.2" fill="oklch(0.98 0.16 230)" filter="url(#eegGlow)">
          <animateMotion dur="9s" repeatCount="indefinite" begin="2s"
                         path="M 840 760 Q 580 700 380 770 T -40 730"/>
        </circle>
      </svg>

      <style>{`
        @keyframes twinkle {
          0%, 100% { opacity: var(--o, 0.4); }
          50% { opacity: 1; }
        }
        @keyframes sparkle {
          0%, 100% { opacity: 0.6; transform: scale(0.85); }
          50%      { opacity: 1;   transform: scale(1.15); }
        }
        @keyframes neb1Drift {
          from { transform: translate(-12px, -8px) scale(1); }
          to   { transform: translate(14px, 10px)  scale(1.04); }
        }
        @keyframes neb2Drift {
          from { transform: translate(10px, 12px)  scale(1.03); }
          to   { transform: translate(-14px, -10px) scale(0.98); }
        }
        @keyframes neb3Drift {
          from { transform: translate(8px, -10px) scale(0.99); }
          to   { transform: translate(-12px, 14px) scale(1.05); }
        }
        @keyframes eegDrift0 { from { transform: translateX(-14px); } to { transform: translateX(16px); } }
        @keyframes eegDrift1 { from { transform: translateX(12px);  } to { transform: translateX(-18px); } }
      `}</style>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// Brain hologram — sits in front of nebula, with orbiting electrodes
function CosmicBrain() {
  return (
    <svg viewBox="0 0 400 400" style={{width: "100%", maxWidth: 380, display: "block"}}>
      <defs>
        <radialGradient id="brainCore2" cx="0.5" cy="0.5" r="0.55">
          <stop offset="0%"  stopColor="oklch(0.96 0.10 320)" stopOpacity="0.95"/>
          <stop offset="35%" stopColor="oklch(0.75 0.22 320)" stopOpacity="0.65"/>
          <stop offset="80%" stopColor="oklch(0.45 0.22 290)" stopOpacity="0.20"/>
          <stop offset="100%" stopColor="oklch(0.30 0.16 280)" stopOpacity="0"/>
        </radialGradient>
        <linearGradient id="ringGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"  stopColor="oklch(0.85 0.18 220)" stopOpacity="0"/>
          <stop offset="35%" stopColor="oklch(0.92 0.20 290)" stopOpacity="0.95"/>
          <stop offset="65%" stopColor="oklch(0.92 0.20 330)" stopOpacity="0.95"/>
          <stop offset="100%" stopColor="oklch(0.85 0.18 350)" stopOpacity="0"/>
        </linearGradient>
        <filter id="brainGlow2">
          <feGaussianBlur stdDeviation="5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <circle cx="200" cy="200" r="180" fill="url(#brainCore2)" opacity="0.7"/>

      {/* orbital rings */}
      <ellipse cx="200" cy="200" rx="160" ry="48" fill="none"
               stroke="url(#ringGrad2)" strokeWidth="1.4"
               transform="rotate(-18 200 200)" opacity="0.85"/>
      <ellipse cx="200" cy="200" rx="172" ry="62" fill="none"
               stroke="url(#ringGrad2)" strokeWidth="1.1" opacity="0.65"
               transform="rotate(35 200 200)"/>
      <ellipse cx="200" cy="200" rx="138" ry="34" fill="none"
               stroke="url(#ringGrad2)" strokeWidth="1.6" opacity="0.95"
               transform="rotate(72 200 200)"/>

      {/* brain hemisphere */}
      <g filter="url(#brainGlow2)">
        <path d="M 120 200
                 C 120 145, 165 110, 200 120
                 C 230 100, 285 130, 280 175
                 C 310 185, 305 230, 280 245
                 C 285 285, 240 305, 210 285
                 C 175 305, 130 280, 130 245
                 C 105 230, 100 195, 120 200 Z"
              fill="oklch(0.30 0.14 290 / 0.45)"
              stroke="oklch(0.92 0.18 320)" strokeWidth="1.6"/>
        <path d="M 145 175 Q 175 165 200 180 Q 225 195 255 180" stroke="oklch(0.92 0.18 320)" strokeWidth="1" fill="none" opacity="0.8"/>
        <path d="M 140 215 Q 170 230 200 220 Q 230 210 260 225" stroke="oklch(0.92 0.18 320)" strokeWidth="1" fill="none" opacity="0.8"/>
        <path d="M 155 250 Q 180 270 215 255 Q 240 245 265 255" stroke="oklch(0.92 0.18 320)" strokeWidth="1" fill="none" opacity="0.7"/>
        <path d="M 200 120 L 200 290" stroke="oklch(0.92 0.18 320)" strokeWidth="0.8" opacity="0.45"/>
      </g>

      {/* electrode constellation */}
      {[
        [200, 105], [150, 130], [250, 130],
        [120, 175], [200, 175], [280, 175],
        [145, 235], [255, 235],
        [180, 290], [220, 290],
      ].map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="3.8" fill="oklch(0.98 0.16 320)"
                  style={{animation: `pulse_n ${2 + (i%4)*0.4}s ease-in-out ${i*0.2}s infinite`}}/>
          <circle cx={x} cy={y} r="6.5" fill="none" stroke="oklch(0.90 0.18 300)" strokeWidth="0.8" opacity="0.55"/>
        </g>
      ))}

      {/* photons orbiting on rings */}
      <circle r="3" fill="oklch(0.98 0.18 300)" filter="url(#brainGlow2)">
        <animateMotion dur="5s" repeatCount="indefinite"
                       path="M 60 200 a 140 36 -18 1 1 280 0 a 140 36 -18 1 1 -280 0"/>
      </circle>
      <circle r="2" fill="oklch(0.98 0.18 340)" filter="url(#brainGlow2)">
        <animateMotion dur="7s" repeatCount="indefinite" begin="1s"
                       path="M 60 200 a 140 60 35 1 1 280 0 a 140 60 35 1 1 -280 0"/>
      </circle>

      <style>{`
        @keyframes pulse_n {
          0%, 100% { opacity: 0.5; r: 2.8; }
          50% { opacity: 1; r: 4.2; }
        }
      `}</style>
    </svg>
  );
}

// ──────────────────────────────────────────────────────────────────
window.LoginScreen = function LoginScreen({lang = "vi", state = "login"}) {
  const L = lang === "vi" ? {
    appName: "NeuraTriage EEG",
    tagline: "Cảnh báo sớm đột quỵ trên EEG",
    welcome: "Chào mừng trở lại",
    sub: "Đăng nhập bằng tài khoản nhân viên y tế để tiếp tục.",
    email: "Email công vụ", emailPlc: "bs.lan@hospital.vn",
    pass: "Mật khẩu", passPlc: "••••••••••••",
    remember: "Giữ đăng nhập trên thiết bị này",
    forgot: "Quên mật khẩu?",
    signIn: "Đăng nhập",
    sso: "SSO bệnh viện", badge: "Quét thẻ", or: "hoặc",
    footer: "Chỉ dành cho nhân viên được uỷ quyền · HIPAA / NĐ 13",
    loading: "Đang khởi tạo phiên làm việc…",
    initSteps: ["Xác thực thiết bị thu EEG", "Tải mô hình ApFu-MFDFA-TPELGBM", "Đồng bộ hồ sơ bệnh nhân"],
    version: "v0.4.2 · ZJU4H",
    headline: "Mỗi phút mất gần 1.9 triệu nơ-ron.",
    headlineSub: "EEG giúp bạn quyết định sớm hơn — ở đâu cũng được.",
  } : {
    appName: "NeuraTriage EEG", tagline: "EEG-based stroke early warning",
    welcome: "Welcome back",
    sub: "Sign in with your clinical staff account to continue.",
    email: "Work email", emailPlc: "dr.lan@hospital.vn",
    pass: "Password", passPlc: "••••••••••••",
    remember: "Keep me signed in on this device",
    forgot: "Forgot password?",
    signIn: "Sign in",
    sso: "Hospital SSO", badge: "Tap badge", or: "or",
    footer: "Authorized personnel only · HIPAA compliant",
    loading: "Initializing your session…",
    initSteps: ["Authenticating EEG device", "Loading ApFu-MFDFA-TPELGBM model", "Syncing patient roster"],
    version: "v0.4.2 · ZJU4H",
    headline: "Each minute costs ~1.9M neurons.",
    headlineSub: "EEG helps you decide earlier — anywhere.",
  };

  const isSplash = state === "splash";

  return (
    <div style={{
      width: "100%", height: "100%", position: "relative",
      display: "grid", gridTemplateColumns: "1.2fr 1fr",
      background: "oklch(0.06 0.04 268)",
      color: "white", fontFamily: "var(--font-ui)",
      overflow: "hidden",
    }}>
      <CosmicBG/>

      {/* Left cosmic panel */}
      <div style={{
        position: "relative", padding: "44px 56px",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        zIndex: 2,
      }}>
        <div style={{display: "flex", alignItems: "center", gap: 12}}>
          <div style={{
            width: 38, height: 38, borderRadius: 10,
            background: "linear-gradient(135deg, oklch(0.88 0.20 320), oklch(0.62 0.24 295))",
            display: "grid", placeItems: "center", fontWeight: 700,
            fontFamily: "var(--font-mono)", fontSize: 14,
            boxShadow: "0 0 28px oklch(0.78 0.24 320 / 0.7)",
          }}>NT</div>
          <div>
            <div style={{fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em"}}>{L.appName}</div>
            <div style={{fontSize: 11, opacity: 0.7, marginTop: 2}}>{L.tagline}</div>
          </div>
        </div>

        <div style={{display: "grid", placeItems: "center", flex: 1, padding: "20px 0"}}>
          <CosmicBrain/>
        </div>

        <div style={{maxWidth: 460}}>
          <div style={{
            fontSize: 34, fontWeight: 600, lineHeight: 1.15,
            letterSpacing: "-0.02em", textWrap: "balance",
            background: "linear-gradient(110deg, white 0%, oklch(0.88 0.18 320) 60%, oklch(0.85 0.18 275) 100%)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            textShadow: "0 0 40px oklch(0.78 0.22 320 / 0.3)",
          }}>{L.headline}</div>
          <div style={{fontSize: 14, opacity: 0.78, marginTop: 12, lineHeight: 1.55}}>{L.headlineSub}</div>

          <div style={{display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 18, fontSize: 11, opacity: 0.92, marginTop: 26}}>
            {[
              {l: "Macro-F1", v: "0.967", c: "oklch(0.82 0.18 152)"},
              {l: "Recall HS", v: "0.972", c: "oklch(0.78 0.22 25)"},
              {l: lang === "vi" ? "Trễ cảnh báo" : "Time-to-alert", v: "5.4s", c: "oklch(0.90 0.16 320)"},
            ].map(s => (
              <div key={s.l} style={{
                padding: "10px 14px",
                border: "1px solid oklch(0.85 0.15 320 / 0.25)",
                borderRadius: 8,
                background: "oklch(0.15 0.06 290 / 0.45)",
                backdropFilter: "blur(10px)",
                boxShadow: "inset 0 1px 0 oklch(1 0 0 / 0.08)",
              }}>
                <div style={{textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.65, fontSize: 9.5}}>{s.l}</div>
                <div style={{fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 600, marginTop: 4, color: s.c}}>{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right glass form panel */}
      <div style={{position: "relative", zIndex: 2, padding: 32, display: "grid", placeItems: "center"}}>
        <div style={{
          width: "100%", maxWidth: 420,
          background: "oklch(0.99 0.005 240 / 0.97)",
          color: "var(--ink)",
          borderRadius: 14,
          padding: "36px 36px 28px",
          boxShadow: "0 30px 90px oklch(0.05 0.05 290 / 0.7), 0 0 60px oklch(0.78 0.22 320 / 0.25), 0 0 0 1px oklch(0.85 0.15 320 / 0.25)",
          backdropFilter: "blur(20px)",
        }}>
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, fontSize: 11}}>
            <span style={{display: "inline-flex", alignItems: "center", gap: 6, color: "var(--ink-3)"}}>
              <span className="dot ns" style={{width: 7, height: 7}}/>
              {lang === "vi" ? "Hệ thống hoạt động bình thường" : "All systems operational"}
            </span>
            <span style={{fontFamily: "var(--font-mono)", color: "var(--ink-3)"}}>VI / EN</span>
          </div>

          {isSplash ? (
            <div>
              <div style={{display: "flex", alignItems: "center", gap: 12, marginBottom: 22}}>
                <div style={{
                  width: 22, height: 22, borderRadius: 11,
                  border: "2.5px solid oklch(0.62 0.22 300)",
                  borderTopColor: "transparent",
                  animation: "spin 0.9s linear infinite",
                }}/>
                <div style={{fontSize: 15, fontWeight: 500}}>{L.loading}</div>
              </div>
              <div style={{display: "flex", flexDirection: "column", gap: 14}}>
                {L.initSteps.map((s, i) => {
                  const done = i < 2;
                  const active = i === 2;
                  return (
                    <div key={i} style={{display: "flex", alignItems: "center", gap: 10, fontSize: 12.5}}>
                      <div style={{
                        width: 16, height: 16, borderRadius: 8,
                        background: done ? "oklch(0.62 0.14 152)" : active ? "oklch(0.78 0.22 320)" : "var(--bg-3)",
                        display: "grid", placeItems: "center",
                        color: "white", fontSize: 9, fontWeight: 700,
                      }}>{done ? "✓" : ""}</div>
                      <span style={{color: "var(--ink-2)", flex: active ? 0 : 1}}>{s}</span>
                      {active && (
                        <span style={{flex: 1, height: 3, background: "var(--bg-3)", borderRadius: 2, overflow: "hidden"}}>
                          <span style={{display:"block", height:"100%", width:"60%",
                            background: "linear-gradient(90deg, oklch(0.62 0.24 295), oklch(0.85 0.20 330))",
                            borderRadius: 2}}/>
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          ) : (
            <div>
              <div style={{fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em"}}>{L.welcome}</div>
              <div style={{fontSize: 12.5, color: "var(--ink-3)", marginTop: 6, lineHeight: 1.55}}>{L.sub}</div>

              <div style={{marginTop: 24, display: "flex", flexDirection: "column", gap: 14}}>
                <div>
                  <div style={{fontSize: 11, fontWeight: 500, color: "var(--ink-2)", marginBottom: 6}}>{L.email}</div>
                  <input placeholder={L.emailPlc} defaultValue="bs.lan@hospital.vn" style={{
                    width: "100%", padding: "10px 12px", fontSize: 13,
                    border: "1px solid var(--line-2)", borderRadius: 7,
                    background: "var(--bg)", fontFamily: "inherit",
                  }} />
                </div>
                <div>
                  <div style={{display: "flex", justifyContent: "space-between", marginBottom: 6}}>
                    <span style={{fontSize: 11, fontWeight: 500, color: "var(--ink-2)"}}>{L.pass}</span>
                    <a style={{fontSize: 11, color: "oklch(0.55 0.20 295)", cursor: "pointer"}}>{L.forgot}</a>
                  </div>
                  <input type="password" placeholder={L.passPlc} defaultValue="password" style={{
                    width: "100%", padding: "10px 12px", fontSize: 13,
                    border: "1px solid var(--line-2)", borderRadius: 7,
                    background: "var(--bg)", fontFamily: "inherit",
                  }} />
                </div>
                <label style={{display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--ink-2)", cursor: "pointer"}}>
                  <input type="checkbox" defaultChecked style={{accentColor: "oklch(0.62 0.22 300)"}} />
                  <span>{L.remember}</span>
                </label>
                <button style={{
                  width: "100%", padding: "11px 14px", fontSize: 13, fontWeight: 600,
                  border: "none", borderRadius: 7, color: "white", cursor: "pointer",
                  background: "linear-gradient(110deg, oklch(0.55 0.22 295), oklch(0.62 0.24 330))",
                  boxShadow: "0 6px 24px oklch(0.62 0.24 310 / 0.45)",
                  fontFamily: "inherit",
                }}>{L.signIn} →</button>
              </div>

              <div style={{display: "flex", alignItems: "center", gap: 10, margin: "20px 0", color: "var(--ink-3)", fontSize: 11}}>
                <div style={{flex: 1, height: 1, background: "var(--line)"}}/>
                <span>{L.or}</span>
                <div style={{flex: 1, height: 1, background: "var(--line)"}}/>
              </div>

              <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8}}>
                <button className="btn" style={{padding: "10px 12px", fontSize: 12, justifyContent: "center"}}>{L.sso}</button>
                <button className="btn" style={{padding: "10px 12px", fontSize: 12, justifyContent: "center"}}>{L.badge}</button>
              </div>
            </div>
          )}

          <div style={{marginTop: 24, paddingTop: 14, borderTop: "1px solid var(--line)",
                       display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--ink-3)"}}>
            <span>{L.footer}</span>
            <span style={{fontFamily: "var(--font-mono)"}}>{L.version}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
