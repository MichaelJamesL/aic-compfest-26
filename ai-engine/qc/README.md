# qc — the fine-tuned defect classifier

The one model the team trains. Everything else here is pre-trained (DeepSeek,
fastembed) or a deterministic rule (IQR fences, weighted health deductions), so
this is what answers the rulebook's *"Model wajib di fine tune sesuai dengan
inovasi fitur per tim"* — and it is the head of the differentiator chain: it
emits the defect class that `mapping/qc_failure_modes.yaml` keys on.

```bash
uv sync --extra qc
uv run python qc/preprocess.py    # download + split (~190MB, not committed)
uv run python qc/train.py         # fine-tune, write model.pt and METRICS.md
uv run python qc/preprocess.py --stats
```

| File | What |
| --- | --- |
| `preprocess.py` | Fetches the 480 MVTec `screw` images and builds a deterministic stratified split |
| `train.py` | MobileNetV3-Small transfer learning, class-balanced |
| `split.json` | The split, committed so results are reproducible |
| `model.pt` | Trained weights + class list |
| `METRICS.md` | Per-class accuracy, confusion matrix, split sizes — generated |
| `data/` | The images. **Not committed**: CC BY-NC-SA 4.0 and ~190MB. |

## Licence

MVTec AD is **CC BY-NC-SA 4.0 — non-commercial**. This is stated openly in the
proposal rather than buried. For a real deployment the images come from the
customer's own line; the public dataset is for development and demonstration.

## Why balanced sampling is not optional

`good` outnumbers each defect class 217:14 in training. With loss weighting
alone, the first run scored 81.1% overall while answering `good` for **all
eight** thread defects in the test split. Overall accuracy hid a dead class,
because `good` is 76% of that split.

Both the sampler and the model-selection metric now work per class. When
reading `METRICS.md`, read the confusion matrix first and the headline second.
