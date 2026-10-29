// Icon set — 16px stroke icons
window.NTIcon = function NTIcon({name, size = 16, color = "currentColor"}) {
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
    case "settings": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4.9a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.5a7 7 0 0 0-2 1.2l-2.4-.9-2 3.5 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-.9a7 7 0 0 0 2 1.2L10 21h4l.5-2.5a7 7 0 0 0 2-1.2l2.4.9 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z"/></svg>);
    case "search": return (<svg viewBox="0 0 24 24" {...s}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.4-4.4"/></svg>);
    case "ack": return (<svg viewBox="0 0 24 24" {...s}><path d="M5 12l5 5L20 7"/></svg>);
    case "page": return (<svg viewBox="0 0 24 24" {...s}><path d="M22 16.92V21a1 1 0 0 1-1.1 1A19.86 19.86 0 0 1 2 4.1 1 1 0 0 1 3 3h4.09a1 1 0 0 1 1 .75l1 4a1 1 0 0 1-.27 1L7 10.5a16 16 0 0 0 6.5 6.5l1.75-1.83a1 1 0 0 1 1-.27l4 1a1 1 0 0 1 .75 1z"/></svg>);
    case "play": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 4l14 8-14 8z" fill={color}/></svg>);
    case "pause": return (<svg viewBox="0 0 24 24" {...s}><rect x="6" y="4" width="4" height="16" fill={color} stroke="none"/><rect x="14" y="4" width="4" height="16" fill={color} stroke="none"/></svg>);
    case "download": return (<svg viewBox="0 0 24 24" {...s}><path d="M12 3v13M6 11l6 6 6-6M5 21h14"/></svg>);
    case "filter": return (<svg viewBox="0 0 24 24" {...s}><path d="M3 5h18l-7 9v6l-4-2v-4z"/></svg>);
    case "plus": return (<svg viewBox="0 0 24 24" {...s}><path d="M12 5v14M5 12h14"/></svg>);
    case "chevron-right": return (<svg viewBox="0 0 24 24" {...s}><path d="M9 6l6 6-6 6"/></svg>);
    case "chevron-down": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 9l6 6 6-6"/></svg>);
    case "logout": return (<svg viewBox="0 0 24 24" {...s}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>);
    case "tweaks": return (<svg viewBox="0 0 24 24" {...s}><path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h14M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="18" r="2" /></svg>);
    case "brain": return (<svg viewBox="0 0 24 24" {...s}><path d="M9 4a3 3 0 0 0-3 3v0a3 3 0 0 0-2 5 3 3 0 0 0 2 5v0a3 3 0 0 0 3 3v-16zM15 4a3 3 0 0 1 3 3v0a3 3 0 0 1 2 5 3 3 0 0 1-2 5v0a3 3 0 0 1-3 3v-16z"/></svg>);
    case "bell": return (<svg viewBox="0 0 24 24" {...s}><path d="M6 19h12l-1.5-2v-5a4.5 4.5 0 0 0-9 0v5L6 19z"/><path d="M10 22a2 2 0 0 0 4 0"/></svg>);
    case "sun": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>);
    case "moon": return (<svg viewBox="0 0 24 24" {...s}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>);
    case "auto": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="9"/><path d="M12 3v18" /><path d="M12 3a9 9 0 0 1 0 18" fill={color} stroke="none"/></svg>);
    case "github": return (<svg viewBox="0 0 24 24" {...s}><path d="M9 19c-4 1.5-4-2-6-2.5M15 22v-3.9c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.7 4.7 0 0 0-1.3-3.2 4.4 4.4 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6 0C6.7 2.4 5.7 2.7 5.7 2.7a4.4 4.4 0 0 0-.1 3.2A4.7 4.7 0 0 0 4.3 9c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V22"/></svg>);
    case "globe": return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>);
    case "home": return (<svg viewBox="0 0 24 24" {...s}><path d="M3 11l9-7 9 7v9a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2v-9z"/></svg>);
    default: return null;
  }
};
