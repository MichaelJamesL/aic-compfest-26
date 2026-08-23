"""Fetch and split the QC training data.

Source: MVTec AD, category `screw`, via the Voxel51 mirror on Hugging Face.
**Licence: CC BY-NC-SA 4.0 — non-commercial.** Stated openly in the proposal;
for a real deployment the images come from the customer's own line.

    uv run python qc/preprocess.py            # download + split
    uv run python qc/preprocess.py --stats    # report an existing split

Writes:
    qc/data/<class>/*.png     the 480 screw images, one folder per class
    qc/split.json            deterministic train/val/test assignment

Preprocessing decisions live here rather than in the trainer so the proposal
can point at one file (rulebook: the dataset pipeline must be described).
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SPLIT_FILE = HERE / "split.json"

REPO = "Voxel51/mvtec-ad"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"
SAMPLES = f"{BASE}/samples.json"
CATEGORY = "screw"

# The five defect classes the mapping table keys on, plus the nominal class.
# A binary ok/defect split would leave `mapping/qc_failure_modes.yaml` with
# nothing to look up (DECISIONS.md D2).
CLASSES = [
    "good",
    "manipulated_front",
    "scratch_head",
    "scratch_neck",
    "thread_side",
    "thread_top",
]

# Stratified per class. MVTec's own train/test split is built for unsupervised
# anomaly detection — its train set is nominal-only — so it cannot be reused
# for a classifier. We resplit all 480 images.
RATIOS = (0.6, 0.2, 0.2)
SEED = 20260823


def _fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1024:
        return
    with urllib.request.urlopen(url, timeout=120) as response:
        dest.write_bytes(response.read())


def download() -> list[dict]:
    print(f"index: {SAMPLES}")
    with urllib.request.urlopen(SAMPLES, timeout=180) as response:
        samples = json.load(response)["samples"]

    screw = [s for s in samples if s.get("category", {}).get("label") == CATEGORY]
    if not screw:
        raise SystemExit("no screw samples in the index — the mirror may have changed")

    items = []
    for sample in screw:
        label = sample["defect"]["label"]
        if label not in CLASSES:
            continue
        name = sample["filepath"].replace("/", "_")
        items.append({"label": label, "url": f"{BASE}/{sample['filepath']}", "name": name})

    print(f"{len(items)} images across {len({i['label'] for i in items})} classes")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: _fetch(i["url"], DATA / i["label"] / i["name"]), items))
    return items


def split(items: list[dict]) -> dict:
    """Stratified, deterministic, and disjoint by image.

    MVTec `screw` photographs a different physical screw per image, so a
    per-image split does not leak an object across sets. Categories where one
    object appears in several shots would need grouping by object id; this one
    does not, and saying so is more honest than claiming a grouping we did not
    actually perform.
    """
    rng = random.Random(SEED)
    assignment: dict[str, list[str]] = {"train": [], "val": [], "test": []}

    for label in CLASSES:
        names = sorted(i["name"] for i in items if i["label"] == label)
        rng.shuffle(names)
        n_train = round(len(names) * RATIOS[0])
        n_val = round(len(names) * RATIOS[1])
        for split_name, chunk in (
            ("train", names[:n_train]),
            ("val", names[n_train : n_train + n_val]),
            ("test", names[n_train + n_val :]),
        ):
            assignment[split_name].extend(f"{label}/{name}" for name in chunk)

    return assignment


def stats(assignment: dict) -> str:
    lines = ["| Class | Train | Val | Test | Total |", "| --- | ---: | ---: | ---: | ---: |"]
    totals = collections.Counter()
    for label in CLASSES:
        counts = [sum(1 for p in assignment[s] if p.startswith(f"{label}/")) for s in ("train", "val", "test")]
        totals.update({s: c for s, c in zip(("train", "val", "test"), counts)})
        lines.append(f"| `{label}` | {counts[0]} | {counts[1]} | {counts[2]} | {sum(counts)} |")
    lines.append(
        f"| **Total** | **{totals['train']}** | **{totals['val']}** | **{totals['test']}** | "
        f"**{sum(totals.values())}** |"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true", help="report the existing split only")
    args = parser.parse_args()

    if args.stats:
        print(stats(json.loads(SPLIT_FILE.read_text())))
        return

    items = download()
    assignment = split(items)
    SPLIT_FILE.write_text(json.dumps(assignment, indent=1) + "\n")
    print(f"\nsplit → {SPLIT_FILE}\n")
    print(stats(assignment))


if __name__ == "__main__":
    main()
