**AI Maintenance Coordinator** 

### **Digital Employee for Small-Medium Manufacturers**

**Background**  
Banyak pabrik kecil dan menengah di Indonesia sudah memiliki mesin dengan sensor atau controller, tetapi proses maintenance masih dilakukan secara manual menggunakan Excel, WhatsApp, atau pengalaman teknisi. Akibatnya:

* Maintenance sering terlambat karena hanya dilakukan setelah mesin rusak.  
* Sulit menentukan kapan waktu terbaik melakukan maintenance tanpa mengganggu produksi.  
* Informasi tersebar di berbagai tempat (SOP, history maintenance, stok sparepart, jadwal produksi).  
* Maintenance coordinator harus mengumpulkan semua informasi tersebut secara manual sebelum mengambil keputusan.

Di sisi lain, solusi predictive maintenance yang ada umumnya mahal, membutuhkan implementasi yang rumit, dan ditujukan untuk perusahaan besar. 

**Solution**  
Membangun **AI Maintenance Coordinator**, yaitu **digital employee yang berperan layaknya seorang Maintenance Coordinator**. AI tidak hanya memonitor kondisi mesin, tetapi juga menganalisis berbagai informasi operasional untuk membantu mengambil keputusan maintenance yang paling optimal. Target utama adalah **small-medium manufacturers** yang ingin mulai mengadopsi AI tanpa investasi besar maupun implementasi yang kompleks.

AI mengintegrasikan berbagai informasi operasional, seperti machine data, SOP, maintenance history, production schedule, inventory, serta ketersediaan technician untuk menentukan tindakan maintenance yang paling optimal. Sistem juga akan terintegrasi dengan quality control berbasis CV untuk memantau kualitas produk yang sedang diproduksi. Hasil dari QC yang tidak sesuai dengan standar akan menjadi input tambahan bagi AI untuk mendeteksi adanya potensi kerusakan pada mesin. **\[QC\]**

AI juga tidak berhenti setelah menghasilkan jadwal maintenance, tetapi juga akan membantu monitoring pelaksanaan maintenance, menerima update dari technician, memverifikasi hasil perbaikan, dan membuat laporan akhir. Informasi hasil maintenance akan digunakan sebagai input training model.  **\[LOOP\]**

Kenapa implementasi lebih cepat? Onboarding sederhana, memanfaatkan data yang sudah dimiliki oleh pabrik, AI secara otomatis membangun knowledge dari data tersebut, dapat diimplementasikan secara bertahap sesuai kesiapan digitalisasi (baca packages deployment di bawah)

Kenapa implementasi lebih murah? Tidak memerlukan fine-tuning model AI untuk setiap pabrik, tidak perlu membangun sistem maintenance dari nol, tidak memerlukan digitalisasi menyeluruh di awal, dan mengurangi kebutuhan konfigurasi manual dan konsultasi implementasi

keyword: Lower Adoption Barrier, plug-and-play, low implementation AI

Minus kita kayaknya kurang bukti kuat buat ngeklaim kalau solusi yang sekarang itu masih belum solusi terbaik.

**Value Proposition**  
Mengubah maintenance dari proses yang reaktif menjadi pengambilan keputusan yang cerdas. AI Maintenance Coordinator berperan layaknya seorang coordinator maintenance yang tidak hanya memonitor kondisi mesin dan beraksi ketika ada mesin yang mengalami penurunan kualitas, tetapi juga menerima informasi dari berbagai bagian operasional, seperti operator, warehouse, purchasing, hingga production planner. Lalu menggabungkannya dengan data mesin, SOP, dan histori maintenance untuk menentukan tindakan serta waktu maintenance yang paling optimal.

\-From detecting machine problems to managing the complete maintenance cycle.  
\-Simple secara integrasinya

**AI Responsibilities**  
AI menjalankan sebagian besar tugas seorang Maintenance Coordinator, yaitu:

* Monitoring kesehatan mesin  
* Mendeteksi anomali  
* Menganalisis penyebab kerusakan  
* Menentukan prioritas maintenance  
* Membuat jadwal maintenance  
* Mempertimbangkan jadwal produksi  
* Mengecek ketersediaan sparepart  
* Membuat work order   
* Membuat laporan maintenance  
* Memberikan rekomendasi tindakan kepada teknisi  
* Monitoring hasil produksi tiap fase (keknya)  
* Monitoring proses maintenance yang sedang berlangsung  
* Memverifikasi apakah maintenance berhasil dilakukan

Monitor → Diagnose → Prioritize → Plan → Coordinate → Monitor Maintenance → Verify → Loop → Report & Learn 

Flow

Lucidchart

| MACHINE \+ PRODUCTION         ↓ AI observes continuously         ↓ ┌──────────────────────────────┐ │                                Detection Agent                           │ │                 "Is there something abnormal?"            │ └──────────────────────────────┘         ↓ Machine Anomaly / Product Defect         ↓         ┌─────────────────────────────┐         │                                                                                       │         ↓                             ↓ Machine Condition              Product QC         │                                                       (Computer Vision)         │                                                                                       │         └──────────────┬──────────────┘                        ↓               Detection Agent                        ↓         "Is this meaningful / abnormal?"                        ↓               Diagnosis Agent                        ↓            "What is likely wrong?"                        ↓               Root Cause Analysis                        ↓               Decision Agent                        ↓         "Do we need to intervene now?"                        ↓               Priority Assessment                        ↓               Planning Agent                        ↓         "When and how should we              perform maintenance?"                        ↓        ┌───────────────┼────────────────┐        ↓                         ↓                      ↓ Production         Sparepart         Technician   Schedule          & Tools          Availability        │                        │                         │        └───────────────┼────────────────┘                        ↓               Scheduling / Optimization                        ↓               Work Order Agent                        ↓          Work Order \+ SOP \+ Instructions                        ↓                   Technician                        ↓             Technician Copilot                        ↓               Physical Maintenance                        ↓              Maintenance Updates                        ↓              Verification Agent                        ↓         "Did the repair solve the problem?"                        ↓                  ┌─────┴─────┐                  ↓           ↓                YES           NO                  ↓           ↓         Post-maintenance    Back to              Agent          Diagnosis                  ↓             ↑        Update Maintenance     │             History           │                  ↓             │           Final Report        │                  ↓             │        Return to Monitoring ──┘                  ↓           Reliability Agent                  ↓        Updated Asset Knowledge                  ↓         Better Future Detection         & Maintenance Decisions |
| :---: |

**AI Decision Making**  
Berbeda dengan predictive maintenance biasa, AI tidak mengambil keputusan hanya berdasarkan kondisi mesin. AI juga mempertimbangkan beberapa **business constraints**, seperti:

* Kondisi mesin  
* Jadwal dan target produksi  
* Stok sparepart  
* Estimasi kedatangan sparepart  
* Ketersediaan teknisi  
* Tingkat prioritas mesin  
* Hasil QC product  
* Hasil maintenance sebelumnya

**Initial Setup (Sekali di awal)**  
Implementasi dibuat sesederhana mungkin kalau bisa. Pengguna tinggal melakukan:

* Upload daftar mesin   
* Upload SOP (pdf/format lain)  
* Upload history maintenance (excel/format lain)  
* Upload daftar stok tools perbaikan  
* Upload jadwal produksi  
* Upload standar/spesifikasi kualitas produk  
* Connect machine data (PLC, Controller, IoT, dll) but optional (baca deployment packages)

**Operational Inputs**  
Selama penggunaan, AI menerima update sederhana mengenai:  
Automatic

* Sensor / PLC  
* Runtime mesin  
* Alarm  
* Temperature  
* Vibration  
* Current  
* Hasil QC produk  
* Hasil perbaikan

Manual

* Sparepart datang  
* ETA sparepart berubah  
* Jadwal dan target produksi berubah  
* Laporan operator  
* Ketersediaan teknisi

**Main Outputs**

* Machine Health Dashboard  
* Anomaly Detection  
* Root Cause Analysis  
* Maintenance Recommendation  
* **Optimal Maintenance Scheduling dengan Technician Assignment**  
* Sparepart Recommendation  
* Work Order  
* Daily / Weekly Maintenance Report


**Target Users**  
Small medium manufactur yang:

* Sudah memiliki mesin industri  
* Belum memiliki CMMS atau predictive maintenance  
* Ingin implementasi AI dengan biaya rendah  
* Tidak memiliki tim AI maupun tim IT khusus

**Deployment Packages (Not primary si, bisa asumsi atau state semua target itu pabrik yang udah punya alat dengan PLC, tapi kalau nerapin bagus juga jadi ya biar lebih cocok sm target pabrik kecil yang digitalisasi belum menyeluruh. Tapi buat pengumpulan doang gausa diimplementasikan bgt keknya si, buat sesuai paket professional aja)**

| Starter | Standard | Professional |
| ----- | ----- | ----- |
| Input: SOP Asset List Maintenance History Output: AI Maintenance Planning Work Order Reporting  | Tambahan: Machine Data (PLC / Controller / IoT) Output: Machine Health Monitoring Anomaly Detection AI Maintenance Recommendation  | Tambahan: Production Schedule Sparepart Inventory Technician Availability QC Product dengan CV Output: AI Decision Making Business-aware Maintenance Scheduling Constraint-based Optimization |

