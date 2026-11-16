"""frontend/shared/study-log.js under Node: study-mode params and the events it posts."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STUDY_LOG = Path(__file__).resolve().parents[1] / "frontend" / "shared" / "study-log.js"
NODE = shutil.which("node")

HARNESS = r"""
const fs = require("fs");
const [file, search, script] = process.argv.slice(1);
const posted = [];
const listeners = {};
const dispatched = [];
global.CustomEvent = function (type, init) { this.type = type; this.detail = init && init.detail; };
global.window = {
  NTApi: { post: (path, body) => { posted.push({ path, body }); return Promise.resolve({}); } },
  addEventListener: (type, fn) => { listeners[type] = fn; },
  dispatchEvent: (ev) => { dispatched.push({ type: ev.type, detail: ev.detail }); },
};
global.location = { search };
global.document = {
  body: { classList: { add: (c) => (global.__bodyClass = c) }, appendChild: () => {} },
  createElement: () => ({ style: {}, setAttribute: () => {} }),
};
eval(fs.readFileSync(file, "utf8"));
const press = (key) => listeners.keydown && listeners.keydown({ ctrlKey: true, shiftKey: true, key, preventDefault() {} });
eval(script);
if (listeners.load) listeners.load();
process.stdout.write(JSON.stringify({ study: window.NTStudy, posted, dispatched, bodyClass: global.__bodyClass || null }));
"""


def _run(search: str, script: str = "") -> dict:
    out = subprocess.run([NODE, "-e", HARNESS, str(STUDY_LOG), search, script],
                         capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.mark.unit
def test_inactive_without_a_valid_participant_code() -> None:
    for search in ("", "?participant=Nguyen", "?participant=p07", "?condition=B"):
        r = _run(search)
        assert r["study"]["active"] is False and r["bodyClass"] is None


@pytest.mark.unit
def test_active_study_mode_reads_params_and_locks_the_ui() -> None:
    r = _run("?participant=P07&condition=b&trial=2")
    assert r["study"]["active"] is True
    assert (r["study"]["participant"], r["study"]["condition"], r["study"]["trial"]) == ("P07", "B", 2)
    assert r["bodyClass"] == "nt-study"


@pytest.mark.unit
def test_log_posts_a_well_formed_event() -> None:
    r = _run("?participant=P07&condition=G", "window.NTStudy.log('quality', {score: 0.6, worst: 'AF4'})")
    assert len(r["posted"]) == 1
    p = r["posted"][0]
    assert p["path"] == "/api/study/events"
    body = p["body"]
    assert body["participant"] == "P07" and body["condition"] == "G" and body["trial"] == 1
    assert body["type"] == "quality" and body["payload"]["worst"] == "AF4"
    assert body["client_ts"].endswith("Z")


@pytest.mark.unit
def test_log_is_a_no_op_outside_study_mode() -> None:
    assert _run("", "window.NTStudy.log('quality', {})")["posted"] == []


@pytest.mark.unit
def test_study_url_exposes_a_validated_start_source() -> None:
    # app.html reads startSource when it registers its nt:nav listener (React mounts after
    # Babel compiles asynchronously, so an early event could be lost).
    assert _run("?participant=P07&source=device")["study"]["startSource"] == "device"
    assert _run("?participant=P07&source=replay")["study"]["startSource"] == "replay"


@pytest.mark.unit
def test_unknown_source_and_inactive_mode_start_nothing() -> None:
    assert _run("?participant=P07&source=evil")["study"]["startSource"] == ""
    assert _run("?source=device")["study"]["startSource"] == ""
    assert _run("?participant=P07&source=device")["dispatched"] == []


@pytest.mark.unit
def test_facilitator_hotkeys_mark_trials_and_actions() -> None:
    r = _run("?participant=P07", "press('S'); press('A'); press('R'); press('E'); press('S')")
    types = [(p["body"]["type"], p["body"]["trial"]) for p in r["posted"]]
    assert types == [("trial_start", 1), ("operator_action", 1), ("fault_resolved", 1), ("trial_end", 1), ("trial_start", 2)]
