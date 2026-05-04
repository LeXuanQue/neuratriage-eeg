# Research Guide

## 1. The study question

The app studies whether EEG features can separate three classes:

- non-stroke
- ischemic stroke
- hemorrhagic stroke

This is not a raw deep-learning pipeline. It is a feature-engineering pipeline:

```text
EEG windows -> handcrafted signal features -> LightGBM classifier
```

## 2. Input signal

The pipeline expects EEG as:

```text
n_channels x n_samples
```

Default sampling rate is `256 Hz`. Default windows:

- entropy window: `1.0 s`
- entropy step: `0.5 s`
- MFDFA window: `4.0 s`

The default montage has 18 EEG channels.

## 3. Preprocessing

The preprocessing stage makes the signal more comparable across subjects:

- channel names are canonicalized
- missing channels can be imputed
- sampling rate can be resampled
- extreme artifacts are clipped
- linear trend is removed
- notch filtering removes power-line noise
- bandpass filtering keeps the EEG band used by the model
- common average reference reduces shared noise

## 4. ApFu features

ApFu means:

```text
Approximate Entropy + Fuzzy Entropy
```

Entropy features estimate signal irregularity. Stroke can change EEG
complexity, especially across affected and unaffected hemispheres.

The pipeline computes:

- ApEn per channel
- FuEn per channel
- left-right asymmetry for homologous channel pairs
- absolute left-right ApFu difference

## 5. MFDFA features

MFDFA means:

```text
Multifractal Detrended Fluctuation Analysis
```

It measures signal complexity across multiple time scales. This is why the
pipeline uses a longer 4-second buffer for MFDFA.

The code summarizes the multifractal spectrum into numeric features such as:

- `h2`
- `alpha0`
- `delta_alpha`
- `width_left`
- `width_right`
- `asymmetry_alpha`

## 6. SQI features

SQI means:

```text
Signal Quality Index
```

The model should not make confident predictions on bad EEG. SQI checks:

- flatline
- clipping
- line-noise ratio
- high-frequency noise ratio

When SQI is too low, inference returns `no-decision`.

## 7. Model

The classifier is LightGBM. It receives a feature table where:

```text
each row = one EEG window
each column = one extracted feature
```

Optuna/TPE searches for good LightGBM hyperparameters. The optimization target
is macro F1, which is better than raw accuracy when classes are imbalanced.

## 8. Evaluation

Patient-wise splitting is essential. Windows from the same patient must not be
in both train and test sets. Otherwise, the model may learn patient identity
instead of stroke-related EEG patterns.

The pipeline uses group-aware splitting with `patient_id`.

Main metrics:

- macro F1
- balanced accuracy
- per-class recall
- multiclass Brier score
- expected calibration error
- one-vs-rest AUC

## 9. App build path

Recommended build order:

1. Keep the pipeline importable and tested.
2. Make offline inference reliable.
3. Add evaluation on manifest CSV.
4. Add training only after manifest and features are stable.
5. Add realtime alerts after offline results are trusted.

The current app implements steps 1 through 4 and keeps the realtime detector in
the pipeline for future UI work.
