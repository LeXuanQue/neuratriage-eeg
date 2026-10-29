This directory is the default model location for the JSON API.

Expected file:

```text
backend/models/model.joblib
```

For local development, `legacy/api/index.py` also falls back to `out/model.joblib`
when the default model is missing. In production, either commit a small
validated model here or set `MODEL_PATH` to the deployed model path.
