# End-to-end user flow — screenshot guide

For building the user-flow diagram in Canva. Every route in the app is listed,
in the order a real user walks them, with what each screen shows, what state it
needs, and who has to do what to get there.

> **Scope check:** the app has **12 routes**. All 12 are covered below —
> 11 screens plus one redirect. Nothing is left out.
>
> Related but different: [`../DEMO_VIDEO.md`](../DEMO_VIDEO.md) is the narration
> script for the 7-minute video. This file is the screenshot inventory. They
> agree on the story; this one is exhaustive about screens, that one is
> exhaustive about what to say.

---

## 0. Before you screenshot

### Get the app running

```bash
# Terminal 1 — backend on :8000
cd backend && uvicorn app.main:app --port 8000

# Terminal 2 — frontend on :5173
cd frontend && npm run dev
```

Or the whole thing in Docker, which is what the judges will run:

```bash
docker compose up --build      # app at :5173, API at :8000
```

### Load the demo factory

```bash
python demo-data/make_demo_data.py                      # timestamps → now
python3 demo-data/seed.py --api http://localhost:8000
```

That gives you 8 machines, 12 SOP/manual PDFs, 35 maintenance records, 480
sensor readings per machine, the factory business context, and 2 QC batches.

### Get your URLs

IDs change every re-seed, so derive them instead of copying from here:

```bash
sh scripts/flow-urls.sh
```

It prints all 11 numbered URLs ready to paste into the browser.

### Two decisions that change what the screenshots show

| | Offline stub *(default)* | Real engine |
| --- | --- | --- |
| Set | nothing | `AI_ENGINE_ENABLED=true` + `DEEPSEEK_API_KEY` in `.env`, needs pgvector |
| Health score, anomalies | real, deterministic | same |
| RCA narrative, work-order steps | generic placeholder text | written by the model, with citations |
| Document status on Setup | stays **Belum diindeks** | becomes **Terindeks** |
| QC Model screen | cannot fit a model | fits, shows accuracy |
| Sources list on the result | empty | real document citations |

**My recommendation:** screenshot with the **real engine**. Three of the screens
below are visibly thinner without it, and the citation list is one of the
judged claims. If you'd rather not set it up, tell me and I'll run the whole
seed against the real engine for you — I just need the `DEEPSEEK_API_KEY` put
in `.env`; I will not ask you to paste it into chat.

---

## 1. The flow at a glance

For the Canva diagram, the story is four bands. Colours below match the app's
own palette so the diagram and the product agree.

```
  ┌── ONBOARDING ──────────────┐   once per factory
  │  01 Setup                  │
  │  02 Mesin baru             │
  │  03 Model QC               │
  │  04 Konteks bisnis         │
  └──────────┬─────────────────┘
             ▼
  ┌── ANALYSIS ────────────────┐   per request
  │  05 Analisis baru          │
  │  05b Sedang berjalan       │
  │  06 Hasil analisis         │
  │  07 Perbandingan run       │
  └──────────┬─────────────────┘
             ▼
  ┌── DECISION ────────────────┐   human in the loop
  │  08 Daftar work order      │
  │  09 Work order  ──┬─ ajukan
  │                   ├─ setujui   (coordinator only)
  │                   └─ tolak     (coordinator only)
  └──────────┬─────────────────┘
             ▼
  ┌── EXECUTION & CLOSE ───────┐
  │  10 Eksekusi teknisi       │
  │  11 Verifikasi & laporan   │
  │     └─ ekspor CSV / JSON   │
  └────────────────────────────┘
```

Band colours from the design system: onboarding `#B4A193` clay · analysis
`#7F9E8C` sage · decision `#DD9251` apricot · execution `#5F8B8A` teal.

---

## 2. Route inventory — all 12

| # | Route | Screen | Needs |
| --- | --- | --- | --- |
| — | `/` | redirect → `/analyze` | nothing |
| 01 | `/setup` | Setup | seeded documents |
| 02 | `/machines/new` | Mesin baru | nothing (blank form) |
| 03 | `/qc-model` | Model QC | reference images; a fitted model needs the AI engine |
| 04 | `/business-context` | Konteks bisnis | seeded business context |
| 05 | `/analyze` | Analisis baru | ≥1 machine |
| 06 | `/analysis/:id` | Hasil analisis | a completed run |
| 07 | `/analysis/:id/compare?with=:id2` | Perbandingan run | **two** runs on the same machine |
| 08 | `/work-orders` | Daftar work order | ≥1 work order |
| 09 | `/work-orders/:id` | Work order | a work order |
| 10 | `/work-orders/:id/execute` | Eksekusi teknisi | work order at `in_progress` |
| 11 | `/work-orders/:id/report` | Verifikasi & laporan | a submitted technician result |

The catch-all `*` also redirects to `/analyze`; not worth a screenshot unless
you want to show the 404 behaviour.

---

## 3. Screen by screen

### 01 · Setup — `/setup`

**Band:** onboarding. **Story:** onboarding is uploading documents, not
retraining a model per factory.

Three drop zones (machine list, SOP & manual, maintenance history) and a
document table with per-document ingestion status.

Screenshot: the full page with 12 documents listed.

> **Watch the Status column.** With the offline stub every row reads
> **Belum diindeks** — meaning the document is *not* in the knowledge base and
> cannot be cited. That is honest, but it undercuts the grounding story. With
> the real engine plus `--reindex` they read **Terindeks**.

**Extra shot worth taking:** the empty state. Point the browser at a fresh
backend before seeding to catch "Belum ada dokumen…".

---

### 02 · Mesin baru — `/machines/new`

**Band:** onboarding. **Story:** adding a machine is a form, not an integration
project.

Sections: Identitas mesin · Spesifikasi · Histori data sensor · Citra referensi.

Screenshot: empty form, then **fill it in and screenshot again** — a filled form
reads far better in a flow diagram than an empty one. Suggested values:
`PUMP-02`, type `pump`, criticality `high`, location `Utilitas`.

**You do this one** — it is typing, and it takes a minute.

---

### 03 · Model QC — `/qc-model`

**Band:** onboarding. **Story:** the vision model is real and fitted from the
factory's own good units.

Sections: Mesin dan produk · Citra unit normal.

> **Currently shows an unavailable state.** Fitting a model calls the AI engine,
> and the seed skipped it (`ai_engine_unavailable`). With the engine on, seed
> again and this screen shows the fitted bank plus how many of its own reference
> images it flags back.

Screenshot both if you can: the unfitted state, and the fitted one. The pair
tells the onboarding story better than either alone.

---

### 04 · Konteks bisnis — `/business-context`

**Band:** onboarding. **Story:** decisions know constraints — stock, schedules,
people. This is the screen that makes "business-constraint-aware" concrete.

Sections: Jadwal produksi · Teknisi (3 seeded) · Stok sparepart (20 parts).

Screenshot: the full page. Scroll to the sparepart table and take a second shot
if the stock/ETA columns fall below the fold — the out-of-stock part is what
later blocks scheduling.

---

### 05 · Analisis baru — `/analyze`

**Band:** analysis. **Story:** one form, one synchronous analysis.

Sections: Mesin · Data sensor · Citra QC · Kondisi manual, plus the
**Kelengkapan input** panel on the right.

Screenshot **twice**:

1. **Empty** — nothing selected. Shows the input-completeness panel with
   everything hollow.
2. **Filled** — pick **Pompa Air Pendingin Utama** (PUMP-01), attach
   `demo-data/readings/PUMP-01.csv`, type an operator note. The completeness
   panel fills in as you go, which is the point of the screen.

**You do this one** — it needs a file picker.

---

### 05b · Sedang berjalan *(no route of its own)*

**Band:** analysis. **Story:** the wait is honest — the stage list says it is an
estimate, not telemetry.

This appears **after you press "Jalankan analisis"** and lasts until the run
returns. It is not reachable by URL.

Screenshot: as soon as the stage list appears. There is a **Batalkan** control —
worth capturing, it shows the user is never trapped.

> With the offline stub this is over in under a second. To catch it, use the
> real engine (10–60 s), or tell me and I can add a deliberate delay for one
> screenshot run.

---

### 06 · Hasil analisis — `/analysis/:id`

**Band:** analysis. **The centrepiece — give it the most space in the diagram.**

Band of four cards, then Root cause analysis, Anomali sensor, Hasil QC, Draft
work order, and the sticky approval bar.

Screenshot **at least three**:

1. **Top band** — health score donut with its deduction breakdown, QC → mesin
   chain, jendela maintenance, sumber & keterbatasan.
2. **Middle** — root cause analysis with confidence bars and citations, plus the
   anomaly table showing observed vs normal range and the method (`IQR`).
3. **Bottom** — draft work order and the approval bar reading
   *"AI mengusulkan dan menyiapkan; coordinator menyetujui."*

On PUMP-01 the health score comes out around **5/100** with critical anomalies
on `bearing_temp_c`, `vibration_mm_s` and `flow_m3h`. That is the machine to
use.

---

### 07 · Perbandingan run — `/analysis/:id/compare?with=:id2`

**Band:** analysis. **Story:** adoption is gradual — the same machine analysed
with partial input versus full input.

Needs **two runs on the same machine**. `flow-urls.sh` wires the two most recent
together. Run A is the minimal one, Run B the full one; each column shows its
input coverage as `n/7`.

Screenshot: the whole page, both columns side by side.

---

### 08 · Daftar work order — `/work-orders`

**Band:** decision.

Table with number, title, priority, status, created, and a chevron per row.

Screenshot: with 2–3 work orders in different statuses, so the status column
actually varies. Also worth a shot of the **empty state** on a fresh backend.

---

### 09 · Work order — `/work-orders/:id`

**Band:** decision. **This is the autonomy boundary — screenshot every state.**

Sections: Asal usul (links back to the analysis) · Penugasan · Pekerjaan, with
the six-step state track at the top and the action bar at the bottom.

**Screenshot the state track at each stage**, because the diagram needs the
progression:

| Shot | Status | How to get there |
| --- | --- | --- |
| a | `draft` | fresh from the analysis |
| b | `pending_approval` | click **Ajukan persetujuan** |
| c | `approved` | switch role to **Coordinator**, click **Setujui** |
| d | `scheduled` | click **Jadwalkan** |
| e | `in_progress` | click **Mulai kerjakan** |
| f | `rejected` | on a *different* work order: as Coordinator click **Tolak**, give a reason |

**Role switching:** top-right avatar chip → Coordinator / Teknisi / Engineer.
Approve and reject are coordinator-only; as Engineer the buttons are disabled
and say why. **That disabled state is worth a screenshot too** — it is the
governance claim, visible.

**You do this one** — it is clicking through, and each click is a diagram node.

---

### 10 · Eksekusi teknisi — `/work-orders/:id/execute`

**Band:** execution. **Story:** the technician submits a result; submitting does
not close the work order.

Sections: Langkah SOP (checklist) · Hasil pekerjaan · Bukti.

Needs the work order at **`in_progress`** and the role set to **Teknisi**.

Screenshot: with a few SOP steps ticked and findings typed, so it looks used.
Note the line *"Hasil ini tidak menutup work order"* — that is the claim.

**You do this one.**

---

### 11 · Verifikasi & laporan — `/work-orders/:id/report`

**Band:** execution. **Story:** AI verifies evidence; it never marks its own work
done.

Screenshot **twice**:

1. **Before verification** — the "Belum diverifikasi" state explaining the three
   possible verdicts (`resolved` / `partial` / `not_resolved`).
2. **After verification** — the verdict card with its evidence, the follow-up
   list, the final report, and the **Ekspor CSV / Ekspor JSON** buttons.

To verify: as Coordinator, trigger verification from the work order after the
technician result is in.

---

## 4. What I can run for you

Say the word on any of these and I'll do it:

- [ ] **Re-seed against the real engine** so documents index, the QC model fits,
      and the analysis carries real citations. Needs `DEEPSEEK_API_KEY` placed
      in `.env` by you — don't paste it in chat.
- [ ] **Walk a work order to any state** via the API, so you can screenshot a
      state without clicking through to it.
- [ ] **Create extra work orders** in mixed statuses, so the list screen (08)
      shows variety.
- [ ] **Capture all 11 routes automatically** at 1440×900 with Playwright and
      hand you the PNGs. Faster than clicking, but it cannot fill forms — shots
      02, 05-filled and 10 would still be yours.
- [ ] **Add a deliberate delay** to one run so the progress screen (05b) is
      catchable with the offline stub.

## 5. Checklist

Onboarding

- [ ] 01 Setup — seeded
- [ ] 01b Setup — empty state
- [ ] 02 Mesin baru — blank
- [ ] 02b Mesin baru — filled
- [ ] 03 Model QC — unfitted
- [ ] 03b Model QC — fitted *(needs the engine)*
- [ ] 04 Konteks bisnis — schedule + technicians
- [ ] 04b Konteks bisnis — sparepart stock

Analysis

- [ ] 05 Analisis baru — empty
- [ ] 05b Analisis baru — filled
- [ ] 05c Sedang berjalan — stage list
- [ ] 06 Hasil analisis — top band
- [ ] 06b Hasil analisis — RCA + anomalies
- [ ] 06c Hasil analisis — work order + approval bar
- [ ] 07 Perbandingan run

Decision

- [ ] 08 Daftar work order — populated
- [ ] 08b Daftar work order — empty
- [ ] 09a draft
- [ ] 09b pending_approval
- [ ] 09c approved
- [ ] 09d scheduled
- [ ] 09e in_progress
- [ ] 09f rejected
- [ ] 09g approve disabled as Engineer

Execution

- [ ] 10 Eksekusi — filled in
- [ ] 11 Verifikasi — before
- [ ] 11b Verifikasi — verdict + report + export

**27 screenshots across 12 routes.** The 12 marked *(needs the engine)* or
requiring typing are yours; the rest I can capture for you.

## 6. Things to keep out of the diagram

From `FINAL_IDEA.md` §16 — the wording judges check:

- Don't label anything **"real-time"** or **"monitoring"**. It is *synchronous,
  on request*.
- Don't imply the AI **acts**. It proposes; a coordinator approves.
- Don't draw a **feedback loop arrow** from verification back to analysis.
  Re-diagnosis is a user-initiated action, not an automatic loop — an arrow
  suggesting otherwise contradicts the scope claim.
- The knowledge base **does** get an arrow from the finished work order: the
  completed order is written back as a maintenance-history document. That is
  learning-as-documents, and it is the one loop that is real.
