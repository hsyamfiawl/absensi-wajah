"""Absensi wajah versi terminal.

Jalankan dengan:  python absensi.py

Tombol:
  t  daftar wajah baru ke dataset (nama diketik di jendela kamera)
  r  muat ulang encoding dari dataset
  q  keluar

Alternatif tanpa kamera: python tambah_dataset.py
WebUI lengkap: python webui.py
"""

import os
import sys
import time

import cv2
import face_recognition

import wajah_dasar as wd

# ======================
# KONFIGURASI
# ======================
SKALA_FRAME = 0.25
JEDA_ANTAR_FOTO = 1.0
HITUNG_MUNDUR = 3
BATAS_NAMA_LAYAR = 22

MODE_ABSEN = "absen"
MODE_KETIK_NAMA = "ketik_nama"
MODE_REKAM = "rekam"


# ======================
# MUAT DATASET
# ======================
def muat_dataset_awal():
    print("Sedang memuat data wajah dari folder dataset...")
    try:
        wd.siapkan_folder_dataset()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit()

    galeri = wd.GaleriWajah().muat(cetak_laporan=True)
    if galeri.jumlah_arah == 0:
        print("\nError: Tidak ada foto valid di dalam folder dataset.")
        print("Tambahkan foto wajah ke folder dataset/<nama>/ terlebih dahulu,")
        print("atau pakai 'python tambah_dataset.py' untuk merekam lewat kamera.")
        sys.exit()

    print(f"Encoding selesai! {galeri.jumlah_arah} sample dari {len(galeri.nama_unik())} orang.")
    return galeri


# ======================
# GAMBAR KOTAK WAJAH
# ======================
def gambar_hasil(frame, tinggi, lebar, daftar):
    """Menggambar kotak hijau/merah beserta nama pada frame."""
    faktor = 1.0 / SKALA_FRAME if SKALA_FRAME < 1 else 1.0
    for item in daftar:
        atas, kanan, bawah, kiri = item["lokasi"]
        y1 = int(max(0, min(tinggi - 1, atas * faktor)))
        x2 = int(max(0, min(lebar, kanan * faktor)))
        y2 = int(max(0, min(tinggi, bawah * faktor)))
        x1 = int(max(0, min(lebar - 1, kiri * faktor)))

        if item["nama"]:
            wd.kotak_wajah(frame, (y1, x2, y2, x1), (0, 255, 0), label=item["nama"])
        else:
            wd.kotak_wajah(frame, (y1, x2, y2, x1), (0, 0, 255), label="TIDAK DIKENAL")
    return frame


def analisis_frame(frame, galeri, tandai_absen=True):
    """Mendeteksi wajah pada frame lalu mengembalikan (daftar_hasil, factor_y)."""
    kecil = wd.perkecil(frame, SKALA_FRAME)
    rgb = wd.bgr_ke_rgb(kecil)
    lokasi_list = wd.cari_wajah_bertapa(rgb)

    daftar = []
    if lokasi_list:
        try:
            encoding_list = face_recognition.face_encodings(rgb, lokasi_list, model="hog")
        except Exception as e:
            print(f"Peringatan: Gagal membuat encoding: {e}")
            encoding_list = []

        for lokasi, encoding in zip(lokasi_list, encoding_list):
            nama = None
            if encoding is not None:
                nama, _ = galeri.cari(encoding)
            daftar.append({
                "lokasi": lokasi,
                "encoding": encoding,
                "nama": nama.upper() if nama else None,
            })
    return daftar


# ======================
# MODE PENDAFTARAN WAJAH
# ======================
def jalankan_pendaftaran(kamera, galeri, pencatat):
    """Berubah jadi mode pendaftaran wajah baru sampai pengguna menekan 'q'.

    Alur: ketik nama di jendela kamera -> hitung mundur -> rekam foto ->
    encoding dimuat ulang -> kembali ke mode absen.
    """
    mode = MODE_KETIK_NAMA
    ketikan = ""
    waktu_foto = 0.0
    sisa_target = 0
    nama_baru = ""
    hitung = 0

    while True:
        berhasil, frame = kamera.read()
        if not berhasil:
            return
        tinggi, lebar = frame.shape[:2]

        if mode == MODE_KETIK_NAMA:
            wd.teks_di_layar(
                frame, "DAFTAR WAJAH BARU", (20, 40), skala=0.9,
                warna=(0, 255, 255), tebal=2,
            )
            wd.teks_di_layar(
                frame, f"Nama: {ketikan}_", (20, 80), skala=0.9,
            )
            wd.teks_di_layar(
                frame,
                "Enter = lanjut   Esc = batal   Backspace = hapus",
                (20, tinggi - 20), skala=0.6, warna=(180, 180, 180),
            )

        elif mode == MODE_REKAM:
            if hitung > 0:
                wd.teks_di_layar(
                    frame, f"Mulai dalam {hitung}", (20, 40), skala=1.2,
                    warna=(0, 200, 255), tebal=3,
                )
                if time.time() >= waktu_foto:
                    hitung -= 1
                    waktu_foto = time.time() + 1.0
            else:
                daftar = analisis_frame(frame, galeri, tandai_absen=False)
                gambar_hasil(frame, tinggi, lebar, daftar)

                if daftar and daftar[0]["encoding"] is not None:
                    folder = wd.folder_orang(nama_baru)
                    os.makedirs(folder, exist_ok=True)
                    nama_file = f"reg_{time.strftime('%Y%m%d_%H%M%S')}_{sisa_target}.jpg"
                    if wd.simpan_foto(os.path.join(folder, nama_file), frame):
                        sisa_target -= 1
                        print(f"  [SIMPAN] {nama_baru}/{nama_file} (sisa {sisa_target})")

                    wd.teks_di_layar(
                        frame, f"TERSIMPAN, sisa {sisa_target} foto",
                        (20, 40), skala=0.9, warna=(0, 255, 0),
                    )
                    waktu_foto = time.time() + JEDA_ANTAR_FOTO
                else:
                    wd.teks_di_layar(
                        frame, "Wajah tidak terdeteksi - cari posisi yang pas",
                        (20, 40), skala=0.8, warna=(0, 0, 255),
                    )

                if sisa_target <= 0:
                    galeri.muat(paksa=True, cetak_laporan=False)
                    print(f"\n[SELESAI] Wajah '{nama_baru}' didaftarkan. "
                          f"Total encoding: {galeri.jumlah_arah}")
                    return

        cv2.imshow("Sistem Absensi Wajah", frame)
        tombol = cv2.waitKey(20) & 0xFF

        if tombol == ord("q"):
            if mode == MODE_KETIK_NAMA:
                print("Pendaftaran dibatalkan.")
                return
            print("Pendaftaran dihentikan.")
            galeri.muat(paksa=True, cetak_laporan=False)
            return

        if mode == MODE_KETIK_NAMA:
            if tombol == 13:  # Enter
                nama_baru = wd.bersihkan_nama(ketikan)
                if not wd.nama_valid(nama_baru):
                    wd.teks_di_layar(frame, "Nama tidak valid, ketik ulang", (20, 120),
                                      skala=0.7, warna=(0, 0, 255))
                    continue
                ketikan = ""
                mode = MODE_REKAM
                hitung = HITUNG_MUNDUR
                sisa_target = wd.JUMLAH_FOTO_DEFAULT
                waktu_foto = time.time()
                print(f"\nMerekam {wd.JUMLAH_FOTO_DEFAULT} foto untuk '{nama_baru}'...")
            elif tombol == 27:  # Esc
                print("Pendaftaran dibatalkan.")
                return
            elif tombol == 8:  # Backspace
                ketikan = ketikan[:-1]
            elif 32 <= tombol <= 126:
                if len(ketikan) < 40:
                    ketikan += chr(tombol)


# ======================
# PROGRAM UTAMA
# ======================
def main():
    galeri = muat_dataset_awal()
    pencatat = wd.PencatatAbsensi()
    pencatat.muat_yang_sudah()

    kamera, indeks = wd.buka_kamera()
    if kamera is None:
        print("Error: Tidak dapat mengakses kamera.")
        print("Catatan: aplikasi ini tidak bisa memakai kamera yang sedang dipakai program lain.")
        sys.exit()
    print(f"Kamera aktif (indeks {indeks}). Tekan 'q' untuk keluar, 't' untuk daftar wajah baru.\n")

    while True:
        berhasil, frame = kamera.read()
        if not berhasil:
            print("Gagal membaca frame dari kamera.")
            break

        tinggi, lebar = frame.shape[:2]
        daftar = analisis_frame(frame, galeri)

        for item in daftar:
            if item["nama"]:
                catatan = pencatat.catat(item["nama"])
                if catatan:
                    print(f"\n[ABSEN BERHASIL] {catatan['nama']} tercatat pada "
                          f"{catatan['tanggal']} {catatan['waktu']}")

        gambar_hasil(frame, tinggi, lebar, daftar)
        wd.teks_di_layar(
            frame, "q=keluar   t=daftar wajah baru   r=muat ulang encoding",
            (20, tinggi - 20), skala=0.55, warna=(170, 170, 170),
        )
        wd.teks_di_layar(
            frame, f"Encoding dimuat: {galeri.jumlah_arah}", (20, 30), skala=0.6,
            warna=(150, 150, 150),
        )

        cv2.imshow("Sistem Absensi Wajah", frame)
        tombol = cv2.waitKey(1) & 0xFF

        if tombol == ord("q"):
            break
        if tombol == ord("t"):
            print("\nMode pendaftaran wajah. Ketik nama pada jendela kamera...")
            jalankan_pendaftaran(kamera, galeri, pencatat)
        if tombol == ord("r"):
            print("\nMemuat ulang encoding...")
            galeri.muat(paksa=True, cetak_laporan=True)
            print(f"Selesai. {galeri.jumlah_arah} encoding dimuat.")

    kamera.release()
    cv2.destroyAllWindows()
    print("\nProgram selesai.")


if __name__ == "__main__":
    main()