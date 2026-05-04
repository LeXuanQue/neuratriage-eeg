// Shared layout shell — sidebar nav + topbar + content
const { useContext: useCtx, createContext } = React;

window.AppContext = createContext({lang: "vi", t: window.I18N.vi});

window.useT = function() {
  const ctx = useCtx(window.AppContext);
  return ctx.t;
};

// Tiny stroke icons (16px)
window.Icon = function Icon({name, size = 16, color = "currentColor"}) {
  const s = {width: size, height: size, fill: "none", stroke: color, strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round"};
  switch(name) {
    case "live": return (<svg viewBox="0 0 24 24" {...s}><path d="M3 12h3l2-6 4 12 2-9 2 5h5"/></svg>);
    case "dashboard": return (<svg viewBox="0 0 24 24" {...s}><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>);
    case "patient": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/></svg>);
    case "alerts": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 19h12l-1.5-2v-5a4.5 4.5 0 0 0-9 0v5L6 19z"/><path d="M10 22a2 2 0 0 0 4 0"/></svg>);
    case "setup": return (<svg viewBox="0 0 24 24" {...s}><path d="M12 3a9 9 0 1 0 9 9"/><path d="M12 8v4l3 2"/></svg>);
    case "device": return (<svg viewBox="0 0 24 24" {...s}><rect x="4" y="6" width="16" height="12" rx="2"/><path d="M8 10v4M12 10v4M16 10v4"/><path d="M2 12h2M20 12h2"/></svg>);
    case "wifi": return (<svg viewBox="0 0 24 24" {...s}><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1" fill={color}/></svg>);
    case "bt": return (<svg viewBox="0 0 24 24" {...s}><path d="M7 7l10 10-5 5V2l5 5L7 17"/></svg>);
    case "battery": return (<svg viewBox="0 0 24 24" {...s}><rect x="2" y="8" width="18" height="8" rx="1"/><path d="M22 11v2"/><rect x="4" y="10" width="11" height="4" fill={color} stroke="none"/></svg>);
    case "insights": return (<svg viewBox="0 0 24 24" {...s}><path d="M3 18l5-6 4 4 4-7 5 8"/></svg>);
    case "reports": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5"/><path d="M9 13h7M9 17h5"/></svg>);
    case "settings": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1A1.7 1.7 0 0 0 8 19.3a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H2a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 3.6 8a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H8a1.7 1.7 0 0 0 1-1.5V2a2 2 0 0 1 4 0v.1A1.7 1.7 0 0 0 14 3.6a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V8c0 .7.4 1.3 1 1.7"/></svg>);
    case "search": return (<svg viewBox="0 0 24 24" {...s}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.4-4.4"/></svg>);
    case "ack": return (<svg viewBox="0 0 24 24" {...s}><path d="M5 12l5 5L20 7"/></svg>);
    case "page": return (<svg viewBox="0 0 24 24" {...s}><path d="M22 16.92V21a1 1 0 0 1-1.1 1A19.86 19.86 0 0 1 2 4.1 1 1 0 0 1 3 3h4.09a1 1 0 0 1 1 .75l1 4a1 1 0 0 1-.27 1L7 10.5a16 16 0 0 0 6.5 6.5l1.75-1.83a1 1 0 0 1 1-.27l4 1a1 1 0 0 1 .75 1z"/></svg>);
    case "lang": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/></svg>);
    case "play": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 4l14 8-14 8z" fill={color}/></svg>);
    default: return null;
  }
};

window.AppShell = function AppShell({children, active = "live", onNav, onLang, lang, accent}) {
  const t = window.useT();
  const navItems = [
    {key: "live", icon: "live", live: true},
    {key: "dashboard", icon: "dashboard"},
    {key: "patient", icon: "patient"},
    {key: "alerts", icon: "alerts"},
    {key: "device", icon: "device"},
    {key: "setup", icon: "setup"},
    {key: "insights", icon: "insights"},
    {key: "reports", icon: "reports"},
    {key: "settings", icon: "settings"},
  ];
  return (
    <div style={{display: "grid", gridTemplateColumns: "232px 1fr", height: "100%", background: "var(--bg-2)"}}>
      {/* Sidebar */}
      <aside style={{
        background: "var(--bg)", borderRight: "1px solid var(--line)",
        display: "flex", flexDirection: "column", padding: "14px 0",
      }}>
        <div style={{padding: "0 18px 14px", borderBottom: "1px solid var(--line)"}}>
          <div style={{display: "flex", alignItems: "center", gap: 10}}>
            <div style={{
              width: 28, height: 28, borderRadius: 7,
              background: accent || "var(--brand)",
              display: "grid", placeItems: "center",
              color: "white", fontWeight: 700, fontSize: 12,
              fontFamily: "var(--font-mono)",
            }}>NT</div>
            <div>
              <div style={{fontWeight: 600, fontSize: 13, lineHeight: 1.1, letterSpacing: "-0.01em"}}>{t.appName}</div>
              <div style={{fontSize: 10, color: "var(--ink-3)", marginTop: 2}}>{t.tagline}</div>
            </div>
          </div>
        </div>
        <nav style={{padding: "10px 8px", display: "flex", flexDirection: "column", gap: 1}}>
          {navItems.map(it => {
            const isActive = it.key === active;
            return (
              <a key={it.key} onClick={() => onNav && onNav(it.key)}
                 style={{
                   display: "flex", alignItems: "center", gap: 10,
                   padding: "8px 10px", borderRadius: 6,
                   color: isActive ? "var(--ink)" : "var(--ink-2)",
                   background: isActive ? "var(--bg-3)" : "transparent",
                   fontSize: 12.5, fontWeight: isActive ? 500 : 400,
                   cursor: "pointer", textDecoration: "none",
                 }}>
                <window.Icon name={it.icon} size={15} />
                <span style={{flex: 1}}>{t.nav[it.key]}</span>
                {it.live && (
                  <span className="dot live" style={{width: 6, height: 6}} />
                )}
              </a>
            );
          })}
        </nav>
        <div style={{marginTop: "auto", padding: "12px 16px", borderTop: "1px solid var(--line)", fontSize: 10.5, color: "var(--ink-3)", lineHeight: 1.6}}>
          <div className="mono" style={{display: "flex", justifyContent: "space-between"}}>
            <span>v0.4.2</span><span>ApFu-MFDFA</span>
          </div>
          <div className="mono" style={{display: "flex", justifyContent: "space-between", marginTop: 2}}>
            <span>ZJU4H</span><span>256 Hz</span>
          </div>
        </div>
      </aside>
      {/* Main */}
      <main style={{display: "flex", flexDirection: "column", overflow: "hidden"}}>
        <header style={{
          padding: "12px 22px", borderBottom: "1px solid var(--line)",
          background: "var(--bg)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{display: "flex", alignItems: "center", gap: 12}}>
            <div style={{fontSize: 14, fontWeight: 600}}>{t.nav[active]}</div>
            <span className="tag" style={{fontSize: 10, padding: "1px 6px"}}>
              <span className="dot live"/>LIVE
            </span>
          </div>
          <div style={{display: "flex", alignItems: "center", gap: 8}}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "4px 10px", borderRadius: 999,
              border: "1px solid var(--ns)", background: "var(--ns-soft)",
              fontSize: 11, color: "var(--ns)", fontWeight: 500,
              cursor: "pointer",
            }} title="g.tec g.HIamp · 256Hz · USB · 87%"
            onClick={() => onNav && onNav("device")}>
              <window.Icon name="device" size={12} color="var(--ns)" />
              <span className="mono">g.HIamp</span>
              <span style={{width:1,height:10,background:"var(--ns)",opacity:0.4}}/>
              <span className="mono">256Hz</span>
              <span style={{width:1,height:10,background:"var(--ns)",opacity:0.4}}/>
              <span style={{display:"inline-flex",alignItems:"center",gap:4}}>
                <window.Icon name="battery" size={12} color="var(--ns)" />
                <span className="mono">87%</span>
              </span>
            </span>
            <div style={{position: "relative"}}>
              <input placeholder={lang === "vi" ? "Tìm bệnh nhân, mã ca…" : "Search patient, MRN…"}
                     style={{
                       padding: "6px 12px 6px 30px", borderRadius: 5,
                       border: "1px solid var(--line)", background: "var(--bg-2)",
                       fontSize: 12, fontFamily: "inherit", width: 240,
                     }} />
              <span style={{position: "absolute", left: 9, top: 7, color: "var(--ink-3)"}}>
                <window.Icon name="search" size={14} />
              </span>
            </div>
            <button className="btn btn-ghost" style={{fontFamily: "var(--font-mono)", fontSize: 11}}
                    onClick={() => onLang && onLang(lang === "vi" ? "en" : "vi")}>
              <window.Icon name="lang" size={13} />
              {lang === "vi" ? "VI" : "EN"}
            </button>
            <div style={{
              width: 28, height: 28, borderRadius: 14, background: "var(--bg-3)",
              display: "grid", placeItems: "center", fontSize: 11,
              color: "var(--ink-2)", fontWeight: 600,
            }}>HV</div>
          </div>
        </header>
        <div style={{flex: 1, overflow: "auto"}}>
          {children}
        </div>
      </main>
    </div>
  );
};
