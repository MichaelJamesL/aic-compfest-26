# ADR 0001 — Sensor anomaly detection: a per-machine robust baseline, not a forest

- **Status:** accepted
- **Date:** 2026-08-25
- **Scope:** `ai-engine/src/baseline.py`, `ai-engine/src/signals.py`
- **Supersedes:** nothing. The IQR fence it sits in front of is still there and still used.

## Context

`signals.detect_anomalies` scored a batch of readings with a per-tag IQR fence
computed *from that same batch*. The fence is cheap, explainable, and needs no
training — but it can only answer "is this point extreme compared to its
neighbours in this request?".

That is the wrong question for maintenance. A bearing that has crept from 50 °C
to 80 °C over three months is uniformly hot in every batch we score, so the
fence sees a tight, well-behaved distribution and reports nothing. The question
the factory wants answered is "is this unusual **for this machine**", which
needs the machine's own history, and therefore something fitted once and stored.

The requirement was a *lightweight* learned model, fitted from historical
readings uploaded when the machine is registered.

## The experiment

The first implementation was a per-tag `IsolationForest` (scikit-learn), one
model per tag, fitted on that tag's history — the obvious "simple ML" choice.
It does not work on this data, in two distinct ways.

**1. `contamination="auto"` fits nothing.** On 60 readings of a stable sensor
cycling 50–52 °C, `predict` labelled *all 60 training points* outliers, so the
"inliers" used to define the normal band were empty and no tag ever fitted.
The steadier the sensor — the better the factory — the worse this got.

**2. `decision_function` saturates, so it cannot rank distance.** Fitted on the
same 50–52 °C history:

| value | `decision_function` |
| --- | --- |
| 50.5 (interior) | −0.0217 |
| 53 | −0.0367 |
| 60 | −0.0367 |
| 80 | −0.0367 |
| 200 | −0.0367 |
| worst training point (50 or 52) | −0.0367 |

Every value beyond the training range collapses to one identical score, and it
is the same score the *edge* training values already have. A 1-D isolation tree
splits within the observed range; once a point is outside it, there is nothing
left to isolate, so "slightly out" and "wildly out" are indistinguishable.

The consequence is not academic: any threshold low enough to catch 80 °C also
fires on a perfectly ordinary 52 °C reading, which occurs in a third of all
samples. The detector would cry wolf on the most common value the machine
produces, and could not tell a warning from a catastrophe.

Adding tags as extra dimensions does not fix it. Saturation is per-dimension:
a point outside the range in one tag isolates in one split regardless of how
far outside it is.

## Decision

Fit a **robust z-score baseline per tag**: store the median and a MAD-derived
scale from the machine's historical readings, and flag readings whose modified
z-score exceeds 3.5 (Iglewicz–Hoaglin).

```
scale    = max(1.4826 · MAD, 1% · |median|, 1e-6)
z        = |value − median| / scale
anomaly  = z > 3.5
severity = existing ladder, fed (z / 3.5 − 1)
```

- **No saturation.** `z` grows without bound, so severity is a real measurement
  of how far out the reading is, and the existing severity ladder keeps meaning.
- **Edge-of-normal stays normal.** 52 °C is well inside the band; 80 °C is not.
- **No new dependency.** numpy only — `scikit-learn` was added to
  `ai-engine/pyproject.toml` for the forest and removed again with it. This
  matters here: the QC training endpoint is already unusable in the deployed
  backend image because `anomalib` is not installed in it, and a second heavy
  dependency on the analysis path would have been the same mistake twice.
- **Persisted as JSON**, not a pickle: two floats per tag, readable by a human
  debugging a false positive, and no pickle-compatibility trap on upgrade.

The scale floor (1% of the median) is a deliberate calibration knob, marked in
the code. A sensor that reads exactly 50.0 forever has MAD 0, and without a
floor any reading of 50.1 would score as infinitely anomalous.

## Consequences

- The baseline is fitted once, at machine registration, from the historical CSV
  (`POST /api/v1/assets/{id}/baseline`), and stored per machine.
- **The fence is not gone.** `detect_anomalies` uses the baseline for the tags
  it knows and falls back to the IQR fence for everything else — machines
  registered without history, and sensors added after registration. `method` on
  each `Anomaly` says which one spoke: `robust_z` or `iqr`.
- A baseline fitted on history that already contains a fault will treat that
  fault as normal. Refitting is a re-upload; there is no automatic drift
  handling, and deliberately so at this size.
- Each tag is scored independently. "Temperature normal, vibration normal, but
  not together" is not detectable this way. That is genuinely what a
  multivariate IsolationForest is good at, and is the sane reason to revisit
  this decision — but it needs readings resampled onto a shared time grid
  first, which we do not have.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Per-tag `IsolationForest` | The experiment above. Cannot rank distance; false-positives the most common value. |
| `IsolationForest` + a p1/p99 range gate | Works, but the range does all the discriminating. Paying a sklearn dependency for a decorative model. |
| Multivariate `IsolationForest` across tags | The one genuinely attractive version. Needs time-grid resampling that does not exist yet; still cannot rank distance. Revisit if cross-tag faults become the ask. |
| Keep the batch-local IQR fence alone | Cannot see a uniformly degraded machine — the case that motivated the work. |
