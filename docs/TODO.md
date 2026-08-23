# TODO — jadwal eksekusi ke deadline

> Ditulis 23 Agustus 2026 ~04:00 WIB. **Deadline 25 Agustus 23:55 WIB; target
> submit 25 Agustus 20:00.** Sisa ≈ 64 jam efektif, 3 track paralel.
>
> Ini jadwal, bukan scoreboard. Status kebenaran ada di
> [`STATUS.md`](STATUS.md); centang checklist ada di [`requirements/`](requirements/).
> Menggantikan tabel "Rencana ~71 jam" di `DECISIONS.md`, yang ditulis ketika
> `backend/` belum ada.

## Yang mengikat

Bukan kedalaman AI. Tiga hal ini, berurutan:

1. **Compliance** — satu model wajib di-fine-tune (`DEFECTS.md#compliance-finetune`).
   Belum ada. Tidak bisa disubstitusi, tidak bisa digeser ke hari terakhir.
2. **Aplikasi yang bisa dijalankan panitia** — `docker compose up` dari clone
   bersih, lalu rantai 13 langkah jalan tanpa putus untuk direkam **tanpa cut**.
3. **Proposal + video ≈ 30% bobot** — setara arsitektur. Bukan pekerjaan sisa.

Konsekuensinya: **fitur baru di luar daftar ini dilarang.** Overbuilt dihukum
sama kerasnya dengan underbuilt (`DECISIONS.md` D0).

---

## BLOK 0 — selesai

Semua track lain menunggu ini. Seluruhnya di `backend/app/main.py`, sekali duduk.

| # | Tugas | Ref | Buka jalan untuk |
| --- | --- | --- | --- |
| 0.1 | ~~Route `approve` → `approved` dan `reject` → `rejected`; rename yang lama jadi `submit`~~ | `DEFECTS.md#wo-approve` | **done**; demo langkah 10–13, seluruh screen 4–6 |
| 0.2 | ~~Hapus route `documents` duplikat + `transition`/`TRANSITIONS` yang dobel di `main.py`~~ | `#duplicate-doc-route`, `#transition-shadowed` | **done**; state machine diuji |
| 0.3 | ~~Perbaiki `reindex_document` (`Document` tidak ter-import)~~ | `#reindex-nameerror` | **done**; grounding & sitasi dapat berjalan |
| 0.4 | ~~Tiga one-liner: `data.specs_json`, `request: Request` di `progress`, urutan argumen `JSONResponse`~~ | `#patch-asset-specs`, `#progress-nameerror`, `#ready-jsonresponse-args` | **done** |
| 0.5 | ~~Pisah `AIENGINE_DATABASE_URL` dari `DATABASE_URL`~~ | `#env-database-url` | **done** |
| 0.6 | ~~Test: lifecycle work order penuh, transisi ilegal → 409, isolasi `factory_id`~~ | `requirements/BACKEND.md` | **done** |

**Hasil:** lifecycle `draft → pending_approval → approved → scheduled → in_progress
→ completed` hijau di test, dan document ingestion/re-index sudah diuji terhadap pgvector.

---

## BLOK 1 — paralel, 23 Agustus pagi → 24 Agustus malam

### Track AI — urutan ini, jangan ditukar

| # | Tugas | Est | Catatan |
| --- | --- | --- | --- |
| A1 | Unduh AI4I + MVTec `screw`; `qc/preprocess.py` | 3j | Resize 224, normalisasi ImageNet, augmentasi, class-weight, split tanpa bocor antar-objek. Wajib didokumentasikan di proposal. |
| A2 | **`qc/train.py` → latih → bobot → `qc/METRICS.md`** | 4j | **COMPLIANCE. Kerjakan hari ini.** MobileNetV3-Small, 5 kelas + `good`, < 1 jam CPU. Per-class accuracy + confusion matrix + ukuran split. |
| A3 | `mapping/qc_failure_modes.yaml` + loader + langkah koroborasi | 4j | Isi filenya sudah jadi di `FINAL_IDEA.md` §7.2 — salin, jangan karang ulang. **Termasuk jalur menahan diri** saat sinyal tidak mendukung. |
| A4 | `defect_class` + `class_confidence` di `DefectFinding`; wire classifier ke pipeline | 2j | Ubah kontrak → update `API.md` + tipe frontend serentak. `DEFECTS.md#defect-class` |
| A5 | `decide.py` — kandidat jendela, filter infeasible, skor, **runner-up + alasan kalah** | 4j | Tanpa LLM. Ini yang mengubah "optimal" jadi angka yang bisa dibantah. |
| A6 | ~~`engine.verify()` → verdict + bukti~~ | 2j | **Selesai.** Satu panggilan sinkron. Tidak ada loop. |
| A7 | `detect_anomalies` baseline per aset yang dibekukan | 2j | Sisi bawah sudah diperbaiki dan diuji; baseline beku tetap syarat rulebook. |
| A8 | `scripts/gen_synthetic.py` — jadwal produksi, stok+ETA, roster teknisi, korpus SOP | 2j | Asumsi generator ditulis; dipakai di proposal §metodologi. |

### Track Backend — setelah Blok 0

| # | Tugas | Est | Catatan |
| --- | --- | --- | --- |
| B1 | ~~`POST /assets/{id}/qc-batches` — upload batch citra~~ | 3j | **done**; classifier dan mapping tetap tersisa di track AI |
| B2 | `POST /assets/{id}/readings/import` — CSV sensor sekali request | 1j | Implemented and covered by backend API tests. |
| B3 | ~~`POST /assets/{id}/ingest/plc` + `/ingest/iot`~~ | 1j | **done**; mock adapters persist readings |
| B4 | ~~`POST /work-orders/{id}/result`, `/verify`, `GET /report`~~ | 3j | **done**; synchronous verification workflow, frontend gating covered separately |
| B5 | Ekspor work order + laporan CSV/JSON | 2j | Pengganti jujur untuk integrasi ERP. |
| B6 | **`docker-compose.yml` full-stack + Dockerfile pasang `ai-engine` + uji dari clone bersih** | 3j | build and existing-stack smoke pass; isolated clean-clone run remains |
| B7 | Seed script data demo (2 mesin, SOP, histori, batch QC) | 2j | Dikunci sebelum dry run; jangan diubah setelah itu. |

### Track Frontend — mulai sekarang juga, jangan menunggu backend

Bangun ke bentuk yang ada di [`API.md`](API.md). Tujuh screen di
[`design/SCREENS.md`](design/SCREENS.md); urutan ini menaruh yang paling sering
muncul di kamera lebih dulu.

| # | Tugas | Est |
| --- | --- | --- |
| F1 | Scaffold Vite+React+TS, token `@theme`, font, `api/client.ts` + `api/types.ts` | 4j |
| F2 | Primitives: Card, MetricCard, Badge, Button, Input, DropZone, Table, Dot, Donut, Bars, Skeleton | 6j |
| F3 | Shell: rail 3 item, header, status card mesin analisis | 3j |
| F4 | Screen 3 — **Hasil analisis** (band 4 kartu, RCA, tabel anomali, QC, draft WO, approval bar) | 8j |
| F5 | Screen 2 — Analisis baru + **waiting state bertahap** | 5j |
| F6 | Screen 1 — Setup, tabel dokumen dengan 3 status ingestion | 3j |
| F7 | Screen 4–6 — Work order, eksekusi teknisi, verifikasi + laporan | 6j |
| F8 | Screen 7 — Perbandingan run (degradasi anggun) | 2j |

F4 lebih dulu dari F5/F6 karena itu layar yang paling lama tampil di video dan
paling menentukan penilaian.

---

## BLOK 2 — 24 Agustus malam: integrasi & dry run

- Rangkai 13 langkah `DECISIONS.md` D11 end-to-end di atas seed data.
- **Dry run 3×.** Catat setiap yang patah; perbaiki hanya yang patah.
- Jalankan run kedua dengan input minimal (bukti degradasi anggun).
- `git clone` ke folder baru → `docker compose up` → ulangi rantai. Kalau gagal
  di sini, ini prioritas di atas segalanya.

---

## BLOK 3 — 25 Agustus: freeze, rekam, tulis

**Feature freeze 25 Agustus 06:00 WIB.** Setelah jam ini hanya perbaikan bug
yang muncul saat rekaman. Tidak ada pengecualian.

| Kapan | Apa |
| --- | --- |
| Pagi | Latihan rekaman 2×, lalu **rekam proof of work** — double screen terminal + aplikasi, **dilarang keras ada cut** |
| Siang | Rekam video karya inovasi. Semua fitur di video inovasi **wajib ada** di proof of work |
| Sore | Finalisasi proposal: metodologi, alur perolehan dataset (A1), preprocessing, tabel landscape (D7), hitungan ROI (D8) |
| 20:00 | **Submit.** Jangan menyentuh 23:55 |

Cek terakhir: repo public · Conventional Commits · tidak ada jejak institusi
pendidikan · video proof of work unlisted dengan penamaan yang benar.

---

## Kalau tertinggal — potong dengan urutan ini

Dari `DECISIONS.md`, ditambah dua baris frontend:

1. Screen 7 (perbandingan) dibuang.
2. Screen 5+6 digabung ke halaman detail work order.
3. Kelas classifier 5 → 3 (`thread_top`, `scratch_neck`, `good`).
4. `decide.py` disederhanakan: probabilitas → tier risiko low/med/high.
5. Seed data 2 mesin → 1.
6. Frontend polos tanpa styling.

**Jangan pernah dipotong:** fine-tune (A2), `docker compose` + README yang jalan
(B6), video proof of work, bagian metodologi proposal.
