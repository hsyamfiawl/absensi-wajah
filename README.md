# Sistem Absensi Wajah

Aplikasi absensi berbasis pengenalan wajah dengan dua antarmuka:

- **Web UI** (Flask) yang modern dan responsif untuk mengelola dataset, memantau
  kehadiran, dan melakukan absensi langsung lewat browser.
- **Terminal + OpenCV** untuk absensi cepat dan perekaman dataset dari webcam.

Semua data (foto wajah dan riwayat absensi) disimpan **lokal di komputer**.
Aplikasi berjalan offline dan tidak mengirim data ke server mana pun.

## Fitur

- Pengenalan wajah real-time menggunakan `face_recognition` (dlib) dan OpenCV.
- Dashboard statistik: jumlah orang, foto, kehadiran hari ini, dan log kejadian.
- Absensi langsung lewat browser dengan streaming kamera.
- Pencatatan otomatis **satu kali per orang per hari**.
- Kelola dataset wajah: upload/drag & drop foto, ambil foto dari kamera, hapus.
- Multi-foto per orang dengan pemeriksaan duplikat.
- Rekap absensi dengan filter nama/tanggal, ekspor CSV, dan reset data.
- Tema gelap/terang, sidebar mobile, notifikasi, dan tampilan responsif.
- Tanpa CDN atau dependensi frontend tambahan, sehingga tetap cepat dan bisa
  dipakai offline.

## Teknologi

| Komponen | Keterangan |
| --- | --- |
| Bahasa | Python 3.11 |
| Pengenalan wajah | `face_recognition` 1.2.3 + `dlib` 19.24.1 |
| Kamera & gambar | OpenCV 4.10, NumPy, Pillow |
| Web | Flask 3.1 |
| Frontend | HTML, CSS, JavaScript (tanpa framework/CDN) |

## Persyaratan

- Windows 10/11 64-bit (jalur utama) atau Linux/macOS.
- **Python 3.11 64-bit** — wheel dlib yang disertakan hanya untuk CPython 3.11
  Windows 64-bit.
- Webcam yang berfungsi.
- RAM minimal 4 GB (8 GB lebih nyaman).
- Untuk Linux/macOS: `cmake` dan compiler C++ untuk membangun dlib.

## Instalasi (Windows)

```bat
git clone https://github.com/hsyamfiawl/absensi-wajah.git
cd absensi-wajah
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install dlib-19.24.1-cp311-cp311-win_amd64.whl
python -m pip install -r requirements.txt
```

`dlib` sengaja dipasang terpisah karena kompilasi manual di Windows cukup rumit.
Wheel yang sudah disertakan membuat proses instalasi jauh lebih cepat.

## Instalasi (Linux/macOS)

```bash
git clone https://github.com/hsyamfiawl/absensi-wajah.git
cd absensi-wajah
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Jika dlib gagal dibangun, pasang dependensi sistem terlebih dahulu, misalnya:

```bash
# Debian/Ubuntu
sudo apt install build-essential cmake python3-dev

# macOS (Homebrew)
brew install cmake
```

## Menjalankan

### Web UI

Cara paling mudah di Windows: klik dua kali `jalankan_webui.bat`.

Atau lewat terminal:

```bash
python webui.py --buka
```

Buka `http://127.0.0.1:5000` di browser. Opsi `--buka` membuat browser terbuka
otomatis.

### Versi terminal

```bash
python absensi.py
```

Tombol di jendela kamera: `t` tambah wajah baru, `r` muat ulang dataset,
`q` keluar.

### Menambah dataset lewat kamera

```bash
python tambah_dataset.py                  # interaktif
python tambah_dataset.py "Budi Santoso"   # langsung dengan nama
python tambah_dataset.py Budi 20          # rekam 20 foto
python tambah_dataset.py --daftar         # lihat orang terdaftar
```

### Uji cepat Web UI

```bash
python uji_webui.py
```

Pengujian ini tidak membutuhkan kamera atau browser.

## Cara Pakai Singkat

1. Buka halaman **Dataset Wajah**, lalu unggah 5–10 foto wajah dengan
   pencahayaan yang cukup dan sudut yang bervariasi. Foto juga bisa diambil
   langsung dari kamera.
2. Buka halaman **Absensi Langsung** dan izinkan browser mengakses kamera.
3. Wajah yang dikenali akan dicatat otomatis. Orang yang sama tidak dicatat dua
   kali pada hari yang sama.
4. Lihat atau ekspor rekap di halaman **Rekap Absensi**.

Tips agar pengenalan lebih akurat:

- Gunakan wajah yang terlihat jelas, tidak terlalu kecil, dan tidak blur.
- Hindari pencahayaan yang terlalu gelap atau terlalu kontras.
- Tambahkan beberapa foto dengan ekspresi dan sudut berbeda.
- Pastikan hanya ada satu wajah utama di depan kamera saat absensi.

## Struktur Project

```
absensi-wajah/
├── absensi.py               # Absensi versi terminal + OpenCV
├── webui.py                 # Server Flask dan seluruh endpoint Web UI
├── wajah_dasar.py           # Dataset, encoding wajah, dan pencatatan absensi
├── tambah_dataset.py        # Perekaman dataset lewat kamera
├── uji_webui.py             # Uji otomatis halaman & endpoint Web UI
├── jalankan_webui.bat       # Launcher Web UI untuk Windows
├── requirements.txt
├── README.md
├── README_WEBUI.md          # Panduan khusus tampilan web
├── dlib-19.24.1-cp311-cp311-win_amd64.whl
├── templates/               # Halaman HTML (dashboard, absensi, dataset, dll.)
└── static/                  # CSS, JavaScript, dan ikon
```

Folder `dataset/`, `daftar_absensi.csv`, dan `.webui_kunci` dibuat otomatis saat
aplikasi berjalan dan **tidak disertakan di repository** karena berisi data
pribadi.

## Data dan Privasi

- Foto wajah disimpan di `dataset/<nama>/` dan hanya ada di komputer pengguna.
- Riwayat absensi disimpan di `daftar_absensi.csv`.
- `.webui_kunci` adalah kunci rahasia Flask yang dibuat otomatis.
- File-file tersebut sudah masuk `.gitignore` sehingga tidak ikut terunggah.
- Tidak ada koneksi keluar selain pemuatan halaman lokal di `127.0.0.1`.

## Troubleshooting

**Gagal memasang dlib di Windows**

- Pastikan Python yang dipakai benar-benar 3.11 64-bit (`python -c "import sys; print(sys.version)"`).
- Gunakan wheel yang disertakan, lalu jalankan `pip install -r requirements.txt`.
- Jika tetap gagal, pasang CMake dan Visual Studio Build Tools, atau gunakan
  Python 3.11 sesuai instruksi di atas.

**Kamera tidak terdeteksi**

- Tutup aplikasi lain yang sedang memakai kamera.
- Periksa izin kamera di pengaturan Windows dan izin situs di browser.
- Coba cabut dan pasang ulang webcam, lalu restart aplikasi.

**Wajah tidak dikenali**

- Tambahkan foto yang lebih jelas dan beragam untuk orang tersebut.
- Pastikan pencahayaan cukup dan wajah menghadap kamera.
- Ambang kecocokan bawaan adalah `0.5` (lihat `AMBANG_KECOCOKAN` di
  `wajah_dasar.py`).

**Muncul pesan tidak ada foto valid**

- Foto harus menampilkan wajah yang terdeteksi dengan jelas.
- Hindari foto yang terlalu gelap, blur, atau wajahnya terlalu kecil.
- Rekam ulang lewat halaman Dataset atau `tambah_dataset.py`.

**Port 5000 sedang dipakai**

- Hentikan proses lain yang memakai port 5000, atau ubah `port=5000` pada
  `app.run(...)` di bagian akhir `webui.py`.

**Pemuatan awal lambat**

- Encoding wajah dihitung dari seluruh foto dataset saat aplikasi dimulai.
  Semakin banyak foto dan semakin besar resolusinya, semakin lama prosesnya.
  Ini normal pada CPU.

## Catatan Pengembangan

- `face_recognition` memakai model HOG bawaan dlib, sehingga cukup cepat di CPU
  tetapi kurang akurat untuk wajah yang sangat kecil atau sudut ekstrem.
- Pencatatan absensi hanya aktif saat halaman **Absensi Langsung** dibuka.
- File `daftar_absensi.csv.bak` dibuat otomatis ketika data absensi direset.
- Jalankan `python uji_webui.py` sebelum melakukan perubahan besar pada Web UI.
