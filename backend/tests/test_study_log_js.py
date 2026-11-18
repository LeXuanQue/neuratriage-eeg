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
const [file, search, script, failFirst] = process.argv.slice(1);
const posted = [];
const listeners = {};
const dispatched = [];
let fails = parseInt(failFirst || "0", 10);
global.CustomEvent = function (type, init) { this.type = type; this.detail = init && init.detail; };
global.window = {
  NTApi: { post: (path, body) => {
    if (fails > 0) { fails -= 1; return Promise.reject(new Error("offline")); }
    posted.push({ path, body }); return Promise.resolve({});
  } },
  addEventListener: (type, fn) => { listeners[type] = fn; },
  dispatchEvent: (ev) => { dispatched.push({ type: ev.type, detail: ev.detail }); },
};
global.location = { search, pathname: "/app.html", hash: "" };
global.history = { replaceState: (_s, _t, url) => { global.__url = url; } };
global.document = {
  body: { classList: { add: (c) => (global.__bodyClass = c) }, appendChild: (el) => { global.__badge = el; } },
  createElement: () => ({ style: {}, setAttribute: () => {}, textContent: "" }),
};
eval(fs.readFileSync(file, "utf8"));
const press = (key) => listeners.keydown && listeners.keydown({ ctrlKey: true, shiftKey: true, key, preventDefault() {} });
(async () => {
  for (const line of script.split(";;")) { if (line.trim()) { await eval(line); await new Promise((r) => setTimeout(r, 5)); } }
  await new Promise((r) => setTimeout(r, 20));
  process.stdout.write(JSON.stringify({
    study: window.NTStudy, posted, dispatched, bodyClass: global.__bodyClass || null,
    badge: global.__badge ? global.__badge.textContent : null, url: global.__url || null,
  }));
})();
"""


def _run(search: str, script: str = "", fail_first: int = 0) -> dict:
    out = subprocess.run([NODE, "-e", HARNESS, str(STUDY_LOG), search, script, str(fail_first)],
                         capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.mark.unit
def test_inactive_without_a_valid_participant_code_and_explicit_condition() -> None:
    for search in ("", "?participant=Nguyen&condition=G", "?participant=p07&condition=G",
                   "?condition=B", "?participant=P07", "?participant=P07&condition=X"):
        r = _run(search)
        assert r["study"]["active"] is False and r["bodyClass"] is None, search


@pytest.mark.unit
def test_active_study_mode_reads_params_and_locks_the_ui() -> None:
    r = _run("?participant=P07&condition=b&trial=2")
    assert r["study"]["active"] is True
    assert (r["study"]["participant"], r["study"]["condition"], r["study"]["trial"]) == ("P07", "B", 2)
    assert r["bodyClass"] == "nt-study"
    assert r["badge"] == "P07 · T2"


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
def test_failed_events_are_retried_with_the_next_one() -> None:
    r = _run("?participant=P07&condition=G",
             "window.NTStudy.log('trial_start', {});;window.NTStudy.log('quality', {})", fail_first=1)
    assert [p["body"]["type"] for p in r["posted"]] == ["trial_start", "quality"]


@pytest.mark.unit
def test_study_url_exposes_a_validated_start_source() -> None:
    # app.html reads startSource when it registers its nt:nav listener (React mounts after
    # Babel compiles asynchronously, so an early event could be lost).
    assert _run("?participant=P07&condition=G&source=device")["study"]["startSource"] == "device"
    assert _run("?participant=P07&condition=G&source=replay")["study"]["startSource"] == "replay"


@pytest.mark.unit
def test_unknown_source_and_inactive_mode_start_nothing() -> None:
    assert _run("?participant=P07&condition=G&source=evil")["study"]["startSource"] == ""
    assert _run("?source=device")["study"]["startSource"] == ""
    assert _run("?participant=P07&condition=G&source=device")["dispatched"] == []


@pytest.mark.unit
def test_facilitator_hotkeys_mark_trials_and_actions() -> None:
    r = _run("?participant=P07&condition=G", "press('S');;press('A');;press('R');;press('E');;press('S')")
    types = [(p["body"]["type"], p["body"]["trial"]) for p in r["posted"]]
    assert types == [("trial_start", 1), ("operator_action", 1), ("fault_resolved", 1), ("trial_end", 1), ("trial_start", 2)]


@pytest.mark.unit
def test_trial_number_survives_a_reload_via_the_url() -> None:
    r = _run("?participant=P07&condition=G&trial=1&source=device", "press('E')")
    assert r["url"] is not None and "trial=2" in r["url"] and "participant=P07" in r["url"]
    assert r["badge"] == "P07 · T2"


@pytest.mark.unit
def test_not_recording_is_flagged_on_the_badge() -> None:
    r = _run("?participant=P07&condition=G", "window.NTStudy.markNotRecording()")
    assert "NOT RECORDING" in r["badge"]


@pytest.mark.unit
def test_rapid_events_are_each_sent_exactly_once() -> None:
    script = "Promise.all([window.NTStudy.log('quality', {i: 1}), window.NTStudy.log('quality', {i: 2})])"
    r = _run("?participant=P07&condition=G", script + ";;window.NTStudy.log('note', {})")
    assert [p["body"]["payload"].get("i") for p in r["posted"]] == [1, 2, None]
