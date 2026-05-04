// Device Connection screen — scan, connect, monitor live device status

window.DeviceScreen = function DeviceScreen() {
  const t = window.useT();
  const lang = (window.useT() === window.I18N.vi) ? "vi" : "en";
  const L = lang === "vi" ? {
    title: "Kết nối thiết bị",
    subtitle: "Quét, ghép nối và giám sát thiết bị thu EEG.",
    sources: "Nguồn tín hiệu",
    live: "Thiết bị thực", liveSub: "USB / Bluetooth / Wi-Fi · LSL",
    replay: "Phát lại file", replaySub: "EDF / BDF / FIF từ ổ đĩa",
    demo: "Chế độ Demo", demoSub: "Tín hiệu mô phỏng để huấn luyện",
    detected: "Thiết bị phát hiện", scan: "Quét lại", connect: "Kết nối", connected: "Đã kết nối", disconnect: "Ngắt",
    streamHealth: "Tình trạng luồng dữ liệu",
    packetLoss: "Mất gói", latency: "Độ trễ", jitter: "Jitter", uptime: "Thời gian chạy",
    incoming: "Lưu lượng vào · 60 giây qua",
    paired: "Đã ghép nối", available: "Có thể kết nối",
    saveDefault: "Đặt làm thiết bị mặc định",
    proceed: "Tiếp tục → Kiểm tra impedance",
    secure: "Truyền mã hóa TLS · ID thiết bị xác thực",
    samplesIn: "mẫu / giây vào",
  } : {
    title: "Device connection",
    subtitle: "Scan, pair and monitor your EEG acquisition device.",
    sources: "Signal source",
    live: "Live device", liveSub: "USB / Bluetooth / Wi-Fi · LSL",
    replay: "Replay file", replaySub: "EDF / BDF / FIF from disk",
    demo: "Demo mode", demoSub: "Synthetic signal for training",
    detected: "Detected devices", scan: "Rescan", connect: "Connect", connected: "Connected", disconnect: "Disconnect",
    streamHealth: "Stream health",
    packetLoss: "Packet loss", latency: "Latency", jitter: "Jitter", uptime: "Uptime",
    incoming: "Incoming throughput · last 60s",
    paired: "Paired", available: "Available",
    saveDefault: "Set as default device",
    proceed: "Proceed → Impedance check",
    secure: "TLS-encrypted stream · authenticated device ID",
    samplesIn: "samples / sec",
  };

  const devices = [
    {name: "g.tec g.HIamp", sn: "S/N 4421", iface: "USB 3.0", ch: 19, hz: 256, bat: 87, sig: "—", status: "connected", default: true},
    {name: "Emotiv EPOC X", sn: "S/N 7782", iface: "Bluetooth 5.2", ch: 14, hz: 256, bat: 64, sig: -52, status: "paired"},
    {name: "OpenBCI Cyton + Daisy", sn: "S/N 1031", iface: "Wi-Fi 5G", ch: 16, hz: 250, bat: 92, sig: -41, status: "available"},
    {name: "Neurosity Crown", sn: "S/N 5520", iface: "Bluetooth 5.0", ch: 8, hz: 256, bat: 23, sig: -68, status: "available"},
  ];

  const tput = React.useMemo(() => {
    const arr = [];
    for (let i = 0; i < 60; i++) arr.push(0.78 + 0.18 * Math.sin(i*0.5) + (Math.random()-0.5)*0.06);
    return arr;
  }, []);

  return (
    <div style={{padding: 18, display: "flex", flexDirection: "column", gap: 14}}>
      {/* Source picker */}
      <div className="panel">
        <div className="panel-header"><span>{L.sources}</span><span style={{fontSize:10,color:"var(--ink-3)",textTransform:"none"}}>{L.secure}</span></div>
        <div style={{padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12}}>
          {[
            {key: "live", icon: "device", title: L.live, sub: L.liveSub, sel: true},
            {key: "replay", icon: "reports", title: L.replay, sub: L.replaySub},
            {key: "demo", icon: "play", title: L.demo, sub: L.demoSub},
          ].map(s => (
            <div key={s.key} style={{
              padding: "14px 16px",
              border: `1.5px solid ${s.sel ? "var(--brand)" : "var(--line)"}`,
              borderRadius: 8,
              background: s.sel ? "var(--brand-soft)" : "var(--bg)",
              cursor: "pointer",
              display: "flex", gap: 12, alignItems: "flex-start",
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 6,
                background: s.sel ? "var(--brand)" : "var(--bg-3)",
                color: s.sel ? "white" : "var(--ink-2)",
                display: "grid", placeItems: "center",
              }}>
                <window.Icon name={s.icon} size={16} color="currentColor" />
              </div>
              <div style={{flex: 1}}>
                <div style={{fontSize: 13, fontWeight: 600, marginBottom: 2}}>{s.title}</div>
                <div style={{fontSize: 11, color: "var(--ink-3)"}}>{s.sub}</div>
              </div>
              {s.sel && <span style={{color:"var(--brand)"}}><window.Icon name="ack" size={16} color="var(--brand)" /></span>}
            </div>
          ))}
        </div>
      </div>

      {/* Detected devices */}
      <div className="panel">
        <div className="panel-header">
          <span>{L.detected}</span>
          <button className="btn btn-ghost" style={{fontSize: 11}}>↻ {L.scan}</button>
        </div>
        <div>
          {devices.map((d, i) => {
            const isConnected = d.status === "connected";
            const isPaired = d.status === "paired";
            const statusColor = isConnected ? "var(--ns)" : isPaired ? "var(--brand)" : "var(--ink-3)";
            const statusLabel = isConnected ? L.connected : isPaired ? L.paired : L.available;
            const ifaceIcon = d.iface.startsWith("USB") ? "device" : d.iface.startsWith("Bluetooth") ? "bt" : "wifi";
            return (
              <div key={d.sn} style={{
                padding: "14px 18px",
                borderTop: i ? "1px solid var(--line)" : "none",
                display: "grid",
                gridTemplateColumns: "auto 1.4fr 1fr 1fr 1fr auto",
                gap: 16, alignItems: "center",
                background: isConnected ? "var(--ns-soft)" : "transparent",
                borderLeft: isConnected ? "3px solid var(--ns)" : "3px solid transparent",
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 6,
                  background: "var(--bg-3)", color: "var(--ink-2)",
                  display: "grid", placeItems: "center",
                }}>
                  <window.Icon name={ifaceIcon} size={18} />
                </div>
                <div>
                  <div style={{fontSize: 13, fontWeight: 600}}>{d.name}</div>
                  <div className="mono" style={{fontSize: 11, color: "var(--ink-3)", marginTop: 2}}>{d.sn} · {d.iface}</div>
                </div>
                <div>
                  <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>Channels</div>
                  <div className="mono" style={{fontSize: 13, marginTop: 2}}>{d.ch} ch · {d.hz} Hz</div>
                </div>
                <div>
                  <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>Battery</div>
                  <div className="mono" style={{fontSize: 13, marginTop: 2, color: d.bat < 30 ? "var(--hs)" : "var(--ink)"}}>{d.bat}%</div>
                </div>
                <div>
                  <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>Signal</div>
                  <div className="mono" style={{fontSize: 13, marginTop: 2}}>{typeof d.sig === "number" ? d.sig + " dBm" : d.sig}</div>
                </div>
                <div style={{display: "flex", alignItems: "center", gap: 10}}>
                  <span className="tag" style={{borderColor: statusColor, color: statusColor}}>
                    <span className="dot" style={{background: statusColor}}/>{statusLabel}
                  </span>
                  {isConnected
                    ? <button className="btn" style={{fontSize: 11}}>{L.disconnect}</button>
                    : <button className="btn btn-primary" style={{fontSize: 11}}>{L.connect}</button>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stream health for active device */}
      <div style={{display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 14}}>
        <div className="panel">
          <div className="panel-header">
            <span>{L.streamHealth} · g.tec g.HIamp</span>
            <span className="tag" style={{borderColor:"var(--ns)",color:"var(--ns)"}}><span className="dot live" style={{background:"var(--ns)"}}/>{L.connected}</span>
          </div>
          <div style={{padding: 16, display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14}}>
            {[
              {l: L.packetLoss, v: "0.02", u: "%", c: "var(--ns)"},
              {l: L.latency, v: "12", u: "ms", c: "var(--ns)"},
              {l: L.jitter, v: "0.8", u: "ms", c: "var(--ns)"},
              {l: L.uptime, v: "00:42:18", u: "", c: "var(--ink)"},
            ].map(m => (
              <div key={m.l}>
                <div style={{fontSize: 10, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em"}}>{m.l}</div>
                <div className="mono" style={{fontSize: 20, fontWeight: 600, marginTop: 4, color: m.c}}>{m.v}<span style={{fontSize: 11, color: "var(--ink-3)", marginLeft: 3}}>{m.u}</span></div>
              </div>
            ))}
          </div>
          <div style={{padding: "0 16px 14px"}}>
            <div style={{fontSize: 10.5, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6}}>{L.incoming}</div>
            <svg width="100%" height="80" viewBox="0 0 600 80" preserveAspectRatio="none" style={{display: "block"}}>
              <line x1="0" y1="60" x2="600" y2="60" stroke="var(--line)" strokeDasharray="2 4"/>
              <path d={"M0," + (60 - tput[0]*48) + " " + tput.map((v,i) => "L" + (i*10) + "," + (60 - v*48)).join(" ") + " L590,80 L0,80 Z"}
                    fill="var(--brand-soft)" stroke="none"/>
              <path d={"M0," + (60 - tput[0]*48) + " " + tput.map((v,i) => "L" + (i*10) + "," + (60 - v*48)).join(" ")}
                    fill="none" stroke="var(--brand)" strokeWidth="1.5"/>
            </svg>
            <div style={{display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--ink-3)", marginTop: 4}}>
              <span className="mono">−60s</span>
              <span className="mono"><b style={{color:"var(--ink)"}}>4 864</b> {L.samplesIn}</span>
              <span className="mono">now</span>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><span>Configuration</span></div>
          <div style={{padding: 16, fontSize: 12.5, display: "flex", flexDirection: "column", gap: 12}}>
            {[
              ["Driver", "g.NEEDaccess 1.18.04"],
              ["Sampling rate", "256 Hz"],
              ["Reference", "Cz (mastoid avg available)"],
              ["Notch filter", "50 Hz · IIR-4"],
              ["Bandpass", "0.5 – 45 Hz"],
              ["Buffer size", "256 samples (1.0 s)"],
              ["LSL stream name", "EEG-HIamp-4421"],
            ].map(([l,v]) => (
              <div key={l} style={{display: "grid", gridTemplateColumns: "130px 1fr", gap: 12}}>
                <span style={{color:"var(--ink-3)"}}>{l}</span>
                <span className="mono" style={{color:"var(--ink)"}}>{v}</span>
              </div>
            ))}
          </div>
          <div style={{padding: "12px 16px", borderTop: "1px solid var(--line)", display: "flex", gap: 8, justifyContent: "flex-end"}}>
            <button className="btn" style={{fontSize: 11}}>{L.saveDefault}</button>
            <button className="btn btn-primary" style={{fontSize: 11}}>{L.proceed}</button>
          </div>
        </div>
      </div>
    </div>
  );
};
