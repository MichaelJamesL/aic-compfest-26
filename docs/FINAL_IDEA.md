# FINAL IDEA — AI Maintenance Coordinator

**Digital employee untuk maintenance di pabrik kecil–menengah.**

> **Status: SINGLE SOURCE OF TRUTH.** Kalau ada yang bertentangan antara dokumen
> ini dengan tab/dokumen lain, dokumen ini yang menang. Perubahan ide diedit di
> sini dulu, baru menyebar ke proposal, video, dan kode.
> Alasan di balik tiap keputusan ada di `docs/DECISIONS.md`; rencana eksekusi
> ~71 jam juga di sana.
> Versi: 23 Agustus 2026, 01:00 WIB.

---

## RINGKASAN (on point)

1. **Apa ini.** AI yang mengerjakan pekerjaan seorang *maintenance coordinator*:
   menggabungkan kondisi mesin, hasil QC produk, SOP, histori maintenance,
   jadwal produksi, stok sparepart, dan ketersediaan teknisi menjadi satu
   keputusan maintenance — tindakan apa, seberapa mendesak, kapan, oleh siapa —
   lengkap dengan work order dan laporan.

2. **Pembeda utama, satu kalimat.** Kami memakai **hasil QC produk sebagai
   sinyal kondisi mesin**, dan mengambil keputusan yang **sadar constraint
   bisnis** — bukan sekadar mengirim alert kondisi. CMMS mencatat dan
   menjadwalkan tapi tidak memutuskan; predictive maintenance biasa mendeteksi
   tapi buta terhadap jadwal produksi dan tidak pernah melihat produknya.

3. **Mekanisme pembeda itu, konkret.** Defect `thread_top` naik tiga batch →
   tabel mapping menarik kandidat `tool_wear` → dikonfirmasi `tool_wear_min` di
   persentil 95 dan torque menaik → prioritas CNC-02 naik `medium → high`,
   jendela maintenance digeser maju ke setelah shift malam — **tanpa satu pun
   sensor menyalakan alarm.**

4. **"Optimal" didefinisikan.** Meminimalkan ekspektasi biaya downtime tak
   terencana + biaya scrap, dengan constraint jadwal & target produksi, ETA
   sparepart, ketersediaan teknisi, dan batasan keselamatan pada SOP. Dihitung
   deterministik, bukan dikarang LLM.

5. **Batas otonomi.** AI mengusulkan dan menyiapkan; coordinator menyetujui;
   teknisi mengeksekusi; AI memverifikasi bukti — bukan menyatakan selesai
   sendiri.

6. **Angka yang tidak dikarang.** Health score, deteksi anomali, mapping
   defect→failure mode, dan pemilihan jendela maintenance semuanya deterministik.
   LLM **menjelaskan** angka itu dan menulis narasi; LLM tidak boleh membuatnya.

7. **Model yang di-fine-tune tim:** satu image classifier defect produk
   (MobileNetV3-Small / ResNet18, transfer learning). LLM **tidak** di-fine-tune —
   pengetahuan pabrik masuk lewat dokumen (RAG), bukan lewat bobot.

8. **Adopsi bertahap tanpa tiga produk.** Tidak ada paket Starter/Standard/
   Professional sebagai lini produk. Satu sistem: *analisis tetap dihasilkan
   dengan input apa pun yang tersedia; makin lengkap input, makin dalam
   keputusannya.* Dibuktikan dengan menjalankan aset yang sama dua kali.

9. **Ruang lingkup penyisihan.** Semuanya sinkron, parameter statis saat demo,
   tanpa background job, tanpa auto-tuning, tanpa loop umpan balik otomatis,
   tanpa dashboard analitik lanjutan. Ini bukan pemangkasan karena kehabisan
   waktu — ini batasan yang ditetapkan rulebook, dan mematuhinya bernilai poin.

10. **Yang jadi roadmap, bukan MVP:** continuous learning, dashboard multi-mesin,
    notifikasi, streaming real-time, integrasi ERP/CMMS, autentikasi, riwayat
    analisis.

---

## 1. Latar belakang

Banyak pabrik kecil dan menengah di Indonesia sudah memiliki mesin dengan
controller atau sensor, tetapi maintenance masih dijalankan dengan Excel,
WhatsApp, dan ingatan teknisi senior. Akibatnya:

- Maintenance terlambat karena baru dikerjakan setelah mesin berhenti.
- Sulit menentukan kapan waktu terbaik melakukan perbaikan tanpa mengganggu
  target produksi.
- Informasi tercecer: SOP di lemari, histori di buku atau spreadsheet, stok
  sparepart di gudang, jadwal produksi di kepala production planner.
- Maintenance coordinator harus mengumpulkan semuanya secara manual sebelum
  memutuskan — dan sering hanya sempat memutuskan setelah masalahnya terjadi.

Yang jarang disadari: **produk cacat sudah menjadi gejala kerusakan mesin jauh
sebelum sensor mengeluh.** Burr, ulir tidak sempurna, permukaan tergores,
dimensi bergeser — semua itu laporan kondisi mesin yang selama ini hanya dibaca
sebagai masalah kualitas, lalu dibuang bersama produknya.

---

## 2. Solusi

**AI Maintenance Coordinator** — digital employee yang berperan seperti seorang
maintenance coordinator. Ia tidak hanya memantau kondisi mesin, tetapi menerima
informasi dari berbagai bagian operasional (operator, quality control, gudang,
purchasing, production planner), menggabungkannya dengan data mesin, SOP, dan
histori maintenance, lalu menghasilkan **keputusan** maintenance beserta
alasannya, work order-nya, dan verifikasinya setelah dikerjakan.

Rentangnya: **dari mendeteksi masalah sampai menutup siklus maintenance** —
bukan berhenti di alert.

---

## 3. Yang membedakan dari solusi yang sudah ada

Landscape harus disebut namanya. Tabel berikut **wajib diisi dengan harga dan
sumbernya** sebelum masuk proposal — jangan dibiarkan kualitatif.

| Kategori & produk | Harga & waktu implementasi | Yang TIDAK dia lakukan |
| --- | --- | --- |
| CMMS self-serve — MaintainX, UpKeep, Fiix, Limble | *(isi: per user/bulan, sumber halaman harga)* | Mencatat dan menjadwalkan pekerjaan, tetapi tidak memutuskan; tidak membaca kondisi mesin; tidak melihat produk |
| Predictive maintenance spesialis — Augury, Senseye/Siemens | *(isi: per aset/tahun + biaya sensor, sumber)* | Mendeteksi degradasi dari getaran/arus, tetapi tidak tahu jadwal produksi, stok sparepart, maupun ketersediaan teknisi; tidak melihat produk |
| Status quo — Excel + WhatsApp + pengalaman teknisi | Rp 0, tetapi biaya tersembunyi di downtime | Tidak ada memori terstruktur, tidak ada prioritisasi, keputusan bergantung satu orang |

**Kejujuran yang harus dipegang:** klaim "lebih murah daripada CMMS" kemungkinan
besar tidak bertahan — CMMS SMB-friendly sudah murah dan self-serve. Karena itu
wedge kami **bukan harga**, melainkan dua hal yang memang belum dilakukan
siapa pun sekaligus:

1. **Keputusan yang sadar constraint bisnis** — kondisi mesin, jadwal & target
   produksi, stok dan ETA sparepart, ketersediaan teknisi, kekritisan aset,
   dipertimbangkan bersamaan dalam satu fungsi objektif.
2. **Hasil QC produk sebagai sinyal kondisi mesin** — jalur informasi yang
   selama ini terputus antara bagian kualitas dan bagian maintenance.

Klaim biaya yang tetap boleh dipakai, karena ini soal implementasi bukan
langganan: tidak perlu melatih ulang model AI untuk tiap pabrik, tidak perlu
memasang sensor baru sebagai syarat awal, tidak perlu digitalisasi menyeluruh
sebelum bisa dipakai.

---

## 4. Fungsi objektif — definisi "paling optimal"

> Sistem memilih tindakan dan jendela maintenance yang **meminimalkan ekspektasi
> biaya total = biaya downtime tak terencana + biaya scrap/defect**, dengan
> constraint: **jadwal dan target produksi, ETA sparepart, ketersediaan teknisi
> (jumlah dan skill), serta batasan keselamatan pada SOP.**

Kalimat ini dipakai apa adanya di proposal, video, dan README. Kata "optimal"
tidak boleh muncul di dokumen mana pun tanpa merujuk definisi ini.

Perhitungannya deterministik:

1. Enumerasi kandidat jendela dari celah jadwal produksi, ditambah opsi
   "sekarang, hentikan produksi".
2. Buang kandidat yang tidak layak — sparepart belum datang, tidak ada teknisi
   dengan skill yang diminta, SOP melarang pekerjaan pada kondisi tersebut.
3. Skor tiap kandidat:
   `P(gagal sebelum jendela) × biaya_downtime + kehilangan_produksi_selama_jendela + scrap_yang_terakumulasi`
4. Kembalikan pemenang **beserta runner-up dan alasan kekalahannya.**

LLM menerima hasil ini dan menuliskan penjelasannya. LLM tidak memilih jendela.

---

## 5. Batas otonomi (human-in-the-loop)

> **AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi mengeksekusi;
> AI memverifikasi bukti — bukan menyatakan selesai sendiri.**

Diimplementasikan harfiah, bukan hanya ditulis:

- Rekomendasi muncul dengan tombol **Approve / Reject**.
- Work order baru berstatus aktif **setelah** di-approve coordinator.
- Verifikasi menghasilkan **verdict + bukti** (`resolved` / `partial` /
  `not_resolved` beserta alasan), bukan status "selesai" otomatis.
- Setiap keluaran AI menyertakan sitasi ke dokumen sumber; klaim tanpa dasar
  harus dinyatakan sebagai tidak cukup bukti.

Di konteks maintenance, keputusan otonom yang salah berarti mesin rusak atau
orang celaka. Human-in-the-loop di sini adalah nilai jual, bukan keterbatasan.

---

## 6. Alur sistem

Analisis berjalan **atas permintaan** (satu input → satu keluaran), bukan
observasi terus-menerus. Label di kanan menunjukkan siapa yang mengerjakan.

```
        INPUT  (satu form)
        ├── asset list · SOP · histori maintenance        → knowledge base (RAG)
        ├── data mesin: CSV sensor / PLC export
        ├── citra QC produk (batch)
        └── konteks bisnis: jadwal produksi, stok & ETA sparepart,
            ketersediaan teknisi, laporan operator
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. SIGNALS        anomali (rolling median + IQR)            │  deterministik
   │                   health score (deduksi berbobot)           │
   ├─────────────────────────────────────────────────────────────┤
   │ 2. QC VISION      klasifikasi jenis defect per citra        │  MODEL FINE-TUNED
   │                   agregasi defect rate per batch            │
   ├─────────────────────────────────────────────────────────────┤
   │ 3. MAPPING        defect → kandidat failure mode            │  tabel pengetahuan
   │                   → sinyal yang harus mengkonfirmasi        │  (YAML, auditable)
   │                   → konfirmasi terhadap data sensor         │
   ├─────────────────────────────────────────────────────────────┤
   │ 4. RETRIEVAL      SOP + histori relevan (pgvector)          │  deterministik
   ├─────────────────────────────────────────────────────────────┤
   │ 5. DIAGNOSIS      root cause + confidence + evidence        │  LLM (grounded)
   │                   penjelasan bersitasi                      │
   ├─────────────────────────────────────────────────────────────┤
   │ 6. PRIORITY       tingkat prioritas + alasan                │  aturan + LLM
   ├─────────────────────────────────────────────────────────────┤
   │ 7. SCHEDULING     jendela optimal + runner-up + alasan      │  deterministik
   │                   kalah + blocker (mis. ETA sparepart)      │  (§4)
   ├─────────────────────────────────────────────────────────────┤
   │ 8. WORK ORDER     langkah dari SOP, parts, skill, safety,   │  LLM (grounded)
   │                   estimasi durasi, usulan teknisi           │
   └─────────────────────────────────────────────────────────────┘
                     │
                     ▼
        9.  COORDINATOR  → Approve / Reject                        manusia
                     │
                     ▼
       10.  TEKNISI      → eksekusi, lalu submit hasil + temuan     manusia
                     │
                     ▼
       11.  VERIFICATION  satu panggilan sinkron:                   LLM (grounded)
            "apakah perbaikan menyelesaikan masalahnya?"
            verdict: resolved / partial / not_resolved + bukti
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
     resolved                not_resolved
        │                         │
        ▼                         └─→ diagnosis ulang dijalankan
   12. LAPORAN AKHIR                  atas permintaan pengguna
        │                             (bukan loop otomatis)
        ▼
   Work order yang selesai ditulis kembali sebagai dokumen
   histori maintenance di knowledge base → dibaca analisis berikutnya
```

**Catatan penting soal langkah terakhir.** Inilah bentuk "belajar" yang dipakai
di tahap penyisihan: pengetahuan baru masuk sebagai **dokumen**, bukan sebagai
pembaruan bobot model. Tidak ada retraining, tidak ada auto-tuning, tidak ada
proses latar belakang.

---

## 7. QC sebagai sinyal kondisi mesin — mekanismenya

Ini bagian yang paling membedakan, jadi ditulis paling rinci.

### 7.1 Aset dan produk yang didemokan

Mesin CNC (milling/turning) yang memproduksi komponen logam berulir.

### 7.2 Artefak mapping

Berkas `mapping/qc_failure_modes.yaml` — bagian dari repo, bisa dibaca dan
dibantah siapa pun:

```yaml
- defect_class: thread_top
  candidate_failure_modes: [tool_wear, spindle_runout]
  corroborate:
    - tag: tool_wear_min
      rule: "> p90 baseline"
    - tag: torque_nm
      rule: "trend_up over last 50 cycles"
  priority_delta: +1
  recommended_action: "Ganti insert/tap, verifikasi runout spindle"
  source: "SOP-CNC-04 §3.2"

- defect_class: thread_side
  candidate_failure_modes: [tool_wear, axis_backlash]
  corroborate:
    - tag: torque_nm
      rule: "trend_up"
  priority_delta: +1
  source: "SOP-CNC-04 §3.4"

- defect_class: scratch_neck
  candidate_failure_modes: [fixture_misalignment, chip_evacuation_failure]
  corroborate:
    - tag: torque_nm
      rule: "variance > 2x baseline"
  priority_delta: +1
  source: "SOP-CNC-07 §2.1"

- defect_class: scratch_head
  candidate_failure_modes: [material_handling, clamping_pressure]
  corroborate: []
  priority_delta: 0            # sering bukan masalah mesin — jangan dipaksakan
  note: "Tidak menaikkan prioritas tanpa konfirmasi sinyal."

- defect_class: manipulated_front
  candidate_failure_modes: [axis_backlash, clamping_loss]
  corroborate:
    - tag: rotational_speed_rpm
      rule: "variance > 2x baseline"
  priority_delta: +1
  source: "SOP-CNC-09 §1.5"
```

### 7.3 Aturan main

- Classifier hanya menghasilkan **kelas + confidence**. Ia tidak menyimpulkan
  kerusakan mesin.
- Mapping menghasilkan **kandidat** failure mode dan **daftar sinyal yang harus
  mengkonfirmasi**.
- Prioritas hanya naik kalau sinyal mengkonfirmasi. Kalau tidak, sistem
  mengatakan apa adanya: "defect meningkat, tetapi tidak ada sinyal mesin yang
  mendukung; kemungkinan penyebab di luar mesin (material/handling)". Kemampuan
  menahan diri ini justru ditunjukkan di demo.
- Mapping adalah **pengetahuan teknik yang diturunkan dari SOP dan handbook,
  bukan hasil pembelajaran**. Katakan terbuka di proposal. Auditable lebih
  berharga daripada terkesan learned.

### 7.4 Beat demo (±60 detik, jangan dilewat)

Defect kelas `thread_top` naik tiga batch berturut-turut → mapping menarik
kandidat `tool_wear` → dikonfirmasi `tool_wear_min` di persentil 95 dan torque
menaik → prioritas CNC-02 naik `medium → high` → jendela maintenance digeser
maju dari Sabtu ke setelah shift malam ini, karena scrap yang terus terakumulasi
lebih mahal daripada berhenti 2 jam malam ini — **dan sepanjang itu tidak ada
satu pun alarm sensor yang menyala.**

---

## 8. Model dan data

### 8.1 Pembagian peran model

| Komponen | Model | Status |
| --- | --- | --- |
| Klasifikasi defect QC | MobileNetV3-Small / ResNet18 | **Di-fine-tune tim selama periode lomba** |
| Deteksi anomali & health score | aturan statistik (rolling median + IQR, deduksi berbobot) | Baseline di-fit per aset dari data nominal, **dibekukan saat demo** |
| Mapping defect → failure mode | tabel pengetahuan (YAML) | Deterministik, versioned |
| Penjadwalan | optimasi berbasis aturan (§4) | Deterministik |
| Reasoning, RCA, penjelasan, work order, verifikasi | LLM (DeepSeek) via pydantic_ai, output terstruktur | Pre-trained, **tidak di-fine-tune**, di-ground dengan RAG |
| Embedding untuk RAG | `intfloat/multilingual-e5-large` (fastembed, lokal) | Pre-trained |

**Kalimat resmi soal biaya implementasi** — dua hal ini harus dipisah dan tidak
boleh tercampur lagi:

> *Klaim bisnis:* pabrik tidak perlu melatih ulang LLM untuk setiap pabrik;
> pengetahuan spesifik pabrik masuk lewat dokumen (SOP, histori) melalui
> retrieval, bukan lewat bobot model. Itulah sebabnya onboarding cukup dengan
> unggah dokumen.
>
> *Sisi teknis & pengembangan:* tim melatih satu model computer vision untuk
> klasifikasi defect produk selama periode lomba, dan mem-fit baseline statistik
> per aset dari data nominal, dengan seluruh parameter dibekukan saat
> demonstrasi.

### 8.2 Sumber data

| Peran | Sumber | Lisensi | Isi yang dipakai |
| --- | --- | --- | --- |
| Sinyal mesin | UCI **AI4I 2020 Predictive Maintenance** | CC BY 4.0 | air/process temperature, rotational speed, torque, tool wear; label kegagalan TWF/HDF/PWF/OSF |
| Citra QC | **MVTec AD**, kategori `screw` | CC BY-NC-SA 4.0 — **non-komersial, disebut terbuka** | 5 kelas defect: `thread_top`, `thread_side`, `scratch_head`, `scratch_neck`, `manipulated_front` + `good` |
| Jadwal produksi, stok & ETA sparepart, roster teknisi, korpus SOP | **Sintetik**, generator ditulis tim (`scripts/gen_synthetic.py`) | milik tim | konteks bisnis dan basis pengetahuan |

Untuk produk sesungguhnya, citra QC berasal dari lini pelanggan sendiri; dataset
publik dipakai murni untuk pengembangan dan demonstrasi. Nyatakan ini di
proposal — bukan disembunyikan.

### 8.3 Preprocessing yang wajib didokumentasikan

- Citra: resize 224×224, normalisasi ImageNet, augmentasi (flip horizontal,
  rotasi kecil, jitter kecerahan), penanganan imbalance kelas dengan
  class-weight, split train/val/test yang tidak bocor antar-objek.
- Sinyal: parsing timestamp, penyeragaman satuan, pengelompokan per tag,
  pembuangan pembacaan tidak valid, penghitungan baseline per aset (median,
  IQR, p90/p95) dari periode nominal.
- Dokumen: pemecahan berdasarkan heading lalu jendela ±800 karakter dengan
  tumpang tindih 100 karakter, embedding, indeks HNSW.

Metrik hasil pelatihan (akurasi per kelas, confusion matrix, ukuran split)
disimpan di `ai-engine/qc/METRICS.md`.

---

## 9. Onboarding dan input

### 9.1 Sekali di awal

- Daftar mesin (aset, tipe, kekritisan, spesifikasi).
- SOP dan manual (PDF/teks) → knowledge base.
- Histori maintenance (Excel/CSV) → knowledge base.
- Standar/spesifikasi kualitas produk.
- Stok sparepart dan tools.
- Jadwal produksi.
- Data mesin: unggah CSV/JSON hasil ekspor PLC/controller, atau lewat satu
  endpoint mock. *(Koneksi live ke PLC/IoT adalah roadmap — lihat §12.)*

### 9.2 Selama pemakaian

- Data mesin terbaru (runtime, alarm, temperatur, getaran, arus, torque, tool wear).
- Batch citra QC produk.
- Laporan operator.
- Perubahan: sparepart datang, ETA berubah, jadwal/target produksi berubah,
  ketersediaan teknisi berubah.
- Hasil pengerjaan dari teknisi.

Semua masuk lewat unggahan atau form, diproses **sinkron** saat analisis
diminta.

---

## 10. Keluaran

| Keluaran | Isi |
| --- | --- |
| Ringkasan kesehatan mesin | health score + penjelasan komponennya |
| Deteksi anomali | tag, nilai teramati, rentang normal, tingkat keparahan, metode |
| Hasil QC | kelas defect per citra, defect rate per batch, tren |
| Rantai QC → mesin | kandidat failure mode, sinyal yang mengkonfirmasi/menyangkal |
| Root cause analysis | penyebab + confidence + bukti + sitasi dokumen |
| Prioritas | tingkat + alasan |
| Jadwal maintenance | jendela terpilih, runner-up dan alasan kalah, blocker |
| Rekomendasi sparepart | parts yang dibutuhkan, status stok, ETA |
| Work order | judul, langkah dari SOP, parts, skill, catatan keselamatan, estimasi durasi, usulan teknisi |
| Verifikasi | verdict + bukti + tindak lanjut bila belum selesai |
| Laporan maintenance | ringkasan satu siklus, siap diarsipkan dan dibaca ulang oleh sistem |

Setiap keluaran menyertakan daftar sumber yang benar-benar dipakai — jejak audit
yang tidak bisa dikarang model.

---

## 11. Target pengguna

> Pabrik kecil–menengah yang **mesinnya sudah memiliki controller/PLC atau sudah
> mencatat parameter proses**, tetapi **belum memiliki CMMS maupun predictive
> maintenance**, dan **tidak memiliki tim IT/AI khusus**.

Batasan "sudah punya controller atau pencatatan parameter" sengaja dinyatakan
supaya tidak bertabrakan dengan kebutuhan data sistem. Untuk pabrik yang belum
sampai di sana, sistem tetap bisa dipakai dengan input manual — dengan kedalaman
keputusan yang lebih dangkal, dan itu dinyatakan terus terang.

### Adopsi bertahap tanpa tiga produk

Tidak ada lini produk Starter/Standard/Professional. Satu sistem, satu model AI,
satu aplikasi:

> **Sistem tetap menghasilkan analisis dengan input apa pun yang tersedia; makin
> lengkap input, makin dalam keputusannya.**

Dibuktikan di demo dalam ±40 detik: aset yang sama dijalankan dua kali — pertama
hanya dengan SOP, histori, dan kondisi manual; kedua dengan data sensor, citra
QC, jadwal produksi, stok sparepart, dan roster teknisi. Keluaran yang kedua
jelas lebih dalam. Pelanggan bisa mulai dari yang pertama dan naik bertahap
tanpa mengganti aplikasi maupun model.

---

## 12. Ruang lingkup penyisihan

### 12.1 Masuk MVP — rantai yang didemokan utuh

1. Unggah daftar aset, SOP, histori maintenance.
2. Input: CSV sensor + batch citra QC + konteks bisnis, dalam satu form.
3. Deteksi anomali + health score (deterministik).
4. Klasifikasi defect QC (model fine-tuned).
5. Mapping defect → kandidat failure mode → konfirmasi sinyal.
6. Root cause analysis bersitasi.
7. Prioritas.
8. Jendela maintenance optimal + runner-up + blocker.
9. Draft work order.
10. Approve oleh coordinator.
11. Teknisi submit hasil.
12. Verifikasi sinkron → verdict.
13. Laporan akhir; work order selesai masuk kembali ke knowledge base.
14. Demonstrasi degradasi anggun (§11).

### 12.2 Sengaja TIDAK dibangun di penyisihan

Bukan karena kehabisan waktu, melainkan karena rulebook membatasi ruang lingkup
MVP pada interaksi sinkron, inferensi inti dengan parameter statis, dan UI yang
fokus pada alur inti:

- Continuous learning / auto-tuning / retraining otomatis.
- Loop umpan balik otomatis dan background job apa pun.
- Dashboard analitik multi-mesin.
- Halaman riwayat analisis.
- Notifikasi dan pengingat.
- Streaming sensor real-time.
- Integrasi live PLC/IoT (diganti unggahan CSV/JSON + satu endpoint mock sinkron).
- Integrasi ERP/CMMS.
- Autentikasi dan manajemen akun.
- Skrip pengujian massal.

Daftar ini **disebutkan terbuka** di README dan proposal sebagai keputusan
ruang lingkup yang disengaja, lengkap dengan alasannya. Menyebutnya lebih baik
daripada membiarkan juri mengira kalian lupa.

---

## 13. Nilai bisnis

Satu perhitungan, semua asumsi ditandai dan ditampilkan:

```
Pabrik contoh: 12 mesin CNC, 2 shift
Unplanned downtime saat ini        : 18 jam/bulan                [ASUMSI]
Kontribusi margin per jam berhenti : Rp 1.200.000/jam            [ASUMSI]
Kerugian downtime per tahun        : Rp 259 juta
Porsi yang dapat dicegah           : 25%   [ASUMSI, rentang literatur PdM 20–40%]
Penghematan downtime               : Rp 65 juta/tahun
Scrap akibat defect terlambat      : ... (isi)                   [ASUMSI]
Biaya sistem                       : ... (isi)
```

Aturannya: satu hitungan jujur dengan asumsi terbuka, tidak dibulatkan ke atas.
Kata "lebih cepat", "lebih murah", "lebih cerdas" tidak boleh berdiri sendiri di
proposal maupun video tanpa angka atau definisi yang mendukungnya.

---

## 14. Roadmap pasca-penyisihan

Diceritakan di video karya inovasi dan proposal **dengan label roadmap**, tidak
diimplementasikan sekarang:

1. **Continuous learning** — hasil work order yang terverifikasi dipakai untuk
   mengkalibrasi ulang baseline anomali dan bobot mapping; classifier QC dilatih
   ulang berkala dengan citra dari lini pelanggan.
2. **Monitoring berkelanjutan** — ingest sensor terjadwal dan deteksi berjalan
   otomatis, dengan notifikasi.
3. **Dashboard armada** — kesehatan seluruh mesin dalam satu tampilan,
   prioritisasi lintas aset.
4. **Integrasi ERP/CMMS** — sinkronisasi work order dan stok sparepart dua arah.
5. **Copilot teknisi di lapangan** — panduan langkah demi langkah dari SOP,
   dengan input suara/foto.
6. **Penjadwalan lintas mesin** — mengoptimalkan beberapa aset dan beberapa
   teknisi sekaligus.

---

## 15. Kalimat resmi (pakai persis, jangan diparafrase)

Dipakai identik di proposal, kedua video, README, dan UI. Ketidakkonsistenan
antar dokumen adalah hal pertama yang ditangkap juri.

- **Positioning:** "AI Maintenance Coordinator — digital employee yang mengubah
  data mesin, hasil QC produk, SOP, histori, dan constraint operasional menjadi
  satu keputusan maintenance yang bisa dipertanggungjawabkan."
- **Pembeda:** "Kami memakai hasil QC produk sebagai sinyal kondisi mesin, dan
  mengambil keputusan yang sadar constraint bisnis — bukan sekadar mengirim
  alert kondisi."
- **Optimal:** "Meminimalkan ekspektasi biaya downtime tak terencana dan scrap,
  dengan constraint jadwal produksi, ETA sparepart, ketersediaan teknisi, dan
  batasan keselamatan pada SOP."
- **Otonomi:** "AI mengusulkan dan menyiapkan; coordinator menyetujui; teknisi
  mengeksekusi; AI memverifikasi bukti — bukan menyatakan selesai sendiri."
- **Angka:** "Health score, anomali, mapping, dan pemilihan jendela dihitung
  secara deterministik; LLM menjelaskannya, tidak membuatnya."
- **Adopsi:** "Sistem tetap menghasilkan analisis dengan input apa pun yang
  tersedia; makin lengkap input, makin dalam keputusannya."
- **Model:** "Satu model computer vision di-fine-tune tim untuk klasifikasi
  defect produk; LLM tidak di-fine-tune — pengetahuan pabrik masuk lewat dokumen,
  bukan lewat bobot."
- **Ruang lingkup:** "Seluruh pemrosesan berjalan sinkron dengan parameter statis
  saat demonstrasi; tidak ada auto-tuning, background job, maupun loop umpan
  balik otomatis pada tahap ini."

---

## 16. Kata yang dilarang muncul tanpa penjelas

| Dilarang berdiri sendiri | Ganti dengan |
| --- | --- |
| "AI observes continuously" | "analisis berjalan atas permintaan pengguna" |
| "paling optimal" | rujuk definisi di §4 |
| "lebih murah" | konteks: lebih murah dalam hal apa, dibanding siapa, dengan angka |
| "lebih cerdas" / "canggih" | sebutkan mekanismenya |
| "real-time" | "sinkron, saat analisis diminta" |
| "otomatis penuh" | rujuk batas otonomi di §5 |
| "paket Starter/Standard/Professional" | rujuk §11 |
