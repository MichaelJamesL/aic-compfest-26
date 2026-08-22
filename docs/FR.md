# Functional Requirements (PRD)

> Diselaraskan dengan `docs/FINAL_IDEA.md` (single source of truth ide) dan
> dengan batasan ruang lingkup MVP pada AIC Rulebook hal. 15–16.
> Versi: 23 Agustus 2026. Menggantikan versi FR sebelumnya di repo ini.
>
> Prinsip edit: **hanya menambah atau mengurangi baris**, struktur dan bahasa
> baris yang bertahan tidak diubah. Ringkasan perubahan ada di bagian akhir.

---

## Functional Requirements

| Module | Feature | Description |
| --- | --- | --- |
| **Knowledge setup** | Document upload | Sistem bisa menerima upload SOP sebagai knowledge AI. Primary |
| | Maintenance history upload | Sistem bisa menerima upload histori maintenance sebagai referensi AI. Primary |
| | Asset information upload | Sistem bisa menerima daftar mesin yang akan dianalisis. Primary |
| | QC Standard / Product specification upload | Sistem bisa menerima standar kualitas atau spesifikasi produk sebagai referensi untuk proses QC berbasis Computer Vision. Primary |
| **Operational input** | Machine condition input | Sistem bisa menerima input kondisi mesin (manual atau sensor). Primary |
| | Business context input | Sistem bisa menerima input seperti jadwal produksi, status sparepart, ETA sparepart, ketersediaan teknisi, dan laporan operator. Primary |
| | Product QC input | Sistem bisa menerima hasil QC produk yang sedang diproduksi sebagai input tambahan dalam analisis kondisi mesin dan proses produksi. Primary |
| | Maintenance progress input | Sistem bisa menerima update dari technician mengenai status dan perkembangan maintenance yang berlangsung. Primary |
| **AI Analysis** | Maintenance recommendation | AI bisa menghasilkan rekomendasi maintenance berdasarkan seluruh informasi yang diberikan. Primary |
| | Root cause analysis | AI bisa mengidentifikasi kemungkinan penyebab masalah mesin. Primary |
| | Constraint-based Reasoning | AI bisa mempertimbangkan SOP, histori maintenance, jadwal produksi, sparepart, dan laporan operator dalam proses reasoning. Primary |
| | Maintenance prioritization | AI bisa menentukan prioritas maintenance ketika terdapat beberapa faktor yang perlu dipertimbangkan. Primary |
| | Maintenance scheduling optimization | AI bisa membuat schedule maintenance sesuai dengan prioritas, ketersediaan technician, dan constraint lainnya (jadwal produksi, dll). Primary |
| | Anomaly Detection | AI bisa mendeteksi anomali dari data mesin. Primary |
| | Machine Health Scoring | AI bisa menghasilkan skor kesehatan mesin. Primary |
| | **Product defect classification** ➕ | AI bisa mengklasifikasikan jenis defect pada citra produk menggunakan model computer vision yang dilatih (fine-tuned) oleh tim. Primary |
| | Product Quality Analysis | AI bisa menganalisis hasil QC produk untuk mendeteksi abnormal terhadap standar kualitas. Primary |
| | QC-based machine signal analysis | AI bisa menggunakan hasil QC produk sebagai signal tambahan untuk mengidentifikasi kemungkinan masalah pada mesin atau proses produksi. Primary |
| | **Defect-to-failure-mode mapping** ➕ | AI bisa memetakan jenis defect produk ke kandidat failure mode mesin, lalu mengonfirmasinya dengan data sensor terkait sebelum menaikkan prioritas. Bila sinyal mesin tidak mendukung, sistem menyatakan bahwa penyebabnya kemungkinan di luar mesin. Primary |
| | **Sparepart requirement & availability check** ➕ | AI bisa menentukan sparepart yang dibutuhkan suatu tindakan maintenance, memeriksa ketersediaannya, dan menjadikan ETA sparepart sebagai blocker penjadwalan. Primary |
| | Technician assignment | AI bisa mengusulkan seorang atau beberapa technician berdasarkan kebutuhan maintenance dan skill yang diperlukan. Primary |
| | **Maintenance result verification** ➕ | AI bisa memverifikasi, atas permintaan setelah technician mengirimkan hasil pekerjaan, apakah tindakan maintenance sudah dilakukan sesuai SOP dan masalah kondisi mesin benar-benar terselesaikan, dengan hasil berupa verdict beserta buktinya. Primary |
| | Post maintenance analysis | AI bisa menganalisis hasil maintenance setelah pekerjaan selesai dan memperbarui informasi kondisi aset serta maintenance history. Primary |
| | **Decision explanation & traceability** ➕ | Sistem bisa menjelaskan alasan di balik setiap keputusan AI — rekomendasi, prioritas, dan jendela maintenance terpilih beserta alternatif yang kalah dan alasannya — dengan sitasi ke SOP dan histori yang benar-benar dipakai. Primary |
| **Output generation** | Machine Health Summary | Sistem bisa menampilkan ringkasan kondisi kesehatan mesin. Primary |
| | Work Order Generation | Sistem bisa menampilkan draft work order hasil analisis AI untuk teknisi. Primary |
| | Maintenance Report | Sistem bisa menampilkan ringkasan hasil analisis maintenance (mulai dari rekomendasi, explanation, dll.). Primary |
| | Maintenance execution status | Sistem bisa menampilkan status maintenance yang sedang berlangsung dan progress pekerjaan technician. Primary |
| | Product quality report | Sistem bisa menampilkan hasil monitoring dan analisis kualitas produk. Primary |
| | Post maintenance report | Sistem bisa menghasilkan laporan akhir setelah maintenance selesai, termasuk masalah, tindakan, hasil verifikasi, dan status akhir mesin. Primary |
| | **Work order & report export** ➕ | Sistem bisa mengekspor work order dan laporan maintenance dalam format standar (CSV/JSON) agar bisa dimasukkan ke sistem yang sudah dipakai perusahaan. Primary |
| **System & Integration** | **Coordinator approval** ➕ | Sistem bisa meminta persetujuan maintenance coordinator sebelum sebuah rekomendasi menjadi work order aktif; AI mengusulkan dan menyiapkan, coordinator menyetujui, teknisi mengeksekusi, AI memverifikasi bukti. Primary |
| | **Partial-input analysis** ➕ | Sistem bisa tetap menghasilkan analisis dengan input apa pun yang tersedia, dan menyatakan secara eksplisit input mana yang tidak ada beserta dampaknya terhadap kedalaman keputusan. Primary |
| | PLC / Controller Integration | Sistem bisa terhubung dengan PLC atau controller mesin melalui ingest data hasil ekspor maupun endpoint sinkron. Primary |
| | IoT Sensor Integration | Sistem bisa terhubung dengan data dari sensor IoT melalui ingest data hasil ekspor maupun endpoint sinkron. Primary |
| | Docker deployment | Sistem bisa dijalankan menggunakan Docker Compose sesuai README. Primary |

**Total: 36 baris** (sebelumnya 38).

---

## Roadmap — di luar ruang lingkup penyisihan

Bukan dibatalkan; dipindahkan keluar dari PRD penyisihan karena bertabrakan
langsung dengan Batasan Ruang Lingkup MVP pada rulebook, atau karena tidak bisa
didemonstrasikan secara jujur dalam 7 menit. **Sebutkan daftar ini secara
terbuka di README dan proposal** sebagai keputusan ruang lingkup yang disengaja.

| Feature | Alasan dikeluarkan |
| --- | --- |
| Continuous Learning | Rulebook hal. 15: dilarang menyertakan "sistem pembaruan otomatis (auto-tuning) ... atau mekanisme loop umpan balik otomatis". Parameter wajib statis saat demonstrasi. |
| Dashboard Monitoring | Rulebook hal. 15: UI wajib fokus pada alur interaksi inti; "tidak perlu membangun ... dashboard analitik tingkat lanjut". |
| Analysis History | Rulebook hal. 15: "tidak perlu ... halaman riwayat penggunaan". |
| Notification | Membutuhkan penjadwal/background job — dilarang pada arsitektur sinkron. |
| Real-time monitoring (streaming sensor) | Membutuhkan automated data logging dan proses latar belakang — dilarang. |
| Authentication | Rulebook hal. 15: "tidak perlu ... sistem otentikasi yang kompleks". Sebelumnya sudah tertiary. |
| ERP / CMMS Integration | Integrasi termahal dan paling tidak terlihat di demo; digantikan sementara oleh *Work order & report export*. |
| Computer vision integration (sistem CV eksternal) | Pada MVP, model CV berada **di dalam** sistem dan dilatih sendiri oleh tim. Integrasi ke sistem CV pihak lain adalah kebutuhan pelanggan lanjutan. |
| Deployment Package Configuration | Digantikan oleh *Partial-input analysis* — lihat bagian berikutnya. |

---

## Deployment Packages

### Keputusan

**Paket tetap ada sebagai tangga adopsi di proposal dan video, tetapi tidak lagi
menjadi functional requirement.**

Alasannya: sebagai FR, "Deployment Package Configuration" mewajibkan tiga produk
yang dapat dikonfigurasi, dan panitia berhak meminta ketiganya saat klarifikasi.
Padahal secara teknis tidak ada tiga produk — engine memang tidak bercabang
berdasarkan paket, ia hanya menalar atas input yang tersedia. Satu FR
*Partial-input analysis* mewujudkan ketiga paket sekaligus, tanpa utang
implementasi dan tanpa klaim yang tidak bisa ditunjukkan.

Cara membuktikannya dalam ±40 detik di video: jalankan aset yang sama dua kali —
sekali dengan dokumen dan input manual saja, sekali dengan seluruh input — lalu
tunjukkan keluarannya mendalam.

### Perbaikan penting pada matriks: naikkan Product QC/CV ke Starter

Pada matriks saat ini, **Product QC / Computer vision ditempatkan sebagai
Professional-only.** Ini keliru pada tiga hal sekaligus:

1. **Secara biaya, terbalik.** Memotret produk dengan kamera atau ponsel adalah
   sumber data **termurah** yang dimiliki pabrik kecil — jauh lebih murah
   daripada menyadap PLC, memasang sensor IoT, apalagi integrasi ERP.
   Menempatkannya di paket termahal bertentangan dengan kenyataan lapangan.
2. **Pembeda utama jadi terkunci di rak paling atas.** QC sebagai sinyal kondisi
   mesin adalah alasan produk ini berbeda dari CMMS mana pun. Kalau baru muncul
   di Professional, cerita "low adoption barrier" dan cerita "pembeda" tidak
   pernah bertemu — persis di paket yang justru menuntut pabrik sudah punya
   segalanya.
3. **Starter jadi lemah tanpa alasan.** Sekarang Starter dideskripsikan sebagai
   "AI yang pure buat jawab aja". Dengan foto QC, Starter memberi **sinyal
   kondisi mesin kepada pabrik yang tidak punya satu pun sensor** — itu bukti
   terkuat dari klaim low adoption barrier yang bisa kalian punya.

**Matriks yang disarankan** (perubahan: baris Product QC/CV terisi dari Starter;
baris ERP/CMMS dikeluarkan karena sudah jadi roadmap):

| Integration | Starter | Standard | Professional |
| --- | :---: | :---: | :---: |
| SOP | ✔ | ✔ | ✔ |
| Maintenance History | ✔ | ✔ | ✔ |
| Asset list | ✔ | ✔ | ✔ |
| Manual Machine Condition | ✔ | ✔ | ✔ |
| Manual Business Context | ✔ | ✔ | ✔ |
| **Product QC / Computer vision** | **✔ (upload foto)** | **✔** | **✔ (inline)** |
| PLC / Controller | | ✔ | ✔ |
| IoT Sensor | | ✔ | ✔ |
| Production Schedule | | | ✔ |
| Sparepart Inventory | | | ✔ |
| Technician Availability | | | ✔ |

### Tangga adopsi — pembeda yang makin dalam, bukan yang muncul belakangan

**Starter** — semua input manual, tanpa integrasi otomatis.

- Menjawab pertanyaan maintenance
- Memberikan rekomendasi maintenance
- Root Cause Analysis
- Menentukan prioritas maintenance
- Membuat Work Order
- Membuat Maintenance Report
- **Deteksi defect produk dari foto yang diunggah, beserta kandidat failure mode
  mesin — dinyatakan sebagai dugaan karena belum ada sinyal sensor yang
  mengonfirmasi**

**Standard** — mulai ada integrasi otomatis ke sensor.

- Monitoring kondisi mesin otomatis
- Anomaly Detection
- Machine Health lebih akurat
- Tidak perlu input kondisi mesin secara manual
- **Dugaan dari QC dikonfirmasi silang dengan data sensor: prioritas hanya naik
  bila sinyal mesin mendukung**

**Professional** — rekomendasi yang sadar constraint bisnis.

- Menentukan waktu maintenance paling optimal
- Menghindari bentrok dengan jadwal produksi
- Memastikan sparepart tersedia sebelum maintenance
- Menyesuaikan dengan ketersediaan teknisi
- **Biaya scrap akibat defect ikut masuk perhitungan, sehingga QC dapat menggeser
  jendela maintenance lebih awal**
- Ekspor work order dan laporan ke format yang bisa dibaca sistem perusahaan

Perhatikan polanya: QC hadir di ketiga rung, dan **makin dalam** di tiap rung —
dugaan, lalu terkonfirmasi, lalu ikut menentukan jadwal. Itu tangga yang jauh
lebih meyakinkan daripada fitur yang baru muncul di paket termahal.

---

## Ringkasan perubahan terhadap PRD sebelumnya

### Ditambahkan (8)

| Feature | Alasan |
| --- | --- |
| Product defect classification | Rulebook mewajibkan "Model wajib di fine tune sesuai dengan inovasi fitur per tim" (hal. 7 & 16). Baris ini membuat model yang di-fine-tune terlihat sebagai requirement, bukan detail implementasi. Menggantikan *Computer vision integration* yang justru menyiratkan CV milik pihak lain. |
| Defect-to-failure-mode mapping | Mengubah pembeda utama dari klaim menjadi mekanisme: defect → kandidat failure mode → konfirmasi sinyal → baru prioritas naik. Termasuk perilaku menahan diri saat sinyal tidak mendukung. |
| Sparepart requirement & availability check | Sudah dijanjikan di paket Professional dan di daftar output konsep, tetapi belum pernah ada sebagai FR. |
| Maintenance result verification | Menggantikan *Maintenance execution monitoring*. Kata "monitoring" menyiratkan pengawasan berjalan terus; yang dibangun adalah satu verifikasi sinkron setelah teknisi mengirim hasil. |
| Decision explanation & traceability | *Recommendation explanation* ada di versi FR paling awal lalu hilang di revisi ini. Explainability + sitasi adalah dasar kepercayaan pada keputusan maintenance, dan sekaligus tempat menaruh "alternatif jendela dan alasan kalahnya". |
| Coordinator approval | Menyelesaikan kontradiksi antar-dokumen soal batas otonomi, dan menyasar kriteria bonus Business Value & Governance. |
| Partial-input analysis | Menggantikan *Deployment Package Configuration*: mewujudkan ketiga paket tanpa membangun tiga produk. |
| Work order & report export | Menggantikan *ERP / CMMS Integration* dengan versi yang murah, jujur, dan bisa didemonstrasikan. |

### Dikeluarkan ke roadmap (10)

Continuous Learning · Dashboard Monitoring · Analysis History · Notification ·
Real-time monitoring · Authentication · ERP / CMMS Integration · Computer vision
integration · Deployment Package Configuration · Maintenance execution monitoring

### Tidak diubah

Seluruh baris lain dipertahankan apa adanya, termasuk penamaan dan deskripsinya.
Dua deskripsi menerima penajaman ruang lingkup tanpa mengubah maksud:
*PLC / Controller Integration* dan *IoT Sensor Integration* kini menyebut ingest
sinkron, agar tidak terbaca sebagai koneksi live yang dilarang di tahap
penyisihan. *Technician assignment* memakai kata "mengusulkan", selaras dengan
batas otonomi.
