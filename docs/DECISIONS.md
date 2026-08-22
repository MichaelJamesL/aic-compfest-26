# DECISIONS — AIC COMPFEST 18 (Penyisihan)

> Ditulis 23 Agustus 2026, 00:25 WIB. **Sisa waktu ke deadline: ~71 jam**
> (25 Agustus 2026, 23:55 WIB). Dokumen ini mengunci keputusan; kalau ada yang
> mau diubah, ubah di sini dulu, jangan di kode.

Semua kutipan aturan di bawah diverifikasi langsung dari `[AIC] AI Innovation
Challenge.pdf` (AIC RULEBOOK, 28 hal.) — bukan dari ingatan.

---

## 0. Fakta yang mengubah prioritas

**Repo belum punya `backend/` maupun `frontend/`.** 14 commit, semuanya
`ai-engine`. `docker-compose.yml` cuma menyalakan Postgres.

Rulebook mensyaratkan (hal. 17, 20):
- repo public berisi **README setup guide + docker compose** yang bisa dijalankan panitia,
- **video proof of work maks. 7 menit** yang menunjukkan *double screen terminal + aplikasi*,
  **DILARANG KERAS memotong (cut) video**.

Artinya: yang mengikat sekarang bukan kedalaman AI, tapi **adanya sesuatu yang
bisa dijalankan end-to-end dan direkam tanpa potongan**. Semua keputusan di
bawah tunduk pada ini.

**Koreksi tanggal:** 9–10 September bukan demo live terjadwal — itu jendela
*standby Discord jam 20.00* di mana panitia **boleh** minta klarifikasi atau
menjadwalkan live demo (hal. 21). Live pitching sesungguhnya 27 September,
hackathon 26 September (hal. 13–14).

**Bobot penilaian penyisihan** (hal. 23–25) — dipakai untuk memutuskan ke mana
jam dialokasikan:

| Kriteria | Bobot |
| --- | --- |
| Implementasi Teknologi & Kematangan Arsitektur | 25% |
| Orisinalitas dan Dampak Sosial | 20% |
| Kesiapan MVP untuk Babak Final | 15% |
| Kualitas Proposal & Proses Pengembangan | 15% |
| Video Promosi | ~15% (angka tertutup grafis di PDF) |
| Relevansi dengan Tema | 10% |
| Business Value & Governance (BONUS) | 5% |
| Kehadiran AIC Talks (BONUS) | 1,5% |

Perhatikan: **proposal + video = ~30%**, setara dengan arsitektur. Menulis dan
merekam bukan pekerjaan sisa.

---

## D0 — Freeze `ai-engine` hari ini. Sisanya untuk demo yang jalan.

Kalau harus memilih antara "AI lebih pintar" dan "aplikasi bisa dijalankan
panitia", pilih yang kedua. Kriteria MVP (15%) secara eksplisit menghukum
**overbuilt** sama kerasnya dengan underbuilt.

Fitur baru `ai-engine` yang boleh ditambah setelah dokumen ini cuma tiga:
`qc/` (D1), `mapping/` (D2), `decide.py` (D3). Selain itu: tidak.

---

## D1 — Fine-tune tepat satu model, dan jadikan itu classifier QC. **[COMPLIANCE — prioritas tertinggi]**

Rulebook, Ketentuan Khusus #10 (hal. 7) dan Ketentuan Deliverables (hal. 16),
kalimat identik dua kali:

> "Diperbolehkan untuk menggunakan model API dan pre-trained model. **Model
> wajib di fine tune sesuai dengan inovasi fitur per tim.**"

Stack sekarang: DeepSeek API + `fastembed` pre-trained + aturan IQR. **Nol
fine-tuning.** Dan dokumen justru menjual "tidak memerlukan fine-tuning" sebagai
keunggulan — itu bukan cuma lubang argumen, itu terbaca seperti mengumumkan
ketidakpatuhan.

**Keputusan:**

1. Fine-tune **satu** image classifier kecil (MobileNetV3-Small atau ResNet18,
   transfer learning, head + last block) untuk klasifikasi jenis defect produk.
   Target: 5–6 kelas, < 1 jam training di CPU. Ini sekaligus *adalah* inovasi
   fitur tim (lihat D2) — jadi memenuhi frasa "sesuai dengan inovasi fitur".
2. **Jangan** fine-tune LLM-nya. DeepSeek tetap dipakai sebagai reasoner
   ter-grounding.
3. Deliverable yang wajib ada di repo, karena proposal menuntut "alur
   pengembangan model (tiap feature)" + preprocessing (hal. 17):
   `ai-engine/qc/train.py`, `qc/preprocess.py`, bobot hasil training,
   `qc/METRICS.md` (akurasi per kelas + confusion matrix + split data).
4. Parameter **dibekukan** saat demo — sesuai batasan "parameter yang bersifat
   statis pada saat demonstrasi berjalan" (hal. 15).

**Perbaiki paragraf "kenapa implementasi lebih murah"** — pisahkan dua hal yang
sekarang tercampur:

> Klaim bisnis: pabrik tidak perlu melatih ulang LLM untuk setiap pabrik;
> pengetahuan spesifik pabrik masuk lewat dokumen (RAG), bukan lewat bobot model.
> Kepatuhan & teknis: satu model computer vision di-fine-tune tim selama periode
> lomba untuk klasifikasi defect produk, dan baseline anomali statistik di-fit
> per aset dari data nominal lalu dibekukan saat demo.

Kalimat kedua itu yang selama ini hilang.

---

## D2 — QC → failure mode harus jadi mekanisme, bukan satu kalimat. **[INI JUDUL CERITANYA]**

Kritik yang benar: defect produk sebagai sinyal degradasi mesin memang tidak
dilakukan CMMS maupun monitoring IoT. Itu wedge kalian. Tapi sekarang isinya
kosong.

**Keputusan — rantai konkret yang dipilih:**

Aset demo: **mesin CNC (milling/turning) yang memproduksi komponen logam
berulir.**

| Sumber | Dataset | Lisensi | Dipakai untuk |
| --- | --- | --- | --- |
| Sinyal mesin | **UCI AI4I 2020 Predictive Maintenance** | CC BY 4.0 | air/process temp, rotational speed, torque, **tool wear**, label TWF/HDF/PWF/OSF |
| Citra QC | **MVTec AD — kategori `screw`** | CC BY-NC-SA 4.0 (non-komersial — **sebut terbuka di proposal**) | 5 kelas defect: `scratch_head`, `scratch_neck`, `thread_side`, `thread_top`, `manipulated_front` |
| Jadwal produksi, stok sparepart, roster teknisi, SOP | **Sintetik**, generator ditulis tim (`scripts/gen_synthetic.py`) | milik tim | konteks bisnis + korpus RAG |

Rulebook membolehkan keduanya: "Dataset yang digunakan boleh berasal dari
sumber publik yang telah tersedia sebelumnya dan juga boleh dari data sintetik"
(hal. 16). Yang **tidak** boleh dilewatkan: preprocessing wajib dijelaskan.

**Artefak baru yang menjadikannya mekanisme — `mapping/qc_failure_modes.yaml`:**

```yaml
- defect_class: thread_top
  candidate_failure_modes:
    - tool_wear            # tap/insert aus
    - spindle_runout
  corroborate:             # sinyal yang harus dicek sebelum prioritas dinaikkan
    - tag: tool_wear_min
      rule: "> p90 baseline"
    - tag: torque_nm
      rule: "trend_up over last 50 cycles"
  priority_delta: +1
  recommended_action: "Ganti insert/tap, verifikasi runout spindle"
  source: "SOP-CNC-04 §3.2"

- defect_class: scratch_neck
  candidate_failure_modes: [fixture_misalignment, chip_evacuation_failure]
  corroborate:
    - tag: torque_nm
      rule: "variance > 2x baseline"
  priority_delta: +1
  ...
```

Aturannya sama dengan `signals.py`: **mapping deterministik, LLM menjelaskan,
bukan mengarang.** Classifier menghasilkan kelas + confidence → mapping
menghasilkan kandidat failure mode + sinyal yang harus dikonfirmasi → engine
mengecek sinyal → baru prioritas naik. Kalau sinyal tidak mengkonfirmasi,
sistem bilang begitu (dan itu justru bagus untuk ditunjukkan di video).

**Beat demo (60 detik, ini yang paling diingat juri):**
defect rate kelas `thread_top` naik 3 batch berturut → mapping menarik
`tool_wear` → dikonfirmasi `tool_wear_min` di p95 dan torque naik →
prioritas mesin CNC-02 naik `medium → high`, jendela maintenance digeser maju
dari Sabtu ke setelah shift malam ini — **tanpa satu pun sensor melaporkan
alarm.** Itu kalimat pembeda kalian dari semua CMMS dan semua PdM biasa.

**Jujur soal mapping:** tabel ini pengetahuan teknik (dari SOP/handbook), bukan
hasil belajar. Katakan terang-terangan di proposal. Auditable > pura-pura
learned.

**Fallback kalau lisensi MVTec bikin ragu:** generator defect sintetik sendiri
(tekstur + augmentasi), kualitas cerita turun sedikit, kepatuhan aman. Jangan
pakai dataset biner ok/defect — mapping-nya jadi kosong lagi.

---

## D3 — Definisikan fungsi objektif, lalu benar-benar hitung.

"Paling optimal" muncul berkali-kali tanpa pernah didefinisikan. Kalimat resmi,
dipakai identik di proposal, video, dan README:

> **Meminimalkan ekspektasi biaya total = biaya downtime tak terencana + biaya
> scrap/defect, dengan constraint: jadwal & target produksi, ETA sparepart,
> ketersediaan teknisi, dan batasan keselamatan pada SOP.**

**Implementasi (`ai-engine/src/decide.py`, ~150 baris, tanpa LLM):**

1. Enumerasi kandidat jendela dari celah jadwal produksi (+ opsi "sekarang,
   hentikan produksi").
2. Buang yang infeasible: sparepart belum datang, tidak ada teknisi dengan skill
   yang diminta, SOP melarang.
3. Skor tiap kandidat:
   `P(fail sebelum jendela) × biaya_downtime + kehilangan_produksi_selama_jendela + scrap_terakumulasi`
4. Kembalikan pemenang **plus runner-up plus alasan kekalahannya**.

Nilai balik ini yang dipakai LLM untuk menulis penjelasan. Efeknya: "optimal"
berubah dari kata sifat jadi angka yang bisa dibantah — persis yang ditanya juri
teknis, dan langsung menyerang kriteria Arsitektur (25%).

---

## D4 — LOOP: sinkron, verifikasi sekali, tanpa belajar. **[COMPLIANCE]**

Rulebook hal. 15, Batasan Ruang Lingkup MVP, poin 3:

> "Implementasi AI wajib hanya berfokus pada fungsionalitas inferensi utama
> (core inference) dengan **parameter yang bersifat statis pada saat demonstrasi
> berjalan**. Peserta **tidak diminta untuk menyertakan sistem pembaruan
> otomatis (auto-tuning), skrip pengujian massal (bulk testing scripts), atau
> mekanisme loop umpan balik otomatis** pada repository tahap penyisihan ini."

Dan poin 2: backend **wajib hanya sampai pemrosesan interaksi sinkron**, tanpa
background jobs, tanpa automated data logging.

**Keputusan:**
- Teknisi submit hasil lewat satu form → **satu panggilan** `engine.verify(...)`
  → verdict (`resolved` / `not_resolved` / `partial`) → laporan akhir.
- Work order yang selesai **ditulis sebagai dokumen RAG baru** (maintenance
  history), sehingga analisis berikutnya membacanya. Itu "belajar" dalam arti
  yang legal di sini: pengetahuan, bukan bobot.
- **Nol** background job, **nol** retraining, **nol** scheduler daemon.
- Tulis di README satu paragraf yang mengutip aturan di atas dan menyatakan
  kepatuhannya. Juri yang mencari batasan ini akan menemukannya dalam 10 detik —
  itu poin gratis di kriteria MVP.
- Di video karya inovasi dan proposal, continuous learning tetap diceritakan,
  **berlabel roadmap pasca-penyisihan**.

---

## D5 — "AI observes continuously" dihapus. Ganti dengan "analisis berjalan atas permintaan".

Bertabrakan langsung dengan batasan sinkron di atas, dan dengan batasan
frontend: "UI wajib hanya berfokus pada alur interaksi inti, yaitu **menerima
input tunggal** dari pengguna dan menampilkan output dari AI. Peserta tidak
perlu membangun ... dashboard analitik tingkat lanjut, sistem otentikasi yang
kompleks, atau halaman riwayat penggunaan" (hal. 15).

**Konsekuensi ke `docs/FR.md` — ini harus diedit malam ini:**

| FR | Sekarang | Jadi |
| --- | --- | --- |
| Dashboard Monitoring | secondary | **Roadmap** (dilarang eksplisit) |
| Analysis History | secondary | **Roadmap** (dilarang eksplisit) |
| Notification | secondary | **Roadmap** |
| Real-time monitoring / streaming | secondary | **Roadmap** |
| Authentication | tertiary | **Roadmap** |
| Continuous Learning | secondary | **Roadmap** (dilarang eksplisit) |
| PLC / Controller Integration | Primary | **Mock adapter sinkron** (upload CSV/JSON + 1 endpoint), bukan koneksi live |
| IoT Sensor Integration | Primary | idem |
| ERP / CMMS Integration | Primary | **Roadmap** — paling mahal, paling tidak terlihat di demo |
| Deployment Package Configuration | Primary | Turunkan jadi satu kalimat (lihat D6) |

Yang tersisa sebagai Primary adalah persis rantai demo di D11. Ini bukan
kekalahan: memangkas di sini **menaikkan** skor Kesiapan MVP.

---

## D6 — Paket Starter/Standard/Professional: satu kalimat, bukan tiga produk.

Catatan di dokumen kalian sendiri sudah mengakui paket ini dibuat untuk memenuhi
rubrik. Bahayanya nyata: begitu disebut di proposal/video, panitia berhak
memintanya saat klarifikasi 9–10 September.

**Keputusan:** buang bahasa "paket". Engine memang sudah tidak bercabang
berdasarkan tier — itulah versi jujurnya:

> "Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
> lengkap input, makin dalam keputusannya."

**Buktikan dalam 40 detik di video:** jalankan aset yang sama dua kali — sekali
hanya dengan SOP + history + kondisi manual, sekali dengan sensor + QC + jadwal
produksi + sparepart + teknisi. Tunjukkan outputnya mendalam. Nol biaya
implementasi, klaim low adoption barrier terbukti, dan tidak ada utang tiga
produk.

**Sekalian selesaikan kontradiksi target user.** Persempit jadi:

> "Pabrik kecil–menengah yang mesinnya sudah punya controller/PLC atau sudah
> mencatat parameter proses, tetapi belum punya CMMS maupun predictive
> maintenance, dan tidak punya tim IT/AI khusus."

---

## D7 — Landscape harus bernama. Wedge lama gugur, ganti wedge.

Sekarang dokumen bilang "solusi existing mahal, rumit, untuk perusahaan besar"
tanpa satu pun nama produk. Landscape tanpa nama = landscape yang belum diriset,
dan pemain SMB-friendly memang sudah ada.

Bangun tabel tiga kolom: **produk | harga & waktu implementasi (dengan sumber) |
apa yang TIDAK dia lakukan**. Minimal isi: MaintainX, UpKeep, Fiix, Limble
(CMMS self-serve, langganan per user/bulan), Augury & Senseye/Siemens (PdM
spesialis, mahal), dan Excel + WhatsApp sebagai status quo.

**Setelah tabel itu diisi jujur, klaim "lebih murah dari CMMS" kemungkinan besar
gugur.** Jangan dipertahankan. Pindahkan wedge ke dua klausa yang memang belum
dilakukan siapa pun sekaligus:

> (1) keputusan maintenance yang sadar constraint bisnis — jadwal produksi, stok
> & ETA sparepart, ketersediaan teknisi — bukan sekadar alert kondisi;
> (2) hasil QC produk sebagai sinyal kondisi mesin.

CMMS mencatat dan menjadwalkan tapi tidak memutuskan. PdM spesialis mendeteksi
tapi tidak tahu jadwal produksi dan tidak melihat produknya.

---

## D8 — Satu angka, asumsinya ditulis terbuka.

Nol angka di seluruh dokumen, padahal video dinilai untuk "menggugah antusiasme
pengguna baru dan minat investor" (hal. 19). Satu slide, semua ditandai
`[ASUMSI]`:

```
Pabrik contoh: 12 mesin CNC, 2 shift
Unplanned downtime saat ini      : 18 jam/bulan            [ASUMSI]
Kontribusi margin per jam henti  : Rp 1.200.000/jam        [ASUMSI]
Kerugian downtime                : Rp 259 juta/tahun
Porsi yang dapat dicegah         : 25%                     [ASUMSI, rentang literatur PdM 20-40%]
Penghematan                      : Rp 65 juta/tahun
Scrap akibat defect terlambat    : ... (isi)               [ASUMSI]
```

Satu hitungan jujur dengan asumsi terbuka jauh lebih kuat daripada lima manfaat
kualitatif. Jangan bulatkan ke atas.

---

## D9 — Batas otonomi: satu kalimat, dan taruh tombolnya di UI.

Antar tab dokumen kalian bertentangan (PROPOSAL: coordinator pengambil keputusan
akhir; tab ini: AI menugaskan teknisi dan memverifikasi). Di konteks
maintenance, keputusan otonom yang salah = mesin rusak atau orang celaka. Juri
pasti menanyakan ini.

**Kalimat resmi, dipakai identik di semua tempat:**

> "AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi mengeksekusi;
> AI memverifikasi bukti — bukan menyatakan selesai sendiri."

**Implementasikan harfiah:** tombol Approve/Reject pada rekomendasi; work order
baru aktif setelah di-approve; verifikasi menghasilkan verdict + bukti, bukan
status "selesai" otomatis. Biaya ~30 menit, dan ini langsung menyasar bonus
**Business Value & Governance (5%)** yang menanyakan "aspek regulasi AI, etika,
atau prinsip sistem cerdas yang bertanggung jawab".

---

## D10 — Bagian "Alur memperoleh dataset" ditulis sekarang, bukan hari terakhir.

Wajib di proposal (hal. 17). Isinya sudah diputuskan di D2. Yang perlu ditulis
untuk masing-masing: sumber, lisensi, jumlah sampel, split train/val/test,
langkah preprocessing (resize, normalisasi, augmentasi, penanganan imbalance),
dan — untuk data sintetik — asumsi generatornya.

---

## D11 — Rantai demo yang dikunci (7 menit, tanpa potongan)

```
1. Setup     : upload asset list + SOP + maintenance history        (RAG ingest)
2. Input     : sensor CSV (AI4I) + batch citra QC + business context (single form)
3. Signals   : anomaly (IQR) + health score            [deterministik]
4. QC        : klasifikasi defect                      [MODEL FINE-TUNED — D1]
5. Mapping   : defect -> candidate failure modes -> sinyal konfirmasi  [D2]
6. RCA       : root cause + sitasi SOP/history         [LLM, grounded]
7. Priority  : prioritas + alasan
8. Schedule  : jendela optimal + runner-up + alasan kalah  [deterministik — D3]
9. Work Order: draft + SOP steps + parts + skill
10. Approve  : coordinator menyetujui                  [human-in-the-loop — D9]
11. Execute  : teknisi submit hasil                    (form sinkron)
12. Verify   : satu panggilan verifikasi -> verdict     [D4]
13. Report   : laporan akhir + work order masuk ke RAG history
```

Tunjukkan juga (D6) run kedua dengan input minimal untuk membuktikan degradasi
yang anggun. Apa pun di luar 13 langkah ini: roadmap.

---

## Rencana ~71 jam

| Kapan | AI Engineer | Backend | Frontend / Media |
| --- | --- | --- | --- |
| **Minggu pagi** | Kunci dataset, unduh AI4I + MVTec, tulis `qc/preprocess.py` | Scaffold FastAPI + endpoint `/analyze`, `/verify`, `/upload`; docker compose full-stack | Satu halaman: form input → hasil; belum styling |
| **Minggu sore–malam** | Fine-tune classifier, `qc/METRICS.md`, `mapping/*.yaml` | Wiring `MaintenanceEngine`, seed script | Render hasil: health, anomali, QC, RCA, jadwal, WO |
| **Senin pagi** | `decide.py` + integrasi ke engine & prompt | Endpoint approve + submit hasil teknisi | Tombol Approve, form hasil teknisi, halaman laporan |
| **Senin sore** | Rapikan `docs/FR.md`, README compliance paragraph | **README + docker compose diuji dari clone bersih** | Riset & isi tabel landscape (D7), hitung ROI (D8) |
| **Senin malam** | Dry run end-to-end 3x | idem | Draft proposal (metodologi sudah setengah jadi dari D10) |
| **Selasa pagi** | Perbaikan hasil dry run — **fitur baru dilarang** | idem | Rekam proof of work (latihan dulu; **tidak boleh ada cut**) |
| **Selasa sore** | Bantu proposal | Bantu proposal | Rekam video karya inovasi, finalisasi proposal |
| **Selasa 20:00** | **Submit.** Jangan menyentuh 23:55. | | |

**Jangan lupa (mudah bikin gugur):**
- Repo **public** sebelum deadline; push terakhir sebelum 25 Agustus 23:55.
- Commit wajib **Conventional Commits** (`feat:`/`fix:`/`refactor:`) — sudah
  benar sejauh ini, pertahankan.
- Tidak boleh ada jejak institusi pendidikan di mana pun.
- Video proof of work: unlisted, nama `COMPFEST 18 AIC: PROOF OF WORK - [Tim] - [Proyek]`.
  Video inovasi: public, `COMPFEST 18 AIC: [Tim] - [Proyek]`.
- Semua fitur yang muncul di video inovasi **wajib ada** di video proof of work.

---

## Kalau tertinggal, potong dengan urutan ini

1. Turunkan kelas classifier dari 5 ke 3 (`thread_top`, `scratch_neck`, `ok`).
2. Sederhanakan `decide.py`: ganti probabilitas dengan tier risiko (low/med/high).
3. Kurangi seed data jadi 2 mesin.
4. Frontend polos tanpa styling.

**Jangan pernah dipotong:** fine-tune (D1 — compliance), docker compose + README
yang jalan, video proof of work, proposal bagian metodologi.
