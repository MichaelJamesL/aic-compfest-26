# Visual quality control (PatchCore via anomalib) in the maintenance engine

## Context

`ai-engine` today turns **sensor readings + SOPs + history + business constraints**
into a typed `AnalysisResult`. Its central design rule (`AGENTS.MD`, `README.md`):

> Signals are deterministic, not the LLM's. `signals.py` computes anomalies and
> health score; the model *explains* the numbers, it can never invent them.

There is no visual input. A camera on the line is the one data source a mid-size
factory already has and the engine can't use — and defects are the highest-signal
evidence of degradation there is. This adds a third deterministic signal
alongside `detect_anomalies` and `health_score`: **PatchCore** unsupervised
visual anomaly detection, fitted on nominal images per asset, producing typed
`DefectFinding`s that flow into the health score, the prompt, and the audit trail.

The shape of the change follows the existing one exactly. `readings →
detect_anomalies → ContextBundle → prompt → engine overwrites the field`
becomes `images → vision.inspect → ContextBundle → prompt → engine overwrites
the field`. No new agent, no new orchestration layer.

### Decisions

| Decision | Chosen | Why |
| --- | --- | --- |
| **Implementation** | **anomalib** (`anomalib.models.Patchcore`) | Your call. Also the `AGENTS.MD` house rule: *"do not hand-roll something a framework already provides."* anomalib owns the backbone, coreset subsampling, kNN scoring, thresholding, and heatmap rendering — all of which the previous draft hand-rolled. |
| **Subject** | One `DefectFinding` per image, with a `subject: "asset" \| "product"` tag | Per-image findings cover machine inspection *and* product QC; batch defect rate falls out as `defective / total` with zero extra schema. |
| **Where it runs** | Inside the engine; `AnalysisRequest.images` carries paths | Mirrors `readings`. Backend and engine are one process (`AGENTS.MD`), so a path is free. |
| **Agent shape** | Precomputed signal, one LLM call | Same contract as `signals.py`. A tool call would let the model skip or misread the inspection, and defects would become hallucinable. |

**The cost of anomalib, stated plainly:** it pulls torch + Lightning +
torchmetrics + timm + opencv — roughly 3GB installed, versus ~180MB for
torchvision alone. That is the price of not owning the algorithm. It buys a
correct, maintained PatchCore instead of ~140 lines you'd have to defend to a
judge, and it cuts `vision.py` to about 60 lines. Contained behind an optional
`[vision]` extra so the base install is unchanged for anyone not doing QC.

## Files

### New: `ai-engine/src/vision.py` (~60 lines)

Same posture as `signals.py`: deterministic, no LLM. `anomalib` is imported
**inside** the functions so the base install still works without the extra.

Two paths, deliberately split — the Lightning `Engine` is a fit-time tool, not
a request-time one:

```python
def fit(asset_id: str, normal_dir: str | Path) -> Path:
    """Fit PatchCore on nominal-only images, export to {BANK_DIR}/{asset_id}.pt."""
    from anomalib.data import Folder
    from anomalib.models import Patchcore
    from anomalib.engine import Engine
    # Folder(name=asset_id, root=..., normal_dir=...) -> engine.fit(...)
    # -> engine.export(model, ExportType.TORCH, export_root=BANK_DIR)

def inspect(asset_id: str, paths: list[str], subject="asset") -> list[DefectFinding]:
    """Score images against the fitted model. TorchInferencer, no trainer."""
    from anomalib.deploy import TorchInferencer
    # cached per asset_id; map each prediction -> DefectFinding
```

- **`fit`** is called once per asset from the backend's "upload reference
  photos" endpoint. PatchCore is one-epoch — a memory-bank fit, not gradient
  descent — so ~20 images take seconds on CPU.
- **`inspect`** loads the exported `.pt` through `TorchInferencer`, cached in a
  module-level dict keyed by `asset_id` (same singleton pattern as
  `embed._ensure_model`). Per-image it reads `pred_score`, `pred_label`,
  `anomaly_map`, `pred_mask` off the prediction and maps them onto
  `DefectFinding`.
- **`region`** = bounding box of `pred_mask`'s nonzero extent.
- **`heatmap_path`** = anomalib's own visualizer output. Do not blend a heatmap
  by hand; the library renders one.
- **Severity** from `score / threshold`, reused through **`signals._severity`** —
  its `_SEVERITY_BY_MULT` ladder already maps a multiple to
  low/medium/high/critical. Don't write a second one.

> **Threshold caveat — read before demo day.** anomalib's `F1AdaptiveThreshold`
> calibrates against *anomalous* validation samples. Fitting on normals only
> leaves it with nothing to separate, so the exported threshold is not
> trustworthy out of the box. Keep `AIENGINE_DEFECT_THRESHOLD` as an explicit
> override and default to it when set. A real camera's lighting will not match
> the fit set either — this is the calibration knob, and it is not optional.

> **Version caveat.** anomalib's API moved between v1 and v2 (`Engine.export`,
> `ExportType`, the `Batch`/`ImageBatch` prediction dataclasses, and
> `anomalib.deploy` inferencer names all changed). Pin the version in
> `pyproject.toml` and confirm the exact call signatures against the installed
> package before writing `vision.py` — the sketch above is the v2 shape.

### `ai-engine/src/schemas.py`

```python
class DefectFinding(BaseModel):
    image: str
    subject: Literal["asset", "product"] = "asset"
    score: float
    threshold: float
    label: Literal["ok", "defect"]
    severity: Literal["low", "medium", "high", "critical"] = "low"
    region: tuple[int, int, int, int] | None = None   # x, y, w, h
    heatmap_path: str | None = None
    method: str = "patchcore"                          # mirrors Anomaly.method
```

- `AnalysisRequest.images: list[str] = []` — optional like everything else, so
  the tier still doesn't gate logic.
- `ContextBundle.defects: list[DefectFinding] = []`, plus a `defect_rate`
  property (`defective / total`) for the product-QC read.
- `AnalysisResult.defects: list[DefectFinding] = []` — overwritten by the engine.

### `ai-engine/src/signals.py`

Add `"defect"` to `HEALTH_WEIGHTS` mirroring the `"anomaly"` sub-dict, and a
`defects` parameter to `health_score(asset, anomalies, history, defects=(), now=None)`
that deducts per severity and appends to `reasons`. Same loop shape as the
existing anomaly loop — this is the shared function every caller routes
through, so putting it here means no caller needs changing twice.

### `ai-engine/src/context.py`

```python
defects = vision.inspect(request.asset.id, request.images) if request.images else []
health, summary = health_score(request.asset, anomalies, request.history, defects)
```

Also fold defect labels into `_retrieval_query` so RAG pulls the *right* SOP
(a surface defect should retrieve the surface-finish SOP, not the generic pump
manual), and mention the defect count in `_assets_facts`.

### `ai-engine/src/prompts.py`

- One rule in `SYSTEM`: defects are precomputed by PatchCore, copy them
  verbatim, cite them as evidence — same wording as the existing health/anomaly
  rule.
- Add `defects` to the schema listing and one entry to the worked example.
- `_context_str`: a `=== VISUAL INSPECTION ===` block directly after
  `=== PRECOMPUTED HEALTH ===` (same class of signal), rendering score,
  threshold, severity, region, and the batch defect rate. `"(no images
  inspected)"` when empty, matching the other blocks' style.

### `ai-engine/src/engine.py`

One line in `analyze`, next to the existing overwrites:

```python
result.defects = bundle.defects
```

### `ai-engine/src/config.py`

`BANK_DIR` (default `ai-engine/.banks`), `DEFECT_THRESHOLD` override,
`PATCHCORE_BACKBONE` — same env-var-with-default style as the rest.

### `ai-engine/pyproject.toml`

```toml
[project.optional-dependencies]
vision = ["anomalib>=2.0"]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
torchvision = { index = "pytorch-cpu" }
```

The CPU index is **not** optional — anomalib's `torch` dependency resolves to
the CUDA build on linux by default, dragging in ~2.5GB of runtime this will
never use. Verify with `uv run python -c "import torch; print(torch.__version__)"` —
a `+cpu` suffix means it worked.

### `ai-engine/src/demo.py`

Extend `fixture_request()` to generate its own images with PIL (already
installed via fastembed): ~8 nominal gray plates with mild noise written to a
temp dir, plus one with a drawn scratch. `vision.fit` on the nominal dir, pass
the scratched one as `images`. Zero binary fixtures in git, and the demo proves
the whole path end to end.

### Tests

- `ai-engine/tests/test_vision.py` — `pytest.importorskip("anomalib")` on the
  fit/inspect round trip (planted scratch scores above threshold, a clean plate
  does not). The severity mapping and `DefectFinding` construction need no
  anomalib and run in the default suite.
- `ai-engine/tests/test_signals.py` — one case: health score falls monotonically
  as defect severity rises. Mirrors the existing anomaly assert.

### Docs

`README.md` (layout, a Visual QC section, the `[vision]` install line) and
`AGENTS.MD` (architecture diagram + the "signals are deterministic" bullet,
which now covers three signals, and a line adding anomalib to the framework-first
list).

## Verification

```bash
cd ai-engine
uv sync --extra dev --extra vision
uv run python -c "import torch; print(torch.__version__)"   # expect +cpu
uv run pytest                      # anomalib-free asserts + the vision path
uv run python -m src.demo          # generates plates, fits, inspects, calls DeepSeek
```

The demo passes if:
1. `result.defects[0].label == "defect"` with a `heatmap_path` that exists and
   visibly highlights the scratch;
2. `health_score` is lower than the same fixture run with `images=[]`;
3. `explanation` cites the visual finding alongside the bearing temperature —
   that is the actual test of whether the prompt integration worked;
4. `result.defects` matches `bundle.defects` exactly (engine-owned, not
   model-invented).

Then `uv run python eval/run_eval.py` — `_build_request` gains
`images=case.get("images", [])`, one line. Labelled defect cases in
`cases.yaml` are a follow-up: they need real MVTec-style images, and scoring
them properly means a `defect_detected` expectation, not a synthetic scratch.

## Deliberately not doing

- **Defect classification** ("scratch" vs "dent"). PatchCore is unsupervised —
  it localizes anomalies, it does not name them. Naming needs labelled data the
  project doesn't have. The LLM can describe the region from context.
- **A separate QC agent / tool call.** Adds latency and cost, and makes the
  defect list hallucinable. Revisit only if the model needs to inspect
  *selectively*.
- **anomalib's other models** (PaDiM, FastFlow, EfficientAD). Swapping is a
  one-line change in `vision.fit` once anomalib owns the fit; decide on eval
  numbers, not intuition — same rule `PLAN.md` applies to `deepseek-reasoner`.
- **OpenVINO export.** anomalib supports it and it would cut inference latency
  and image size substantially. A deployment optimization, not a hackathon one.
