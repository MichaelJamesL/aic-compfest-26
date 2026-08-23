# Screens

Seven screens, mapped one-to-one onto the locked demo chain
(`DECISIONS.md` D11). Nothing outside this list gets built — no dashboard, no
history page, no notification centre, no settings (`FR.md` roadmap).

Read [`VISUAL_LANGUAGE.md`](VISUAL_LANGUAGE.md) first; this document assumes its
tokens and never restates a colour or a size that lives there.

UI copy is **Indonesian**. Where `FINAL_IDEA.md` §15 fixes a phrase, use it
verbatim — those sentences also appear in the proposal and the video, and a
judge comparing them will notice a paraphrase.

---

## 0. App shell

```
┌──────────────────────────────────────────────────────────────────────┐
│  --page                                                              │
│   ┌────────────┬───────────────────────────────────────────────────┐ │
│   │ nav rail   │  --panel  (r-panel, inset 12)                     │ │
│   │ (white)    │  ┌─────────────────────────────────────────────┐  │ │
│   │            │  │ header: title · subtitle    search  ⚙ 🔔 avatar│ │
│   │ ○ Sistem   │  ├─────────────────────────────────────────────┤  │ │
│   │            │  │                                             │  │ │
│   │ ▪ Setup    │  │  screen content                             │  │ │
│   │ ▪ Analisis │  │                                             │  │ │
│   │ ▪ Work order│ │                                             │  │ │
│   │            │  └─────────────────────────────────────────────┘  │ │
│   │ [status]   │                                                   │ │
│   └────────────┴───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

Three nav items. Not four, not seven.

| Item | Route | Demo steps |
| --- | --- | --- |
| Setup | `/setup` | 1 |
| Analisis | `/analyze` → `/analysis/:id` | 2–9 |
| Work order | `/work-orders` → `/work-orders/:id` | 10–13 |

**Status card** — bottom of the rail, occupying the slot the reference gives its
promo card, in `--mint`. It replaces an upsell with something a judge needs to
see:

```
Mesin analisis
● DeepSeek aktif          ← GET /config/capabilities → capabilities.ai_engine
Semua proses sinkron.
Tidak ada background job.
```

When `ai_engine` is `false`, the dot turns `--warn` and the label reads
`Mode offline (stub)`. **Never hide this.** Presenting stub output as model
output is the one thing that would sink the submission.

Header: page title (22/600) with a one-line subtitle in `--text-3`. Right side:
settings icon, notification icon (no badge — we do not build notifications), and
an avatar chip with the demo user's name and role from `X-Demo-User`. A role
switcher lives here, because the demo needs to move between coordinator and
technician — style it as the reference's avatar chevron, not as a form control.

The header becomes `.glass-dark` and sticky once the content scrolls past 24px.
That is one of the five sanctioned glass uses.

---

## 1. Setup — `/setup`

Demo step 1. Three uploads, one screen, no wizard.

Layout: a 12-column band of three `--card` panels, then a full-width document
table below — the reference's card-row-then-table rhythm.

| Card | Content | API |
| --- | --- | --- |
| Daftar mesin | drop zone, `.csv` / `.json`, then a count and the parsed asset names | `POST /api/v1/assets/import` |
| SOP & manual | drop zone, multi-file, per-file progress | `POST /api/v1/knowledge/documents?kind=sop` |
| Histori maintenance | drop zone plus a manual "tambah catatan" link | `POST /api/v1/knowledge/documents?kind=log`, `POST …/maintenance-records` |

Drop zone: dashed 1px `--hairline`, radius `--r-control`, 120 tall, centred
16px icon over a 13/500 label and a 12 `--text-3` hint listing accepted
extensions and the 10 MB cap. On drag-over the border goes solid `--text-2`.
No animation beyond that.

**Document table** (full width, mirrors the reference's invoices table):
`Nama · Jenis · Ukuran · Status · Aksi`. Status is a dot plus label:

| `ingestion_status` | Dot | Label | Meaning |
| --- | --- | --- | --- |
| `pending` | `--warn` | Belum diindeks | **Not in the knowledge base yet.** Not retrievable. |
| `ready` | `--ok` | Terindeks | in pgvector |
| `failed` | `--crit` | Gagal | show `ingestion_error` in a tooltip |

Action column: "Indeks" button for `pending`, "Ulangi" for `failed`.

This distinction is load-bearing, not cosmetic: a `pending` document contributes
nothing to `sources`, and today **every** document is stuck there
(`../DEFECTS.md#reindex-nameerror`). The UI must make that visible rather than
implying the corpus is loaded.

**Empty state:** one line — "Belum ada dokumen. Unggah SOP dan histori agar
analisis punya dasar yang bisa dikutip." — plus the three drop zones. No
illustration, no onboarding checklist.

---

## 2. Analisis baru — `/analyze`

Demo step 2. **One form, one submit.** The rulebook requires the UI to accept a
single input and show the AI's output; this is that form.

Two columns, 8/4:

**Left (8) — input, in the order the engine consumes it**

1. *Mesin* — asset select. Shows type, criticality, last analysis date.
2. *Data sensor* — CSV drop zone, or "gunakan endpoint mock PLC/IoT" as a
   secondary action. After parsing, show a compact preview: row count, detected
   tags, time range. Do not render the rows.
3. *Citra QC* — multi-image drop zone with a thumbnail grid (64px, radius
   `--r-control`), count, and remove-on-hover. *Blocked on
   `../API.md` → `POST …/qc-batches`.*
4. *Konteks bisnis* — production schedule, sparepart + ETA, technicians
   available, operator report. Send the **complete** object; this endpoint
   replaces rather than patches (`../API.md` gotcha 2).
5. *Kondisi manual* — free-text, always available. This is the field that keeps
   the Starter path working with no sensors at all.

**Right (4) — "Kelengkapan input"**

A `--clay` card listing the five inputs with a filled or hollow dot each, and
one honest line underneath:

> Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
> lengkap input, makin dalam keputusannya.

(Fixed wording — `FINAL_IDEA.md` §15 "Adopsi". Do not rewrite it.)

Below it, a plain-language note about what each missing input costs — "tanpa
jadwal produksi, jendela maintenance tidak bisa dioptimalkan, hanya
diprioritaskan". This is the *Partial-input analysis* FR made visible, and it is
what the second demo run (`FINAL_IDEA.md` §11) shows off.

Primary button: **Jalankan analisis**. One button. It is disabled only when no
asset is selected — never because an input is missing; that is the whole point.

### The waiting state

`POST …/analyses` blocks for up to 120 seconds with no progress endpoint.
Do not show a spinner for two minutes.

Show the pipeline as a stepped list on the panel, advancing on **elapsed-time
estimates**, with each step labelled by what it does and whether it is
deterministic:

```
✓ Deteksi anomali          deterministik      0.2s
✓ Klasifikasi defect QC    model fine-tuned   1.4s
✓ Mapping defect → failure mode              0.1s
◐ Menyusun diagnosis       DeepSeek           …
○ Jendela maintenance      deterministik
○ Draft work order         DeepSeek
```

Be honest that the timings are estimates: the ticks reflect the pipeline order,
not server events. Label the section "Perkiraan tahap" so it is not read as
telemetry. Cap the estimate at the real timeout and fall back to "masih
berjalan…" rather than stalling at 99%.

This screen is on camera for two minutes of a seven-minute video. It is worth
the effort, and it doubles as an explanation of the architecture.

---

## 3. Hasil analisis — `/analysis/:id`

Demo steps 3–9. The centrepiece.

Header: asset name, run timestamp, `engine_mode` chip, priority badge.
Actions: `Ekspor` (secondary), `Buat work order` (primary).

### Band — four cards, 12-column grid, `col-span-3` each

This is the reference's card row, reused exactly.

**A. Skor kesehatan** — dark card, donut, 150/26 as specified.
Centre: the score at 30/600 with `/100` in `--text-3`, and the severity word
below. The ring segments are the **deduction breakdown**, not decoration:
anomalies / defects / overdue / repeat / remaining, in `--crit`, `--high`,
`--warn`, `--clay`, `--raised`. Legend in a 2×2 grid beneath, same as the
reference's platform legend — label plus percentage.

A 11.5 `--teal` line under the card: `Dihitung deterministik, bukan oleh LLM.`

**B. Rantai QC → mesin** — `--sage` card. **The differentiator. Never cut it.**

```
thread_top   ▲ 3 batch berturut-turut          ← defect class + trend
   ↓
Kandidat: tool_wear · spindle_runout           ← from qc_failure_modes.yaml
   ↓
tool_wear_min  p95   ✓ mendukung               ← corroboration
torque_nm      naik  ✓ mendukung
   ↓
Prioritas naik: medium → high                  ← priority_delta, applied
SOP-CNC-04 §3.2
```

The **restraint case** must be designed, not treated as an error state: when no
signal corroborates, the last two rows become

```
Tidak ada sinyal mesin yang mendukung
Prioritas tidak dinaikkan — kemungkinan penyebab di luar mesin
```

in `--text-3` on the same card. A judge seeing the system decline to escalate is
worth more than a system that always escalates.

*Blocked on `mapping/qc_failure_modes.yaml` and the classifier — see
`../requirements/AI_ENGINE.md` §3–4.*

**C. Jendela maintenance** — `--apricot` card.

Chosen window as a date-time range at 17/600, the expected cost beneath it, then
the runner-up with **why it lost**, then blockers as `--crit` dots. The runner-up
line is the point of the card — it is what makes "optimal" arguable:

```
Terpilih     Sen 24 Agu, 22:00 – 00:00      Rp 18,4 jt
Runner-up    Sab 29 Agu, 08:00 – 12:00      Rp 24,1 jt
             kalah: scrap terus terakumulasi 3 shift lagi
Blocker      ● insert TNMG ETA 2 hari
```

Footer, small: the objective function from `FINAL_IDEA.md` §4, in full. It is
one sentence and it answers the obvious jury question in place.

*Blocked on `decide.py`.*

**D. Sumber & keterbatasan** — `--clay` card.
Top: the documents actually used, from `result.sources`, each as
`Judul §chunk`. Bottom: which inputs were absent and what that limited. If
`sources` is empty, say so plainly — "Tidak ada dokumen terindeks; analisis
tidak memiliki dasar dokumen yang bisa dikutip" — do not render an empty list.

### Root cause analysis — full-width `--card`

One row per cause: the cause at 15/500, a confidence bar (4px, `--teal`, with
the percentage as tabular text — no percentage ring), evidence chips, and
document citations rendered as `[Judul]` links that scroll to card D.

Sort by confidence descending. Show at most four; the rest behind "lihat
semua".

### Detail row — 8/4

**Anomali sensor** (8) — table exactly like the reference's invoices table:
`Tag · Nilai teramati · Rentang normal · Keparahan · Metode`. Severity is a dot
plus label. `Metode` reads `IQR` — showing the method is what separates this
from a black box.
Empty: "Tidak ada anomali di luar rentang normal." — a real result, not an
empty state.

**Hasil QC** (4) — bar chart of defect rate per batch, bars 14/10/r6, the
current batch one step darker, per-class breakdown below as label + count +
percentage. Tooltip is the one glass element in the chart.

### Draft work order — full-width `--card`

Title, steps as a numbered list, parts with stock status, required skills,
safety notes in a `--crit`-bordered block, estimated duration, suggested
technician.

### Approval bar — sticky, `.glass-dark`, bottom of the viewport

```
AI mengusulkan dan menyiapkan; coordinator menyetujui.     [Tolak]  [Setujui]
```

`Setujui` is primary; `Tolak` is destructive and opens a required-reason field.
Both are disabled with a tooltip when the current role is not coordinator or
manager. This bar is the autonomy boundary made literal, per `DECISIONS.md` D9 —
and it is currently unbuildable server-side (`../DEFECTS.md#wo-approve`).

### States

| State | Design |
| --- | --- |
| `status: "failed"` | Full-card message with `error_code`, the `request_id`, and a retry button. Never a blank result page. |
| `engine_mode: "offline_stub"` | Persistent `--warn` strip at the top of the panel: "Output dari stub offline, bukan model." |
| partial input | Cards C and D render with what exists; missing sections say which input is absent, in `--text-3`. Never hide a card — the absence is the message. |

---

## 4. Work order — `/work-orders` and `/work-orders/:id`

Demo step 10.

**List**: the reference's table, one row per order —
`No · Aset · Judul · Prioritas · Status · Dibuat · Aksi`. Status as a dot plus
label across the eight states. Filter control top-right styled like the
reference's `Filter` button: hairline border, radius `--r-control`, 16px icon.

**Detail**: the work order as the approved artefact — header with status and a
horizontal state track (`draft → pending_approval → approved → scheduled →
in_progress → completed`), the steps, parts, skills, safety, and an audit trail
list showing who did what and when, from the audit events.

The state track is a row of 6 labelled dots connected by 1px hairlines; the
current one is filled and labelled, past ones filled and dim, future ones
hollow. Terminal `rejected` / `cancelled` render the track in `--text-3` with
the terminal step in `--crit`.

---

## 5. Eksekusi teknisi — `/work-orders/:id/execute`

Demo step 11. Role: technician. Deliberately plain — this is a form filled on a
factory floor.

Checklist of the SOP steps with checkboxes; a findings textarea; parts actually
used; time spent; optional photo evidence. One primary button: **Kirim hasil
pekerjaan**.

Do **not** let this screen mark the work order complete. It submits a result;
verification decides the outcome. (The current `progress` endpoint auto-completes
at 100% — that bypasses the autonomy boundary and is flagged in
`../DEFECTS.md#progress-nameerror`.)

*Blocked on `POST …/result`.*

---

## 6. Verifikasi & laporan — `/work-orders/:id/report`

Demo steps 12–13.

**Verdict card** — full width, tinted by outcome:

| Verdict | Card | Label |
| --- | --- | --- |
| `resolved` | `--sage` | Masalah terselesaikan |
| `partial` | `--apricot` | Sebagian terselesaikan |
| `not_resolved` | `--crit` at 18% tint with a `--crit` border | Belum terselesaikan |

Beneath the verdict: the evidence the engine used, each line traceable to a
reading, a document, or the technician's own report. For `partial` and
`not_resolved`, a follow-up list and a secondary button "Jalankan diagnosis
ulang" — which starts a **new** analysis on user request. It must be visibly
manual; an automatic re-run would be a feedback loop, which the rulebook
forbids (`DECISIONS.md` D4).

**Final report** — problem, action taken, verification result, final asset
state, and one line confirming the completed work order was written back to the
knowledge base as maintenance history. Export as CSV/JSON from the header.

---

## 7. Perbandingan run — `/analysis/:id/compare?with=:otherId`

The graceful-degradation beat, ±40 seconds of the video (`FINAL_IDEA.md` §11).

Two columns, same asset, two runs. Left: dokumen + kondisi manual only. Right:
full input. Same section order down both sides so the eye compares by row.
Sections present on the right but absent on the left render as a `--text-3`
line naming the missing input.

**Run B is picked, not typed.** A select above the columns lists the asset's
other runs (`GET /assets/{id}/analyses`), each labelled with its timestamp, tier
and health score. Reaching this screen must not require editing a UUID into the
address bar — it is a 40-second video beat. When the asset has only one run the
select says so and offers "Jalankan analisis kedua"; a run is never offered as
its own comparison.

This is the one sanctioned use of the per-asset analyses endpoint. It is not a
history page — see `DEFECTS.md#analysis-history-out-of-scope`.

One line at the top, fixed wording:

> Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
> lengkap input, makin dalam keputusannya.

Under 150 lines of layout — it reuses the section components from screen 3.
Build it last; it is the cheapest high-value screen in the set.

---

## Responsive

Desktop-first: the demo is recorded at 1440. Below 1024 the rail collapses to a
64px icon-only strip; below 768 the 12-column band stacks to one column and the
tables scroll horizontally inside their own container — the panel itself must
never scroll sideways. No mobile-specific navigation.

## State coverage

Every screen ships four states. A screen with only its happy path is unfinished:

- **Empty** — a sentence saying what to do, no illustration.
- **Loading** — skeletons in `--raised` at the real content's dimensions. No
  shimmer in another hue, no spinner where a skeleton fits.
- **Error** — the message mapped from `error.code`, plus the `request_id` in
  `--text-3`, plus one retry action.
- **Partial** — sections render with what exists and name what is missing. This
  is a first-class state in this product, not a degraded one.
