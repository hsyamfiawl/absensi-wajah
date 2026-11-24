"""Uji otomatis semua halaman & endpoint webui.py.

Jalankan: python uji_webui.py
Tidak butuh browser dan tidak butuh kamera.
"""

import io
import os
import sys

import numpy as np
from PIL import Image

import wajah_dasar as wd
import webui

# ======================
# PENGATURAN UJI
# ======================
SINKRON = {400, 404, 503}  # status yang memang diharapkan untuk kasus negatif

wd.siapkan_folder_dataset()
webui.muat_galeri(paksa=True, cetak=False)
webui.pencatat.muat_yang_sudah()

klien = webui.app.test_client()
lulus = []
gagal = []


def cek(nama, method, url, diharapkan=200, **kwargs):
    """Menjalankan satu permintaan.

    `diharapkan` boleh berupa satu status (mis. 404) atau sekumpulan status
    yang sama-sama benar (mis. SINKRON untuk kasus yang boleh gagal atau tidak).
    """
    try:
        # Formulir di aplikasi ini selalu mengarahkan ulang setelah submit,
        # jadi ikuti redirect agar isi halaman & pesan flash ikut terambil.
        kwargs.setdefault("follow_redirects", method == "post")
        resp = getattr(klien, method)(url, **kwargs)
        status = resp.status_code
    except Exception as e:
        print(f"GAGAL   {nama:<32} ERROR {type(e).__name__}: {e}")
        gagal.append(nama)
        return None

    if isinstance(diharapkan, int):
        ebenar = {diharapkan}
    else:
        ebenar = set(diharapkan)

    benar = status in ebenar
    label = "LULUS" if benar else "GAGAL"
    print(f"{label}   {nama:<32} {status}  bytes={len(resp.data)}")
    (lulus if benar else gagal).append(nama)
    return resp


def cek_flash(resp, harus_ada):
    """Memastikan pesan flash tertentu muncul di halaman tujuan."""
    if resp is None:
        return False
    teks = resp.data.decode("utf-8", "ignore")
    if harus_ada in teks:
        print(f"  FLASH  \"{harus_ada[:56]}\" tampil")
        return True
    print(f"  FLASH  \"{harus_ada[:56]}\" TIDAK ditemukan")
    gagal.append(f"flash: {harus_ada[:30]}")
    return False


def bytes_gambar(isi, nama_berkas="a.jpg"):
    luang = io.BytesIO()
    Image.fromarray(isi).save(luang, format="JPEG")
    luang.seek(0)
    return (luang, nama_berkas)


print("\n--- HALAMAN UTAMA ---")
cek("dashboard", "get", "/")
cek("dataset", "get", "/dataset")
cek("rekap absensi", "get", "/absensi")
cek("kamera langsung", "get", "/kamera")
cek("stylesheet", "get", "/static/style.css")

print("\n--- FILTER ABSENSI ---")
cek("filter nama", "get", "/absensi?nama=HIS")
cek("filter tanggal", "get", "/absensi?tanggal=2026-10-18")
cek("filter rentang", "get", "/absensi?mulai=2026-01-01&selesai=2026-12-31")
cek("ekspor csv", "get", "/absensi/export")
cek("ekspor csv + filter", "get", "/absensi/export?nama=HIS")

print("\n--- FOTO (harus menolak path berbahaya) ---")
contoh = next((o for o in wd.ringkasan_dataset() if o["cover"]), None)
if contoh:
    cek("foto valid", "get", f"/foto/{contoh['nama']}/{os.path.basename(contoh['cover'])}")
cek("path traversal -> 404", "get", "/foto/../webui.py", diharapkan=404)
cek("foto tak ada -> 404", "get", "/foto/Entah/TidakAda.jpg", diharapkan=404)
cek("hapus traversal -> 404", "post", "/dataset/foto/hapus",
    data={"nama": "..", "file": "..\\..\\webui.py"}, diharapkan=404)

print("\n--- API ---")
cek("status", "get", "/api/status")
cek("tangkap tanpa nama -> 400", "post", "/api/tangkap", data={}, diharapkan=400)
cek("tangkap tanpa kamera -> 503", "post", "/api/tangkap",
    data={"nama": "Uji Kamera"}, diharapkan=503)
cek("restart kamera", "post", "/api/kamera/restart")

print("\n--- KELOLA DATASET ---")
datarata = np.full((480, 640, 3), 90, dtype=np.uint8)

resp = cek("nama tidak valid -> ditolak", "post", "/dataset/tambah",
           data={"nama": "!!", "foto": [bytes_gambar(datarata)]},
           content_type="multipart/form-data")
cek_flash(resp, "Nama tidak valid")

resp = cek("foto tanpa wajah -> ditolak", "post", "/dataset/tambah",
           data={"nama": "Orang Tanpa Wajah", "foto": [bytes_gambar(datarata)]},
           content_type="multipart/form-data")
cek_flash(resp, "Tidak ada foto tersimpan")

if contoh:
    with open(contoh["cover"], "rb") as f:
        data_wajah = f.read()
    cek("upload wajah valid", "post", "/dataset/tambah",
        data={"nama": "Orang Uji", "foto": [(io.BytesIO(data_wajah), "wajah.jpg")]},
        content_type="multipart/form-data")
    cek_flash(cek("cek daftar orang uji", "get", "/dataset"), "Orang Uji")
    cek("hapus orang uji", "post", "/dataset/orang/hapus", data={"nama": "Orang Uji"})
    cek_flash(cek("hapus lagi -> pesan galat", "post", "/dataset/orang/hapus",
                  data={"nama": "Orang Uji"}), "tidak ditemukan")

cek("muat ulang encoding", "post", "/dataset/muat-ulang")

print("\n--- PENCATATAN ABSENSI ---")
sisa_awal = len(webui.pencatat.baca_semua())
hasil = webui.pencatat.catat("UjiOtomatis")
kedua = webui.pencatat.catat("UjiOtomatis")
sisa_akhir = len(webui.pencatat.baca_semua())

if hasil and kedua is None and sisa_akhir == sisa_awal + 1:
    print("LULUS   catat 1x per hari                  benar")
    lulus.append("catat 1x per hari")
else:
    print(f"GAGAL   catat 1x per hari                  {hasil} / {kedua}")
    gagal.append("catat 1x per hari")

stat = webui.pencatat.statistik()
print(f"LULUS   statistik absensi                  {stat['total_catatan']} catatan, "
      f"{stat['hadir_hari_ini']} hari ini")

print("\n--- DETEKSI WAJAH PADA FRAME KAMERA ---")
import cv2  # noqa: E402

if contoh:
    bingkai = cv2.imread(contoh["cover"])
    if bingkai is not None:
        # Foto dataset dipakai sebagai pengganti frame kamera
        _, hasil = webui.proses_absensi(bingkai, tandai_absen=False)
        nama_dikenali = [h["nama"] for h in hasil if h["dikenal"]]
        if nama_dikenali:
            print(f"LULUS   wajah dikenali pada frame          {nama_dikenali}")
            lulus.append("deteksi wajah")
        else:
            print(f"GAGAL   wajah dikenali pada frame          tidak ada yang cocok: {hasil}")
            gagal.append("deteksi wajah")

        # Frame tanpa wajah sama sekali
        _, hasil_kosong = webui.proses_absensi(np.full((360, 640, 3), 40, np.uint8),
                                               tandai_absen=False)
        if not hasil_kosong:
            print("LULUS   frame tanpa wajah                 tidak ada false positive")
            lulus.append("tanpa false positive")
        else:
            print(f"GAGAL   frame tanpa wajah                 {hasil_kosong}")
            gagal.append("tanpa false positive")

        # Pencatatan otomatis saat wajah dikenali
        awal = len(webui.pencatat.baca_semua())
        _, hasil_absen = webui.proses_absensi(bingkai, tandai_absen=True)
        akhir = len(webui.pencatat.baca_semua())
        baru_tertandai = any(h["baru"] for h in hasil_absen)
        if (akhir == awal + 1) == baru_tertandai:
            print(f"LULUS   catat otomatis sekali/hari         {awal} -> {akhir} baris")
            lulus.append("catat otomatis")
        else:
            print(f"GAGAL   catat otomatis sekali/hari         {awal} -> {akhir}, baru={baru_tertandai}")
            gagal.append("catat otomatis")

print("\n--- RESET ABSENSI ---")
cek("reset", "post", "/absensi/reset")
sisa = len(webui.pencatat.baca_semua())
if sisa == 0:
    print("LULUS   catatan jadi kosong                 benar")
    lulus.append("reset mengosongkan")
else:
    print(f"GAGAL   catatan jadi kosong                 masih {sisa} baris")
    gagal.append("reset mengosongkan")

print("\n--- HASIL ---")
print(f"{len(lulus)} lulus, {len(gagal)} gagal")
if gagal:
    print("Gagal: " + ", ".join(str(g) for g in gagal))
    sys.exit(1)
print("Semua pengujian lulus.")