from __future__ import annotations

import argparse
import html
import json
import math
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, urlparse


APP_TITLE = "EEG Stroke Research App"
DEFAULT_MODEL = r"C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\model_smoke.joblib"
DEFAULT_MANIFEST = r"C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\manifest.csv"
DEFAULT_EEG = r"C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\sub-01.npz"
DEFAULT_OUTPUT_DIR = r"C:\Users\Admin\eeg-stroke-app\out"

pipeline = None
pipeline_error: Optional[BaseException] = None


def import_pipeline():
    global pipeline, pipeline_error
    if pipeline is not None:
        return pipeline
    if pipeline_error is not None:
        raise RuntimeError(f"Pipeline import failed: {pipeline_error}")
    try:
        import eeg_stroke_pipeline as imported_pipeline

        pipeline = imported_pipeline
        return pipeline
    except BaseException as exc:  # Keep the app page alive if dependencies are missing.
        pipeline_error = exc
        raise RuntimeError(f"Pipeline import failed: {exc}") from exc


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def field(form: Dict[str, list[str]], name: str, default: str = "") -> str:
    value = form.get(name, [default])[0]
    return value.strip().strip('"').strip("'")


def parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def ensure_parent(path_text: str) -> None:
    if not path_text:
        return
    Path(path_text).expanduser().parent.mkdir(parents=True, exist_ok=True)


def json_default(obj: Any) -> Any:
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass
    return str(obj)


def format_cell(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, float) and math.isnan(value):
            return ""
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float):
            if math.isnan(value):
                return ""
            return f"{value:.4f}"
    except Exception:
        pass
    return str(value)


def frame_to_html(frame: Any, columns: Iterable[str], max_rows: int = 12) -> str:
    if frame is None or getattr(frame, "empty", True):
        return '<p class="muted">No rows.</p>'
    present = [col for col in columns if col in frame.columns]
    if not present:
        return '<p class="muted">No display columns.</p>'
    view = frame.loc[:, present].tail(max_rows)
    head = "".join(f"<th>{e(col)}</th>" for col in present)
    body_rows = []
    for _, row in view.iterrows():
        cells = "".join(f"<td>{e(format_cell(row[col]))}</td>" for col in present)
        body_rows.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def metric_grid(metrics: Dict[str, Any]) -> str:
    preferred = [
        "macro_f1",
        "balanced_accuracy",
        "macro_recall",
        "recall_nonstroke",
        "recall_ischemic",
        "recall_hemorrhagic",
        "auc_ovr",
        "log_loss",
        "brier_multiclass",
        "ece",
        "n_window_eval",
        "n_patient_eval",
    ]
    items = []
    for key in preferred:
        if key not in metrics:
            continue
        value = metrics[key]
        if isinstance(value, float):
            value_text = "nan" if math.isnan(value) else f"{value:.4f}"
        else:
            value_text = str(value)
        items.append(f'<div class="metric"><span>{e(key)}</span><strong>{e(value_text)}</strong></div>')
    return f'<div class="metrics">{"".join(items)}</div>'


def probability_bars(row: Any) -> str:
    names = [
        ("non-stroke", "p_nonstroke_smooth"),
        ("ischemic", "p_ischemic_smooth"),
        ("hemorrhagic", "p_hemorrhagic_smooth"),
    ]
    bars = []
    for label, column in names:
        value = row.get(column, float("nan")) if hasattr(row, "get") else float("nan")
        try:
            value = float(value)
        except Exception:
            value = float("nan")
        pct = 0.0 if math.isnan(value) else max(0.0, min(100.0, value * 100.0))
        bars.append(
            f"""
            <div class="prob-row">
              <span>{e(label)}</span>
              <div class="prob-track"><div class="prob-fill" style="width:{pct:.2f}%"></div></div>
              <strong>{pct:.1f}%</strong>
            </div>
            """
        )
    return f'<div class="prob-card">{"".join(bars)}</div>'


def load_trained_model(p: Any, model_path: str) -> Any:
    # Models saved by running eeg_stroke_pipeline.py as a script can reference
    # __main__.TrainedStrokeModel. Register aliases before joblib loads them.
    import __main__

    for name in ("PipelineConfig", "TemperatureScaler", "TrainedStrokeModel"):
        if hasattr(p, name):
            setattr(__main__, name, getattr(p, name))
    return p.TrainedStrokeModel.load(model_path)


def config_from_form(p: Any, form: Dict[str, list[str]]) -> Any:
    config_json = field(form, "config_json")
    if config_json:
        with open(config_json, "r", encoding="utf-8") as handle:
            cfg = p.PipelineConfig(**json.load(handle))
    else:
        cfg = p.PipelineConfig()
    n_trials = parse_int(field(form, "n_trials", str(cfg.n_trials)), cfg.n_trials)
    cfg.n_trials = max(1, n_trials)
    mfdfa_variant = field(form, "mfdfa_variant", cfg.mfdfa_variant)
    if mfdfa_variant:
        cfg.mfdfa_variant = mfdfa_variant
    return cfg


def run_infer(form: Dict[str, list[str]]) -> str:
    p = import_pipeline()
    model_path = field(form, "model_path", DEFAULT_MODEL)
    eeg_path = field(form, "eeg_path", DEFAULT_EEG)
    output_csv = field(form, "output_csv", str(Path(DEFAULT_OUTPUT_DIR) / "inference.csv"))
    patient_id = field(form, "patient_id", "unknown")
    label = field(form, "label", "non-stroke")

    trained = load_trained_model(p, model_path)
    cfg = p.PipelineConfig(**trained.config)
    data, channels, fs_in_file = p.load_array_file(eeg_path)
    fs = fs_in_file or cfg.fs
    record = p.EEGRecord(
        patient_id=patient_id,
        label=p.parse_label(label),
        data=p.reorder_to_target_channels(data, channels, cfg.channels),
        channels=list(cfg.channels),
        fs=float(fs),
    )
    frame = p.run_offline_inference(trained, record, cfg)
    if output_csv:
        ensure_parent(output_csv)
        frame.to_csv(output_csv, index=False)

    result = '<section class="result"><h2>Inference Result</h2>'
    if frame.empty:
        result += '<p class="bad">No windows were produced. Check signal length and SQI threshold.</p>'
    else:
        last = frame.tail(1).iloc[0]
        result += f"""
        <div class="summary-line">
          <div><span class="label">Latest class</span><strong>{e(last.get("pred_class", ""))}</strong></div>
          <div><span class="label">Latest t_end_sec</span><strong>{e(format_cell(last.get("t_end_sec", "")))}</strong></div>
          <div><span class="label">Latest SQI</span><strong>{e(format_cell(last.get("sqi_total", "")))}</strong></div>
        </div>
        {probability_bars(last)}
        """
        result += frame_to_html(
            frame,
            [
                "t_end_sec",
                "sqi_total",
                "pred_class",
                "p_nonstroke_smooth",
                "p_ischemic_smooth",
                "p_hemorrhagic_smooth",
            ],
        )
    if output_csv:
        result += f'<p class="muted">CSV: {e(output_csv)}</p>'
    return result + "</section>"


def run_evaluate(form: Dict[str, list[str]]) -> str:
    p = import_pipeline()
    model_path = field(form, "eval_model_path", DEFAULT_MODEL)
    manifest_path = field(form, "eval_manifest_path", DEFAULT_MANIFEST)
    output_csv = field(form, "eval_output_csv", str(Path(DEFAULT_OUTPUT_DIR) / "evaluation_predictions.csv"))

    trained = load_trained_model(p, model_path)
    cfg = p.PipelineConfig(**trained.config)
    records = p.load_records_from_manifest(manifest_path, cfg)
    feature_table = p.build_feature_table(records, cfg)
    probs = trained.predict_proba_from_feature_frame(feature_table)
    metrics = p.evaluate_probabilities_with_patient_aggregation(
        feature_table["patient_id"].to_numpy(),
        feature_table["label"].to_numpy(dtype=int),
        probs,
    )
    if output_csv:
        ensure_parent(output_csv)
        out = feature_table[["patient_id", "label", "t_end_sec"]].copy()
        out["p_nonstroke"] = probs[:, 0]
        out["p_ischemic"] = probs[:, 1]
        out["p_hemorrhagic"] = probs[:, 2]
        out.to_csv(output_csv, index=False)

    return f"""
    <section class="result">
      <h2>Evaluation Result</h2>
      {metric_grid(metrics)}
      <details><summary>Metrics JSON</summary><pre>{e(json.dumps(metrics, indent=2, default=json_default))}</pre></details>
      <p class="muted">Windows: {len(feature_table)} | Patients: {feature_table["patient_id"].nunique()}</p>
      <p class="muted">CSV: {e(output_csv)}</p>
    </section>
    """


def run_train(form: Dict[str, list[str]]) -> str:
    p = import_pipeline()
    manifest_path = field(form, "train_manifest_path", DEFAULT_MANIFEST)
    output_model = field(form, "output_model", str(Path(DEFAULT_OUTPUT_DIR) / "model.joblib"))
    cfg = config_from_form(p, form)

    records = p.load_records_from_manifest(manifest_path, cfg)
    feature_table = p.build_feature_table(records, cfg)
    trained, metadata = p.train_final_model(feature_table, cfg)
    ensure_parent(output_model)
    trained.save(output_model)

    return f"""
    <section class="result">
      <h2>Training Result</h2>
      <div class="summary-line">
        <div><span class="label">Model</span><strong>{e(output_model)}</strong></div>
        <div><span class="label">Windows</span><strong>{e(metadata.get("n_windows"))}</strong></div>
        <div><span class="label">Patients</span><strong>{e(metadata.get("n_patients"))}</strong></div>
      </div>
      <details open><summary>Training metadata</summary><pre>{e(json.dumps(metadata, indent=2, default=json_default))}</pre></details>
    </section>
    """


def run_cv(form: Dict[str, list[str]]) -> str:
    p = import_pipeline()
    manifest_path = field(form, "cv_manifest_path", DEFAULT_MANIFEST)
    cfg = config_from_form(p, form)
    records = p.load_records_from_manifest(manifest_path, cfg)
    feature_table = p.build_feature_table(records, cfg)
    summary = p.cross_validate_pipeline(feature_table, cfg)
    return f"""
    <section class="result">
      <h2>Cross-Validation Result</h2>
      {metric_grid(summary)}
      <details open><summary>CV summary JSON</summary><pre>{e(json.dumps(summary, indent=2, default=json_default))}</pre></details>
    </section>
    """


def pipeline_status() -> str:
    try:
        p = import_pipeline()
        count = len(getattr(p, "ALL_FEATURES", []))
        return f'<span class="status ok">Pipeline ready | {count} features</span>'
    except Exception as exc:
        return f'<span class="status bad">Pipeline unavailable | {e(exc)}</span>'


def page(result_html: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{APP_TITLE}</title>
  <style>
    :root {{
      --bg: #f6f7f4;
      --panel: #ffffff;
      --line: #d9ded7;
      --text: #20231f;
      --muted: #677069;
      --green: #1f7a5a;
      --red: #b43d3d;
      --amber: #b87521;
      --blue: #2d6f91;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      min-height: 270px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfa;
    }}
    .hero-copy {{
      padding: 34px clamp(20px, 5vw, 64px);
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 16px;
    }}
    h1, h2, h3 {{ margin: 0; line-height: 1.15; }}
    h1 {{ font-size: 2.4rem; max-width: 760px; }}
    h2 {{ font-size: 1.15rem; }}
    h3 {{ font-size: 1rem; }}
    p {{ line-height: 1.55; }}
    .subtitle {{ color: var(--muted); max-width: 760px; margin: 0; }}
    .wave-panel {{
      min-height: 270px;
      border-left: 1px solid var(--line);
      background: #111411;
      position: relative;
      overflow: hidden;
    }}
    canvas {{ width: 100%; height: 100%; display: block; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 24px auto 48px; }}
    .status-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }}
    .status {{ border: 1px solid var(--line); background: var(--panel); padding: 8px 10px; border-radius: 8px; font-size: 0.92rem; }}
    .ok {{ color: var(--green); }}
    .bad {{ color: var(--red); }}
    .workspace {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .panel, .result, .research {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    form {{ display: grid; gap: 12px; margin-top: 14px; }}
    label {{ display: grid; gap: 6px; color: var(--muted); font-size: 0.9rem; }}
    input, select {{
      width: 100%;
      border: 1px solid #cbd2ca;
      border-radius: 6px;
      padding: 10px 11px;
      font: inherit;
      color: var(--text);
      background: #fff;
      min-height: 40px;
    }}
    button {{
      justify-self: start;
      min-height: 40px;
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      background: var(--green);
      cursor: pointer;
    }}
    button.secondary {{ background: var(--blue); }}
    button.warning {{ background: var(--amber); }}
    .result {{ margin-bottom: 18px; border-left: 4px solid var(--green); }}
    .summary-line {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }}
    .summary-line > div, .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfa;
      min-width: 0;
    }}
    .label, .metric span {{
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      margin-bottom: 5px;
      overflow-wrap: anywhere;
    }}
    strong {{ overflow-wrap: anywhere; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }}
    .prob-card {{ display: grid; gap: 9px; margin: 14px 0; }}
    .prob-row {{ display: grid; grid-template-columns: 110px minmax(120px, 1fr) 64px; gap: 10px; align-items: center; }}
    .prob-track {{ height: 12px; background: #e8ece7; border-radius: 6px; overflow: hidden; }}
    .prob-fill {{ height: 100%; background: linear-gradient(90deg, var(--green), var(--amber)); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }}
    th {{ background: #eef2ed; color: #3f4942; }}
    .muted {{ color: var(--muted); }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #111411;
      color: #f1f5ef;
      padding: 12px;
      border-radius: 8px;
      overflow-x: auto;
    }}
    details {{ margin-top: 12px; }}
    .research {{ margin-top: 16px; }}
    .research-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .step {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfa;
      min-height: 118px;
    }}
    .step b {{ display: block; margin-bottom: 7px; }}
    .step span {{ color: var(--muted); font-size: 0.9rem; line-height: 1.4; }}
    @media (max-width: 900px) {{
      header, .workspace, .summary-line, .metrics, .research-grid {{ grid-template-columns: 1fr; }}
      .wave-panel {{ border-left: 0; border-top: 1px solid var(--line); }}
      h1 {{ font-size: 2rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="hero-copy">
      <h1>EEG Stroke Research App</h1>
      <p class="subtitle">ApFu entropy, MFDFA, SQI gating, LightGBM/TPE, calibration, and offline inference in one local workspace.</p>
    </div>
    <div class="wave-panel"><canvas id="wave"></canvas></div>
  </header>
  <main>
    <div class="status-row">{pipeline_status()}</div>
    {result_html}
    <section class="workspace">
      <div class="panel">
        <h2>Offline Inference</h2>
        <form method="post" action="/infer">
          <label>Model path<input name="model_path" value="{e(DEFAULT_MODEL)}"></label>
          <label>EEG .npz/.npy path<input name="eeg_path" value="{e(DEFAULT_EEG)}"></label>
          <label>Patient ID<input name="patient_id" value="demo-patient"></label>
          <label>Known label<select name="label"><option>non-stroke</option><option>ischemic</option><option>hemorrhagic</option></select></label>
          <label>Output CSV<input name="output_csv" value="{e(str(Path(DEFAULT_OUTPUT_DIR) / 'inference.csv'))}"></label>
          <button type="submit">Run inference</button>
        </form>
      </div>
      <div class="panel">
        <h2>Evaluate Model</h2>
        <form method="post" action="/evaluate">
          <label>Model path<input name="eval_model_path" value="{e(DEFAULT_MODEL)}"></label>
          <label>Manifest CSV<input name="eval_manifest_path" value="{e(DEFAULT_MANIFEST)}"></label>
          <label>Output CSV<input name="eval_output_csv" value="{e(str(Path(DEFAULT_OUTPUT_DIR) / 'evaluation_predictions.csv'))}"></label>
          <button class="secondary" type="submit">Run evaluation</button>
        </form>
      </div>
      <div class="panel">
        <h2>Train Model</h2>
        <form method="post" action="/train">
          <label>Manifest CSV<input name="train_manifest_path" value="{e(DEFAULT_MANIFEST)}"></label>
          <label>Output model<input name="output_model" value="{e(str(Path(DEFAULT_OUTPUT_DIR) / 'model.joblib'))}"></label>
          <label>Config JSON<input name="config_json" placeholder="optional"></label>
          <label>Optuna trials<input name="n_trials" value="5"></label>
          <label>MFDFA variant<select name="mfdfa_variant"><option>mfdfa</option><option>mfdfai</option></select></label>
          <button class="warning" type="submit">Train</button>
        </form>
      </div>
      <div class="panel">
        <h2>Cross-Validation</h2>
        <form method="post" action="/cv">
          <label>Manifest CSV<input name="cv_manifest_path" value="{e(DEFAULT_MANIFEST)}"></label>
          <label>Config JSON<input name="config_json" placeholder="optional"></label>
          <label>Optuna trials<input name="n_trials" value="3"></label>
          <label>MFDFA variant<select name="mfdfa_variant"><option>mfdfa</option><option>mfdfai</option></select></label>
          <button class="secondary" type="submit">Run CV</button>
        </form>
      </div>
    </section>
    <section class="research">
      <h2>Research Map</h2>
      <div class="research-grid">
        <div class="step"><b>1. Signal</b><span>EEG is loaded as channels by samples, then ordered into the 18-channel montage.</span></div>
        <div class="step"><b>2. Preprocess</b><span>Resample, impute, clip artifacts, detrend, notch, bandpass, and common average reference.</span></div>
        <div class="step"><b>3. Features</b><span>ApEn, FuEn, left-right asymmetry, MFDFA summaries, and SQI become a feature table.</span></div>
        <div class="step"><b>4. Model</b><span>LightGBM learns the three-class decision boundary, with TPE choosing hyperparameters.</span></div>
        <div class="step"><b>5. Decision</b><span>Calibration, EMA, thresholds, and no-decision logic make probabilities usable.</span></div>
      </div>
    </section>
  </main>
  <script>
    const canvas = document.getElementById('wave');
    const ctx = canvas.getContext('2d');
    function resize() {{
      canvas.width = canvas.clientWidth * window.devicePixelRatio;
      canvas.height = canvas.clientHeight * window.devicePixelRatio;
    }}
    window.addEventListener('resize', resize);
    resize();
    let t = 0;
    function draw() {{
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#111411';
      ctx.fillRect(0, 0, w, h);
      for (let c = 0; c < 8; c++) {{
        const y = (c + 1) * h / 9;
        ctx.strokeStyle = c % 2 === 0 ? '#58b88b' : '#d79b45';
        ctx.lineWidth = 1.5 * window.devicePixelRatio;
        ctx.beginPath();
        for (let x = 0; x < w; x += 3 * window.devicePixelRatio) {{
          const phase = x / w * Math.PI * 8 + t + c * 0.7;
          const amp = (10 + c * 1.3) * window.devicePixelRatio;
          const yy = y + Math.sin(phase) * amp + Math.sin(phase * 0.37) * amp * 0.5;
          if (x === 0) ctx.moveTo(x, yy); else ctx.lineTo(x, yy);
        }}
        ctx.stroke();
      }}
      t += 0.035;
      requestAnimationFrame(draw);
    }}
    draw();
  </script>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def send_html(self, content: str, status: int = 200) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/health":
            self.send_html(page('<section class="result"><h2>Health</h2><p class="muted">Server is running.</p></section>'))
            return
        if route != "/":
            self.send_html(page(f'<section class="result"><h2>Not Found</h2><p>{e(route)}</p></section>'), status=404)
            return
        self.send_html(page())

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw, keep_blank_values=True)
        try:
            if route == "/infer":
                result = run_infer(form)
            elif route == "/evaluate":
                result = run_evaluate(form)
            elif route == "/train":
                result = run_train(form)
            elif route == "/cv":
                result = run_cv(form)
            else:
                self.send_html(page(f'<section class="result"><h2>Not Found</h2><p>{e(route)}</p></section>'), status=404)
                return
            self.send_html(page(result))
        except Exception as exc:
            tb = traceback.format_exc()
            result = f"""
            <section class="result">
              <h2>Run Failed</h2>
              <p class="bad">{e(exc)}</p>
              <details open><summary>Traceback</summary><pre>{e(tb)}</pre></details>
            </section>
            """
            self.send_html(page(result), status=500)


def main() -> None:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"{APP_TITLE} running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
