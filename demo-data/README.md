# Demo data

A whole factory's worth of input for a demo run: 8 machines, 12 PDFs (SOPs and
vendor manuals), 35 maintenance records, PLC/sensor exports for every machine,
and the factory-wide business context the recommendation depends on.

```
demo-data/
  assets.csv              8 machines: name, type, criticality, location, specs
  readings/<ID>.csv       PLC export per machine (tag, value, unit, recorded_at)
  maintenance-history.csv 35 records across all machines
  business-context.json   shifts, technician roster, warehouse stock, operator reports
  docs/                   9 real vendor/regulator PDFs + 3 Indonesian SOPs
  qc/reference/           20 known-good part photos, to fit the PatchCore model
  qc/batches/<ID>/        one end-of-shift inspection batch per mill
  source/ai4i2020.csv     upstream dataset the mill readings come from
  make_demo_data.py       regenerates the CSVs (timestamps relative to now)
  seed.py                 pushes everything into a running backend
```

## Load it

```bash
backend/.venv/bin/python demo-data/make_demo_data.py    # refresh timestamps to "now"
python3 demo-data/seed.py                               # http://localhost:8000
python3 demo-data/seed.py --api http://localhost:8000 --reindex   # + RAG ingest
```

`seed.py` is stdlib-only and re-runnable: assets match on `external_id`, readings
and maintenance records carry `external_id`s the backend de-duplicates on, and
the business context is a full replace by design. Re-uploading documents is the
one thing that duplicates.

It walks the same endpoints a person would: `POST /api/v1/assets` per machine,
`POST /api/v1/assets/{id}/readings/import`, `POST /api/v1/assets/{id}/baseline`
(fits the anomaly baseline on the readings just imported),
`POST /api/v1/maintenance-records/import`, `PUT /api/v1/business-context`
(factory-wide), `PUT /api/v1/assets/{id}/condition` (the per-machine operator
report), `POST /api/v1/knowledge/documents` per PDF, and for visual QC
`POST /api/v1/assets/{id}/models` (fits PatchCore on the reference photos)
followed by `POST /api/v1/assets/{id}/qc-batches` per inspection batch.

To demo the upload flow by hand instead, every file here goes through a UI path
as-is. The CSV asset importer only reads `name`, `asset_type`, `criticality` and
`external_id`, so `location` and `specs_json` are dropped on that path —
`seed.py` posts them properly.

## The machines, and what the demo should show

Scores are what the engine's own `health_score` computes from these files — the
deterministic part, no LLM involved. Two detectors can produce them: the
per-batch IQR fence (what the offline stub uses) and the robust-z baseline
fitted by `POST /assets/{id}/baseline` (what the real engine uses). The data is
built so both agree on which machines are sick; the exact number moves a little
between them, shown below as fence / baseline.

| Machine | What it is | Score | Story |
| --- | --- | --- | --- |
| PUMP-01 | Grundfos NK 80-250 cooling water pump, 30 kW | 5 / 5 | Bearing failing: 62→93 C, vibration 2.6→8.1 mm/s past the ISO 10816-3 limit, flow falling off its duty point. SOP-PM-001 names the bearing (SKF 3306 A-2Z) and stock is 1 against a minimum of 2. Two identical unscheduled inspections in the last 30 days add a repeat-failure deduction. |
| COMP-01 | OPPAIR 55 kW screw compressor | 30 / 40 | Air filter clogging: dP 0.22→0.64 bar past the 0.50 limit, oil temp 78→101 C past the 95 C trip, network pressure sagging. The separator is out of stock, ETA 5 days. |
| CNC-MILL-01 | Bridgeport Series I mill | 30 / 55 | Real labelled heat-dissipation failures from AI4I: the process-to-air temperature gap collapses below 8.6 C while the spindle slows to 1222 rpm and torque climbs to 66.8 Nm. IK-CNC-003 describes exactly this mode. |
| MOTOR-01 | ABB 30 kW conveyor motor | 70 / 70 | One vibration spike to 3.9 mm/s. Watch, don't panic — and the loose mounting bolts are already in its history. |
| CNC-MILL-02 | Bridgeport Series I mill | 100 | Healthy twin of MILL-01 running the same job — the comparison that makes the anomaly credible. |
| CONV-01, PRESS-01, CHILL-01 | conveyor, 100 t press, 80 TR chiller | 100 | Healthy fleet background. |

PUMP-01 is the machine to demo end to end: the sensor signature, the SOP, the
maintenance history, the spare-part shortage and the operator report all have to
line up in one recommendation.

## Visual QC

The mills machine four-lug flanged nuts (product code `metal-nut-4lug`). QC
photographs a sample at the end of each shift and the batch goes to the engine
alongside the sensor data — a hot spindle shows up as scratches and
discolouration before it shows up as a breakdown, which is the link IK-CNC-003
section 7 spells out.

| Set | Contents |
| --- | --- |
| `qc/reference/metal-nut-4lug/` | 20 known-good parts. `POST /assets/{id}/models` fits the PatchCore memory bank on these. |
| `qc/batches/CNC-MILL-01/` | 8 parts off the failing mill: 3 good, 2 scratched, 2 bent, 1 discoloured. Filenames carry the ground truth. |
| `qc/batches/CNC-MILL-02/` | 6 parts off the healthy mill, all good. |

Attach a batch to an analysis with `{"qc_batch_id": "<id>"}` — `seed.py` prints
the ids it created. Defect detection needs the vision extra
(`uv sync --extra vision` in `ai-engine`, i.e. anomalib); without it the batches
still upload and appear in the analysis snapshot, just with no findings.

Two banks get fitted from the same reference set, under the product name and
under the asset id, because the engine inspects the batch images under
`batch.product` and then the same paths again under `asset.id`
(`ai-engine/src/context.py`). One fit would leave the second call without a
bank.

The images are **MVTec AD** (`metal_nut`), CC BY-NC-SA 4.0 — non-commercial,
share-alike. They are downloaded on demand by `make_demo_data.py` and
**not committed**; `qc/.gitignore` keeps them out and `qc/LICENSE-mvtec.txt`
carries the licence. Cite Bergmann, Fauser, Sattlegger and Steger, *MVTec AD — A
Comprehensive Real-World Dataset for Unsupervised Anomaly Detection*, CVPR 2019.

## Where the data comes from

**Real, downloaded:**

| File | Source |
| --- | --- |
| `source/ai4i2020.csv`, `readings/CNC-MILL-0{1,2}.csv` | [UCI AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset) (CC BY 4.0) — 10,000 labelled milling cycles |
| `docs/manual-bridgeport-series-i-milling-machine.pdf` | [Bridgeport Series I mill manual](https://me.berkeley.edu/wp-content/uploads/2020/09/Bridgeport-Vertical-Mill-Manual.pdf) (UC Berkeley ME) |
| `docs/tds-coolant-castrol-syntilo-9902.pdf` | [Castrol Syntilo 9902 technical data sheet](https://cdn.mscdirect.com/global/images/ProductDataSheet/pds_sku_1180520_technicaldatasheet_technicalspecifications_spec.pdf) (via MSC Direct) — 2 pages, the coolant the mills run |
| `docs/manual-pump-grundfos-nk-nkg.pdf` | [Grundfos NK, NKG installation and operating instructions](https://api.grundfos.com/literature/Grundfosliterature-4609696.pdf) |
| `docs/manual-motor-abb-low-voltage.pdf` | [ABB low voltage motors installation, operation and maintenance manual](https://docs.rs-online.com/6952/0900766b81294de7.pdf) |
| `docs/manual-screw-air-compressor-oppair.pdf` | [OPPAIR screw air compressor user manual](https://www.oppaircompressor.com/uploads/OPPAIR-User-Manual.pdf) |
| `docs/manual-bearing-installation-maintenance-skf.pdf` | [SKF bearing installation and maintenance guide](https://cdn.skfmediahub.skf.com/api/public/0901d1968024f02a/pdf_preview_medium/0901d1968024f02a_pdf_preview_medium.pdf) |
| `docs/manual-bearing-handbook-electric-motors-skf.pdf` | [SKF bearing handbook for electric motors](https://cdn.skfmediahub.skf.com/api/public/0901d19680056c36/pdf_preview_medium/0901d19680056c36_pdf_preview_medium.pdf) |
| `docs/manual-pump-life-cycle-costs-doe.pdf` | [Pump life cycle costs, US DOE / Hydraulic Institute](https://www.energy.gov/sites/prod/files/2014/05/f16/pumplcc_1001.pdf) |
| `qc/reference/`, `qc/batches/` | [MVTec AD, `metal_nut` category](https://www.mvtec.com/company/research/datasets/mvtec-ad) (CC BY-NC-SA 4.0), fetched from a [Hugging Face mirror](https://huggingface.co/datasets/MSherbinii/mvtec-ad-metal-nut) |
| `docs/sop-lockout-tagout-osha-3120.pdf` | [OSHA 3120, control of hazardous energy](https://www.osha.gov/sites/default/files/publications/osha3120.pdf) |

Third-party documents, used here as demo inputs under their own licences.

**Written for the demo:** the three Indonesian SOPs — `sop-pm-001` (PUMP-01),
`sop-pm-002` (COMP-01), `sop-ik-cnc-003` (both mills). Their thresholds are not
invented: bearing relubrication intervals and grease quantities come from the
Grundfos manual's table for a 48 mm shaft, vibration limits from ISO 10816-3
class II, the mill's failure modes from AI4I's own published failure definitions.

**Synthetic but matched to the nameplate:** readings for PUMP-01, COMP-01,
MOTOR-01, CONV-01, PRESS-01 and CHILL-01, `maintenance-history.csv`, and
`business-context.json`. Levels follow the machine: 48 A on a 30 kW motor,
118 m3/h at the NK 80-250's duty point, 27 bar condensing for R-410A. A steady
level with noise, and a fault signature grafted onto the last few hours.

## What "consistent" means here

Everything cross-references, and the generator fails if it stops doing so:

- Every part code in `maintenance-history.csv` is either stocked in
  `business-context.json` or listed as vendor-supplied, and the ones the story
  turns on are named in the SOPs (`skf-3306-a2z`, `separator-element`, …).
  Parts are linked to the machines they fit, so an analysis of PUMP-01 sees pump
  parts and not the whole warehouse.
- Tag names in `readings/*.csv` are the tags the SOP threshold tables list.
- Every machine that fails in this demo has a manual in `docs/` covering that
  machine, and specs in `assets.csv` that match that manual.
- The mills' AI4I cycles are narrowed to one product type inside one operating
  band, because one machine runs one job — AI4I samples independent cycles
  across products and settings, and a single failure is invisible against that
  spread. The measured tuples are untouched; only the selection is ours.
- The QC images are the product the mills are said to make, the SOP names the
  same product code, and the defect types in the batch are the ones the SOP's
  defect table explains.
- AI4I's tool-wear column is not exported as a PLC tag: each row is a fresh
  tool, so it would read as a counter resetting at random. Tool life is an
  operator rule in IK-CNC-003 instead.

## Regenerating

`make_demo_data.py` re-emits every CSV with timestamps relative to *now* — run
it before a demo so "3 hours ago" really is 3 hours ago. Run it with an
interpreter that can import `ai-engine/src` (`backend/.venv/bin/python`): it
verifies the result with the engine's own `detect_anomalies` and `health_score`,
in both detector modes, over exactly the rows the analyzer reads. A demo where
the sick machines don't light up, or the healthy ones do, fails there instead of
on stage.
