// Sidebar + Topbar + Command Palette + Notifications + Avatar dropdown
const { useState: useShellS, useEffect: useShellE, useRef: useShellR, useMemo: useShellM } = React;

// === Theme controller (auto + manual) ===
window.useTheme = function useTheme() {
  const [theme, setTheme] = useShellS(() => {
    try {
      const stored = localStorage.getItem("nt_theme");
      if (stored) return stored;
    } catch(e){}
    return "auto";
  });
  useShellE(() => {
    const apply = () => {
      let resolved = theme;
      if (theme === "auto") {
        resolved = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
      }
      document.documentElement.setAttribute("data-theme", resolved);
    };
    apply();
    try { localStorage.setItem("nt_theme", theme); } catch(e){}
    if (theme === "auto" && window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: light)");
      const handler = () => apply();
      mq.addEventListener?.("change", handler);
      return () => mq.removeEventListener?.("change", handler);
    }
  }, [theme]);
  return [theme, setTheme];
};

// === Notifications store (live alerts + local read-state) ===
window.useNotifications = function useNotifications(frame) {
  const { data } = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/alerts?only_open=true&limit=10"), [], 30000)
    : { data: null };

  const [readSet, setReadSet] = useShellS({});

  const items = React.useMemo(() => {
    const raw = data && data.items ? data.items : (Array.isArray(data) ? data : null);
    if (!raw) return [];
    return raw.map(a => {
      const kind = (a.severity || "info").toLowerCase();
      const ago = (() => {
        if (!a.created_at) return "";
        const s = Math.round((Date.now() - new Date(a.created_at)) / 1000);
        if (s < 60) return `${s}s`;
        if (s < 3600) return `${Math.round(s/60)}m`;
        return `${Math.round(s/3600)}h`;
      })();
      return {
        id: a.id,
        kind,
        title: a.title || a.message || "Alert",
        body: `Bed ${a.patient_bed || a.bed || "—"} · ${ago} ago`,
        ago,
        read: !!readSet[a.id],
      };
    });
  }, [data, readSet]);

  const unread = items.filter(i => !i.read).length;
  const markAllRead = () => setReadSet(s => {
    const next = {...s};
    items.forEach(i => { next[i.id] = true; });
    return next;
  });
  return { items, unread, markAllRead };
};

// === Sidebar ===
window.NTSidebar = function NTSidebar({active, onChange, t, lang, sessionInfo, onSignOut, onOpenCmdK, connection}) {
  const items = [
    {id:"demo", icon:"play"},
    {id:"live", icon:"live"},
    {id:"dashboard", icon:"dashboard"},
    {id:"patient", icon:"patient"},
    {id:"alerts", icon:"alerts"},
    {id:"device", icon:"device"},
    {id:"setup", icon:"setup"},
    {id:"insights", icon:"insights"},
    {id:"reports", icon:"reports"},
    {id:"settings", icon:"settings"},
  ];

  return (
    <aside style={{
      width:240, flex:"none", background:"var(--bg-1)", borderRight:"1px solid var(--line)",
      display:"flex", flexDirection:"column", height:"100vh", position:"sticky", top:0, zIndex:20
    }}>
      {/* Brand */}
      <div style={{padding:"18px 18px 14px", borderBottom:"1px solid var(--line)", display:"flex", alignItems:"center", gap:10}}>
        <a href="landing.html" style={{display:"flex", alignItems:"center", gap:10, textDecoration:"none", color:"inherit", flex:1, minWidth:0}}>
          <div style={{
            width:30, height:30, borderRadius:7,
            background:"linear-gradient(135deg, var(--brand-2), var(--brand-3))",
            display:"grid", placeItems:"center",
            fontFamily:"var(--font-mono)", fontSize:11, fontWeight:700, color:"#fff",
            boxShadow:"0 0 12px oklch(0.55 0.18 240 / 0.4)",
          }}>NT</div>
          <div style={{minWidth:0}}>
            <div style={{fontSize:13, fontWeight:600, lineHeight:1.1}}>NeuraTriage</div>
            <div style={{fontSize:10, color:"var(--ink-3)", fontFamily:"var(--font-mono)", letterSpacing:"0.04em"}}>EEG · v0.4.2</div>
          </div>
        </a>
      </div>

      {/* Search / Command palette trigger */}
      <div style={{padding:"10px 12px 8px"}}>
        <button onClick={onOpenCmdK} style={{
          width:"100%", display:"flex", alignItems:"center", gap:8,
          padding:"7px 10px", background:"var(--bg-3)", border:"1px solid var(--line)",
          borderRadius:6, color:"var(--ink-3)", fontSize:11.5, cursor:"pointer", fontFamily:"inherit", textAlign:"left",
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = "var(--line-2)"}
        onMouseLeave={e => e.currentTarget.style.borderColor = "var(--line)"}>
          <window.NTIcon name="search" size={13}/>
          <span style={{flex:1}}>{lang==="vi" ? "Tìm kiếm…" : "Search…"}</span>
          <span className="mono" style={{fontSize:9.5, padding:"2px 5px", background:"var(--bg-2)", border:"1px solid var(--line-2)", borderRadius:3, color:"var(--ink-3)"}}>⌘K</span>
        </button>
      </div>

      {/* Session info card */}
      <div style={{padding:"10px 16px 14px", borderBottom:"1px solid var(--line)", fontSize:11.5}}>
        <div style={{fontSize:10, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.10em", marginBottom:8}}>{t.sidebar.sessionInfo}</div>
        <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:6}}>
          <div style={{width:24, height:24, borderRadius:"50%", background:"var(--bg-3)", display:"grid", placeItems:"center", fontSize:10, fontFamily:"var(--font-mono)", color:"var(--brand-2)", border:"1px solid var(--line-2)"}}>{sessionInfo.patient.initials}</div>
          <div style={{minWidth:0, flex:1}}>
            <div style={{fontWeight:500, color:"var(--ink)", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis"}}>{sessionInfo.patient.name}</div>
            <div className="mono" style={{fontSize:10, color:"var(--ink-3)"}}>{sessionInfo.patient.mrn}</div>
          </div>
        </div>
        <div style={{display:"flex", justifyContent:"space-between", color:"var(--ink-3)", fontSize:10.5, marginTop:10, fontFamily:"var(--font-mono)"}}>
          <span>{sessionInfo.device.name}</span>
          <span style={{color:"var(--ink-2)"}}>{sessionInfo.duration}</span>
        </div>
      </div>

      {/* Nav */}
      <nav style={{flex:1, padding:"12px 8px", overflowY:"auto"}}>
        {items.map(item => (
          <button key={item.id} onClick={() => onChange(item.id)} style={{
            display:"flex", alignItems:"center", gap:11, width:"100%",
            padding:"9px 10px", marginBottom:1, borderRadius:6,
            background: active===item.id ? "var(--bg-3)" : "transparent",
            border:"none",
            color: active===item.id ? "var(--ink)" : "var(--ink-2)",
            fontSize:13, cursor:"pointer", fontFamily:"inherit", textAlign:"left",
            transition:"background 0.12s",
            position:"relative",
          }}
          onMouseEnter={e => { if (active !== item.id) e.currentTarget.style.background = "var(--bg-2)"; }}
          onMouseLeave={e => { if (active !== item.id) e.currentTarget.style.background = "transparent"; }}>
            {active===item.id && (
              <div style={{position:"absolute", left:0, top:6, bottom:6, width:2, background:"var(--brand-2)", borderRadius:1, boxShadow:"0 0 6px var(--brand-2)"}}/>
            )}
            <window.NTIcon name={item.icon} size={15} color={active===item.id ? "var(--brand-2)" : "currentColor"}/>
            <span>{t.nav[item.id]}</span>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div style={{padding:"10px 14px 12px", borderTop:"1px solid var(--line)", fontSize:11, color:"var(--ink-3)"}}>
        <div style={{display:"flex", alignItems:"center", gap:8}}>
          <div style={{width:7, height:7, borderRadius:"50%", background: connection==="backend" ? "var(--ns)" : "var(--ink-4)", boxShadow: connection==="backend" ? "0 0 6px var(--ns)" : "none"}}/>
          <span className="mono" style={{color: connection==="backend" ? "var(--ink-2)" : "var(--ink-4)"}}>
            {connection==="backend" ? "backend connected" : "waiting for data"}
          </span>
        </div>
        <a href="https://github.com/LeXuanQue" target="_blank" rel="noopener" style={{
          marginTop:10, display:"flex", alignItems:"center", gap:7, padding:"6px 8px",
          color:"var(--ink-2)", textDecoration:"none", borderRadius:5, fontSize:11.5,
          transition:"background 0.12s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "var(--bg-3)"}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
          <window.NTIcon name="github" size={13}/>
          <span>github.com/LeXuanQue</span>
        </a>
        <button onClick={onSignOut} className="btn-ghost btn btn-sm" style={{marginTop:4, width:"100%", justifyContent:"flex-start", fontSize:11.5, padding:"6px 8px"}}>
          <window.NTIcon name="logout" size={13}/>
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
};

// === Notifications popover ===
function NotificationsPopover({open, onClose, notifs, lang}) {
  if (!open) return null;
  const kindColor = { is:"var(--is)", ns:"var(--ns)", info:"var(--brand-2)" };
  return (
    <>
      <div onClick={onClose} style={{position:"fixed", inset:0, zIndex:80}}/>
      <div style={{
        position:"absolute", top:46, right:0, width:340, background:"var(--bg-1)",
        border:"1px solid var(--line-2)", borderRadius:10, boxShadow:"var(--shadow-2)",
        zIndex:81, overflow:"hidden", animation:"npopIn .14s ease-out",
      }}>
        <style>{`@keyframes npopIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}`}</style>
        <div style={{padding:"12px 14px", borderBottom:"1px solid var(--line)", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
          <div style={{fontSize:12.5, fontWeight:600}}>{lang==="vi" ? "Thông báo" : "Notifications"}</div>
          <button onClick={notifs.markAllRead} style={{background:"transparent", border:"none", color:"var(--brand-2)", fontSize:11, cursor:"pointer", fontFamily:"inherit"}}>
            {lang==="vi" ? "Đánh dấu đã đọc" : "Mark all read"}
          </button>
        </div>
        <div style={{maxHeight:380, overflowY:"auto"}}>
          {notifs.items.map(n => (
            <div key={n.id} style={{
              padding:"11px 14px", borderBottom:"1px solid var(--line)", display:"flex", gap:10,
              opacity: n.read ? 0.6 : 1, position:"relative", cursor:"pointer",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--bg-2)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <div style={{width:6, height:6, borderRadius:"50%", background:kindColor[n.kind] || kindColor.info, marginTop:6, flex:"none", boxShadow:`0 0 6px ${kindColor[n.kind] || kindColor.info}`}}/>
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontSize:12, fontWeight:500, color:"var(--ink)"}}>{n.title}</div>
                <div style={{fontSize:11, color:"var(--ink-3)", marginTop:2}}>{n.body}</div>
              </div>
              {!n.read && <div style={{width:6, height:6, borderRadius:"50%", background:"var(--brand-2)", marginTop:7, flex:"none"}}/>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// === Avatar dropdown ===
function AvatarMenu({open, onClose, lang, theme, setTheme, onSignOut, onLangToggle}) {
  if (!open) return null;
  const Item = ({icon, label, onClick, right}) => (
    <button onClick={onClick} style={{
      display:"flex", alignItems:"center", gap:9, width:"100%", padding:"8px 12px",
      background:"transparent", border:"none", color:"var(--ink-2)", fontSize:12,
      cursor:"pointer", fontFamily:"inherit", textAlign:"left",
    }}
    onMouseEnter={e => e.currentTarget.style.background = "var(--bg-3)"}
    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
      <window.NTIcon name={icon} size={13}/>
      <span style={{flex:1}}>{label}</span>
      {right && <span style={{fontSize:10.5, color:"var(--ink-3)", fontFamily:"var(--font-mono)"}}>{right}</span>}
    </button>
  );
  return (
    <>
      <div onClick={onClose} style={{position:"fixed", inset:0, zIndex:80}}/>
      <div style={{
        position:"absolute", top:46, right:0, width:240, background:"var(--bg-1)",
        border:"1px solid var(--line-2)", borderRadius:10, boxShadow:"var(--shadow-2)",
        zIndex:81, overflow:"hidden", animation:"npopIn .14s ease-out",
      }}>
        <div style={{padding:"12px 14px", borderBottom:"1px solid var(--line)"}}>
          <div style={{fontSize:12.5, fontWeight:600, color:"var(--ink)"}}>Trung Văn</div>
          <div style={{fontSize:10.5, color:"var(--ink-3)"}}>vantrung66055@gmail.com</div>
          <div style={{marginTop:6, fontSize:10, color:"var(--brand-2)", fontFamily:"var(--font-mono)", letterSpacing:"0.04em"}}>NEUROLOGIST · ICU</div>
        </div>

        <div style={{padding:"6px 0"}}>
          <div style={{padding:"8px 12px 4px", fontSize:9.5, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.10em"}}>{lang==="vi" ? "Giao diện" : "Appearance"}</div>
          <div style={{display:"flex", gap:4, padding:"0 10px 6px"}}>
            {[
              {v:"light", icon:"sun", label:lang==="vi"?"Sáng":"Light"},
              {v:"dark", icon:"moon", label:lang==="vi"?"Tối":"Dark"},
              {v:"auto", icon:"auto", label:"Auto"},
            ].map(opt => (
              <button key={opt.v} onClick={() => setTheme(opt.v)} style={{
                flex:1, display:"flex", flexDirection:"column", alignItems:"center", gap:4, padding:"7px 4px",
                background: theme===opt.v ? "var(--bg-3)" : "transparent",
                border:`1px solid ${theme===opt.v ? "var(--brand-2)" : "var(--line)"}`,
                borderRadius:6, color: theme===opt.v ? "var(--ink)" : "var(--ink-3)",
                fontSize:10, cursor:"pointer", fontFamily:"inherit",
              }}>
                <window.NTIcon name={opt.icon} size={13}/>
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div style={{borderTop:"1px solid var(--line)", padding:"4px 0"}}>
          <Item icon="globe" label={lang==="vi" ? "Ngôn ngữ" : "Language"} onClick={onLangToggle} right={lang.toUpperCase()}/>
          <Item icon="settings" label={lang==="vi" ? "Cài đặt" : "Settings"} onClick={() => { onClose(); /* nav handled outside */ }} right="⌘,"/>
          <Item icon="github" label="GitHub" onClick={() => window.open("https://github.com/LeXuanQue", "_blank")}/>
        </div>

        <div style={{borderTop:"1px solid var(--line)", padding:"4px 0"}}>
          <Item icon="logout" label={lang==="vi" ? "Đăng xuất" : "Sign out"} onClick={onSignOut}/>
        </div>
      </div>
    </>
  );
}

// === Topbar ===
window.NTTopbar = function NTTopbar({title, subtitle, badges=[], mode, theme, setTheme, lang, onLangToggle, onSignOut, notifs, onOpenCmdK, onNavSettings}) {
  const [now, setNow] = useShellS(() => new Date());
  useShellE(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const [openNotif, setOpenNotif] = useShellS(false);
  const [openAvatar, setOpenAvatar] = useShellS(false);

  const time = now.toLocaleTimeString("en-GB", {hour:"2-digit", minute:"2-digit", second:"2-digit"});

  const cycleTheme = () => {
    const next = theme === "dark" ? "light" : theme === "light" ? "auto" : "dark";
    setTheme(next);
  };
  const themeIcon = theme === "light" ? "sun" : theme === "dark" ? "moon" : "auto";

  return (
    <header style={{
      height:54, flex:"none", borderBottom:"1px solid var(--line)",
      background:"var(--bg-1)", display:"flex", alignItems:"center", padding:"0 22px",
      gap:18, position:"sticky", top:0, zIndex:15,
    }}>
      <div style={{flex:1, minWidth:0}}>
        <div style={{display:"flex", alignItems:"center", gap:10}}>
          <h1 style={{fontSize:14, fontWeight:600, margin:0, letterSpacing:"-0.005em"}}>{title}</h1>
          {badges.map((b, i) => (
            <span key={i} className={`tag ${b.kind || ""}`}>{b.icon && <span className={`dot ${b.live ? "live" : ""} ${b.kind || ""}`}/>}{b.label}</span>
          ))}
        </div>
        {subtitle && <div style={{fontSize:11.5, color:"var(--ink-3)", marginTop:2}}>{subtitle}</div>}
      </div>

      <div style={{display:"flex", alignItems:"center", gap:8, fontSize:11.5, color:"var(--ink-3)", fontFamily:"var(--font-mono)"}}>
        <span style={{marginRight:4}}>{time}</span>
        <span style={{padding:"3px 8px", border:"1px solid var(--line-2)", borderRadius:4, color:"var(--ink-2)", letterSpacing:"0.06em"}}>{mode}</span>

        {/* Search shortcut */}
        <button onClick={onOpenCmdK} title="Search (⌘K)" style={iconBtnStyle()}>
          <window.NTIcon name="search" size={14}/>
        </button>

        {/* Theme toggle */}
        <button onClick={cycleTheme} title={`Theme: ${theme}`} style={iconBtnStyle()}>
          <window.NTIcon name={themeIcon} size={14}/>
        </button>

        {/* Notifications */}
        <div style={{position:"relative"}}>
          <button onClick={() => { setOpenNotif(v => !v); setOpenAvatar(false); }} title="Notifications" style={iconBtnStyle(openNotif)}>
            <window.NTIcon name="bell" size={14}/>
            {notifs.unread > 0 && (
              <span style={{
                position:"absolute", top:2, right:2, minWidth:14, height:14, padding:"0 3px",
                background:"var(--hs)", color:"#fff", fontSize:9, fontWeight:700,
                borderRadius:7, display:"grid", placeItems:"center", fontFamily:"var(--font-mono)",
                border:"2px solid var(--bg-1)", lineHeight:1,
              }}>{notifs.unread}</span>
            )}
          </button>
          <NotificationsPopover open={openNotif} onClose={() => setOpenNotif(false)} notifs={notifs} lang={lang}/>
        </div>

        {/* Avatar */}
        <div style={{position:"relative"}}>
          <button onClick={() => { setOpenAvatar(v => !v); setOpenNotif(false); }} title="Account" style={{
            display:"flex", alignItems:"center", gap:7, padding:"4px 8px 4px 4px",
            background: openAvatar ? "var(--bg-3)" : "transparent", border:`1px solid ${openAvatar ? "var(--line-2)" : "var(--line)"}`,
            borderRadius:18, cursor:"pointer", color:"var(--ink-2)", fontFamily:"inherit",
          }}>
            <div style={{
              width:24, height:24, borderRadius:"50%",
              background:"linear-gradient(135deg, var(--brand-2), var(--brand-3))",
              display:"grid", placeItems:"center", fontSize:10, fontWeight:600, color:"#fff",
              fontFamily:"var(--font-mono)",
            }}>TV</div>
            <window.NTIcon name="chevron-down" size={11}/>
          </button>
          <AvatarMenu open={openAvatar} onClose={() => setOpenAvatar(false)} lang={lang} theme={theme} setTheme={setTheme} onSignOut={onSignOut} onLangToggle={onLangToggle}/>
        </div>
      </div>
    </header>
  );
};

function iconBtnStyle(active) {
  return {
    width:30, height:30, display:"grid", placeItems:"center",
    background: active ? "var(--bg-3)" : "transparent",
    border:`1px solid ${active ? "var(--line-2)" : "transparent"}`,
    borderRadius:6, cursor:"pointer", color:"var(--ink-2)", position:"relative",
    transition:"background 0.12s, border-color 0.12s",
  };
}

// === Command Palette ===
window.CommandPalette = function CommandPalette({open, onClose, onNav, lang, theme, setTheme, onLangToggle}) {
  const [q, setQ] = useShellS("");
  const [idx, setIdx] = useShellS(0);
  const inputRef = useShellR();

  useShellE(() => {
    if (open) { setQ(""); setIdx(0); setTimeout(() => inputRef.current?.focus(), 30); }
  }, [open]);

  const commands = useShellM(() => {
    const navs = [
      {id:"demo", label:lang==="vi"?"Chế độ demo":"Demo mode", group:lang==="vi"?"Điều hướng":"Navigate", icon:"play", action:() => onNav("demo")},
      {id:"live", label:lang==="vi"?"Live Monitor":"Live Monitor", group:lang==="vi"?"Điều hướng":"Navigate", icon:"live", action:() => onNav("live")},
      {id:"dashboard", label:"Dashboard", group:lang==="vi"?"Điều hướng":"Navigate", icon:"dashboard", action:() => onNav("dashboard")},
      {id:"patient", label:lang==="vi"?"Bệnh nhân":"Patient", group:lang==="vi"?"Điều hướng":"Navigate", icon:"patient", action:() => onNav("patient")},
      {id:"alerts", label:lang==="vi"?"Cảnh báo":"Alerts", group:lang==="vi"?"Điều hướng":"Navigate", icon:"alerts", action:() => onNav("alerts")},
      {id:"device", label:lang==="vi"?"Thiết bị":"Device", group:lang==="vi"?"Điều hướng":"Navigate", icon:"device", action:() => onNav("device")},
      {id:"setup", label:"Setup", group:lang==="vi"?"Điều hướng":"Navigate", icon:"setup", action:() => onNav("setup")},
      {id:"insights", label:lang==="vi"?"Phân tích":"Insights", group:lang==="vi"?"Điều hướng":"Navigate", icon:"insights", action:() => onNav("insights")},
      {id:"reports", label:lang==="vi"?"Báo cáo":"Reports", group:lang==="vi"?"Điều hướng":"Navigate", icon:"reports", action:() => onNav("reports")},
      {id:"settings", label:lang==="vi"?"Cài đặt":"Settings", group:lang==="vi"?"Điều hướng":"Navigate", icon:"settings", action:() => onNav("settings"), shortcut:"⌘,"},
    ];
    const acts = [
      {id:"theme-light", label:lang==="vi"?"Giao diện sáng":"Light theme", group:lang==="vi"?"Hành động":"Actions", icon:"sun", action:() => setTheme("light")},
      {id:"theme-dark", label:lang==="vi"?"Giao diện tối":"Dark theme", group:lang==="vi"?"Hành động":"Actions", icon:"moon", action:() => setTheme("dark")},
      {id:"theme-auto", label:lang==="vi"?"Theo hệ thống":"Auto (system)", group:lang==="vi"?"Hành động":"Actions", icon:"auto", action:() => setTheme("auto")},
      {id:"lang", label:lang==="vi"?"Đổi ngôn ngữ":"Switch language", group:lang==="vi"?"Hành động":"Actions", icon:"globe", action:onLangToggle},
      {id:"github", label:"Open GitHub · LeXuanQue", group:lang==="vi"?"Liên kết":"Links", icon:"github", action:() => window.open("https://github.com/LeXuanQue", "_blank")},
      {id:"landing", label:lang==="vi"?"Quay lại Landing":"Back to landing", group:lang==="vi"?"Liên kết":"Links", icon:"home", action:() => window.location.href = "landing.html"},
    ];
    return [...navs, ...acts];
  }, [lang]);

  const filtered = useShellM(() => {
    if (!q.trim()) return commands;
    const ql = q.toLowerCase();
    return commands.filter(c => c.label.toLowerCase().includes(ql) || c.id.toLowerCase().includes(ql));
  }, [q, commands]);

  const grouped = useShellM(() => {
    const g = {};
    filtered.forEach((c,i) => { (g[c.group] ||= []).push({...c, _i:i}); });
    return g;
  }, [filtered]);

  useShellE(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); setIdx(i => Math.min(filtered.length-1, i+1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setIdx(i => Math.max(0, i-1)); }
      else if (e.key === "Enter") {
        e.preventDefault();
        const c = filtered[idx];
        if (c) { c.action(); onClose(); }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, idx, onClose]);

  if (!open) return null;
  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"oklch(0 0 0 / 0.5)", backdropFilter:"blur(6px)",
      zIndex:200, display:"flex", alignItems:"flex-start", justifyContent:"center", paddingTop:"12vh",
      animation:"cmdkFade .14s ease-out",
    }}>
      <style>{`
        @keyframes cmdkFade{from{opacity:0}to{opacity:1}}
        @keyframes cmdkSlide{from{opacity:0;transform:translateY(-8px) scale(0.98)}to{opacity:1;transform:translateY(0) scale(1)}}
      `}</style>
      <div onClick={e => e.stopPropagation()} style={{
        width:560, maxWidth:"90vw", background:"var(--bg-1)",
        border:"1px solid var(--line-2)", borderRadius:12, boxShadow:"0 30px 80px -20px oklch(0 0 0 / 0.7), 0 0 0 1px oklch(1 0 0 / 0.04) inset",
        animation:"cmdkSlide .16s ease-out", overflow:"hidden",
      }}>
        <div style={{display:"flex", alignItems:"center", gap:10, padding:"14px 16px", borderBottom:"1px solid var(--line)"}}>
          <window.NTIcon name="search" size={15} color="var(--ink-3)"/>
          <input ref={inputRef} value={q} onChange={e => { setQ(e.target.value); setIdx(0); }}
            placeholder={lang==="vi"?"Gõ lệnh hoặc tìm kiếm…":"Type a command or search…"}
            style={{flex:1, background:"transparent", border:"none", outline:"none", color:"var(--ink)", fontSize:14, fontFamily:"inherit"}}/>
          <span className="mono" style={{fontSize:9.5, padding:"2px 5px", background:"var(--bg-3)", border:"1px solid var(--line-2)", borderRadius:3, color:"var(--ink-3)"}}>esc</span>
        </div>
        <div style={{maxHeight:380, overflowY:"auto", padding:"6px 0"}}>
          {filtered.length === 0 && (
            <div style={{padding:"30px 16px", textAlign:"center", color:"var(--ink-3)", fontSize:12}}>
              {lang==="vi" ? "Không tìm thấy lệnh nào" : "No commands found"}
            </div>
          )}
          {Object.entries(grouped).map(([g, list]) => (
            <div key={g}>
              <div style={{padding:"8px 16px 4px", fontSize:9.5, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.10em"}}>{g}</div>
              {list.map(c => (
                <button key={c.id} onClick={() => { c.action(); onClose(); }}
                  onMouseEnter={() => setIdx(c._i)}
                  style={{
                    display:"flex", alignItems:"center", gap:11, width:"100%", padding:"9px 16px",
                    background: idx === c._i ? "var(--bg-3)" : "transparent",
                    border:"none", color: idx === c._i ? "var(--ink)" : "var(--ink-2)",
                    fontSize:12.5, cursor:"pointer", fontFamily:"inherit", textAlign:"left",
                  }}>
                  <window.NTIcon name={c.icon} size={14} color={idx === c._i ? "var(--brand-2)" : "currentColor"}/>
                  <span style={{flex:1}}>{c.label}</span>
                  {c.shortcut && <span className="mono" style={{fontSize:10, color:"var(--ink-3)"}}>{c.shortcut}</span>}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div style={{padding:"8px 14px", borderTop:"1px solid var(--line)", display:"flex", gap:14, fontSize:10, color:"var(--ink-3)", fontFamily:"var(--font-mono)"}}>
          <span><kbd style={kbdStyle}>↑↓</kbd> {lang==="vi"?"di chuyển":"navigate"}</span>
          <span><kbd style={kbdStyle}>↵</kbd> {lang==="vi"?"chọn":"select"}</span>
          <span><kbd style={kbdStyle}>esc</kbd> {lang==="vi"?"đóng":"close"}</span>
        </div>
      </div>
    </div>
  );
};

const kbdStyle = {
  padding:"1px 5px", background:"var(--bg-3)", border:"1px solid var(--line-2)",
  borderRadius:3, color:"var(--ink-2)", fontSize:9.5, marginRight:4,
};
