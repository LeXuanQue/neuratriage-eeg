# TUSL Same-Rig Runbook

Produce a **same-rig** slow-vs-background macro-F1/AUC on the TUH EEG Slowing
Corpus (TUSL) to break the acquisition confound in the main ischemic-vs-non-stroke
task.

## 1. Why

In the headline ischemic-vs-non-stroke result the ischemic cohort (`sub-*`, clinical
rig) and the non-stroke cohort (`ns-*`, PhysioNet resting) come from *different
acquisition setups*, so recording source is 100% correlated with label (see
`scripts/diagnose_source_confound.py`). The 0.99 macro-F1 can therefore be a rig/batch
fingerprint, not pathology. TUSL fixes this: every recording comes from the single TUH
clinical EEG system, so a slow-vs-background task on it carries **no cross-cohort site
signature** — any signal above chance must come from the EEG itself.

## 2. Task definition

- positive (1) = `slow` (focal/generalized slowing, an EEG lesion proxy)
- negative (0) = `bckg` (complex background, non-slowing)
- `seiz` excluded (different phenomenon, not a lesion proxy).

Honest framing: this is **"focal-abnormality vs background on one rig"**, NOT "ischemic
stroke". It is a mechanistic sanity check that the entropy/MFDFA pipeline sees real
pathology, not a site fingerprint. **Small-N caveat:** only 29 labeled patients (17 with
both classes), 100 `slow` + 100 `bckg` segments — treat the number as directional, not
a benchmark. Report patient-level GroupKFold, never window-level.

Corpus facts (TUSL v2.0.1, `F:\tuh_data\tusl\AAREADME.txt`): slowing = 100 files / 20
patients; seizure = 100 files / 30 patients; all annotations are 10 s, `01_tcp_ar`
averaged-reference montage that canonicalizes onto `DEFAULT_CHANNELS`.

## 3. Step 0 — Download the EDFs (BLOCKER, run in WSL)

Current scan reports `n_edf_present: 0`: the `.tse_agg`/`.lbl`/`.csv` **annotation**
files are staged under `F:\tuh_data\tusl\edf\`, but the `.edf` **signal** files are not
downloaded. Nothing downstream works until this is done.

Download runs from **WSL Ubuntu** via rsync over SSH (restricted shell — no `head`/`find`
pipes; explore only with `rsync --list-only`). Writing to the F: drive over drvfs needs
`--no-times --no-perms --inplace` or mkstemp/set-times fail. Helper reference:
`F:\tuh_data\dry.sh`. **The user must run these in WSL** (this agent cannot):

```bash
K=$HOME/.ssh/id_ed25519
RSH="ssh -i $K -o LogLevel=ERROR"
SRC=nedc-tuh-eeg@www.isip.piconepress.com:data/tuh_eeg/tuh_eeg_slowing

# 0a. Explore: confirm the version subdir and edf/ layout (no download)
rsync --list-only -e "$RSH" "$SRC/"
rsync --list-only -e "$RSH" "$SRC/v2.0.1/edf/"

# 0b. Download ONLY the .edf files into the existing annotation tree
#     (annotations already present; drvfs flags required)
rsync -rz --no-times --no-perms --inplace \
  --include='*/' --include='*.edf' --exclude='*' \
  -e "$RSH" "$SRC/v2.0.1/edf/" /mnt/f/tuh_data/tusl/edf/
```

Adjust `v2.0.1` if `0a` shows a different version dir. Verify the pull landed:

```bash
# count .edf on the remote path vs. locally — they should match
rsync -r --list-only -e "$RSH" "$SRC/v2.0.1/edf/" | grep -c '\.edf'
find /mnt/f/tuh_data/tusl/edf -name '*.edf' | wc -l
```

## 4. Steps 1–3 — Build & evaluate (Windows, project venv)

Exact commands from `scripts/tusl_to_npz.py`'s module docstring:

```powershell
# 1. Confirm the corpus is viable and EDFs are now present (n_edf_present > 0)
.venv\Scripts\python.exe scripts\tusl_to_npz.py --scan-only

# 2. Convert EDFs + annotations -> per-segment npz + dataset_tuh\manifest_tuh.csv
.venv\Scripts\python.exe scripts\tusl_to_npz.py `
    --tusl-root F:/tuh_data/tusl --out-dir dataset_tuh

# 3a. Extract the feature table (existing script, no changes)
.venv\Scripts\python.exe scripts\build_feature_table.py `
    --manifest dataset_tuh\manifest_tuh.csv `
    --out dataset_tuh\feature_table_tuh.csv `
    --workers 8

# 3b. Same-rig macro-F1 / AUC (patient_ids are tuh_* -> tagged tuh_samerig)
.venv\Scripts\python.exe scripts\diagnose_source_confound.py `
    --combined-csv dataset_tuh\feature_table_tuh.csv
```

`--scan-only` needs only the annotation files (safe to run now); Step 2 requires the
EDFs. The manifest carries `patient_id` (`tuh_<code>`), `label`, `path`, `fs`.

## 5. How to read the result

`diagnose_source_confound.py` prints a patient-level GroupKFold probe across three
feature families — **ENTROPY-only**, **SQI-only**, **FULL (Ent+MFDFA+SQI)**:

- **Trustworthy outcome:** same-rig `slow`-vs-`bckg` macro-F1/AUC is well above chance
  (0.5) **with ENTROPY-only** features. Same rig removes the acquisition shortcut, so
  entropy separating the classes means the pipeline sees real pathology.
- **Failure / still quality-driven:** if **SQI-only ≈ FULL** and both sit well above
  ENTROPY-only, even the same-rig signal is signal-quality-driven, not pathology — the
  probe's "CONFOUND LIKELY" verdict fires (SQI AUC ≥ 0.95 and SQI − ENTROPY > 0.05).
- Because source is single-valued here, the source×label cross-tab is not perfectly
  confounded; the ENTROPY-vs-SQI gap is the load-bearing comparison. Cite the ENTROPY-only
  number as the same-rig headline. With N=29, report it as directional evidence.

## 6. TUAB — same-rig at scale (the defensible N)

TUSL is a small-N mechanistic check (29 patients). **TUAB** (TUH EEG Abnormal
Corpus) is the same single clinical rig at ~15x the size — 2,993 recordings /
~2,383 subjects, `normal` vs `abnormal`, same `01_tcp_ar` referential montage.
Run it after TUSL to turn the directional signal into a macro-F1/AUC with real
statistical weight. Same converter contract: it emits only `manifest_tuab.csv`
(+ npz); the unchanged `build_feature_table.py` / `diagnose_source_confound.py`
do the rest, and `tuh_*` patient ids are auto-tagged `tuh_samerig`.

### 6.1 Step 0 — Download the EDFs (WSL, user runs this)

Remote path (confirmed via `F:\tuh_data\dry.sh`):
`data/tuh_eeg/tuh_eeg_abnormal/v3.0.1`. Unlike TUSL, **no** annotation tree is
pre-staged — the label lives in the `.../normal/...` vs `.../abnormal/...`
directory component, so the `.edf` files ARE the dataset. Same drvfs flags
(`--no-times --no-perms --inplace`) and same restricted-shell rule (explore only
with `rsync --list-only`). ~50–60 GB — check free space on F: first.

```bash
K=$HOME/.ssh/id_ed25519
RSH="ssh -i $K -o LogLevel=ERROR"
SRC=nedc-tuh-eeg@www.isip.piconepress.com:data/tuh_eeg/tuh_eeg_abnormal/v3.0.1

# 0a. Confirm the normal|abnormal layout before committing (no download)
bash /mnt/f/tuh_data/dry.sh                      # prints .edf count per partition
rsync -d --list-only -e "$RSH" "$SRC/edf/"       # expect train/ eval/

# 0b. Download ONLY .edf into a fresh tuab/ tree (background + log; resumable)
mkdir -p /mnt/f/tuh_data/tuab/edf
nohup rsync -rz --no-times --no-perms --inplace \
  --include='*/' --include='*.edf' --exclude='*' \
  -e "$RSH" "$SRC/edf/" /mnt/f/tuh_data/tuab/edf/ \
  > /mnt/f/tuh_data/tuab_pull.log 2>&1 &
tail -f /mnt/f/tuh_data/tuab_pull.log

# 0c. Verify: remote .edf count should match local
rsync -r --list-only -e "$RSH" "$SRC/edf/" | grep -c '\.edf'   # ~2993
find /mnt/f/tuh_data/tuab/edf -name '*.edf' | wc -l
```

If space is tight, pulling only `edf/train/` (swap `"$SRC/edf/"` ->
`"$SRC/edf/train/"`) drops ~20% and still gives a large N; the converter pools
whatever is on disk.

### 6.2 Steps 1–3 — Build & evaluate (Windows, project venv)

```powershell
# 1. Label balance + subject coverage (needs EDFs; TUAB has no annotations to scan)
.venv\Scripts\python.exe scripts\tuab_to_npz.py --scan-only

# 2. Crop one comparable window per recording -> npz + dataset_tuab\manifest_tuab.csv
.venv\Scripts\python.exe scripts\tuab_to_npz.py `
    --tuab-root F:/tuh_data/tuab --out-dir dataset_tuab

# 3a. Feature table (existing script, no changes)
.venv\Scripts\python.exe scripts\build_feature_table.py `
    --manifest dataset_tuab\manifest_tuab.csv `
    --out dataset_tuab\feature_table_tuab.csv `
    --workers 8

# 3b. Same-rig macro-F1 / AUC (tuh_* -> tuh_samerig)
.venv\Scripts\python.exe scripts\diagnose_source_confound.py `
    --combined-csv dataset_tuab\feature_table_tuab.csv
```

`--skip-sec`/`--dur-sec` default to 60/60 (skip setup artifacts, keep 60 s).
Read the result exactly as in §5: the **ENTROPY-only vs SQI-only gap** is
load-bearing. At TUAB's N the ENTROPY-only number is no longer merely
directional — it is the defensible, confound-free headline to cite alongside the
confounded 0.99 in the paper.
