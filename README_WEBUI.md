# Web UI Absensi Wajah

Tampilan web modern untuk sistem absensi wajah. Semua data tetap disimpan lokal
di komputer (folder `dataset/` dan `daftar_absensi.csv`).

## Menjalankan

Cara paling mudah:

1. Klik dua kali `jalankan_webui.bat`.
2. Browser akan terbuka otomatis di `http://127.0.0.1:5000`.

Atau lewat terminal:

```bash
python webui.py
```

Buka `http://127.0.0.1:5000` di browser. Tambahkan `--buka` jika ingin browser
terbuka otomatis:

```bash
python webui.py --buka
```

## Halaman

- **Dashboard** - ringkasan orang terdaftar, foto, kehadiran hari ini, log
  kejadian, dan daftar anggota.
- **Absensi Langsung** - streaming kamera, deteksi wajah, pencatatan otomatis
  satu kali per hari, dan log absen terbaru.
- **Rekap Absensi** - filter nama/tanggal/rentang tanggal, rekap per orang,
  daftar yang belum pernah hadir, ekspor CSV, dan reset data.
- **Dataset Wajah** - tambah orang lewat upload foto (termasuk drag & drop) atau
  ambil foto langsung dari kamera, lihat foto, dan hapus data.

## Fitur tampilan

- Desain responsif untuk desktop, tablet, dan HP.
- Mode gelap dan terang (tersimpan otomatis di browser).
- Sidebar mobile, notifikasi toast, animasi statistik, dan indikator kamera.
- Preview foto sebelum diunggah dan pencarian anggota secara langsung.
- Tanpa CDN atau dependensi frontend tambahan, sehingga tetap cepat dan bisa
  dipakai offline.

## Catatan

- Pencatatan absensi hanya dilakukan saat halaman **Absensi Langsung** aktif.
- Wajah yang sudah tercatat tidak akan dicatat ulang pada hari yang sama.
- Gunakan pencahayaan yang cukup dan posisi wajah menghadap kamera.
- File `daftar_absensi.csv.bak` dibuat otomatis saat data absensi direset.
