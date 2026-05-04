# EEG Stroke Research App

Local app built around `eeg_stroke_pipeline.py`.

## What this app does

- Runs offline inference on one `.npz` or `.npy` EEG file.
- Evaluates a saved model on a manifest CSV.
- Trains a LightGBM model from a manifest CSV.
- Runs patient-wise cross-validation.
- Shows the research flow from EEG signal to features to model decision.

## Research pipeline

```text
raw EEG
-> channel ordering and preprocessing
-> 1-second ApEn/FuEn entropy features
-> 4-second MFDFA features
-> SQI quality features
-> LightGBM classifier
-> Optuna/TPE hyperparameter search
-> probability calibration
-> offline inference or realtime alert logic
```

## Data format

Manifest CSV:

```csv
patient_id,label,path,fs
sub-01,non-stroke,C:\path\to\sub-01.npz,256
sub-02,ischemic,C:\path\to\sub-02.npz,256
sub-03,hemorrhagic,C:\path\to\sub-03.npz,256
```

Labels:

- `non-stroke`
- `ischemic`
- `hemorrhagic`
- or numeric `0`, `1`, `2`

`.npz` file keys:

- `data`: float array, shape `(n_channels, n_samples)`
- `channels`: channel names
- `fs`: sampling rate, optional if manifest has `fs`

`.npy` file:

- float array, shape `(n_channels, n_samples)`
- assumed to follow the default channel order in the pipeline

## Run

This project has a fresh `.venv`, but the original EEG environment already has
the scientific dependencies installed. The batch file uses the local `.venv`
when ready and falls back to `C:\Users\Admin\EEG\.venv`.

```bat
run_app.bat
```

Then open:

```text
http://127.0.0.1:8501
```

Direct Python command:

```bat
C:\Users\Admin\EEG\.venv\Scripts\python.exe app.py --host 127.0.0.1 --port 8501
```

Install dependencies into this app's `.venv` later:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Current demo defaults

- Model: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\model_smoke.joblib`
- Manifest: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\manifest.csv`
- EEG file: `C:\Users\Admin\EEG\testdata\pipeline_smoke_npz\sub-01.npz`

These are smoke-test files. Replace them with real experiment outputs for
actual study runs.
