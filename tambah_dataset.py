"""Menambah data wajah ke folder dataset lewat kamera.

Contoh pakai:
    python tambah_dataset.py                # interaktif, nama ditanyakan
    python tambah_dataset.py Budi Santoso   # langsung sebut namanya
    python tambah_dataset.py Budi 20        # 20 foto untuk Budi
    python tambah_dataset.py --daftar       # lihat orang yang sudah terdaftar

Foto otomatis disimpan ke dataset/<nama>/ dan hanya disimpan bila wajah
benar-benar terdeteksi.
"""

import os
import sys
import time

import cv2

import wajah_dasar as wd

# ======================
# KONFIGURASI
# ======================
HITUNG_MUNDUR = 3
JEDA_ANTAR_FOTO = 1.0
SKALA_DETEKSI = 0.5


# ======================
# TAMPILKAN DAFTAR ORANG
# ======================
def tampilkan_daftar():
    nama_orang = wd.daftar_nama_orang()
    if not nama_orang:
        print("Dataset masih kosong.")
        return

    print(f"\nOrang terdaftar ({len(nama_orang)}):")
    for nama in nama_orang:
        foto = wd.foto_orang(nama)
        print(f"  - {nama:<20} {len(foto):>2} foto")


# ======================
# REKAM WAJAH
# ======================
def rekam_wajah(kamera, nama, target):
    """Merekam `target` foto wajah dan menyimpannya ke dataset/<nama>/."""
    folder = wd.folder_orang(nama)
    os.makedirs(folder, exist_ok=True)

    encoding_lama = []
    for lokasi in wd.foto_orang(nama):
        try:
            encoding = wd.encoding_wajah(wd.muat_gambar(lokasi))
        except Exception:
            continue
        if encoding is not None:
            encoding_lama.append(encoding)

    tersimpan = 0
    ditolak = 0
    duplikat = 0
    hitung = 0
    waktu_foto = 0.0
    terakhir_coba = 0.0

    print(f"\nMerekam untuk '{nama}'. Jendela kamera akan terbuka:")
    print("  [SPASI] ambil foto manual   [u] hapus foto terakhir   [q] selesai   [r] mulai ulang\n")

    while tersimpan < target:
        berhasil, frame = kamera.read()
        if not berhasil:
            print("Gagal membaca frame dari kamera.")
            break

        tinggi, lebar = frame.shape[:2]

        # Deteksi wajah pada frame yang diperkecil supaya tetap cepat
        kecil = wd.perkecil(frame, SKALA_DETEKSI)
        lokasi_wajah = wd.cari_wajah_bertapa(wd.bgr_ke_rgb(kecil))

        for lokasi in lokasi_wajah:
            atas, kanan, bawah, kiri = lokasi
            faktor = 1.0 / SKALA_DETEKSI
            wd.kotak_wajah(
                frame,
                (
                    int(atas * faktor), int(kanan * faktor),
                    int(bawah * faktor), int(kiri * faktor),
                ),
                (0, 255, 0) if hitung == 0 else (255, 200, 0),
                label="wajah terdeteksi",
            )

        wd.teks_di_layar(
            frame, f"{nama}  -  tersimpan {tersimpan}/{target}", (20, 40),
            skala=0.9, warna=(255, 255, 255),
        )
        if hitung > 0:
            wd.teks_di_layar(
                frame, f"Mulai dalam {hitung}...", (20, 85), skala=1.2,
                warna=(0, 200, 255), tebal=3,
            )
        wd.teks_di_layar(
            frame, "SPASI=manual  u=hapus terakhir  q=selesai  r=reset",
            (20, tinggi - 20), skala=0.55, warna=(170, 170, 170),
        )

        cv2.imshow(f"Merekam - {nama}", frame)
        tombol = cv2.waitKey(1) & 0xFF

        manual = False

        if tombol == ord("q"):
            break
        if tombol == ord("u"):
            foto = wd.foto_orang(nama)
            if foto:
                wd.hapus_berkas(foto[-1])
                tersimpan = max(0, tersimpan - 1)
                print(f"  [HAPUS] {os.path.basename(foto[-1])}")
            continue
        if tombol == ord("r"):
            tersimpan = 0
            hitung = 0
            continue
        if tombol == ord(" "):
            manual = True
            hitung = 0

        sekarang = time.time()

        # Hitung mundur sebelum mulai merekam otomatis
        if hitung > 0:
            if sekarang >= waktu_foto:
                hitung -= 1
                waktu_foto = sekarang + 1.0
            continue

        # Rekam otomatis setiap JEDA_ANTAR_FOTO detik, atau saat tombol spasi ditekan
        if not manual and sekarang - terakhir_coba < JEDA_ANTAR_FOTO:
            continue
        terakhir_coba = sekarang

        if not lokasi_wajah:
            ditolak += 1
            print("  [LEWATI] wajah tidak terdeteksi")
            continue

        rgb = wd.bgr_ke_rgb(frame)
        encoding = wd.encoding_wajah(rgb)
        if encoding is None:
            ditolak += 1
            print("  [LEWATI] encoding gagal dibuat")
            continue

        if wd.terlalu_serupa(encoding, encoding_lama):
            duplikat += 1
            continue

        nama_file = f"reg_{time.strftime('%Y%m%d_%H%M%S')}_{tersimpan:02d}.jpg"
        if not wd.simpan_foto(os.path.join(folder, nama_file), frame):
            ditolak += 1
            continue

        encoding_lama.append(encoding)
        tersimpan += 1
        print(f"  [SIMPAN] {nama_file} ({tersimpan}/{target})")

    return tersimpan, ditolak, duplikat


# ======================
# PROGRAM UTAMA
# ======================
def parse_argumen(argv):
    """Membaca nama dan jumlah foto dari argumen baris perintah."""
    argumen = [a for a in argv if not a.startswith("-")]
    bendera = {a for a in argv if a.startswith("-")}

    nama = " ".join(argumen).strip()
    target = wd.JUMLAH_FOTO_DEFAULT

    # Argumen terakhir yang hanya angka dianggap jumlah foto
    bagian = nama.split()
    if bagian and bagian[-1].isdigit():
        target = int(bagian.pop())
        nama = " ".join(bagian)

    return nama, target, "--daftar" in bendera


def main():
    nama, target, mau_daftar = parse_argumen(sys.argv[1:])

    if mau_daftar:
        tampilkan_daftar()
        return

    print("=" * 58)
    print("  TAMBAH DATASET WAJAH")
    print("=" * 58)
    wd.siapkan_folder_dataset()
    tampilkan_daftar()

    if not nama:
        try:
            nama = input("\nNama orang: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDibatalkan.")
            return
    nama = wd.bersihkan_nama(nama)

    if not wd.nama_valid(nama):
        print("\nError: Nama tidak valid. Gunakan huruf, angka, spasi, titik, atau tanda hubung.")
        return
    if target < 1:
        print("\nError: Jumlah foto harus minimal 1.")
        return

    sudah = len(wd.foto_orang(nama))
    if sudah:
        print(f"\nCatatan: {nama} sudah punya {sudah} foto, foto baru akan ditambahkan.")

    kamera, indeks = wd.buka_kamera()
    if kamera is None:
        print("\nError: Tidak dapat mengakses kamera.")
        return

    try:
        tersimpan, ditolak, duplikat = rekam_wajah(kamera, nama, target)
    finally:
        kamera.release()
        cv2.destroyAllWindows()

    total = len(wd.foto_orang(nama))
    print(f"\nSelesai. Foto '{nama}' sekarang {total} buah "
          f"(baru {tersimpan}, dilewati {ditolak}, terlalu mirip {duplikat}).")

    if tersimpan:
        print("Encoding wajah akan dimuat otomatis saat absensi.py atau webui.py dijalankan.")
    elif not total:
        print("Tidak ada foto tersimpan. Pastikan wajah terlihat jelas saat rekam.")


if __name__ == "__main__":
    main()