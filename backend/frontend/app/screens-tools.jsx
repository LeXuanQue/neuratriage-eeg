// Setup (analyze EEG file), Insights (model), Reports, Settings screens
const { useState: useS_b } = React;

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.SetupScreen = function SetupScreen({t, lang}) {
  const [tab, setTab] = useS_b("upload");
  const [recent, setRecent] = useS_b(() => {
    try { return JSON.parse(localStorage.getItem("neuratriage_recent_uploads") || "[]"); } catch (e) { return []; }
  });
  const [uploading, setUploading] = useS_b(false);
  const [running, setRunning] = useS_b(false);
  const [pendingFile, setPendingFile] = useS_b(null);
  const [result, setResult] = useS_b(null);
  const [error, setError] = useS_b(null);
  const [patientForm, setPatientForm] = useS_b({
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
    notes: "",
  });
  const fileInputRef = React.useRef(null);
  const replayState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/replay/cases"), [])
    : { data: [], loading: false, error: null };
  const replayCases = Array.isArray(replayState.data) ? replayState.data : [];

  function persistRecent(items) {
    setRecent(items);
    try { localStorage.setItem("neuratriage_recent_uploads", JSON.stringify(items.slice(0, 12))); } catch (e) {}
  }
  function fmtSize(b) {
    if (!b) return "—";
    if (b < 1024) return b + " B";
    if (b < 1024*1024) return (b/1024).toFixed(0) + " KB";
    return (b/(1024*1024)).toFixed(1) + " MB";
  }
  function probsFromOverall(o) {
    return {NS: o?.p_nonstroke ?? 0, IS: o?.p_ischemic ?? 0, HS: o?.p_hemorrhagic ?? 0};
  }
  function modeFromResult(overall) {
    const cls = String(overall?.pred_class || "").toLowerCase().replace(/[_\s]+/g, "-");
    if (["hemorrhagic", "hs", "2"].includes(cls)) return "HS";
    if (["ischemic", "is", "1"].includes(cls)) return "IS";
    if (["non-stroke", "nonstroke", "ns", "normal", "0"].includes(cls)) return "NS";
    const probs = probsFromOverall(overall);
    return Object.entries(probs).sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))[0]?.[0] || "NS";
  }
  function setPatientField(key, value) {
    setPatientForm(prev => ({...prev, [key]: value}));
  }
  async function upsertPatientFromAnalysis(file, analysis) {
    if (!window.NTApi || !file || !analysis) return null;
    const mrn = patientForm.mrn.trim() || null;
    const fullName = patientForm.full_name.trim();
    if (!fullName) throw new Error(lang==="vi" ? "Hãy nhập tên bệnh nhân trước khi phân tích." : "Enter patient name before analysis.");
    const dx = {
      chief_complaint: patientForm.chief_complaint.trim() || null,
      symptoms: patientForm.symptoms.trim() || null,
      medical_history: patientForm.medical_history.trim() || null,
      medications: patientForm.medications.trim() || null,
      allergies: patientForm.allergies.trim() || null,
      eeg_analysis: {
        source_file: file.original_name,
        upload_id: file.upload_id,
        size_bytes: file.size_bytes,
        analysed_at: new Date().toISOString(),
        windows: analysis.windows,
        model: analysis.model,
        source: analysis.source,
        overall: analysis.overall,
        latest: analysis.latest,
      },
    };
    const existing = await window.NTApi.get("/api/patients");
    const arr = Array.isArray(existing) ? existing : (existing?.items || []);
    const found = mrn ? arr.find(p => p.mrn === mrn) : null;
    const body = {
      full_name: fullName,
      mrn,
      bed: patientForm.bed.trim() || null,
      gender: patientForm.gender || null,
      onset_minutes: patientForm.onset_minutes ? parseInt(patientForm.onset_minutes, 10) : null,
      diagnosis_history: {...(found?.diagnosis_history || {}), ...dx},
      notes: patientForm.notes.trim() || `Imported from EEG file: ${file.original_name}`,
    };
    const patient = found
      ? await window.NTApi.put(`/api/patients/${found.id}`, body)
      : await window.NTApi.post("/api/patients", body);
    try {
      localStorage.setItem("neuratriage_selected_patient_id", patient.id);
      sessionStorage.setItem("neuratriage_current_dataset_analysis", JSON.stringify({patient_id: patient.id, patient_name: patient.full_name, mrn: patient.mrn, bed: patient.bed, ...dx.eeg_analysis}));
    } catch (e) {}
    window.dispatchEvent(new CustomEvent("nt:patient-select", {detail:{patientId: patient.id}}));
    window.dispatchEvent(new CustomEvent("nt:analysis-created", {detail:{patientId: patient.id}}));
    return patient;
  }

  async function handleUpload(file) {
    if (!file || !window.NTApi) return;
    setError(null); setUploading(true); setResult(null); setPendingFile(null);
    try {
      sessionStorage.removeItem("neuratriage_current_dataset_analysis");
      window.dispatchEvent(new CustomEvent("nt:analysis-cleared"));
    } catch (e) {}
    try {
      await window.NTApi.ensureAuth();
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(window.NTApi.baseUrl() + "/api/upload", {
        method: "POST",
        headers: {"Authorization": "Bearer " + window.NTApi.getToken()},
        body: form,
      });
      const j = await r.json();
      if (!r.ok || !j.success) throw new Error((j.error && j.error.message) || "Upload failed");
      const uploaded = {...j.data};
      setPendingFile(uploaded);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  }

  async function runInference(file) {
    if (!file || !window.NTApi) return;
    if (!patientForm.full_name.trim()) {
      setError(lang==="vi" ? "Hãy nhập thông tin bệnh nhân trước khi chạy phân tích." : "Enter patient information before running analysis.");
      return;
    }
    setError(null); setRunning(true); setResult(null);
    try {
      const uploadId = file.upload_id || "";
      const data = await window.NTApi.post("/api/infer", {
        upload_id: uploadId,
        patient_id: patientForm.full_name.trim(),
        max_duration_sec: 30,
      });
      setResult(data);
      const patient = await upsertPatientFromAnalysis(file, data);
      const entry = {
        ts: Date.now(),
        upload_id: uploadId,
        original_name: file.original_name,
        size_bytes: file.size_bytes,
        patient_id: patient?.id,
        overall: data.overall,
        windows: data.windows,
      };
      persistRecent([entry, ...recent.filter(r => r.upload_id !== entry.upload_id)]);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setRunning(false);
    }
  }

  async function runReplayCase(c) {
    if (!c || !window.NTApi) return;
    setError(null); setRunning(true); setResult(null);
    try {
      const data = await window.NTApi.post("/api/infer", {
        case_id: c.id,
        patient_id: c.id,
      });
      setResult(data);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setRunning(false);
    }
  }

  function onPickFiles(e) {
    const f = e.target.files && e.target.files[0];
    if (f) handleUpload(f);
    e.target.value = "";
  }

  function onDrop(e) {
    e.preventDefault();
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) handleUpload(f);
  }

  function relativeTime(ts) {
    const dt = (Date.now() - ts) / 1000;
    if (dt < 60) return lang==="vi"?"vừa xong":"just now";
    if (dt < 3600) return Math.floor(dt/60) + (lang==="vi"?"' trước":"m ago");
    if (dt < 86400) return Math.floor(dt/3600) + (lang==="vi"?"h trước":"h ago");
    return Math.floor(dt/86400) + (lang==="vi"?"d trước":"d ago");
  }

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      <div style={{display:"flex", gap:6, marginBottom:14, borderBottom:"1px solid var(--line)"}}>
        {[["upload", lang==="vi"?"Tải file":"Upload"], ["replay", lang==="vi"?"Phát lại":"Replay session"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} style={{
            padding:"8px 14px", fontSize:12.5, background:"transparent", border:"none", color:tab===k?"var(--ink)":"var(--ink-3)",
            borderBottom:tab===k?"2px solid var(--brand-2)":"2px solid transparent", cursor:"pointer", fontFamily:"inherit", marginBottom:-1
          }}>{l}</button>
        ))}
      </div>
      {tab==="upload" && (
        <div className="nt-tools-layout">
          <div className="panel" style={{padding:24}}>
            <input type="file" ref={fileInputRef} onChange={onPickFiles} accept=".npz,.npy" style={{display:"none"}}/>
            <div onDragOver={e=>e.preventDefault()} onDrop={onDrop}
                 style={{border:"2px dashed var(--line-3)", borderRadius:12, padding:"50px 30px", textAlign:"center", background:"var(--bg-1)", cursor:uploading?"wait":"pointer"}}
                 onClick={() => !uploading && fileInputRef.current?.click()}>
              <div style={{width:50, height:50, borderRadius:"50%", background:"var(--bg-3)", display:"grid", placeItems:"center", margin:"0 auto 16px", color:"var(--brand-2)"}}>
                <window.NTIcon name="download" size={24}/>
              </div>
              <div style={{fontSize:15, fontWeight:600, marginBottom:6}}>
                {uploading ? (lang==="vi"?"Đang tải lên...":"Uploading...")
                 : pendingFile ? `OK ${pendingFile.original_name}`
                 : (lang==="vi"?"Kéo thả file EEG vào đây":"Drop EEG file here")}
              </div>
              <div style={{fontSize:12, color:"var(--ink-3)", marginBottom:18}}>{lang==="vi"?"Nhận .npz/.npy đã convert. File EDF/BDF/FIF dùng script converter trước.":"Accepts converted .npz/.npy. Convert EDF/BDF/FIF before upload."}</div>
              <button className="btn btn-primary btn-sm" disabled={uploading} onClick={(e) => {e.stopPropagation(); fileInputRef.current?.click();}}>
                {pendingFile ? (lang==="vi"?"Chọn file khác":"Choose another") : (lang==="vi"?"Chọn file":"Choose file")}
              </button>
            </div>

            {error && (
              <div style={{marginTop:14, padding:12, background:"var(--bg-3)", borderLeft:"3px solid var(--hs)", borderRadius:6, fontSize:12, color:"var(--ink)"}}>
                <strong style={{color:"var(--hs)"}}>{lang==="vi"?"Lỗi:":"Error:"}</strong> {error}
              </div>
            )}

            {result && (
              <div style={{marginTop:18, padding:14, background:"var(--bg-2)", borderRadius:8, border:"1px solid var(--line-2)"}}>
                <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"Kết quả phân tích":"Analysis result"}</div>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10, fontSize:12}}>
                  <span className="mono" style={{color:"var(--ink-3)"}}>{result.windows} windows · model: {(result.model || "").split(/[\\\/]/).pop()}</span>
                  <span className={`tag ${modeFromResult(result.overall).toLowerCase()}`}>
                    {modeFromResult(result.overall)}
                  </span>
                </div>
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginBottom:10}}>
                  Source: {result.source?.mode || "uploaded_file"} · {result.source?.channel_count || "?"}ch · {result.source?.fs || "?"}Hz
                  {result.source?.preview_limited ? ` · preview ${Number(result.source.analysis_duration_sec || 0).toFixed(0)}s/${Number(result.source.duration_sec || 0).toFixed(0)}s` : ""} · Research use only
                </div>
                {Object.entries(probsFromOverall(result.overall)).map(([k, v]) => {
                  const accent = k==="HS"?"var(--hs)":k==="IS"?"var(--is)":"var(--ns)";
                  return (
                    <div key={k} style={{display:"grid", gridTemplateColumns:"40px 1fr 50px", gap:10, alignItems:"center", marginBottom:6, fontSize:12}}>
                      <span className="mono" style={{color:"var(--ink-3)"}}>{k}</span>
                      <div style={{height:6, background:"var(--bg-3)", borderRadius:3, overflow:"hidden"}}>
                        <div style={{width:(v*100)+"%", height:"100%", background:accent, boxShadow:`0 0 4px ${accent}`}}/>
                      </div>
                      <span className="mono" style={{textAlign:"right", color:accent}}>{(v*100).toFixed(1)}%</span>
                    </div>
                  );
                })}
                <div style={{fontSize:11.5, color:"var(--ink-3)", marginTop:10, fontFamily:"var(--font-mono)"}}>
                  SQI mean: {result.overall.sqi.toFixed(3)} · latest: {result.latest.pred_class} @ t={result.latest.t_end_sec.toFixed(1)}s
                </div>
              </div>
            )}

            <div style={{marginTop:18}}>
              <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"File gần đây":"Recent files"}</div>
              {recent.length === 0 && (
                <div style={{padding:12, color:"var(--ink-3)", fontSize:12}}>{lang==="vi"?"Chưa có file nào":"No files yet"}</div>
              )}
              {recent.map((f, i) => {
                const probs = probsFromOverall(f.overall);
                const d = modeFromResult(f.overall);
                const pct = Number(probs[d] || 0);
                return (
                  <div key={i} style={{display:"grid", gridTemplateColumns:"1fr 130px 110px 90px", alignItems:"center", padding:"11px 0", borderBottom:i===recent.length-1?"none":"1px solid var(--line)", fontSize:12, gap:14}}>
                    <div className="mono" style={{color:"var(--ink)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}} title={f.original_name}>{f.original_name}</div>
                    <div className="mono" style={{color:"var(--ink-3)", fontSize:11}}>{fmtSize(f.size_bytes)} · {relativeTime(f.ts)}</div>
                    <div><span className={`tag ${d.toLowerCase()}`}>{t.severityShort[d]} · {(pct*100).toFixed(0)}%</span></div>
                    <div style={{textAlign:"right"}}>
                      <button className="btn btn-sm btn-ghost" style={{padding:"3px 7px"}} onClick={() => runInference({upload_id:f.upload_id, original_name:f.original_name, size_bytes:f.size_bytes})}>
                        {lang==="vi"?"Chạy lại":"Re-run"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="panel" style={{padding:18}}>
            <div className="stat-lbl" style={{marginBottom:12}}>{lang==="vi"?"Thông tin bệnh nhân":"Patient information"}</div>
            <div style={{display:"grid", gap:10, marginBottom:18}}>
              <label style={{display:"grid", gap:5, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Họ tên *":"Full name *"}</span>
                <input value={patientForm.full_name} onChange={e => setPatientField("full_name", e.target.value)} placeholder={lang==="vi"?"Nhập tên bệnh nhân":"Enter patient name"}/>
              </label>
              <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>MRN</span>
                  <input value={patientForm.mrn} onChange={e => setPatientField("mrn", e.target.value)} placeholder="MRN"/>
                </label>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Giường":"Bed"}</span>
                  <input value={patientForm.bed} onChange={e => setPatientField("bed", e.target.value)} placeholder="ED-01"/>
                </label>
              </div>
              <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Giới tính":"Gender"}</span>
                  <select value={patientForm.gender} onChange={e => setPatientField("gender", e.target.value)}>
                    <option value="">{lang==="vi"?"-- chọn --":"-- select --"}</option>
                    <option value="M">{lang==="vi"?"Nam":"Male"}</option>
                    <option value="F">{lang==="vi"?"Nữ":"Female"}</option>
                    <option value="O">{lang==="vi"?"Khác":"Other"}</option>
                  </select>
                </label>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Onset phút trước":"Onset min ago"}</span>
                  <input type="number" min="0" value={patientForm.onset_minutes} onChange={e => setPatientField("onset_minutes", e.target.value)} placeholder="45"/>
                </label>
              </div>
              <label style={{display:"grid", gap:5, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Triệu chứng / lý do vào viện":"Symptoms / chief complaint"}</span>
                <input value={patientForm.symptoms} onChange={e => setPatientField("symptoms", e.target.value)} placeholder={lang==="vi"?"Yếu nửa người, nói khó...":"Weakness, dysarthria..."}/>
              </label>
              <label style={{display:"grid", gap:5, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Tiền sử":"History"}</span>
                <input value={patientForm.medical_history} onChange={e => setPatientField("medical_history", e.target.value)} placeholder={lang==="vi"?"THA, ĐTĐ...":"HTN, diabetes..."}/>
              </label>
              <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10}}>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Thuốc đang dùng":"Medications"}</span>
                  <input value={patientForm.medications} onChange={e => setPatientField("medications", e.target.value)} placeholder="Aspirin, statin"/>
                </label>
                <label style={{display:"grid", gap:5, fontSize:12}}>
                  <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Dị ứng":"Allergies"}</span>
                  <input value={patientForm.allergies} onChange={e => setPatientField("allergies", e.target.value)} placeholder={lang==="vi"?"Không ghi nhận":"NKDA"}/>
                </label>
              </div>
              <label style={{display:"grid", gap:5, fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{lang==="vi"?"Ghi chú":"Notes"}</span>
                <input value={patientForm.notes} onChange={e => setPatientField("notes", e.target.value)} placeholder={lang==="vi"?"Ghi chú thêm":"Additional notes"}/>
              </label>
            </div>

            <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Cấu hình phân tích":"Analysis config"}</div>
            {[
              [lang==="vi"?"Cửa sổ entropy":"Entropy window", "1.0 s"],
              [lang==="vi"?"Bước":"Step", "0.5 s"],
              [lang==="vi"?"Bandpass":"Bandpass", "1.0–35 Hz"],
              ["Notch", "50 Hz"],
              [lang==="vi"?"Reference":"Reference", "CAR"],
              [lang==="vi"?"Đặc trưng":"Features", "ApEn + FuEn + MFDFA + SQI"],
              [lang==="vi"?"Mô hình":"Model", "LightGBM"],
            ].map(([k, v], i) => (
              <div key={i} style={{display:"flex", justifyContent:"space-between", padding:"8px 0", borderBottom:i===6?"none":"1px solid var(--line)", fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{k}</span>
                <span className="mono" style={{color:"var(--ink)"}}>{v}</span>
              </div>
            ))}
            <button className="btn btn-primary btn-sm" disabled={!pendingFile || running || uploading || !patientForm.full_name.trim()}
                    onClick={() => pendingFile && runInference(pendingFile)}
                    style={{width:"100%", marginTop:18, justifyContent:"center"}}>
              {running ? (lang==="vi"?"Đang phân tích...":"Analysing...")
               : !pendingFile ? (lang==="vi"?"Hãy chọn file trước":"Pick a file first")
               : !patientForm.full_name.trim() ? (lang==="vi"?"Nhập thông tin bệnh nhân":"Enter patient info")
               : (lang==="vi"?"Bắt đầu phân tích":"Start analysis")}
            </button>
          </div>
        </div>
      )}
      {tab==="replay" && (
        <div className="nt-tools-layout">
          <div className="panel" style={{padding:0}}>
            <div className="panel-header">
              <div className="title"><window.NTIcon name="setup" size={13}/><span>{lang==="vi"?"Replay EEG đã chuẩn hóa":"Curated EEG replay cases"}</span></div>
              <span className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{replayCases.length} cases</span>
            </div>
            {replayState.loading && <div style={{padding:24, color:"var(--ink-3)", fontSize:12}}>Loading replay cases…</div>}
            {replayState.error && <div style={{padding:24, color:"var(--hs)", fontSize:12}}>Replay cases unavailable: {replayState.error.message}</div>}
            {!replayState.loading && !replayState.error && replayCases.length === 0 && (
              <div style={{padding:24, color:"var(--ink-3)", fontSize:12}}>{lang==="vi"?"Không có case replay":"No replay cases"}</div>
            )}
            <div style={{padding:"6px 18px 18px"}}>
              {replayCases.map((c, idx) => {
                return (
                  <div key={`${c.source}:${c.id}`} style={{display:"grid", gridTemplateColumns:"1fr 110px 88px 86px", gap:12, alignItems:"center", padding:"12px 0", borderBottom:"1px solid var(--line)", fontSize:12}}>
                    <div style={{minWidth:0}}>
                      <div className="mono" style={{overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", color:"var(--ink)"}} title={c.id}>{`Replay case ${idx + 1}`}</div>
                      <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginTop:3}}>{c.source} · {c.id}</div>
                    </div>
                    <span className="tag" style={{justifySelf:"start"}}>{lang==="vi"?"chưa biết":"unknown"}</span>
                    <div className="mono" style={{fontSize:11, color:"var(--ink-3)", textAlign:"right"}}>{fmtSize(c.size_bytes)}</div>
                    <button className="btn btn-sm btn-primary" style={{padding:"4px 9px", justifyContent:"center"}}
                            disabled={running}
                            onClick={() => runReplayCase(c)}>
                      {running ? "…" : (lang==="vi"?"Chạy":"Run")}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="panel" style={{padding:18}}>
            <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Replay status":"Replay status"}</div>
            {[
              ["Total cases", replayCases.length],
              [lang==="vi"?"Nhãn hiển thị trước":"Pre-run labels", lang==="vi"?"Ẩn":"Hidden"],
              [lang==="vi"?"Nguồn đo":"Source", lang==="vi"?"File replay/raw":"Replay/raw files"],
              [lang==="vi"?"Kết quả":"Result", lang==="vi"?"Chỉ sau khi chạy model":"Only after model run"],
            ].map(([k, v], i) => (
              <div key={k} style={{display:"flex", justifyContent:"space-between", padding:"8px 0", borderBottom:i===3?"none":"1px solid var(--line)", fontSize:12}}>
                <span style={{color:"var(--ink-3)"}}>{k}</span>
                <span className="mono" style={{color:"var(--ink)"}}>{v}</span>
              </div>
            ))}
            <div style={{fontSize:11.5, color:"var(--ink-3)", lineHeight:1.55, marginTop:14}}>
              {lang==="vi"
                ? "HS replay dùng các đoạn UCLH ICH đã convert. Kết quả dùng cho demo nghiên cứu, chưa phải claim lâm sàng."
                : "HS replay uses converted UCLH ICH segments. Results are research demo evidence, not clinical claims."}
            </div>
            {error && (
              <div style={{marginTop:14, padding:12, background:"var(--bg-3)", borderLeft:"3px solid var(--hs)", borderRadius:6, fontSize:12, color:"var(--ink)"}}>
                <strong style={{color:"var(--hs)"}}>{lang==="vi"?"Lỗi:":"Error:"}</strong> {error}
              </div>
            )}
            {result && (
              <div style={{marginTop:18, padding:14, background:"var(--bg-2)", borderRadius:8, border:"1px solid var(--line-2)"}}>
                <div className="stat-lbl" style={{marginBottom:10}}>{lang==="vi"?"Kết quả replay":"Replay result"}</div>
                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10, fontSize:12}}>
                  <span className="mono" style={{color:"var(--ink-3)"}}>{result.windows} windows · {(result.model || "").split(/[\\\/]/).pop()}</span>
                  <span className={`tag ${modeFromResult(result.overall).toLowerCase()}`}>
                    {modeFromResult(result.overall)}
                  </span>
                </div>
                {Object.entries(probsFromOverall(result.overall)).map(([k, v]) => {
                  const accent = k==="HS"?"var(--hs)":k==="IS"?"var(--is)":"var(--ns)";
                  return (
                    <div key={k} style={{display:"grid", gridTemplateColumns:"32px 1fr 46px", gap:8, alignItems:"center", marginBottom:6, fontSize:12}}>
                      <span className="mono" style={{color:"var(--ink-3)"}}>{k}</span>
                      <div style={{height:6, background:"var(--bg-3)", borderRadius:3, overflow:"hidden"}}>
                        <div style={{width:(v*100)+"%", height:"100%", background:accent}}/>
                      </div>
                      <span className="mono" style={{textAlign:"right", color:accent}}>{(v*100).toFixed(0)}%</span>
                    </div>
                  );
                })}
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)", marginTop:10}}>
                  {result.source?.mode || "replay_case"} · SQI {result.overall.sqi.toFixed(3)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.InsightsScreen = function InsightsScreen({frame, t, lang}) {
  const metricsState = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/research/metrics"), [])
    : { data: null, loading: false, error: null };
  const research = metricsState.data || {};
  const conditions = Array.isArray(research.conditions) ? research.conditions : [];
  const dataset = research.dataset || {};
  const patientCounts = dataset.patient_label_counts || {};
  const best = conditions.slice().sort((a, b) => (b.macro_f1 || 0) - (a.macro_f1 || 0))[0];
  const bestSqi = conditions.find(c => c.key === "apfu_mfdfa_sqi")
    || conditions.find(c => c.key === "apfu_sqi")
    || best;
  const exploratoryHs = research.exploratory_datasets?.hemorrhagic || {};
  const threeClass = research.exploratory_results?.three_class || {};
  const threeConditions = Array.isArray(threeClass.conditions) ? threeClass.conditions : [];
  const threeComparisons = Array.isArray(threeClass.paired_comparisons) ? threeClass.paired_comparisons : [];
  const threeDataset = threeClass.dataset || {};
  const threePatients = threeDataset.patient_label_counts || {};
  const mfdfaTrend = threeComparisons[0] || null;
  const hsQc = research.qc?.hemorrhagic || {};
  const qcRows = Array.isArray(hsQc.rows) ? hsQc.rows : [];
  const evidenceBadges = [
    {label:"NS/IS cohort", tone:"ns", body:`${patientCounts["0"] || 0} NS / ${patientCounts["1"] || 0} IS`},
    {label:"Macro-F1", tone:"ns", body: bestSqi ? Number(bestSqi.macro_f1 || 0).toFixed(3) : "pending"},
    {label:"Patient-F1 / AUC", tone:"is", body: bestSqi ? `${Number(bestSqi.patient_macro_f1 || 0).toFixed(3)} / ${Number(bestSqi.auc || 0).toFixed(3)}` : "pending"},
    {label:"HS exploratory", tone:"hs", body:`${exploratoryHs.n_patients || 0} patients; +1 for 5-fold`},
  ];
  if (true) {
    return (
      <div className="nt-insights-grid" style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
        <div className="panel" style={{padding:16, gridColumn:"1 / -1", borderLeft:"3px solid var(--brand-2)"}}>
          <div style={{display:"flex", alignItems:"center", gap:10, flexWrap:"wrap"}}>
            <span className="tag ns">Validated scope</span>
            <div style={{fontSize:13, color:"var(--ink-2)", lineHeight:1.5}}>
              {lang==="vi"
                ? "Bằng chứng hiện tại được trình bày như binary NS/IS. HS chỉ là exploratory 4 bệnh nhân và chưa validated 3-class."
                : "Current validated evidence is binary NS/IS. HS is exploratory with 4 patients and is not validated for 3-class use."}
            </div>
          </div>
        </div>
        <div className="panel" style={{padding:18, gridColumn:"1 / -1"}}>
          <div className="stat-lbl" style={{marginBottom:12}}>{lang==="vi"?"Trạng thái bằng chứng":"Evidence status"}</div>
          <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(160px, 1fr))", gap:10}}>
            {evidenceBadges.map((b) => (
              <div key={b.label} style={{padding:12, background:"var(--bg-3)", border:"1px solid var(--line-2)", borderRadius:6}}>
                <span className={`tag ${b.tone}`} style={{marginBottom:8}}>{b.label}</span>
                <div className="mono" style={{fontSize:12, color:"var(--ink-2)", marginTop:8}}>{b.body}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Bằng chứng ablation":"Ablation evidence"}</div>
          {metricsState.loading && <div style={{fontSize:12, color:"var(--ink-3)"}}>Loading metrics...</div>}
          {metricsState.error && <div style={{fontSize:12, color:"var(--hs)"}}>Metrics unavailable: {metricsState.error.message}</div>}
          <div style={{display:"grid", gap:8}}>
            {conditions.map((c) => (
              <div key={c.key} style={{display:"grid", gridTemplateColumns:"1fr 70px 70px 70px", gap:10, alignItems:"center", padding:"9px 10px", background:"var(--bg-3)", border:"1px solid var(--line-2)", borderRadius:6}}>
                <div>
                  <div style={{fontSize:12.5, fontWeight:600}}>{c.label}</div>
                  <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{c.n_features} features</div>
                </div>
                <div className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>F1 {Number(c.macro_f1 || 0).toFixed(3)}</div>
                <div className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>AUC {Number(c.auc || 0).toFixed(3)}</div>
                <div className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>ECE {Number(c.ece || 0).toFixed(3)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Validation hiện tại":"Current validation"}</div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
            {[
              ["Task", research.task || "binary"],
              ["Patients", dataset.n_patients || "—"],
              ["Best condition", bestSqi ? bestSqi.label : "—"],
              ["ECE", bestSqi ? Number(bestSqi.ece || 0).toFixed(4) : "—"],
            ].map(([k, v]) => (
              <div key={k} style={{padding:12, background:"var(--bg-3)", borderRadius:6, border:"1px solid var(--line-2)"}}>
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{k}</div>
                <div style={{fontSize:16, fontWeight:600, marginTop:5}}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{marginTop:14, fontSize:11.5, color:"var(--ink-3)", lineHeight:1.55}}>
            {(research.limitations || []).map((x, i) => <div key={i}>• {x}</div>)}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Cohort HS exploratory":"Exploratory HS cohort"}</div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12}}>
            {[
              ["HS patients", exploratoryHs.available ? exploratoryHs.n_patients : "—"],
              ["HS windows", exploratoryHs.available ? exploratoryHs.n_windows : "—"],
              ["HS SQI mean", exploratoryHs.sqi_mean != null ? Number(exploratoryHs.sqi_mean).toFixed(3) : "—"],
              ["5-fold ready", exploratoryHs.validated_for_3class_cv ? "yes" : "not yet"],
            ].map(([k, v]) => (
              <div key={k} style={{padding:12, background:"var(--bg-3)", borderRadius:6, border:"1px solid var(--line-2)"}}>
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{k}</div>
                <div style={{fontSize:16, fontWeight:600, marginTop:5}}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{fontSize:11.5, color:"var(--ink-3)", marginTop:12, lineHeight:1.55}}>
            {lang==="vi"
              ? "Đã tích hợp P3, P5, P6A, P11 từ UCLH ICH. Cần thêm ít nhất 1 HS patient để dùng 5-fold CV như kế hoạch."
              : "P3, P5, P6A, and P11 UCLH ICH are integrated. One more HS patient is needed for the planned 5-fold CV."}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"3-class exploratory":"3-class exploratory"}</div>
          <div style={{display:"grid", gap:8}}>
            {threeConditions.map((c) => (
              <div key={c.key} style={{display:"grid", gridTemplateColumns:"1fr 70px 70px", gap:10, alignItems:"center", padding:"9px 10px", background:"var(--bg-3)", border:"1px solid var(--line-2)", borderRadius:6}}>
                <div>
                  <div style={{fontSize:12.5, fontWeight:600}}>{c.label}</div>
                  <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{c.n_features} features</div>
                </div>
                <div className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>F1 {Number(c.macro_f1 || 0).toFixed(3)}</div>
                <div className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>ptF1 {Number(c.patient_macro_f1 || 0).toFixed(3)}</div>
              </div>
            ))}
          </div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginTop:12}}>
            <div style={{padding:12, background:"var(--bg-3)", borderRadius:6, border:"1px solid var(--line-2)"}}>
              <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>Patients NS / IS / HS</div>
              <div style={{fontSize:16, fontWeight:600, marginTop:5}}>{threePatients["0"] || 0} / {threePatients["1"] || 0} / {threePatients["2"] || 0}</div>
            </div>
            <div style={{padding:12, background:"var(--bg-3)", borderRadius:6, border:"1px solid var(--line-2)"}}>
              <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>MFDFA delta</div>
              <div style={{fontSize:16, fontWeight:600, marginTop:5}}>{mfdfaTrend ? `+${Number(mfdfaTrend.mean_delta || 0).toFixed(3)}` : "—"}</div>
            </div>
          </div>
          <div style={{fontSize:11.5, color:"var(--ink-3)", marginTop:12, lineHeight:1.55}}>
            {mfdfaTrend
              ? `4-fold fast check: ${mfdfaTrend.verdict || "exploratory"}; p=${Number(mfdfaTrend.p_value || 0).toFixed(3)}.`
              : "3-class exploratory result not available yet."}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"QC hemorrhagic":"Hemorrhagic QC"}</div>
          <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:12}}>
            {[
              ["Retained windows", hsQc.total_retained_windows || "—"],
              ["QC SQI mean", hsQc.sqi_mean != null ? Number(hsQc.sqi_mean).toFixed(3) : "—"],
              ["Amplitude warnings", hsQc.high_amplitude_warning_count ?? "—"],
              ["QC patients", hsQc.n_patients || "—"],
            ].map(([k, v]) => (
              <div key={k} style={{padding:12, background:"var(--bg-3)", borderRadius:6, border:"1px solid var(--line-2)"}}>
                <div className="mono" style={{fontSize:10.5, color:"var(--ink-3)"}}>{k}</div>
                <div style={{fontSize:16, fontWeight:600, marginTop:5}}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{display:"grid", gap:6}}>
            {qcRows.slice(0, 4).map((row) => (
              <div key={row.patient_id} style={{display:"grid", gridTemplateColumns:"1fr 44px 52px 52px", gap:8, alignItems:"center", fontSize:11.5, padding:"6px 0", borderBottom:"1px solid var(--line)"}}>
                <div className="mono" style={{overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", color:"var(--ink-2)"}}>{row.patient_id}</div>
                <div className="mono" style={{color:"var(--ink-3)", textAlign:"right"}}>{row.retained_windows}</div>
                <div className="mono" style={{color:"var(--ink-3)", textAlign:"right"}}>{Number(row.sqi_mean || 0).toFixed(2)}</div>
                <div style={{textAlign:"right"}}><span className={`tag ${row.high_amplitude_warning ? "is" : "ns"}`} style={{fontSize:10}}>{row.high_amplitude_warning ? "amp" : "ok"}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{t.live.multifractal}</div>
          <div style={{minHeight:170, display:"grid", placeItems:"center", textAlign:"center", color:"var(--ink-3)", fontSize:12, lineHeight:1.55, padding:18}}>
            {lang==="vi"
              ? "Chưa có phổ đa fractal của phiên hiện tại. Mục này chỉ hiển thị khi backend trả metric thật từ file/phiên EEG đã phân tích."
              : "No current-session multifractal spectrum is available. This panel only renders metrics returned by backend analysis."}
          </div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Giới hạn sử dụng":"Use limitation"}</div>
          <div style={{fontSize:12, color:"var(--ink-2)", lineHeight:1.65}}>
            NeuraTriage is positioned as uncertainty-aware EEG triage support. Results are replayable research evidence, not a clinical diagnostic claim.
          </div>
        </div>
      </div>
    );
  }
  return null;
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
window.ReportsScreen = function ReportsScreen({t, lang}) {
  function mondayIso(d = new Date()) {
    const x = new Date(d);
    const day = x.getDay() || 7;
    x.setDate(x.getDate() - day + 1);
    return x.toISOString().slice(0, 10);
  }
  const [refreshTick, setRefreshTick] = React.useState(0);
  const [generating, setGenerating] = React.useState(false);
  const [genError, setGenError] = React.useState(null);
  const [selectedPatientId, setSelectedPatientId] = React.useState(() => {
    try { return localStorage.getItem("neuratriage_selected_patient_id") || ""; } catch (e) { return ""; }
  });
  const [weekStart, setWeekStart] = React.useState(() => mondayIso());
  const [sendEmail, setSendEmail] = React.useState(false);

  const { data: reports, loading, error } = window.NTApi
    ? window.NTApi.useApi(
        () => window.NTApi.get(`/api/reports?limit=50${selectedPatientId ? `&patient_id=${encodeURIComponent(selectedPatientId)}` : ""}`),
        [refreshTick, selectedPatientId],
      )
    : { data: [], loading: false, error: null };

  const { data: patientsData } = window.NTApi
    ? window.NTApi.useApi(() => window.NTApi.get("/api/patients?limit=100"), [])
    : { data: null };
  const patientsRaw = patientsData?.items || patientsData || [];
  const patients = Array.isArray(patientsRaw) ? patientsRaw : [];
  const selectedPatient = patients.find(p => p.id === selectedPatientId) || patients[0] || null;
  const selectedId = selectedPatient?.id || "";
  const weeklyRecipients = (selectedPatient?.contacts || [])
    .filter(c => c.email && c.notify_weekly_report)
    .map(c => c.email);

  React.useEffect(() => {
    if (!patients.length) return;
    if (selectedPatientId && patients.some(p => p.id === selectedPatientId)) return;
    setSelectedPatientId(patients[0].id);
  }, [patientsData]);

  React.useEffect(() => {
    if (!selectedPatientId) return;
    try { localStorage.setItem("neuratriage_selected_patient_id", selectedPatientId); } catch (e) {}
  }, [selectedPatientId]);

  async function handleGenerate() {
    if (!selectedId) { setGenError(lang==="vi"?"Chưa chọn bệnh nhân.":"No patient selected."); return; }
    if (!weekStart) { setGenError(lang==="vi"?"Chưa chọn tuần.":"No week selected."); return; }
    setGenerating(true); setGenError(null);
    try {
      await window.NTApi.post("/api/reports/generate", {
        patient_id: selectedId,
        week_start: weekStart,
        send_email: sendEmail,
      });
      setRefreshTick(x => x + 1);
    } catch(e) {
      setGenError(e.message || "Generate failed");
    } finally { setGenerating(false); }
  }

  const list = Array.isArray(reports) ? reports : [];
  const latest = list[0];
  const latestSizeMB = latest && latest.pdf_size_bytes
    ? (latest.pdf_size_bytes / 1024 / 1024).toFixed(1) : "—";

  function statusColor(s) {
    if (s === "sent") return "var(--ns)";
    if (s === "failed") return "var(--hs)";
    if (s === "pdf_only") return "var(--brand-2)";
    if (s === "email_disabled") return "var(--is)";
    return "var(--ink-3)";
  }
  function statusLabel(s) {
    if (s === "sent") return lang === "vi" ? "Đã gửi" : "Sent";
    if (s === "failed") return lang === "vi" ? "Lỗi" : "Failed";
    if (s === "pdf_only") return lang === "vi" ? "Chỉ tạo PDF" : "PDF only";
    if (s === "email_disabled") return lang === "vi" ? "Chưa cấu hình email" : "Email disabled";
    if (s === "no_recipients") return lang === "vi" ? "Không có người nhận" : "No recipients";
    return s || "—";
  }

  async function handleDownloadPdf(reportId, weekLabel, patientName) {
    if (!window.NTApi) return;
    try {
      await window.NTApi.ensureAuth();
      const url = window.NTApi.baseUrl() + `/api/reports/${reportId}/pdf`;
      const resp = await fetch(url, {
        headers: { Authorization: "Bearer " + window.NTApi.getToken() },
      });
      if (!resp.ok) throw new Error("PDF not found");
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `neuratriage_${weekLabel}_${patientName || "report"}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setGenError("PDF download failed: " + e.message);
    }
  }

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto"}}>
      <div className="nt-kpi-grid">
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Báo cáo tự động":"Auto reports"}</div>
          <div className="stat-val">{lang==="vi"?"Mỗi T2 · 7:00":"Every Mon · 7am"}</div>
          <div className="stat-sub">{lang==="vi"?"PDF bắt buộc, SendGrid tùy chọn":"PDF required, SendGrid optional"}</div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Báo cáo gần nhất":"Latest report"}</div>
          <div className="stat-val">{latestSizeMB}<span className="unit">MB</span></div>
          <div className="stat-sub">{latest ? latest.week_label : "—"}</div>
        </div>
        <div className="panel" style={{padding:18}}>
          <div className="stat-lbl">{lang==="vi"?"Tổng báo cáo":"Total reports"}</div>
          <div className="stat-val">{list.length}</div>
          <div className="stat-sub">{weeklyRecipients.length} {lang==="vi"?"người nhận từ hồ sơ BN":"patient-contact recipients"}</div>
        </div>
      </div>

      <div className="panel nt-table-wrap" style={{padding:0}}>
        <div className="panel-header">
          <div className="title"><window.NTIcon name="reports" size={13}/><span>{lang==="vi"?"Lịch sử báo cáo":"Report history"}</span></div>
          <div style={{display:"flex", gap:8, alignItems:"center", flexWrap:"wrap", justifyContent:"flex-end"}}>
            {genError && <span style={{fontSize:11, color:"var(--hs)"}}>{genError}</span>}
            <select value={selectedPatientId} onChange={e => setSelectedPatientId(e.target.value)} style={{height:30, minWidth:190, fontSize:11}}>
              {patients.length === 0 && <option value="">{lang==="vi"?"Chưa có bệnh nhân":"No patients"}</option>}
              {patients.map(p => (
                <option key={p.id} value={p.id}>
                  {p.full_name}{p.bed ? ` · ${p.bed}` : ""}{p.mrn ? ` · ${p.mrn}` : ""}
                </option>
              ))}
            </select>
            <input type="date" value={weekStart} onChange={e => setWeekStart(e.target.value)} style={{height:30, width:136, fontSize:11}}/>
            <label style={{display:"flex", alignItems:"center", gap:6, fontSize:11, color:"var(--ink-2)", whiteSpace:"nowrap"}}>
              <input type="checkbox" checked={sendEmail} onChange={e => setSendEmail(e.target.checked)} style={{width:14, height:14}}/>
              {lang==="vi"?"Gửi email":"Email"}
            </label>
            <button className="btn btn-sm btn-primary" style={{fontSize:11}} onClick={handleGenerate} disabled={generating || !selectedId}>
              {generating ? "…" : (lang==="vi"?"+ Tạo báo cáo":"+ Generate")}
            </button>
            <button className="btn btn-sm btn-ghost" style={{fontSize:11}} onClick={() => setRefreshTick(x=>x+1)}>
              ↻ {lang==="vi"?"Làm mới":"Refresh"}
            </button>
          </div>
        </div>

        {loading && <div style={{padding:24, textAlign:"center", color:"var(--ink-3)", fontSize:12}}>Loading…</div>}
        {error && <div style={{padding:24, color:"var(--hs)", fontSize:12}}>Error loading reports</div>}
        {!loading && !error && list.length === 0 && (
          <div style={{padding:24, textAlign:"center", color:"var(--ink-3)", fontSize:12}}>
            {lang==="vi"
              ? "Chưa có báo cáo nào cho bệnh nhân/tuần đã chọn."
              : "No reports for the selected patient/week yet."}
          </div>
        )}
        {list.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                <th>{lang==="vi"?"Tuần":"Week"}</th>
                <th>{lang==="vi"?"Bệnh nhân":"Patient"}</th>
                <th>{lang==="vi"?"Phiên":"Sessions"}</th>
                <th>{lang==="vi"?"Cảnh báo":"Alerts"}</th>
                <th>Ack / Esc</th>
                <th>Status</th>
                <th>{lang==="vi"?"Người nhận":"Recipients"}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <td className="mono" style={{color:"var(--brand-2)"}}>{r.week_label}</td>
                  <td>{r.patient_name || "—"}</td>
                  <td className="mono">{r.session_count}</td>
                  <td className="mono">{r.alert_count}</td>
                  <td className="mono">{r.ack_count} / {r.escalation_count}</td>
                  <td><span style={{color:statusColor(r.status), fontSize:11.5}}>● {statusLabel(r.status)}</span></td>
                  <td className="mono" style={{fontSize:11, color:"var(--ink-2)"}}>
                    {(r.recipient_emails||[]).join(", ") || "—"}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-ghost"
                      style={{padding:"3px 7px"}}
                      disabled={!r.pdf_size_bytes}
                      onClick={() => handleDownloadPdf(r.id, r.week_label, r.patient_name)}
                    >
                      <window.NTIcon name="download" size={12}/>PDF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const THRESH_KEY = "nt_alert_thresholds";
const RECIP_KEY  = "nt_recipients";

function loadThresholds() {
  try { return JSON.parse(localStorage.getItem(THRESH_KEY)) || null; } catch(e) { return null; }
}
function saveThresholds(v) {
  try { localStorage.setItem(THRESH_KEY, JSON.stringify(v)); } catch(e) {}
}
function loadRecipients() {
  try { return JSON.parse(localStorage.getItem(RECIP_KEY)) || null; } catch(e) { return null; }
}
function saveRecipients(v) {
  try { localStorage.setItem(RECIP_KEY, JSON.stringify(v)); } catch(e) {}
}

// Global accessor used by ReportsScreen when generating reports
window.NTSettings = {
  getRecipientEmails: () => {
    const r = loadRecipients() || DEFAULT_RECIPIENTS;
    return r.map(x => x.email).filter(Boolean);
  },
};

const DEFAULT_THRESHOLDS = { ema_beta:"0.3", thr_high:"0.65", thr_low:"0.55", cooldown:"8.0", sqi_gate:"0.70" };
const DEFAULT_RECIPIENTS = [
  {role:"MD on-call", email:"", channels:["email"]},
  {role:"Family",     email:"", channels:["email"]},
  {role:"Admin",      email:"", channels:["email"]},
];

window.SettingsScreen = function SettingsScreen({t, lang, apiBase, onApiBaseChange}) {
  const { useState, useEffect } = React;

  const [connStatus, setConnStatus] = useState(null);
  const [connTesting, setConnTesting] = useState(false);
  const [reloadStatus, setReloadStatus] = useState(null);
  const [reloading, setReloading] = useState(false);

  const [thresh, setThresh] = useState(() => loadThresholds() || {...DEFAULT_THRESHOLDS});
  const [thrSaved, setThrSaved] = useState(false);

  const [recips, setRecips] = useState(() => loadRecipients() || DEFAULT_RECIPIENTS.map(r => ({...r})));
  const [editIdx, setEditIdx] = useState(null);
  const [editEmail, setEditEmail] = useState("");

  async function reloadModel() {
    if (!window.NTApi) return;
    setReloading(true); setReloadStatus(null);
    try {
      const data = await window.NTApi.post("/api/reload-model", {});
      setReloadStatus({ok:true, msg:`Loaded: ${(data.loaded||"").split(/[\\\/]/).pop()} · ${data.features} features`});
    } catch(e) {
      setReloadStatus({ok:false, msg: e.message || "Reload failed"});
    } finally { setReloading(false); }
  }

  async function testConnection() {
    setConnTesting(true); setConnStatus(null);
    try {
      const data = await window.NTApi.get("/api/health");
      setConnStatus({ok:true, msg: `${data.app} v${data.version}`});
    } catch(e) {
      setConnStatus({ok:false, msg: e.message || "Connection failed"});
    } finally { setConnTesting(false); }
  }

  function saveThresh() {
    saveThresholds(thresh);
    setThrSaved(true);
    setTimeout(() => setThrSaved(false), 1800);
  }

  function startEdit(i) { setEditIdx(i); setEditEmail(recips[i].email); }
  function commitEdit(i) {
    const next = recips.map((r, idx) => idx === i ? {...r, email:editEmail} : r);
    setRecips(next); saveRecipients(next); setEditIdx(null);
  }

  const thrFields = [
    ["EMA beta", "ema_beta"],
    [t.live.threshold + " (high)", "thr_high"],
    [t.live.threshold + " (low)", "thr_low"],
    [t.live.cooldown + " (s)", "cooldown"],
    ["SQI gate", "sqi_gate"],
  ];

  return (
    <div style={{padding:18, height:"calc(100vh - 54px)", overflowY:"auto", maxWidth:760}}>
      {/* Backend connection */}
      <div className="panel" style={{padding:18, marginBottom:14}}>
        <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Kết nối backend":"Backend connection"}</div>
        <div style={{display:"flex", gap:10, alignItems:"center", marginBottom:8}}>
          <input type="text" value={apiBase} onChange={e => onApiBaseChange(e.target.value)}
                 style={{flex:1}} placeholder="http://127.0.0.1:8501"/>
          <button className="btn btn-sm btn-primary" onClick={testConnection} disabled={connTesting}>
            {connTesting ? "…" : (lang==="vi"?"Kiểm tra":"Test")}
          </button>
        </div>
        {connStatus && (
          <div style={{fontSize:11.5, padding:"7px 10px", borderRadius:6, marginTop:6,
                       background: connStatus.ok ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                       color: connStatus.ok ? "var(--ok)" : "var(--hs)",
                       border: `1px solid ${connStatus.ok ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`}}>
            {connStatus.ok ? "OK " : "ERR "}{connStatus.msg}
          </div>
        )}
        <div style={{fontSize:11.5, color:"var(--ink-3)", marginTop:6}}>
          {lang==="vi"?"Để trống nếu chạy demo. Khi backend FastAPI chạy, dán URL đầy đủ.":"Leave empty for demo. When FastAPI backend runs, paste full URL."}
        </div>
      </div>

      {/* Alert thresholds */}
      <div className="panel" style={{padding:18, marginBottom:14}}>
        <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:14}}>
          <div className="stat-lbl">{lang==="vi"?"Cấu hình cảnh báo":"Alert configuration"}</div>
          <button className="btn btn-sm btn-primary" onClick={saveThresh}>
            {thrSaved ? (lang==="vi"?"Đã lưu":"Saved") : (lang==="vi"?"Lưu":"Save")}
          </button>
        </div>
        <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, fontSize:12.5}}>
          {thrFields.map(([label, key]) => (
            <div key={key} style={{display:"flex", flexDirection:"column", gap:4}}>
              <div style={{fontSize:11, color:"var(--ink-3)", textTransform:"uppercase", letterSpacing:"0.05em"}}>{label}</div>
              <input className="mono" type="number" step="0.01" value={thresh[key]}
                     onChange={e => setThresh(s => ({...s, [key]:e.target.value}))}
                     style={{width:"100%", boxSizing:"border-box", fontSize:12.5}}/>
            </div>
          ))}
        </div>
        <div style={{fontSize:11, color:"var(--ink-3)", marginTop:10}}>
          {lang==="vi"?"Lưu vào trình duyệt. Áp dụng cho hiển thị frontend; pipeline backend dùng config model.":"Saved in browser. Applied to frontend display; backend pipeline uses model config."}
        </div>
      </div>

      {/* Model management */}
      {window.NTApi && (
        <div className="panel" style={{padding:18, marginBottom:14}}>
          <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:14}}>
            <div className="stat-lbl">{lang==="vi"?"Quản lý mô hình":"Model management"}</div>
            <button className="btn btn-sm btn-primary" onClick={reloadModel} disabled={reloading}>
              {reloading ? "…" : (lang==="vi"?"Tải lại mô hình":"Reload model")}
            </button>
          </div>
          {reloadStatus && (
            <div style={{fontSize:11.5, padding:"7px 10px", borderRadius:6,
                         background: reloadStatus.ok ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                         color: reloadStatus.ok ? "var(--ok)" : "var(--hs)",
                         border: `1px solid ${reloadStatus.ok ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`}}>
              {reloadStatus.ok ? "OK " : "ERR "}{reloadStatus.msg}
            </div>
          )}
          <div style={{fontSize:11, color:"var(--ink-3)", marginTop:8}}>
            {lang==="vi"
              ? "Tải lại model.joblib từ disk sau khi train xong (không cần restart server)."
              : "Hot-reload model.joblib from disk after training completes — no server restart needed."}
          </div>
        </div>
      )}

      {/* Notification recipients */}
      <div className="panel" style={{padding:18, marginBottom:14}}>
        <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Người nhận thông báo":"Notification recipients"}</div>
        <div style={{fontSize:11.5, color:"var(--ink-3)", marginBottom:10, lineHeight:1.5}}>
          {lang==="vi"
            ? "Các email này chỉ lưu trong trình duyệt cho demo alert. Báo cáo PDF/email lấy người nhận từ patient contacts có notify_weekly_report."
            : "These browser-only entries are for alert demo display. PDF report emails use patient contacts with notify_weekly_report enabled."}
        </div>
        {recips.map((r, i) => (
          <div key={i} style={{padding:"11px 0", borderBottom:i===recips.length-1?"none":"1px solid var(--line)"}}>
            {editIdx === i ? (
              <div style={{display:"flex", gap:8, alignItems:"center"}}>
                <span style={{fontSize:12, fontWeight:500, minWidth:90}}>{r.role}</span>
                <input type="email" value={editEmail} onChange={e => setEditEmail(e.target.value)}
                       style={{flex:1, fontSize:12}} placeholder="email@example.com"/>
                <button className="btn btn-sm btn-primary" onClick={() => commitEdit(i)}>
                  {lang==="vi"?"Lưu":"Save"}
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => setEditIdx(null)}>x</button>
              </div>
            ) : (
              <div style={{display:"flex", alignItems:"center", gap:14}}>
                <div style={{flex:1}}>
                  <div style={{fontSize:12.5, fontWeight:500}}>{r.role}</div>
                  <div className="mono" style={{fontSize:11, color: r.email ? "var(--ink-3)" : "var(--ink-4)", marginTop:2}}>
                    {r.email || (lang==="vi"?"Chưa cấu hình":"Not configured")}
                  </div>
                </div>
                <div style={{display:"flex", gap:5}}>
                  {r.channels.map(c => <span key={c} className="tag" style={{fontSize:10}}>{c}</span>)}
                </div>
                <button className="btn btn-sm btn-ghost" onClick={() => startEdit(i)}>
                  {lang==="vi"?"Sửa":"Edit"}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Version */}
      <div className="panel" style={{padding:18}}>
        <div className="stat-lbl" style={{marginBottom:14}}>{lang==="vi"?"Phiên bản":"Version"}</div>
        <div className="mono" style={{fontSize:12, color:"var(--ink-2)", lineHeight:1.8}}>
          NeuraTriage EEG · v0.4.2<br/>
          Model: ApFu-MFDFA-TPELGBM-RT-v04<br/>
          Build: 2026-05-06 · {lang==="vi"?"Chế độ nghiên cứu":"Research mode"}
        </div>
      </div>
    </div>
  );
};
