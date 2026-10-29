// Dashboard / Patient / Alerts / Device / Setup screens (compact)
const { useMemo: useM_a, useState: useS_a } = React;

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.DashboardScreen = function DashboardScreen({frame, t, lang, channels, animated}) {
  // Live dashboard summary from /api/dashboard/summary, refreshed every 5s.
  // If the endpoint is unreachable, the dashboard stays empty/waiting.
  const [refreshTick, setRefreshTick] = React.useState(0);
  const summaryState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/dashboard/summary"), [refreshTick], 5000)
    : {data: null, error: null, loading: true};
  const apiData = summaryState.data;
  const [showNewPatient, setShowNewPatient] = React.useState(false);
  const [currentAnalysis, setCurrentAnalysis] = React.useState(() => {
    try { return JSON.parse(sessionStorage.getItem("neuratriage_current_dataset_analysis") || "null"); } catch (e) { return null; }
  });

  React.useEffect(() => {
    const onAnalysis = () => {
      try { setCurrentAnalysis(JSON.parse(sessionStorage.getItem("neuratriage_current_dataset_analysis") || "null")); } catch (e) { setCurrentAnalysis(null); }
      setRefreshTick(v => v + 1);
    };
    window.addEventListener("nt:analysis-created", onAnalysis);
    window.addEventListener("nt:analysis-cleared", onAnalysis);
    return () => {
      window.removeEventListener("nt:analysis-created", onAnalysis);
      window.removeEventListener("nt:analysis-cleared", onAnalysis);
    };
  }, []);

  function initialsOf(name) {
    if (!name) return "—";
    const parts = name.trim().split(/\s+/);
    return ((parts[0]?.[0] || "") + (parts[parts.length - 1]?.[0] || "")).toUpperCase();
  }
  function fmtDurationSeconds(sec) {
    if (sec == null || !Number.isFinite(Number(sec))) return "—";
    const total = Math.max(0, Math.round(Number(sec)));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  const liveBeds = (apiData && Array.isArray(apiData.beds)) ? apiData.beds.map(b => ({
    bed: b.bed || (b.session_id ? `WS-${String(b.session_id).slice(0, 4).toUpperCase()}` : "—"),
    patient: b.patient_name || "Unassigned stream",
    initials: initialsOf(b.patient_name),
    age: null,
    mode: b.dominant || "NS",
    prob: typeof b.prob === "number" ? b.prob : 0.33,
    dur: b.duration || "00:00:00",
    sqi: typeof b.sqi === "number" ? b.sqi : null,
    sessionId: b.session_id,
    patient_id: b.patient_id,
    status: b.status,
    alertCount: b.alert_count || 0,
    unassigned: !b.patient_id,
  })) : [];

  function modeFromAnalysis(a) {
    const cls = String(a?.overall?.pred_class || "").toLowerCase().replace(/[_\s]+/g, "-");
    if (["ischemic", "is", "1"].includes(cls)) return "IS";
    if (["non-stroke", "nonstroke", "ns", "normal", "0"].includes(cls)) return "NS";
    const overall = a?.overall || {};
    const probs = {
      NS: Number(overall.p_nonstroke || 0),
      IS: Number(overall.p_ischemic || 0),
    };
    return Number(probs.IS || 0) >= Number(probs.NS || 0) ? "IS" : "NS";
  }
  function probFromAnalysis(a, mode) {
    const overall = a?.overall || {};
    if (mode === "IS") return Number(overall.p_ischemic || 0);
    return Number(overall.p_nonstroke || 0);
  }
  const analysisBeds = currentAnalysis?.overall ? (() => {
    const mode = modeFromAnalysis(currentAnalysis);
    return [{
      bed: currentAnalysis.bed || "OFFLINE",
      patient: currentAnalysis.patient_name || currentAnalysis.source_file || "Imported EEG",
      initials: initialsOf(currentAnalysis.patient_name),
      age: null,
      mode,
      prob: probFromAnalysis(currentAnalysis, mode),
      dur: `${currentAnalysis.windows || 0} windows`,
      sqi: typeof currentAnalysis.overall.sqi === "number" ? currentAnalysis.overall.sqi : null,
      sessionId: null,
      patient_id: currentAnalysis.patient_id,
      status: "offline-analysis",
      alertCount: 0,
      sourceFile: currentAnalysis.source_file,
      channelCount: currentAnalysis.source?.channel_count,
      fs: currentAnalysis.source?.fs,
      durationSec: currentAnalysis.source?.duration_sec,
    }];
  })() : [];
  const analysisPatientIds = new Set(analysisBeds.map(b => b.patient_id).filter(Boolean));
  const beds = analysisBeds.concat(liveBeds.filter(b => !analysisPatientIds.has(b.patient_id)));
  const liveActive = apiData ? apiData.active_session_count : 0;
  const alertsToday = apiData ? apiData.alerts_today : 0;
  const byClass = (apiData && apiData.alerts_by_class) || {};
  const summary = {
    NS: byClass["non-stroke"] || 0,
    IS: byClass["ischemic"] || 0,
  };
  const dataMode = apiData ? "BACKEND" : (summaryState.loading ? "LOADING" : "OFFLINE");

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      {/* KPI row */}
      <div className="nt-kpi-grid">
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{display:"flex", justifyContent:"space-between"}}>
            <span>{lang==="vi"?"Phiên đang chạy":"Active sessions"}</span>
            <span className="mono" style={{fontSize:9, color:dataMode==="BACKEND"?"var(--ns)":"var(--ink-3)", letterSpacing:"0.08em"}}>{dataMode}</span>
          </div>
          <div className="stat-val">{liveActive}<span className="unit">{lang==="vi"?"giường":"beds"}</span></div>
          <div className="stat-sub" style={{display:"flex", gap:10, marginTop:10, fontFamily:"var(--font-mono)"}}>
            <span title={lang==="vi"?"Cảnh báo NS hôm nay":"NS alerts today"}><span className="dot ns"/> {summary.NS}</span>
            <span style={{marginLeft:6}} title={lang==="vi"?"Cảnh báo IS hôm nay":"IS alerts today"}><span className="dot is"/> {summary.IS}</span>
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Cảnh báo hôm nay":"Alerts today"}</div>
          <div className="stat-val">{alertsToday}</div>
          <div className="stat-sub" style={{color:apiData && apiData.open_alerts > 0 ? "var(--hs)" : "var(--ink-3)"}}>
            {apiData ? `${apiData.open_alerts || 0} ${lang==="vi"?"đang mở":"open"}` : (lang==="vi"?"đang chờ dữ liệu":"awaiting data")}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Thời gian đến quyết định":"Median time-to-decision"}</div>
          <div className="stat-val">{fmtDurationSeconds(apiData?.median_time_to_decision_sec)}</div>
          <div className="stat-sub">{lang==="vi"?"từ cảnh báo đến ack":"from alert to ack"}</div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Bằng chứng mô hình":"Model evidence"}</div>
          <div className="stat-val">R&D</div>
          <div className="stat-sub">{lang==="vi"?"xem Insights - không claim lâm sàng":"see Insights - no clinical claim"}</div>
        </div>
      </div>

      {/* Bed grid */}
      <div className="panel" style={{padding:0}}>
        <div className="panel-header">
          <div className="title"><window.NTIcon name="dashboard" size={13} color="var(--brand-2)"/><span>{lang==="vi"?"Giường đang theo dõi":"All monitored beds"}</span></div>
          <div style={{display:"flex", gap:8}}>
            <button className="btn btn-sm btn-ghost"><window.NTIcon name="filter" size={12}/>{t.actions.filter}</button>
            <button className="btn btn-sm btn-primary" onClick={() => setShowNewPatient(true)}>
              <window.NTIcon name="plus" size={12}/>{lang==="vi"?"Bệnh nhân mới":"New patient"}
            </button>
          </div>
        </div>
        {beds.length === 0 ? (
          <div style={{padding:28, display:"grid", placeItems:"center", minHeight:240, background:"var(--bg-2)"}}>
            <div style={{maxWidth:460, textAlign:"center"}}>
              <div style={{width:54, height:54, borderRadius:10, border:"1px solid var(--line-2)", background:"var(--bg-3)", display:"grid", placeItems:"center", margin:"0 auto 14px", color:"var(--brand-2)"}}>
                <window.NTIcon name="dashboard" size={22}/>
              </div>
              <div style={{fontSize:17, fontWeight:650, marginBottom:8}}>{lang==="vi"?"Chưa có phiên đang chạy":"No active sessions"}</div>
              <div style={{fontSize:12.5, color:"var(--ink-3)", lineHeight:1.55, marginBottom:16}}>
                {lang==="vi"
                  ? "Backend hiện không có bed/session active. Hãy kết nối thiết bị, chạy replay, hoặc tạo bệnh nhân trước khi dashboard hiển thị dữ liệu."
                  : "The backend currently has no active bed/session. Connect a device, run a replay, or create a patient to populate the dashboard."}
              </div>
              <div style={{display:"flex", gap:8, justifyContent:"center", flexWrap:"wrap"}}>
                <button className="btn btn-sm" onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"device"}}))}>
                  <window.NTIcon name="device" size={12}/>{lang==="vi"?"Kết nối thiết bị":"Connect device"}
                </button>
                <button className="btn btn-sm" onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"setup"}}))}>
                  <window.NTIcon name="setup" size={12}/>{lang==="vi"?"Chạy replay":"Run replay"}
                </button>
                <button className="btn btn-sm btn-primary" onClick={() => setShowNewPatient(true)}>
                  <window.NTIcon name="plus" size={12}/>{lang==="vi"?"Tạo bệnh nhân":"Create patient"}
                </button>
              </div>
            </div>
          </div>
        ) : (
        <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(260px, 1fr))", gap:1, background:"var(--line)"}}>
          {beds.map((b, i) => {
            const accent = b.mode==="NS"?"var(--ns)":"var(--is)";
            return (
              <div key={i} style={{background:"var(--bg-2)", padding:16, position:"relative"}}>
                <div style={{position:"absolute", top:0, left:0, right:0, height:2, background:accent, opacity:0.5, boxShadow:`0 0 6px ${accent}`}}/>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:10}}>
                  <div>
                    <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", letterSpacing:"0.06em"}}>{b.bed}</div>
                    <div style={{fontSize:13, fontWeight:600, marginTop:3}}>{b.patient}</div>
                    <div style={{fontSize:11, color:"var(--ink-3)", marginTop:1}}>
                      {b.status === "offline-analysis"
                        ? `${b.dur} · ${b.channelCount || "?"}ch · ${b.fs || "?"}Hz`
                        : (b.age != null ? `${b.age}y · ${b.dur}` : b.dur)}
                    </div>
                  </div>
                  <span className={`tag ${b.mode.toLowerCase()}`}>{t.severityShort[b.mode]} · {(b.prob*100).toFixed(0)}%</span>
                </div>
                <div style={{height:34, marginTop:8, marginBottom:10}}>
                  {b.status === "offline-analysis" ? (
                    <div className="mono" style={{height:32, display:"flex", alignItems:"center", color:"var(--ink-3)", fontSize:10.5, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                      {b.sourceFile || (lang==="vi"?"Phân tích offline":"Offline analysis")}
                    </div>
                  ) : (
                    <div className="mono" style={{height:32, display:"flex", alignItems:"center", color:"var(--ink-3)", fontSize:10.5}}>
                      {lang==="vi"?"Trace realtime chưa có raw EEG":"Realtime trace waits for raw EEG"}
                    </div>
                  )}
                </div>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", fontSize:11}}>
                  {b.sqi == null ? (
                    <span className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>SQI pending / {b.alertCount} alerts</span>
                  ) : (
                    <window.SQIBar value={b.sqi} width={90}/>
                  )}
                  <button className="btn btn-sm btn-ghost" style={{padding:"3px 6px", fontSize:11}}
                          onClick={() => {
                            try {
                              if (b.sessionId) localStorage.setItem("neuratriage_selected_session_id", b.sessionId);
                              if (b.patient_id) localStorage.setItem("neuratriage_selected_patient_id", b.patient_id);
                            } catch (e) {}
                            if (b.patient_id) window.dispatchEvent(new CustomEvent("nt:patient-select", {detail:{patientId:b.patient_id}}));
                            window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"patient"}}));
                          }}>{t.actions.seeDetail} -></button>
                </div>
              </div>
            );
          })}
        </div>
        )}
      </div>
      {showNewPatient && (
        <window.NewPatientDialog
          lang={lang}
          onClose={() => setShowNewPatient(false)}
          onCreated={() => { setShowNewPatient(false); setRefreshTick(v => v + 1); }}
        />
      )}
    </div>
  );
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Modal: create a new patient (POST /api/patients).
window.NewPatientDialog = function NewPatientDialog({lang, onClose, onCreated}) {
  const [form, setForm] = React.useState({
    full_name: "",
    mrn: "",
    bed: "",
    gender: "",
    onset_minutes: "",
    chief_complaint: "",
    symptoms: "",
    medical_history: "",
    medications: "",
    allergies: "",
    blood_pressure: "",
    heart_rate: "",
    spo2: "",
    temperature: "",
    glucose: "",
    nihss: "",
    notes: "",
  });
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  function set(k, v) { setForm(s => ({...s, [k]: v})); }

  async function submit(e) {
    e.preventDefault();
    setError(null);
    if (!form.full_name.trim()) { setError(lang==="vi"?"Tên không được trống":"Name required"); return; }
    setSubmitting(true);
    try {
      const body = {
        full_name: form.full_name.trim(),
        mrn: form.mrn.trim() || null,
        bed: form.bed.trim() || null,
        gender: form.gender || null,
        onset_minutes: form.onset_minutes ? parseInt(form.onset_minutes, 10) : null,
        diagnosis_history: {
          chief_complaint: form.chief_complaint.trim() || null,
          symptoms: form.symptoms.trim() || null,
          medical_history: form.medical_history.trim() || null,
          medications: form.medications.trim() || null,
          allergies: form.allergies.trim() || null,
          vitals: {
            blood_pressure: form.blood_pressure.trim() || null,
            heart_rate: form.heart_rate ? Number(form.heart_rate) : null,
            spo2: form.spo2 ? Number(form.spo2) : null,
            temperature: form.temperature ? Number(form.temperature) : null,
            glucose: form.glucose ? Number(form.glucose) : null,
          },
          nihss: form.nihss ? Number(form.nihss) : null,
        },
        notes: form.notes.trim() || null,
      };
      await window.NTApi.post("/api/patients", body);
      onCreated && onCreated();
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const L = lang==="vi";
  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"rgba(8,12,18,0.65)", backdropFilter:"blur(2px)",
      display:"grid", placeItems:"center", zIndex:200,
    }}>
      <form onClick={e => e.stopPropagation()} onSubmit={submit} style={{
        background:"var(--bg-2)", borderRadius:12, border:"1px solid var(--line-2)",
        width:"min(720px, calc(100% - 32px))", maxHeight:"calc(100vh - 36px)", overflowY:"auto", padding:22, boxShadow:"0 20px 60px rgba(0,0,0,0.4)",
      }}>
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:18}}>
          <div style={{fontSize:15, fontWeight:600}}>{L?"Thêm bệnh nhân":"Add patient"}</div>
          <button type="button" onClick={onClose} className="btn btn-sm btn-ghost" style={{fontSize:11}}>{L?"Đóng":"Close"}</button>
        </div>
        <div style={{display:"grid", gap:14}}>
          <label style={{display:"grid", gap:5, fontSize:12}}>
            <span style={{color:"var(--ink-3)"}}>{L?"Họ tên *":"Full name *"}</span>
            <input value={form.full_name} onChange={e => set("full_name", e.target.value)} placeholder="Nguyen Van A" autoFocus/>
          </label>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>MRN</span>
              <input value={form.mrn} onChange={e => set("mrn", e.target.value)} placeholder="MRN-2026-XXXXX"/>
            </label>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Giường":"Bed"}</span>
              <input value={form.bed} onChange={e => set("bed", e.target.value)} placeholder="ED-04"/>
            </label>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Giới tính":"Gender"}</span>
              <select value={form.gender} onChange={e => set("gender", e.target.value)}>
                <option value="">{L?"-- chọn --":"-- select --"}</option>
                <option value="M">{L?"Nam":"Male"}</option>
                <option value="F">{L?"Nữ":"Female"}</option>
                <option value="O">{L?"Khác":"Other"}</option>
              </select>
            </label>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Onset (phút trước)":"Onset (min ago)"}</span>
              <input type="number" min="0" value={form.onset_minutes} onChange={e => set("onset_minutes", e.target.value)} placeholder="42"/>
            </label>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Lý do vào viện":"Chief complaint"}</span>
              <input value={form.chief_complaint} onChange={e => set("chief_complaint", e.target.value)} placeholder={L?"Yếu nửa người phải":"Right-sided weakness"}/>
            </label>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Triệu chứng":"Symptoms"}</span>
              <input value={form.symptoms} onChange={e => set("symptoms", e.target.value)} placeholder={L?"Nói khó, méo miệng":"Dysarthria, facial droop"}/>
            </label>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Tiền sử bệnh":"Medical history"}</span>
              <input value={form.medical_history} onChange={e => set("medical_history", e.target.value)} placeholder={L?"Tăng huyết áp, ĐTĐ":"HTN, diabetes"}/>
            </label>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Thuốc đang dùng":"Medications"}</span>
              <input value={form.medications} onChange={e => set("medications", e.target.value)} placeholder="Aspirin, statin"/>
            </label>
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:10}}>
            {[
              [L?"HA":"BP", "blood_pressure", L?"Nhập nếu có":"Optional"],
              ["HR", "heart_rate", L?"Nhập nếu có":"Optional"],
              ["SpO2", "spo2", L?"Nhập nếu có":"Optional"],
              [L?"Nhiệt độ":"Temp", "temperature", L?"Nhập nếu có":"Optional"],
              [L?"Đường huyết":"Glucose", "glucose", L?"Nhập nếu có":"Optional"],
              ["NIHSS", "nihss", L?"Nhập nếu có":"Optional"],
            ].map(([label, key, ph]) => (
              <label key={key} style={{display:"grid", gap:5, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{label}</span>
                <input value={form[key]} onChange={e => set(key, e.target.value)} placeholder={ph}/>
              </label>
            ))}
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:14}}>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Dị ứng":"Allergies"}</span>
              <input value={form.allergies} onChange={e => set("allergies", e.target.value)} placeholder={L?"Không ghi nhận":"NKDA"}/>
            </label>
            <label style={{display:"grid", gap:5, fontSize:12}}>
              <span style={{color:"var(--ink-3)"}}>{L?"Ghi chú":"Notes"}</span>
              <input value={form.notes} onChange={e => set("notes", e.target.value)} placeholder={L?"Ghi chú thêm":"Additional notes"}/>
            </label>
          </div>
        </div>
        {error && (
          <div style={{marginTop:14, padding:10, background:"var(--bg-3)", borderLeft:"3px solid var(--hs)", borderRadius:6, fontSize:12, color:"var(--ink)"}}>
            <strong style={{color:"var(--hs)"}}>{L?"Lỗi:":"Error:"}</strong> {error}
          </div>
        )}
        <div style={{display:"flex", justifyContent:"flex-end", gap:10, marginTop:20}}>
          <button type="button" onClick={onClose} className="btn btn-sm btn-ghost" disabled={submitting}>{L?"Hủy":"Cancel"}</button>
          <button type="submit" className="btn btn-sm btn-primary" disabled={submitting}>
            {submitting ? (L?"Đang lưu...":"Saving...") : (L?"Lưu":"Save")}
          </button>
        </div>
      </form>
    </div>
  );
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.PatientScreen = function PatientScreen({frame, t, lang}) {
  const [patRefresh, setPatRefresh] = React.useState(0);
  // Pull live patient list from backend; show selector when â‰¥1 patient.
  const patientsState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/patients"), [patRefresh], 15000)
    : {data: null, loading: true, error: null};
  const dbPatients = patientsState.data || [];
  const [selectedId, setSelectedId] = React.useState(() => {
    try { return localStorage.getItem("neuratriage_selected_patient_id") || ""; } catch (e) { return ""; }
  });
  const [editOpen, setEditOpen] = React.useState(false);
  const [editForm, setEditForm] = React.useState({});
  const [editSaving, setEditSaving] = React.useState(false);
  const [deleteConfirm, setDeleteConfirm] = React.useState(false);
  const [deleteLoading, setDeleteLoading] = React.useState(false);
  const [patientNotice, setPatientNotice] = React.useState(null);
  const [contactForm, setContactForm] = React.useState({name:"", relationship_label:"", phone:"", email:"", notify_on_alert:true, notify_weekly_report:true});
  const [contactBusy, setContactBusy] = React.useState(false);
  const [showContactForm, setShowContactForm] = React.useState(false);
  const [showNewPatient, setShowNewPatient] = React.useState(false);

  React.useEffect(() => {
    const onAnalysis = (e) => {
      if (e.detail?.patientId) setSelectedId(e.detail.patientId);
      setPatRefresh(v => v + 1);
    };
    window.addEventListener("nt:analysis-created", onAnalysis);
    return () => window.removeEventListener("nt:analysis-created", onAnalysis);
  }, []);

  React.useEffect(() => {
    if (dbPatients.length === 0) return;
    if (selectedId && dbPatients.some(p => p.id === selectedId)) return;
    setSelectedId(dbPatients[0].id);
  }, [dbPatients]);

  // Persist selection so dashboard "see detail" â†’ patient flow survives refresh.
  React.useEffect(() => {
    if (selectedId) {
      try { localStorage.setItem("neuratriage_selected_patient_id", selectedId); } catch (e) {}
      window.dispatchEvent(new CustomEvent("nt:patient-select", {detail:{patientId:selectedId}}));
    }
  }, [selectedId]);

  const dbPatient = dbPatients.find(p => p.id === selectedId);

  // Fetch real alert history for selected patient
  const patAlertsState = window.NTApi
    ? window.NTApi.useApi(
        () => selectedId
          ? window.NTApi.get(`/api/alerts?patient_id=${selectedId}&since_hours=720&limit=50`)
          : Promise.resolve([]),
        [selectedId, patRefresh], 30000)
    : {data: null};
  const patAlerts = patAlertsState.data || null;

  function openEdit() {
    if (!dbPatient) return;
    const dx = dbPatient.diagnosis_history || {};
    const vitals = dx.vitals || {};
    setPatientNotice(null);
    setEditForm({
      full_name: dbPatient.full_name || "",
      mrn: dbPatient.mrn || "",
      bed: dbPatient.bed || "",
      gender: dbPatient.gender || "",
      onset_minutes: dbPatient.onset_minutes != null ? String(dbPatient.onset_minutes) : "",
      chief_complaint: dx.chief_complaint || "",
      symptoms: dx.symptoms || "",
      medical_history: dx.medical_history || "",
      medications: dx.medications || "",
      allergies: dx.allergies || "",
      blood_pressure: vitals.blood_pressure || "",
      heart_rate: vitals.heart_rate != null ? String(vitals.heart_rate) : "",
      spo2: vitals.spo2 != null ? String(vitals.spo2) : "",
      temperature: vitals.temperature != null ? String(vitals.temperature) : "",
      glucose: vitals.glucose != null ? String(vitals.glucose) : "",
      nihss: dx.nihss != null ? String(dx.nihss) : "",
      notes: dbPatient.notes || "",
    });
    setEditOpen(true);
  }
  async function saveEdit() {
    if (!selectedId) return;
    setEditSaving(true);
    try {
      await window.NTApi.put(`/api/patients/${selectedId}`, {
        full_name: editForm.full_name,
        mrn: editForm.mrn || null,
        bed: editForm.bed || null,
        gender: editForm.gender || null,
        onset_minutes: editForm.onset_minutes ? parseInt(editForm.onset_minutes) : null,
        diagnosis_history: {
          chief_complaint: editForm.chief_complaint || null,
          symptoms: editForm.symptoms || null,
          medical_history: editForm.medical_history || null,
          medications: editForm.medications || null,
          allergies: editForm.allergies || null,
          vitals: {
            blood_pressure: editForm.blood_pressure || null,
            heart_rate: editForm.heart_rate ? Number(editForm.heart_rate) : null,
            spo2: editForm.spo2 ? Number(editForm.spo2) : null,
            temperature: editForm.temperature ? Number(editForm.temperature) : null,
            glucose: editForm.glucose ? Number(editForm.glucose) : null,
          },
          nihss: editForm.nihss ? Number(editForm.nihss) : null,
        },
        notes: editForm.notes || null,
      });
      setEditOpen(false);
      setPatRefresh(v => v + 1);
      setPatientNotice({type:"ok", text: lang==="vi"?"Đã lưu bệnh nhân.":"Patient saved."});
      patientsState.refresh && patientsState.refresh();
    } catch (e) {
      setPatientNotice({type:"error", text:e.message || "Save failed"});
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setDeleteLoading(true);
    try {
      await window.NTApi.del(`/api/patients/${selectedId}`);
      setDeleteConfirm(false);
      setSelectedId("");
      try { localStorage.removeItem("neuratriage_selected_patient_id"); } catch (e) {}
      setPatientNotice({type:"ok", text: lang==="vi"?"Đã xóa bệnh nhân.":"Patient deleted."});
      patientsState.refresh && patientsState.refresh();
    } catch (e) {
      setPatientNotice({type:"error", text:e.message || "Delete failed"});
    } finally {
      setDeleteLoading(false);
    }
  }

  async function addContact() {
    if (!selectedId) return;
    if (!contactForm.name.trim()) {
      setPatientNotice({type:"error", text: lang==="vi"?"Tên người liên hệ không được trống":"Contact name required"});
      return;
    }
    setContactBusy(true);
    setPatientNotice(null);
    try {
      await window.NTApi.post(`/api/patients/${selectedId}/contacts`, {
        name: contactForm.name.trim(),
        relationship_label: contactForm.relationship_label.trim() || null,
        phone: contactForm.phone.trim() || null,
        email: contactForm.email.trim() || null,
        notify_on_alert: !!contactForm.notify_on_alert,
        notify_weekly_report: !!contactForm.notify_weekly_report,
      });
      setContactForm({name:"", relationship_label:"", phone:"", email:"", notify_on_alert:true, notify_weekly_report:true});
      setShowContactForm(false);
      setPatRefresh(v => v + 1);
      setPatientNotice({type:"ok", text: lang==="vi"?"Đã thêm người liên hệ.":"Contact added."});
    } catch (e) {
      setPatientNotice({type:"error", text: e.message || "Add contact failed"});
    } finally {
      setContactBusy(false);
    }
  }

  async function deleteContact(contactId) {
    if (!selectedId || !contactId) return;
    setContactBusy(true);
    setPatientNotice(null);
    try {
      await window.NTApi.del(`/api/patients/${selectedId}/contacts/${contactId}`);
      setPatRefresh(v => v + 1);
      setPatientNotice({type:"ok", text: lang==="vi"?"Đã xóa người liên hệ.":"Contact removed."});
    } catch (e) {
      setPatientNotice({type:"error", text: e.message || "Delete contact failed"});
    } finally {
      setContactBusy(false);
    }
  }

  function initialsOf(name) {
    if (!name) return "—";
    const parts = name.trim().split(/\s+/);
    return ((parts[0]?.[0] || "") + (parts[parts.length - 1]?.[0] || "")).toUpperCase();
  }
  function ageFrom(dob) {
    if (!dob) return "—";
    try {
      const d = new Date(dob);
      const ms = Date.now() - d.getTime();
      return Math.max(0, Math.floor(ms / (365.25 * 24 * 3600 * 1000))) + "y";
    } catch (e) { return "—"; }
  }

  // Patient information must come from an entered patient record, not the demo live frame.
  const dispName = dbPatient ? dbPatient.full_name : (lang==="vi"?"Chưa chọn bệnh nhân":"No patient selected");
  const dispMrn = dbPatient ? (dbPatient.mrn || "—") : "—";
  const dispBed = dbPatient ? (dbPatient.bed || "—") : "—";
  const dispGender = dbPatient ? dbPatient.gender : "";
  const dispAge = dbPatient ? ageFrom(dbPatient.date_of_birth) : "—";
  const dispOnset = dbPatient && dbPatient.onset_minutes != null ? `${dbPatient.onset_minutes} ${t.live.minsAgo}` : "—";
  const dispInitials = dbPatient ? initialsOf(dbPatient.full_name) : "—";
  const dxDisplay = (dbPatient && dbPatient.diagnosis_history) || {};
  const vitalDisplay = dxDisplay.vitals || {};
  function displayModeFromEeg(a) {
    const cls = String(a?.overall?.pred_class || "").toLowerCase().replace(/[_\s]+/g, "-");
    if (["ischemic", "is", "1"].includes(cls)) return "IS";
    if (["non-stroke", "nonstroke", "ns", "normal", "0"].includes(cls)) return "NS";
    const overall = a?.overall || {};
    const probs = {
      NS: Number(overall.p_nonstroke || 0),
      IS: Number(overall.p_ischemic || 0),
    };
    return Number(probs.IS || 0) >= Number(probs.NS || 0) ? "IS" : "NS";
  }
  const vitalRows = [
    ["BP", vitalDisplay.blood_pressure],
    ["HR", vitalDisplay.heart_rate != null && vitalDisplay.heart_rate !== "" ? `${vitalDisplay.heart_rate} bpm` : null],
    ["SpO2", vitalDisplay.spo2 != null && vitalDisplay.spo2 !== "" ? `${vitalDisplay.spo2}%` : null],
    ["Temp", vitalDisplay.temperature != null && vitalDisplay.temperature !== "" ? `${vitalDisplay.temperature} C` : null],
    ["Glucose", vitalDisplay.glucose != null && vitalDisplay.glucose !== "" ? String(vitalDisplay.glucose) : null],
  ].filter(([,v]) => v != null && v !== "");

  return (
    <div className="nt-patient-layout" style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      {patientNotice && (
        <div style={{gridColumn:"1 / -1", padding:"9px 11px", borderRadius:7, border:"1px solid var(--line-2)", background:"var(--bg-3)", color:patientNotice.type==="error"?"var(--hs)":"var(--ns)", fontSize:12}}>
          {patientNotice.text}
        </div>
      )}
      <div className="panel" style={{padding:18}}>
        <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14}}>
          <div className="stat-lbl">{lang==="vi"?"Bệnh nhân":"Patient"}</div>
          <button className="btn btn-sm btn-primary" onClick={() => setShowNewPatient(true)}>
            <window.NTIcon name="plus" size={11}/>{lang==="vi"?"Bệnh nhân mới":"New patient"}
          </button>
        </div>
        {dbPatients.length === 0 && !patientsState.loading && (
          <div style={{padding:"20px 16px", textAlign:"center", border:"1px dashed var(--line-2)", borderRadius:8, background:"var(--bg-3)"}}>
            <div style={{fontSize:13.5, fontWeight:600, marginBottom:6}}>{lang==="vi"?"Chưa có bệnh nhân nào":"No patients yet"}</div>
            <div style={{fontSize:12, color:"var(--ink-3)", lineHeight:1.5, marginBottom:14}}>
              {lang==="vi"
                ? "Tạo hồ sơ bệnh nhân để gán phiên EEG, xem cảnh báo và gửi báo cáo. Hoặc phân tích 1 file EEG ở tab Nhập liệu — hệ thống sẽ tự tạo bệnh nhân."
                : "Create a patient record to attach EEG sessions, view alerts, and send reports. Or analyse an EEG file in the Setup tab — a patient is created automatically."}
            </div>
            <div style={{display:"flex", gap:8, justifyContent:"center", flexWrap:"wrap"}}>
              <button className="btn btn-sm btn-primary" onClick={() => setShowNewPatient(true)}>
                <window.NTIcon name="plus" size={12}/>{lang==="vi"?"Tạo bệnh nhân":"Create patient"}
              </button>
              <button className="btn btn-sm" onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"setup"}}))}>
                <window.NTIcon name="setup" size={12}/>{lang==="vi"?"Phân tích file EEG":"Analyse EEG file"}
              </button>
            </div>
          </div>
        )}
        {dbPatients.length > 0 && (
          <div style={{marginBottom:14}}>
            <div style={{fontSize:10, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:6}}>
              {lang==="vi"?"Chọn bệnh nhân":"Select patient"}
            </div>
            <select value={selectedId} onChange={e => setSelectedId(e.target.value)} style={{width:"100%"}}>
              {dbPatients.map(p => (
                <option key={p.id} value={p.id}>
                  {p.full_name}{p.bed ? ` · ${p.bed}` : ""}{p.mrn ? ` · ${p.mrn}` : ""}
                </option>
              ))}
            </select>
          </div>
        )}
        {dbPatient && (<React.Fragment>
        <div style={{display:"flex", alignItems:"center", gap:14, marginBottom:18, paddingBottom:18, borderBottom:"1px solid var(--line)"}}>
          <div style={{
            width:60, height:60, borderRadius:"50%",
            background:"linear-gradient(135deg, var(--brand-2), var(--brand-3))",
            display:"grid", placeItems:"center", color:"#fff", fontFamily:"var(--font-mono)", fontWeight:600, fontSize:18,
          }}>{dispInitials}</div>
          <div>
            <div style={{fontSize:16, fontWeight:600}}>{dispName}</div>
            <div className="mono" style={{fontSize:11.5, color:"var(--ink-3)", marginTop:3}}>{dispMrn}</div>
            <div className="mono" style={{fontSize:9, color:dbPatient?"var(--ns)":"var(--ink-3)", marginTop:4, letterSpacing:"0.08em"}}>
              {dbPatient ? "BACKEND" : (lang==="vi"?"CHƯA NHẬP":"NO RECORD")}
            </div>
          </div>
          {dbPatient && (
            <div style={{marginLeft:"auto", display:"flex", flexDirection:"column", gap:4, alignSelf:"flex-start"}}>
              <button className="btn btn-sm btn-ghost" onClick={openEdit}>
                <window.NTIcon name="setup" size={11}/>{lang==="vi"?"Sửa":"Edit"}
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(true)}
                style={{color:"var(--hs)", borderColor:"var(--hs)", opacity:0.8}}>
                {lang==="vi"?"Xóa":"Delete"}
              </button>
            </div>
          )}
        </div>
        <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, fontSize:12.5}}>
          {[
            [t.live.age, dispAge],
            [t.live.sex, dispGender==="M" ? t.live.male : dispGender==="F" ? t.live.female : (dispGender || "—")],
            [lang==="vi"?"Giường":"Bed", dispBed],
            [t.live.onsetSymptoms, dispOnset],
          ].map(([k, v], i) => (
            <div key={i}>
              <div style={{fontSize:10, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:4}}>{k}</div>
              <div style={{color:"var(--ink)"}} className="mono">{v}</div>
            </div>
          ))}
        </div>
        </React.Fragment>)}
        {vitalRows.length > 0 && (
        <div style={{marginTop:18, paddingTop:18, borderTop:"1px solid var(--line)"}}>
          <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"Sinh hiệu đã nhập":"Entered vitals"}</div>
          {vitalRows.map(([k, v], i) => (
            <div key={i} style={{display:"grid", gridTemplateColumns:"90px 1fr", alignItems:"center", padding:"7px 0", borderBottom:i===vitalRows.length-1?"none":"1px solid var(--line)", fontSize:12}}>
              <span className="mono" style={{color:"var(--ink-3)"}}>{k}</span>
              <span className="mono" style={{textAlign:"right", color:"var(--ink)"}}>{v}</span>
            </div>
          ))}
        </div>
        )}
        {(dxDisplay.chief_complaint || dxDisplay.symptoms || dxDisplay.medical_history || dxDisplay.medications || dxDisplay.allergies || dxDisplay.nihss != null) && (
          <div style={{marginTop:18, paddingTop:18, borderTop:"1px solid var(--line)"}}>
            <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"Thông tin y tế":"Medical information"}</div>
            {[
              [lang==="vi"?"Lý do vào viện":"Chief complaint", dxDisplay.chief_complaint],
              [lang==="vi"?"Triệu chứng":"Symptoms", dxDisplay.symptoms],
              [lang==="vi"?"Tiền sử":"History", dxDisplay.medical_history],
              [lang==="vi"?"Thuốc":"Medications", dxDisplay.medications],
              [lang==="vi"?"Dị ứng":"Allergies", dxDisplay.allergies],
              ["NIHSS", dxDisplay.nihss],
            ].filter(([,v]) => v).map(([k, v]) => (
              <div key={k} style={{display:"grid", gridTemplateColumns:"120px 1fr", gap:10, padding:"5px 0", fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{k}</span>
                <span style={{color:"var(--ink)"}}>{v}</span>
              </div>
            ))}
          </div>
        )}
        {dxDisplay.eeg_analysis && (
          <div style={{marginTop:18, paddingTop:18, borderTop:"1px solid var(--line)"}}>
            <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"Kết quả EEG đã phân tích":"Analysed EEG result"}</div>
            {[
              [lang==="vi"?"File":"File", dxDisplay.eeg_analysis.source_file],
              [lang==="vi"?"Kênh đo":"Measured channels", dxDisplay.eeg_analysis.source?.channel_count],
              ["Fs", dxDisplay.eeg_analysis.source?.fs != null ? `${dxDisplay.eeg_analysis.source.fs} Hz` : null],
              [lang==="vi"?"Thời lượng":"Duration", dxDisplay.eeg_analysis.source?.duration_sec != null ? `${Number(dxDisplay.eeg_analysis.source.duration_sec).toFixed(1)} s` : null],
              [lang==="vi"?"Đoạn phân tích":"Analysed segment", dxDisplay.eeg_analysis.source?.analysis_duration_sec != null ? `${Number(dxDisplay.eeg_analysis.source.analysis_duration_sec).toFixed(1)} s` : null],
              [lang==="vi"?"Cửa sổ":"Windows", dxDisplay.eeg_analysis.windows],
              ["SQI", dxDisplay.eeg_analysis.overall?.sqi != null ? Number(dxDisplay.eeg_analysis.overall.sqi).toFixed(3) : null],
              [lang==="vi"?"Model nghiêng về":"Model output", displayModeFromEeg(dxDisplay.eeg_analysis)],
              ["NS", dxDisplay.eeg_analysis.overall?.p_nonstroke != null ? `${(dxDisplay.eeg_analysis.overall.p_nonstroke * 100).toFixed(1)}%` : null],
              ["IS", dxDisplay.eeg_analysis.overall?.p_ischemic != null ? `${(dxDisplay.eeg_analysis.overall.p_ischemic * 100).toFixed(1)}%` : null],
            ].filter(([,v]) => v != null && v !== "").map(([k, v]) => (
              <div key={k} style={{display:"grid", gridTemplateColumns:"120px 1fr", gap:10, padding:"5px 0", fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{k}</span>
                <span className="mono" style={{color:"var(--ink)"}}>{String(v)}</span>
              </div>
            ))}
            <div style={{fontSize:10.5, color:"var(--ink-4)", lineHeight:1.45, marginTop:8}}>
              {lang==="vi"?"Kết quả này đến từ file phân tích offline, không phải phiên realtime.":"This result comes from an offline analysed file, not a realtime session."}
            </div>
          </div>
        )}
        {dbPatient && (
          <div style={{marginTop:18, paddingTop:18, borderTop:"1px solid var(--line)"}}>
            <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8}}>
              <div className="stat-lbl">{lang==="vi"?"Người liên hệ khẩn cấp":"Emergency contacts"}</div>
              <button className="btn btn-sm btn-ghost" onClick={() => setShowContactForm(v => !v)}>
                <window.NTIcon name="plus" size={11}/>{showContactForm ? (lang==="vi"?"Đóng":"Close") : (lang==="vi"?"Thêm":"Add")}
              </button>
            </div>
            <div style={{fontSize:11, color:"var(--ink-3)", lineHeight:1.5, marginBottom:10}}>
              {lang==="vi"
                ? "Email bật \"Báo cáo tuần\" sẽ nhận PDF báo cáo tự động qua SendGrid."
                : "Emails with \"Weekly report\" on receive the automated PDF via SendGrid."}
            </div>
            {(dbPatient.contacts || []).length === 0 && !showContactForm && (
              <div style={{fontSize:12, color:"var(--ink-3)", padding:"4px 0"}}>{lang==="vi"?"Chưa có người liên hệ.":"No contacts yet."}</div>
            )}
            {(dbPatient.contacts || []).map((c) => (
              <div key={c.id} style={{display:"flex", alignItems:"center", gap:10, padding:"9px 0", borderBottom:"1px solid var(--line)"}}>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontSize:12.5, fontWeight:500}}>
                    {c.name}{c.relationship_label ? <span style={{color:"var(--ink-3)", fontWeight:400}}> · {c.relationship_label}</span> : null}
                  </div>
                  <div className="mono" style={{fontSize:11, color:"var(--ink-3)", marginTop:2, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>
                    {[c.email, c.phone].filter(Boolean).join(" · ") || (lang==="vi"?"Chưa có email/điện thoại":"No email/phone")}
                  </div>
                  <div style={{display:"flex", gap:5, marginTop:5}}>
                    {c.notify_weekly_report && <span className="tag ns" style={{fontSize:9.5}}>{lang==="vi"?"Báo cáo tuần":"Weekly report"}</span>}
                    {c.notify_on_alert && <span className="tag is" style={{fontSize:9.5}}>{lang==="vi"?"Cảnh báo":"Alerts"}</span>}
                  </div>
                </div>
                <button className="btn btn-sm btn-ghost" style={{color:"var(--hs)", padding:"3px 7px", fontSize:11}} disabled={contactBusy} onClick={() => deleteContact(c.id)}>
                  {lang==="vi"?"Xóa":"Remove"}
                </button>
              </div>
            ))}
            {showContactForm && (
              <div style={{marginTop:12, padding:14, background:"var(--bg-3)", borderRadius:8, border:"1px solid var(--line-2)", display:"grid", gap:10}}>
                <label style={{display:"grid", gap:4, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Tên *":"Name *"}</span>
                  <input value={contactForm.name} onChange={e => setContactForm(f => ({...f, name:e.target.value}))} placeholder={lang==="vi"?"Người thân / bác sĩ":"Relative / clinician"}/>
                </label>
                <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
                  <label style={{display:"grid", gap:4, fontSize:12}}>
                    <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Quan hệ":"Relationship"}</span>
                    <input value={contactForm.relationship_label} onChange={e => setContactForm(f => ({...f, relationship_label:e.target.value}))} placeholder={lang==="vi"?"Con / vợ / BS":"Son / spouse / MD"}/>
                  </label>
                  <label style={{display:"grid", gap:4, fontSize:12}}>
                    <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Điện thoại":"Phone"}</span>
                    <input value={contactForm.phone} onChange={e => setContactForm(f => ({...f, phone:e.target.value}))} placeholder="09xx xxx xxx"/>
                  </label>
                </div>
                <label style={{display:"grid", gap:4, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>Email</span>
                  <input type="email" value={contactForm.email} onChange={e => setContactForm(f => ({...f, email:e.target.value}))} placeholder="email@example.com"/>
                </label>
                <div style={{display:"flex", gap:16, flexWrap:"wrap"}}>
                  <label style={{display:"flex", alignItems:"center", gap:6, fontSize:12, color:"var(--ink-2)"}}>
                    <input type="checkbox" checked={contactForm.notify_weekly_report} onChange={e => setContactForm(f => ({...f, notify_weekly_report:e.target.checked}))} style={{width:14, height:14}}/>
                    {lang==="vi"?"Nhận báo cáo tuần (email)":"Weekly report (email)"}
                  </label>
                  <label style={{display:"flex", alignItems:"center", gap:6, fontSize:12, color:"var(--ink-2)"}}>
                    <input type="checkbox" checked={contactForm.notify_on_alert} onChange={e => setContactForm(f => ({...f, notify_on_alert:e.target.checked}))} style={{width:14, height:14}}/>
                    {lang==="vi"?"Nhận cảnh báo":"On alert"}
                  </label>
                </div>
                <div style={{display:"flex", justifyContent:"flex-end", gap:8}}>
                  <button className="btn btn-sm btn-ghost" onClick={() => setShowContactForm(false)} disabled={contactBusy}>{lang==="vi"?"Hủy":"Cancel"}</button>
                  <button className="btn btn-sm btn-primary" onClick={addContact} disabled={contactBusy || !contactForm.name.trim()}>
                    {contactBusy ? "…" : (lang==="vi"?"Thêm liên hệ":"Add contact")}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="panel" style={{padding:0, display:"flex", flexDirection:"column"}}>
        <div className="panel-header">
          <div className="title"><window.NTIcon name="patient" size={13}/><span>{t.live.patientHistory}</span></div>
          <span className="mono" style={{fontSize:10, color:"var(--ink-3)"}}>{patAlerts ? `${patAlerts.length} alerts · 30d` : "—"}</span>
        </div>
        <div style={{padding:18, flex:1, overflowY:"auto"}}>
          {!patAlerts && <div style={{color:"var(--ink-3)", fontSize:12}}>{selectedId ? (lang==="vi"?"Đang tải...":"Loading...") : (lang==="vi"?"Chọn bệnh nhân":"Select a patient")}</div>}
          {patAlerts && patAlerts.length === 0 && (
            <div style={{color:"var(--ink-3)", fontSize:12}}>{lang==="vi"?"Không có cảnh báo trong 30 ngày qua":"No alerts in the last 30 days"}</div>
          )}
          {patAlerts && patAlerts.map((a, i) => {
            const cls = a.alert_class === "ischemic" ? "is" : "ns";
            const probs = Array.isArray(a.probabilities_smooth) ? a.probabilities_smooth : [];
            const maxProb = probs.length ? Math.max(...probs) : null;
            const dt = a.created_at ? new Date(a.created_at) : null;
            const timeLabel = dt ? dt.toLocaleString("vi-VN", {day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"}) : "—";
            const statusLabel = a.acknowledged ? (lang==="vi"?"Đã ack":"Acked") : a.dismissed ? (lang==="vi"?"Đã bỏ qua":"Dismissed") : (lang==="vi"?"Chưa xử lý":"Open");
            return (
              <div key={a.id} style={{display:"grid", gridTemplateColumns:"90px 1fr", gap:14, marginBottom:14, paddingBottom:14, borderBottom:i===patAlerts.length-1?"none":"1px solid var(--line)"}}>
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", paddingTop:2}}>{timeLabel}</div>
                <div style={{borderLeft:`2px solid var(--${cls})`, paddingLeft:14}}>
                  <div style={{fontSize:13, fontWeight:600, marginBottom:4, color:`var(--${cls})`}}>
                    {a.alert_class === "ischemic" ? "IS" : "NS"} alert
                    {maxProb != null && <span style={{fontWeight:400, color:"var(--ink-2)", marginLeft:8}}>p={maxProb.toFixed(2)}</span>}
                  </div>
                  <div style={{fontSize:11.5, color:"var(--ink-3)"}}>
                    {statusLabel}{a.sqi_total != null && ` · SQI ${a.sqi_total.toFixed(2)}`}{a.acknowledged_by && ` · by ${a.acknowledged_by}`}
                  </div>
                </div>
              </div>
            );
          })}
          {dbPatient && dbPatient.notes && (
            <div style={{marginTop:8, padding:"10px 14px", background:"var(--bg-3)", borderRadius:6, fontSize:12, color:"var(--ink-2)", borderLeft:"2px solid var(--line-2)"}}>
              <div style={{fontSize:10, color:"var(--ink-3)", marginBottom:4, textTransform:"uppercase", letterSpacing:"0.08em"}}>{lang==="vi"?"Ghi chú":"Notes"}</div>
              {dbPatient.notes}
            </div>
          )}
        </div>
      </div>

      {/* Delete patient confirmation modal */}
      {deleteConfirm && (
        <div style={{position:"fixed", inset:0, background:"rgba(0,0,0,0.5)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center"}} onClick={e => e.target===e.currentTarget && setDeleteConfirm(false)}>
          <div className="panel" style={{width:360, padding:24, display:"flex", flexDirection:"column", gap:16}}>
            <div style={{fontSize:14, fontWeight:600}}>{lang==="vi"?"Xóa bệnh nhân?":"Delete patient?"}</div>
            <div style={{fontSize:12.5, color:"var(--ink-2)", lineHeight:1.5}}>
              {lang==="vi"
                ? `Bạn có chắc muốn xóa "${dispName}"? Hành động này không thể hoàn tác.`
                : `Are you sure you want to delete "${dispName}"? This cannot be undone.`}
            </div>
            <div style={{display:"flex", gap:8, justifyContent:"flex-end"}}>
              <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(false)} disabled={deleteLoading}>{lang==="vi"?"Hủy":"Cancel"}</button>
              <button className="btn btn-sm" onClick={handleDelete} disabled={deleteLoading}
                style={{background:"var(--hs)", color:"#fff", border:"none"}}>
                {deleteLoading ? "…" : (lang==="vi"?"Xóa":"Delete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit patient modal */}
      {editOpen && (
        <div style={{position:"fixed", inset:0, background:"rgba(0,0,0,0.5)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center"}} onClick={e => e.target===e.currentTarget && setEditOpen(false)}>
          <div className="panel" style={{width:"min(720px, calc(100% - 32px))", maxHeight:"calc(100vh - 36px)", overflowY:"auto", padding:24, display:"flex", flexDirection:"column", gap:14}}>
            <div style={{fontSize:14, fontWeight:600, marginBottom:4}}>{lang==="vi"?"Sửa bệnh nhân":"Edit patient"}</div>
            {[
              [lang==="vi"?"Họ tên *":"Full name *", "full_name", "text"],
              ["MRN", "mrn", "text"],
              [lang==="vi"?"Giường":"Bed", "bed", "text"],
              [lang==="vi"?"Giới tính (M/F)":"Gender (M/F)", "gender", "text"],
              [lang==="vi"?"Onset (phút trước)":"Onset (min ago)", "onset_minutes", "number"],
              [lang==="vi"?"Lý do vào viện":"Chief complaint", "chief_complaint", "text"],
              [lang==="vi"?"Triệu chứng":"Symptoms", "symptoms", "text"],
              [lang==="vi"?"Tiền sử bệnh":"Medical history", "medical_history", "text"],
              [lang==="vi"?"Thuốc đang dùng":"Medications", "medications", "text"],
              [lang==="vi"?"Dị ứng":"Allergies", "allergies", "text"],
              [lang==="vi"?"HA":"BP", "blood_pressure", "text"],
              ["HR", "heart_rate", "number"],
              ["SpO2", "spo2", "number"],
              [lang==="vi"?"Nhiệt độ":"Temperature", "temperature", "number"],
              [lang==="vi"?"Đường huyết":"Glucose", "glucose", "number"],
              ["NIHSS", "nihss", "number"],
              [lang==="vi"?"Ghi chú":"Notes", "notes", "text"],
            ].map(([label, key, type]) => (
              <label key={key} style={{display:"flex", flexDirection:"column", gap:4, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{label}</span>
                <input type={type} value={editForm[key]} onChange={e => setEditForm(f => ({...f, [key]: e.target.value}))} style={{width:"100%", boxSizing:"border-box"}}/>
              </label>
            ))}
            <div style={{display:"flex", gap:8, justifyContent:"flex-end", marginTop:4}}>
              <button className="btn btn-sm btn-ghost" onClick={() => setEditOpen(false)}>{lang==="vi"?"Hủy":"Cancel"}</button>
              <button className="btn btn-sm btn-primary" onClick={saveEdit} disabled={editSaving}>{editSaving ? "…" : (lang==="vi"?"Lưu":"Save")}</button>
            </div>
          </div>
        </div>
      )}

      {/* Create patient modal — same dialog the dashboard uses, so the Patient
          tab is no longer a dead end when no patient exists yet. */}
      {showNewPatient && (
        <window.NewPatientDialog
          lang={lang}
          onClose={() => setShowNewPatient(false)}
          onCreated={() => { setShowNewPatient(false); setPatRefresh(v => v + 1); }}
        />
      )}
    </div>
  );
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.AlertsScreen = function AlertsScreen({t, lang}) {
  // Real alerts from /api/alerts?since_hours=24, refreshed every 5 s.
  // Each row carries the backend `id` so Ack/Dismiss buttons can POST to
  // /api/alerts/{id}/ack or /dismiss.
  const [refreshTick, setRefreshTick] = React.useState(0);
  const apiState = window.NTApi
    ? window.NTApi.useApi(
        () => window.NTApi.get("/api/alerts?since_hours=24&limit=200"),
        [refreshTick],
        5000,
      )
    : {data: null, loading: true, error: null};
  const patientsState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/patients"), [refreshTick], 15000)
    : {data: null, loading: true, error: null};
  const patientOptions = patientsState.data || [];

  function classToMode(cls) {
    const c = String(cls || "").toLowerCase();
    if (c === "ischemic") return "IS";
    if (c === "non-stroke" || c === "nonstroke") return "NS";
    return "NS";
  }
  function statusOf(a) {
    if (a.dismissed) return "dismissed";
    if (a.acknowledged) return "acked";
    return "open";
  }
  function probOf(a) {
    const ps = a.probabilities_smooth;
    if (!Array.isArray(ps) || ps.length < 1) return 0.0;
    return Math.max.apply(null, ps);
  }
  function fmtTime(iso) {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toTimeString().slice(0, 8);
    } catch (e) {
      return String(iso).slice(11, 19);
    }
  }
  const [search, setSearch] = React.useState("");
  const [classFilter, setClassFilter] = React.useState("IS"); // ALL | IS | NS
  const [alertNotice, setAlertNotice] = React.useState(null);
  const [busyAlertId, setBusyAlertId] = React.useState(null);
  const [assignSelections, setAssignSelections] = React.useState({});
  const [assignBusyId, setAssignBusyId] = React.useState(null);

  const allAlerts = (apiState.data || []).map(a => ({
    id: a.id,
    time: fmtTime(a.created_at),
    patient: a.patient_name || "Unassigned",
    bed: a.patient_bed || (a.session_id ? `WS-${String(a.session_id).slice(0, 4).toUpperCase()}` : "—"),
    mode: classToMode(a.alert_class),
    prob: probOf(a),
    status: statusOf(a),
    ack: a.acknowledged_by || "—",
    sqi: typeof a.sqi_total === "number" ? a.sqi_total : null,
    session: a.session_id ? String(a.session_id).slice(0, 8) : "—",
    unassigned: !a.patient_id,
    raw: a,
  }));

  const q = search.trim().toLowerCase();
  const alerts = allAlerts.filter(a => {
    if (classFilter !== "ALL" && a.mode !== classFilter) return false;
    if (q) {
      const hay = `${a.patient} ${a.bed} ${a.mode} ${a.status}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const sessionGroups = alerts.reduce((acc, a) => {
    const key = a.session || "unknown";
    if (!acc[key]) acc[key] = {session:key, count:0, open:0, unassigned:false, maxProb:0, modes:new Set()};
    acc[key].count += 1;
    if (a.status === "open") acc[key].open += 1;
    if (a.unassigned) acc[key].unassigned = true;
    acc[key].maxProb = Math.max(acc[key].maxProb, a.prob || 0);
    acc[key].modes.add(a.mode);
    return acc;
  }, {});
  const groupedSessions = Object.values(sessionGroups).map(g => ({...g, modes:Array.from(g.modes).join("/")}));

  async function runAlertAction(a, action) {
    if (!window.NTApi || busyAlertId) return;
    setBusyAlertId(a.id);
    setAlertNotice(null);
    try {
      await window.NTApi.post(`/api/alerts/${a.id}/${action}`);
      setAlertNotice({
        type:"ok",
        text: action === "ack"
          ? (lang==="vi"?"Đã ghi nhận cảnh báo.":"Alert acknowledged.")
          : (lang==="vi"?"Đã bỏ qua cảnh báo.":"Alert dismissed."),
      });
      setRefreshTick(v => v + 1);
    } catch (e) {
      setAlertNotice({type:"error", text:(e.message || String(e))});
    } finally {
      setBusyAlertId(null);
    }
  }

  async function runAssignPatient(a) {
    if (!window.NTApi || assignBusyId) return;
    const patientId = assignSelections[a.id] || patientOptions[0]?.id;
    if (!patientId) {
      setAlertNotice({
        type:"error",
        text: lang==="vi" ? "Chưa có bệnh nhân để gán. Hãy tạo bệnh nhân trước." : "No patient available. Create a patient first.",
      });
      return;
    }
    setAssignBusyId(a.id);
    setAlertNotice(null);
    try {
      const result = await window.NTApi.post(`/api/alerts/${a.id}/assign-patient`, {
        patient_id: patientId,
        scope: "session",
      });
      setAlertNotice({
        type:"ok",
        text: lang==="vi"
          ? `Đã gán ${result.patient?.full_name || "bệnh nhân"} cho session ${a.session}.`
          : `Assigned ${result.patient?.full_name || "patient"} to session ${a.session}.`,
      });
      setRefreshTick(v => v + 1);
    } catch (e) {
      setAlertNotice({type:"error", text:(e.message || String(e))});
    } finally {
      setAssignBusyId(null);
    }
  }

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflow:"hidden", display:"flex", flexDirection:"column"}}>
      <div className="nt-toolbar" style={{marginBottom:14}}>
        <input type="text" placeholder={lang==="vi"?"Tìm bệnh nhân, giường, lớp...":"Search patient, bed, class..."}
               value={search} onChange={e => setSearch(e.target.value)} style={{flex:1, maxWidth:340}}/>
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)} className="btn btn-sm" style={{minWidth:110}}>
          <option value="ALL">{lang==="vi"?"Tất cả":"All"}</option>
          <option value="IS">IS</option>
          <option value="NS">NS</option>
        </select>
        <span className="mono" style={{fontSize:11, color:"var(--ink-3)"}}>
          {alerts.length}/{allAlerts.length} · last 24h
        </span>
        <div style={{flex:1}}/>
        <button className="btn btn-sm" onClick={() => {
          const header = "Time,Patient,Bed,Class,Prob,Status,AckedBy";
          const rows = alerts.map(a => [a.time, a.patient, a.bed, a.mode, a.prob, a.status, a.ack].map(v => `"${String(v).replace(/"/g,'""')}"`).join(","));
          const csv = [header, ...rows].join("\n");
          const url = URL.createObjectURL(new Blob([csv], {type:"text/csv"}));
          const el = document.createElement("a"); el.href = url; el.download = `alerts_${new Date().toISOString().slice(0,10)}.csv`; el.click();
          URL.revokeObjectURL(url);
        }}><window.NTIcon name="download" size={12}/>{t.actions.export}</button>
      </div>
      {alertNotice && (
        <div style={{marginBottom:10, padding:"9px 11px", borderRadius:7, border:"1px solid var(--line-2)", background:"var(--bg-3)", color:alertNotice.type==="error"?"var(--hs)":"var(--ns)", fontSize:12}}>
          {alertNotice.text}
        </div>
      )}
      {groupedSessions.length > 0 && (
        <div style={{display:"flex", gap:8, overflowX:"auto", paddingBottom:10}}>
          {groupedSessions.slice(0, 8).map(g => (
            <div key={g.session} style={{minWidth:170, padding:"9px 10px", background:"var(--bg-3)", border:"1px solid var(--line-2)", borderRadius:7}}>
              <div style={{display:"flex", justifyContent:"space-between", gap:8}}>
                <span className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>session {g.session}</span>
                <span className="mono" style={{fontSize:10.5, color:g.open ? "var(--hs)" : "var(--ink-3)"}}>{g.open} open</span>
              </div>
              <div style={{fontSize:11.5, marginTop:5}}>{g.count} alerts - {g.modes}</div>
              {g.unassigned && <div style={{fontSize:10.5, color:"var(--is)", marginTop:3}}>Unassigned stream</div>}
            </div>
          ))}
        </div>
      )}
      <div className="panel nt-table-wrap" style={{flex:1, padding:0}}>
        <table className="tbl">
          <thead><tr>
            <th style={{width:90}}>Time</th>
            <th>Patient</th>
            <th style={{width:80}}>Bed</th>
            <th style={{width:100}}>Class</th>
            <th style={{width:100}}>Prob</th>
            <th style={{width:120}}>Status</th>
            <th style={{width:100}}>{t.live.ackedBy}</th>
            <th style={{width:80}}/>
          </tr></thead>
          <tbody>
          {alerts.length === 0 && (
            <tr><td colSpan={8} style={{textAlign:"center", padding:"24px 12px", color:"var(--ink-3)", fontSize:12}}>
              {apiState.loading ? (lang==="vi"?"Đang tải...":"Loading...")
               : apiState.error ? `${lang==="vi"?"Lỗi":"Error"}: ${apiState.error.message}`
               : (lang==="vi"?"Chưa có cảnh báo trong 24 giờ qua":"No alerts in the last 24 hours")}
            </td></tr>
          )}
          {alerts.map((a) => {
            const accent = a.mode==="NS"?"var(--ns)":"var(--is)";
            return (
              <tr key={a.id}>
                <td className="mono" style={{color:"var(--ink-3)"}}>{a.time}</td>
                <td style={{color:"var(--ink)"}}>
                  <div>{a.patient}</div>
                  <div className="mono" style={{fontSize:10, color:a.unassigned?"var(--is)":"var(--ink-3)", marginTop:2}}>
                    {a.unassigned ? "Unassigned stream" : `session ${a.session}`}
                  </div>
                  {a.unassigned && (
                    <div style={{display:"flex", gap:5, marginTop:7, alignItems:"center", flexWrap:"wrap"}}>
                      <select
                        value={assignSelections[a.id] || patientOptions[0]?.id || ""}
                        onChange={e => setAssignSelections(s => ({...s, [a.id]: e.target.value}))}
                        disabled={assignBusyId===a.id || patientOptions.length===0}
                        style={{fontSize:11, padding:"4px 6px", maxWidth:160}}
                      >
                        {patientOptions.length === 0 && <option value="">{lang==="vi"?"Chưa có bệnh nhân":"No patients"}</option>}
                        {patientOptions.map(p => (
                          <option key={p.id} value={p.id}>{p.full_name || p.id}</option>
                        ))}
                      </select>
                      <button
                        className="btn btn-sm"
                        style={{padding:"3px 7px", fontSize:11}}
                        disabled={assignBusyId===a.id || patientOptions.length===0}
                        onClick={() => runAssignPatient(a)}
                      >
                        {assignBusyId===a.id ? "..." : (lang==="vi"?"Gán":"Assign")}
                      </button>
                    </div>
                  )}
                </td>
                <td className="mono">{a.bed}</td>
                <td><span className={`tag ${a.mode.toLowerCase()}`}><span className={`dot ${a.mode.toLowerCase()}`}/>{t.severityShort[a.mode]}</span></td>
                <td><div style={{display:"flex", alignItems:"center", gap:8}}>
                  <div style={{flex:1, height:4, background:"var(--bg-3)", borderRadius:2, overflow:"hidden", maxWidth:60}}>
                    <div style={{width:(a.prob*100)+"%", height:"100%", background:accent, boxShadow:`0 0 4px ${accent}`}}/>
                  </div>
                  <span className="mono" style={{fontSize:11, color:accent}}>{a.prob.toFixed(2)}</span>
                </div>
                <div className="mono" style={{fontSize:10, color:"var(--ink-3)", marginTop:3}}>
                  SQI {a.sqi == null ? "—" : a.sqi.toFixed(2)}
                </div></td>
                <td>
                  {a.status==="open" && <span style={{color:"var(--hs)", fontSize:11.5}}>● {lang==="vi"?"Đang mở":"Open"}</span>}
                  {a.status==="acked" && <span style={{color:"var(--ns)", fontSize:11.5}}>● {lang==="vi"?"Đã ghi nhận":"Acked"}</span>}
                  {a.status==="dismissed" && <span style={{color:"var(--ink-3)", fontSize:11.5}}>○ {lang==="vi"?"Bỏ qua":"Dismissed"}</span>}
                </td>
                <td className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>{a.ack}</td>
                <td>
                  {a.status === "open" ? (
                    <div style={{display:"flex", gap:4}}>
                      <button className="btn btn-sm" style={{padding:"3px 7px", fontSize:11}} disabled={busyAlertId===a.id} onClick={() => runAlertAction(a, "ack")}>
                        {busyAlertId===a.id ? "..." : (lang==="vi"?"Ghi nhận":"Ack")}
                      </button>
                      <button className="btn btn-sm btn-ghost" style={{padding:"3px 7px", fontSize:11}} disabled={busyAlertId===a.id} onClick={() => runAlertAction(a, "dismiss")}>
                        {lang==="vi"?"Bỏ qua":"Skip"}
                      </button>
                    </div>
                  ) : (
                    <button className="btn btn-sm btn-ghost" style={{padding:"3px 7px", fontSize:11}}>{t.actions.review} -></button>
                  )}
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

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.DeviceScreen = function DeviceScreen({frame, t, lang, channels}) {
  // Real registered devices + preset templates from backend.
  const [refreshTick, setRefreshTick] = React.useState(0);
  const [pairing, setPairing] = React.useState(null);
  const [probing, setProbing] = React.useState(null);
  const [probeResult, setProbeResult] = React.useState(null);
  const [deviceNotice, setDeviceNotice] = React.useState(null);
  const [pendingUnpair, setPendingUnpair] = React.useState(null);
  const [showGuide, setShowGuide] = React.useState(false);
  const devicesState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/devices"), [refreshTick], 10000)
    : {data: null, loading: true, error: null};
  const presetsState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/devices/presets"), [])
    : {data: null, loading: true, error: null};
  // Honest live-device readiness (the real BLE link), separate from a
  // "registered preset" DB row. Without this the screen showed a green WiFi
  // icon for a preset that has no real connection at all.
  const liveStatusState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/devices/live-status"), [refreshTick], 10000)
    : {data: null, loading: true, error: null};
  // Replay case count for the "REPLAY (ready)" source card.
  const replayCasesState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/replay/cases"), [])
    : {data: null};
  const replayCount = Array.isArray(replayCasesState.data) ? replayCasesState.data.length : null;

  async function pairPreset(presetKey, preset) {
    if (!window.NTApi || pairing) return;
    setPairing(presetKey);
    setDeviceNotice(null);
    try {
      const name = (preset.description || presetKey).split("(")[0].trim();
      await window.NTApi.post("/api/devices", {
        device_type: presetKey,
        device_name: name,
        channels: preset.channels || [],
        fs: preset.fs || 256,
      });
      setRefreshTick(v => v + 1);
      setDeviceNotice({type:"ok", text: lang==="vi" ? "Đã đăng ký hồ sơ thiết bị (chưa phải link BLE thật). Bước tiếp theo: gán bệnh nhân hoặc mở Live (replay)." : "Device profile registered (not a real BLE link yet). Next: assign a patient or open Live (replay)."});
    } catch (e) {
      setDeviceNotice({type:"error", text:(lang==="vi"?"Lỗi ghép thiết bị: ":"Pair error: ") + (e.message || e)});
    } finally {
      setPairing(null);
    }
  }

  async function probePreset(presetKey, preset) {
    if (!window.NTApi || probing) return;
    setProbing(presetKey);
    setProbeResult(null);
    try {
      const data = await window.NTApi.post("/api/devices/probe", {
        device_type: presetKey,
        device_name: (preset.description || presetKey).split("(")[0].trim(),
        channels: preset.channels || [],
        fs: preset.fs || 256,
      });
      setProbeResult(data);
    } catch (e) {
      setProbeResult({error: e.message || String(e), device_type: presetKey});
    } finally {
      setProbing(null);
    }
  }

  async function unpairDevice(deviceId) {
    if (!window.NTApi) return;
    if (pendingUnpair !== deviceId) {
      setPendingUnpair(deviceId);
      setDeviceNotice({type:"warn", text: lang==="vi" ? "Bấm Unpair lần nữa để xác nhận tháo thiết bị." : "Click Unpair again to confirm."});
      return;
    }
    try {
      await window.NTApi.del("/api/devices/" + deviceId);
      setRefreshTick(v => v + 1);
      setPendingUnpair(null);
      setDeviceNotice({type:"ok", text: lang==="vi" ? "Đã tháo thiết bị." : "Device unpaired."});
    } catch (e) {
      setDeviceNotice({type:"error", text:(lang==="vi"?"Lỗi: ":"Error: ") + (e.message || e)});
    }
  }

  const dbDevices = devicesState.data || [];
  const presets = presetsState.data || {};

  // Connected = first registered device. Do not present demo frame metadata as a real connection.
  const connected = dbDevices[0];
  const connectedName = connected ? connected.device_name : (lang==="vi" ? "Chưa có thiết bị" : "No device registered");
  const connectedSerial = connected && connected.serial_number ? connected.serial_number : "Not measured";
  const connectedFs = connected ? connected.fs : null;
  const connectedChannelCount = connected ? (connected.channels || []).length : 0;
  const connectedCoverage = connected
    ? Math.min(1, ((connected.channels || []).length || 0) / Math.max(1, channels.length))
    : 0;
  // Real BLE link readiness — a registered preset is NOT a live connection.
  const liveStatus = liveStatusState.data || null;
  const liveReady = !!(liveStatus && liveStatus.ready);
  const liveBlockReason = liveStatus && liveStatus.blocking_reason ? liveStatus.blocking_reason : null;
  // "paired" falsely implied a live link. A registered device with no real BLE
  // link is only a saved profile — label it as such so the card stops claiming
  // a connection that does not exist.
  const connectionState = liveReady
    ? (lang==="vi" ? "đang kết nối" : "connected")
    : connected
    ? (lang==="vi" ? "đã đăng ký · chưa có link thật" : "registered · no live link")
    : (lang==="vi" ? "chưa có thiết bị" : "no device");
  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      <div style={{display:"flex", flexDirection:"column", gap:14, maxWidth:760, margin:"0 auto"}}>
        {deviceNotice && (
          <div style={{padding:"9px 11px", borderRadius:7, border:"1px solid var(--line-2)", background:"var(--bg-3)", color:deviceNotice.type==="error"?"var(--hs)":deviceNotice.type==="warn"?"var(--is)":"var(--ns)", fontSize:12}}>
            {deviceNotice.text}
          </div>
        )}
        {/* ── NGUỒN DỮ LIỆU — two explicit modes ─────────────────── */}
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Nguồn dữ liệu":"Data source"}</div>

          {/* Mode 1: Replay — always available */}
          <div style={{display:"flex", alignItems:"flex-start", gap:12, padding:14, borderRadius:10, border:"1px solid var(--ns)", background:"oklch(0.24 0.08 150 / 0.16)", marginBottom:12}}>
            <span className="dot live ns" style={{marginTop:6}}/>
            <div style={{flex:1, minWidth:0}}>
              <div style={{display:"flex", alignItems:"center", gap:8, flexWrap:"wrap"}}>
                <span style={{fontSize:14, fontWeight:600}}>{lang==="vi"?"Replay":"Replay"}</span>
                <span className="tag ns" style={{fontSize:9.5}}>{lang==="vi"?"Sẵn sàng":"Ready"}</span>
                <span style={{fontSize:10.5, color:"var(--ink-3)"}}>{lang==="vi"?"đang dùng":"in use"}</span>
              </div>
              <div style={{fontSize:12, color:"var(--ink-3)", marginTop:3}}>
                {lang==="vi"?"Phát lại EEG đã ghi sẵn":"Replay of pre-recorded EEG"}{replayCount!=null?` · ${replayCount} ${lang==="vi"?"ca":"cases"}`:""}
              </div>
              <button className="btn btn-sm btn-primary" style={{marginTop:10}} onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"live", source:"replay"}}))}>
                <window.NTIcon name="live" size={12}/>{lang==="vi"?"Bắt đầu replay":"Start replay"}
              </button>
            </div>
          </div>

          {/* Mode 2: Live device — only "ready" once configured */}
          <div style={{display:"flex", alignItems:"flex-start", gap:12, padding:14, borderRadius:10, border:"1px solid " + (liveReady?"var(--ns)":"var(--line-2)"), background: liveReady?"oklch(0.24 0.08 150 / 0.16)":"var(--bg-3)"}}>
            <span className={`dot live ${liveReady?"ns":""}`} style={{marginTop:6}}/>
            <div style={{flex:1, minWidth:0}}>
              <div style={{display:"flex", alignItems:"center", gap:8, flexWrap:"wrap"}}>
                <span style={{fontSize:14, fontWeight:600}}>{lang==="vi"?"Thiết bị thật (BLE Focus+)":"Live device (BLE Focus+)"}</span>
                <span className="tag" style={{fontSize:9.5, color:liveReady?"var(--ns)":"var(--ink-3)", borderColor:liveReady?"var(--ns)":"var(--ink-4)"}}>
                  {liveReady?(lang==="vi"?"Sẵn sàng":"Ready"):(lang==="vi"?"Chưa sẵn":"Not available")}
                </span>
              </div>
              <div style={{fontSize:12, color:"var(--ink-3)", marginTop:3}}>
                {liveReady
                  ? (lang==="vi"?"Đã kết nối · sẵn sàng stream":"Connected · ready to stream")
                  : (lang==="vi"?"Chưa kết nối · ":"Not connected · ") + (liveBlockReason || (lang==="vi"?"giao thức BLE chưa cấu hình":"BLE protocol not configured"))}
              </div>
              {liveReady ? (
                <button className="btn btn-sm btn-primary" style={{marginTop:10}} onClick={() => window.dispatchEvent(new CustomEvent("nt:nav", {detail:{tab:"live", source:"device"}}))}>
                  <window.NTIcon name="live" size={12}/>{lang==="vi"?"Mở Live (thiết bị)":"Open Live (device)"}
                </button>
              ) : (
                <button className="btn btn-sm" style={{marginTop:10}} onClick={() => setShowGuide(v=>!v)}>
                  <window.NTIcon name="bt" size={12}/>{showGuide?(lang==="vi"?"Ẩn hướng dẫn":"Hide guide"):(lang==="vi"?"Xem hướng dẫn kết nối":"Connection guide")}
                </button>
              )}
              {showGuide && !liveReady && (
                <div style={{marginTop:12, padding:"12px 14px", background:"var(--bg-2)", borderRadius:8, border:"1px solid var(--line-2)", fontSize:12, color:"var(--ink-2)", lineHeight:1.6}}>
                  <div style={{fontWeight:600, marginBottom:6, color:"var(--ink)"}}>{lang==="vi"?"Để stream từ Focus+ thật:":"To stream from the real Focus+:"}</div>
                  <ol style={{margin:0, paddingLeft:18, display:"grid", gap:4}}>
                    <li>{lang==="vi"?"Bật thiết bị, chạy ":"Power on the device, run "}<code>scripts/ble_probe.py</code>{lang==="vi"?" để dò giao thức BLE.":" to discover the BLE protocol."}</li>
                    <li>{lang==="vi"?"Điền UUID/format + lệnh start vào ":"Fill UUIDs/format + start command into "}<code>device_source.py</code>{lang==="vi"?", đặt ":", set "}<code>configured=True</code>.</li>
                    <li>{lang==="vi"?"Tải lại app — thẻ này sẽ chuyển sang \"Sẵn sàng\".":"Reload the app — this card flips to \"Ready\"."}</li>
                  </ol>
                  <div style={{marginTop:8, color:"var(--ink-3)"}}>{lang==="vi"?"Lưu ý: Focus+ chỉ 2 kênh → chỉ chạy SQI/No-Decision, không phân loại.":"Note: Focus+ has only 2 channels → drives SQI/No-Decision, not classification."}</div>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14, display:"flex", justifyContent:"space-between"}}>
            <span>{lang==="vi"?"Hồ sơ thiết bị đã đăng ký":"Registered device profiles"}</span>
            <span className="mono" style={{fontSize:9, color:devicesState.data?"var(--ns)":"var(--ink-3)", letterSpacing:"0.08em"}}>
              {devicesState.data ? "BACKEND" : devicesState.loading ? "LOADING" : "FALLBACK"}
            </span>
          </div>
          <div style={{fontSize:11.5, color:"var(--ink-3)", lineHeight:1.5, marginBottom:10}}>
            {lang==="vi"?"Đăng ký = lưu hồ sơ montage của thiết bị (không phải kết nối BLE thật).":"Register = save a device montage profile (not a real BLE connection)."}
          </div>
          {(() => {
            const registeredKeys = new Set(dbDevices.map(d => d.device_type));
            const items = [
              ...dbDevices.map(d => ({
                key: "db:" + d.id,
                kind: "db",
                dbId: d.id,
                name: d.device_name,
                ch: (d.channels || []).length,
                conn: d.mac_address ? "BLE" : "WiFi",
                state: "paired",
              })),
              ...Object.entries(presets)
                .filter(([key]) => !registeredKeys.has(key))
                .map(([key, p]) => ({
                  key: "preset:" + key,
                  kind: "preset",
                  presetKey: key,
                  preset: p,
                  name: (p.description || key).split("(")[0].trim(),
                  ch: (p.channels || []).length,
                  conn: key.includes("brain_life") ? "BLE" : key.includes("openbci") ? "USB" : "WiFi",
                  state: "available",
                })),
            ];
            if (items.length === 0) {
              return <div style={{color:"var(--ink-3)", fontSize:12, padding:"8px 0"}}>{lang==="vi"?"Không có thiết bị":"No devices"}</div>;
            }
            return items.map((d, i) => (
              <div key={d.key} style={{display:"flex", alignItems:"center", gap:10, padding:"10px 0", borderBottom:i===items.length-1?"none":"1px solid var(--line)"}}>
                <window.NTIcon name={d.conn==="BLE"?"bt":d.conn==="USB"?"device":"wifi"} size={14} color="var(--ink-3)"/>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontSize:12.5, color:"var(--ink)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{d.name}</div>
                  <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{d.ch ? d.ch + "-ch" : "—"} · {d.conn}</div>
                </div>
                {d.kind === "db" ? (
                  <button className="btn btn-sm btn-ghost" style={{fontSize:11}} onClick={() => unpairDevice(d.dbId)}>
                    {pendingUnpair === d.dbId ? (lang==="vi"?"Xác nhận":"Confirm") : (lang==="vi"?"Tháo":"Unpair")}
                  </button>
                ) : (
                  <React.Fragment>
                    <button className="btn btn-sm btn-ghost" style={{fontSize:11, marginRight:5}} disabled={probing===d.presetKey || !d.ch}
                            onClick={() => probePreset(d.presetKey, d.preset)}>
                      {probing===d.presetKey ? "..." : (lang==="vi"?"Test":"Probe")}
                    </button>
                    <button className="btn btn-sm" style={{fontSize:11}} disabled={pairing===d.presetKey || !d.ch}
                            onClick={() => pairPreset(d.presetKey, d.preset)}>
                      {pairing===d.presetKey ? "..." : (lang==="vi"?"Đăng ký":"Register")}
                    </button>
                  </React.Fragment>
                )}
              </div>
            ));
          })()}
        </div>
        {probeResult && (
          <div className="panel" style={{padding:18}}>
            <div className="stat-lbl" style={{marginBottom:12}}>{lang==="vi"?"Kết quả probe":"Probe result"}</div>
            {probeResult.error ? (
              <div style={{fontSize:12, color:"var(--hs)"}}>{probeResult.error}</div>
            ) : (
              <div style={{display:"grid", gap:8, fontSize:12}}>
                <div style={{display:"flex", justifyContent:"space-between"}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Thiết bị":"Device"}</span>
                  <span className="mono">{probeResult.device_name || probeResult.device_type || "-"}</span>
                </div>
                <div style={{display:"flex", justifyContent:"space-between"}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Phủ kênh":"Coverage"}</span>
                  <span className="mono">{Math.round((probeResult.coverage_ratio || 0) * 100)}%</span>
                </div>
                <div style={{display:"flex", justifyContent:"space-between"}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Khớp / thiếu":"Matched / missing"}</span>
                  <span className="mono">{(probeResult.matched || []).length} / {(probeResult.missing_target_channels || []).length}</span>
                </div>
                {(probeResult.unrecognised || []).length > 0 && (
                  <div style={{color:"var(--is)"}}>{lang==="vi"?"Kênh lạ: ":"Unknown channels: "}{probeResult.unrecognised.join(", ")}</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
