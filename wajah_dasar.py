"""Fungsi dasar yang dipakai bersama oleh absensi.py dan tambah_dataset.py."""

import os
import re
import csv
import cv2
import numpy as np
import face_recognition
from datetime import datetime
from PIL import Image, ImageOps

# ======================
# KONFIGURASI PATH
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_DATASET = os.path.join(BASE_DIR, "dataset")
FILE_ABSEN = os.path.join(BASE_DIR, "daftar_absensi.csv")

EKSTENSI_GAMBAR = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
JUMLAH_FOTO_DEFAULT = 10
AMBANG_KECOCOKAN = 0.5
JARAK_ANTI_DUPLIKAT = 0.30

# Diurutkan dari paling cepat ke paling akurat.
# Foto beresolusi besar atau wajah kecil sering gagal pada upsample=1,
# jadi selalu ada percobaan cadangan sebelum foto dianggap gagal.
UPSAMPLE_CADANGAN = (1, 2, 0)

POLA_NAMA = re.compile(r"^[A-Za-z0-9 .,'\-_]+$")


# ======================
# HELPER NAMA & FOLDER
# ======================
def bersihkan_nama(nama):
    """Membersihkan nama orang agar aman dipakai sebagai nama folder."""
    nama = " ".join(str(nama).strip().split())
    nama = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nama).strip(". ")
    return nama


def nama_valid(nama):
    return bool(nama) and bool(POLA_NAMA.match(nama))


def folder_orang(nama):
    return os.path.join(PATH_DATASET, bersihkan_nama(nama))


def siapkan_folder_dataset():
    if not os.path.isdir(PATH_DATASET):
        os.makedirs(PATH_DATASET, exist_ok=True)
        print(f"Folder dataset dibuat: {PATH_DATASET}")
    return PATH_DATASET


def daftar_nama_orang():
    """Mengembalikan nama orang yang sudah punya folder di dalam dataset."""
    siapkan_folder_dataset()
    hasil = []
    for nama in os.listdir(PATH_DATASET):
        if os.path.isdir(os.path.join(PATH_DATASET, nama)):
            hasil.append(nama)
    return sorted(hasil)


def foto_orang(nama):
    """Mengembalikan daftar file foto milik satu orang."""
    folder = folder_orang(nama)
    if not os.path.isdir(folder):
        return []
    return [
        os.path.join(folder, f)
        for f in sorted(os.listdir(folder))
        if f.lower().endswith(EKSTENSI_GAMBAR) and not f.startswith(".")
    ]


def ringkasan_dataset():
    """Daftar orang di dataset beserta jumlah foto dan foto pertamanya."""
    hasil = []
    for nama in daftar_nama_orang():
        foto = foto_orang(nama)
        hasil.append({
            "nama": nama,
            "folder": folder_orang(nama),
            "jumlah_foto": len(foto),
            "foto": foto,
            "cover": foto[0] if foto else None,
        })
    return hasil


def simpan_berkas(lokasi, data_byte):
    """Menyamba byte gambar (hasil upload) ke disk. Mengembalikan path atau None."""
    try:
        with open(lokasi, "wb") as f:
            f.write(data_byte)
        return lokasi
    except Exception as e:
        print(f"Peringatan: Gagal menyimpan {lokasi} -> {e}")
        return None


def hapus_berkas(lokasi):
    try:
        os.remove(lokasi)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Peringatan: Gagal menghapus {lokasi} -> {e}")
        return False


def hapus_folder_orang(nama):
    """Menghapus seluruh folder dataset milik satu orang."""
    import shutil

    folder = folder_orang(nama)
    if not os.path.isdir(folder):
        return False
    shutil.rmtree(folder)
    return True


# ======================
# BACA & SIMPEL GAMBAR
# ======================
def muat_gambar(lokasi):
    """Membaca gambar menjadi array RGB 8-bit yang siap dipakai dlib."""
    with Image.open(lokasi) as pil_img:
        pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
        img = np.array(pil_img, dtype=np.uint8)
    return np.ascontiguousarray(img)


def bgr_ke_rgb(frame_bgr):
    return np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), dtype=np.uint8)


def rgb_ke_bgr(img_rgb):
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)


def simpan_foto(lokasi, frame_bgr):
    """Menyimpan frame kamera ke file jpg, mengembalikan path atau None."""
    if frame_bgr is None or frame_bgr.size == 0:
        return None
    try:
        if not cv2.imwrite(lokasi, frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
            return None
    except Exception as e:
        print(f"Peringatan: Gagal menyimpan {lokasi} -> {e}")
        return None
    return lokasi


# ======================
# DETEKSI & ENCODING WAJAH
# ======================
def cari_wajah(img_rgb, upsample=1):
    """Deteksi wajah pada gambar RGB. Mengembalikan list lokasi."""
    return face_recognition.face_locations(
        img_rgb, number_of_times_to_upsample=upsample, model="hog"
    )


def cari_wajah_bertapa(img_rgb, upsample_cadangan=UPSAMPLE_CADANGAN):
    """Deteksi wajah dengan beberapa kali percobaan upsample.

    Foto beresolusi besar atau wajah kecil sering gagal pada upsample=1,
    jadi selalu ada percobaan cadangan sebelum dianggap tidak ada wajah.
    """
    for up in upsample_cadangan:
        lokasi = cari_wajah(img_rgb, upsample=up)
        if lokasi:
            return lokasi
    return []


def wajah_terbesar(lokasi):
    """Mengambil kotak wajah terbesar (mainan) dari daftar lokasi."""
    if not lokasi:
        return None
    return max(lokasi, key=lambda l: (l[2] - l[0]) * (l[3] - l[1]))


def encoding_wajah(img_rgb, lokasi=None):
    """Membuat satu encoding 128-dimensi dari wajah terbesar pada gambar."""
    if lokasi is None:
        lokasi = cari_wajah_bertapa(img_rgb)
    if not lokasi:
        return None
    atas, kanan, bawah, kiri = wajah_terbesar(lokasi)
    hasil = face_recognition.face_encodings(
        img_rgb, [(atas, kanan, bawah, kiri)], model="hog"
    )
    return hasil[0] if hasil else None


def terlalu_serupa(encoding_baru, encoding_lama, jarak_min=JARAK_ANTI_DUPLIKAT):
    """True jika encoding_baru nyaris sama dengan salah satu encoding_lama."""
    if encoding_baru is None or not encoding_lama:
        return False
    jarak = face_recognition.face_distance(encoding_lama, encoding_baru)
    return bool(len(jarak) and float(np.min(jarak)) < jarak_min)


# ======================
# MEMUAT DATASET
# ======================
def muat_dataset(cetak_laporan=True):
    """Membaca seluruh dataset.

    Mengembalikan (encoding_dikenal, nama_valid, laporan).
    `encoding_dikenal` adalah list numpy array, `nama_valid` list str,
    dan `laporan` list baris teks siap dicetak.
    """
    if not os.path.isdir(PATH_DATASET):
        raise FileNotFoundError(
            f"Folder '{PATH_DATASET}' tidak ditemukan! Buat folder 'dataset' terlebih dahulu."
        )

    encoding_dikenal = []
    nama_valid = []
    laporan = []
    gagal = 0
    berhasil = 0

    for nama in sorted(os.listdir(PATH_DATASET)):
        folder = os.path.join(PATH_DATASET, nama)
        if not os.path.isdir(folder):
            continue

        for file_foto in sorted(os.listdir(folder)):
            if not file_foto.lower().endswith(EKSTENSI_GAMBAR) or file_foto.startswith("."):
                continue

            lokasi = os.path.join(folder, file_foto)
            try:
                img = muat_gambar(lokasi)
            except Exception as e:
                gagal += 1
                laporan.append(f"  [GAGAL BACA ] {nama}/{file_foto} -> {e}")
                continue

            lokasi_wajah = cari_wajah_bertapa(img)
            if not lokasi_wajah:
                gagal += 1
                laporan.append(f"  [TIDAK ADA  ] {nama}/{file_foto} -> wajah tidak terbaca, foto dilewati")
                continue

            encoding = encoding_wajah(img, lokasi_wajah)
            if encoding is None:
                gagal += 1
                laporan.append(f"  [GAGAL ENCOD] {nama}/{file_foto} -> encoding kosong, foto dilewati")
                continue

            encoding_dikenal.append(encoding)
            nama_valid.append(nama)
            berhasil += 1
            laporan.append(f"  [OK         ] {nama}/{file_foto}")

    if cetak_laporan:
        for baris in laporan:
            print(baris)
        print(f"Ringkasan dataset: {berhasil} foto dipakai, {gagal} foto dilewati.")

    return encoding_dikenal, nama_valid, laporan


# ======================
# GALERI WAJAH (CACHE ENCODING)
# ======================
class GaleriWajah:
    """Menyimpan encoding wajah dari dataset dan bisa dimuat ulang."""

    def __init__(self):
        self._encoding = []
        self._nama = []
        self._dimuat = False

    @property
    def encoding(self):
        return self._encoding

    @property
    def nama(self):
        return self._nama

    @property
    def jumlah_arah(self):
        """Jumlah sample encoding yang dimuat."""
        return len(self._encoding)

    def sudah_dimuat(self):
        return self._dimuat

    def muat(self, paksa=False, cetak_laporan=True):
        if self._dimuat and not paksa:
            return self

        siapkan_folder_dataset()
        self._encoding, self._nama, _ = muat_dataset(cetak_laporan=cetak_laporan)
        self._dimuat = True
        return self

    def kosongkan(self):
        self._encoding = []
        self._nama = []
        self._dimuat = False

    def nama_unik(self):
        return sorted(set(self._nama))

    def cari(self, encoding_wajah, toleransi=AMBANG_KECOCOKAN):
        """Mencari nama terdekat. Mengembalikan (nama, jarak) atau (None, None)."""
        if not self._encoding:
            return None, None
        jarak = face_recognition.face_distance(self._encoding, encoding_wajah)
        if len(jarak) == 0:
            return None, None
        index = int(np.argmin(jarak))
        jarak_terdekat = float(jarak[index])
        if jarak_terdekat > toleransi:
            return None, jarak_terdekat
        return self._nama[index], jarak_terdekat


# ======================
# PENCATAT ABSENSI
# ======================
class PencatatAbsensi:
    """Menulis dan membaca daftar absensi dalam format CSV."""

    HEADER = ("Nama", "Tanggal", "Waktu")

    def __init__(self, path=FILE_ABSEN):
        self.path = path
        self._sudah = set()

    @staticmethod
    def _kunci(nama, tanggal):
        return (nama.strip().upper(), tanggal.strip())

    def muat_yang_sudah(self):
        """Membaca ulang daftar kehadiran dari file CSV."""
        self._sudah.clear()
        for baris in self.baca_semua():
            kunci = self._kunci(baris["nama"], baris["tanggal"])
            self._sudah.add(kunci)
        return len(self._sudah)

    def sudah_tercatat(self, nama, tanggal):
        return self._kunci(nama, tanggal) in self._sudah

    def catat(self, nama, sekarang=None):
        """Mencatat kehadiran 1x per orang per hari.

        Mengembalikan dict {'baru': bool, 'nama': ..., 'tanggal': ..., 'waktu': ...}
        atau None bila sudah tercatat.
        """
        sekarang = sekarang or datetime.now()
        tanggal = sekarang.strftime("%Y-%m-%d")
        waktu = sekarang.strftime("%H:%M:%S")
        kunci = self._kunci(nama, tanggal)

        if kunci in self._sudah:
            return None

        header_baru = not os.path.exists(self.path)
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            if header_baru:
                f.write(",".join(self.HEADER) + "\n")
            f.write(f"{kunci[0]},{tanggal},{waktu}\n")

        self._sudah.add(kunci)
        return {"baru": True, "nama": kunci[0], "tanggal": tanggal, "waktu": waktu}

    def baca_semua(self):
        """Membaca seluruh catatan sebagai list dict."""
        if not os.path.exists(self.path):
            return []
        hasil = []
        with open(self.path, "r", newline="", encoding="utf-8") as f:
            for baris in csv.reader(f):
                if not baris or len(baris) < 3:
                    continue
                if [b.strip().upper() for b in baris[:3]] == [h.upper() for h in self.HEADER]:
                    continue
                hasil.append({
                    "nama": baris[0].strip(),
                    "tanggal": baris[1].strip(),
                    "waktu": baris[2].strip(),
                })
        return hasil

    def statistik(self):
        """Statistik sederhana dari catatan absensi."""
        catatan = self.baca_semua()
        hari_ini = datetime.now().strftime("%Y-%m-%d")
        bulan_ini = datetime.now().strftime("%Y-%m")

        per_nama = {}
        for row in catatan:
            data = per_nama.setdefault(row["nama"], {"total": 0, "terakhir": "", "bulan_ini": 0})
            data["total"] += 1
            if row["tanggal"] > data["terakhir"]:
                data["terakhir"] = row["tanggal"]
            if row["tanggal"].startswith(bulan_ini):
                data["bulan_ini"] += 1

        return {
            "total_catatan": len(catatan),
            "hadir_hari_ini": sum(1 for r in catatan if r["tanggal"] == hari_ini),
            "jumlah_orang_pernah_hadir": len(per_nama),
            "per_nama": per_nama,
            "hari_ini": hari_ini,
        }


# ======================
# KAMERA
# ======================
def buka_kamera(maks_indeks=3):
    """Mencoba membuka kamera pertama yang tersedia."""
    for indeks in range(maks_indeks):
        kamera = cv2.VideoCapture(indeks)
        if kamera.isOpened():
            if kamera.get(cv2.CAP_PROP_FRAME_WIDTH) == 0:
                kamera.release()
                continue
            return kamera, indeks
        kamera.release()
    return None, -1


# ======================
# GAMBAR DI LAYAR
# ======================
FONT = cv2.FONT_HERSHEY_SIMPLEX


def teks_di_layar(frame, teks, posisi, skala=0.6, warna=(255, 255, 255),
                  tebal=2, latar=(0, 0, 0), kebalikan_y=False):
    """Menulis teks ASCII ke frame dengan kotak latar agar mudah dibaca."""
    (lebar, tinggi), baseline = cv2.getTextSize(teks, FONT, skala, tebal)
    x, y = posisi
    if kebalikan_y:
        y = frame.shape[0] - y
        y = max(tinggi + baseline + 8, y)
    cv2.rectangle(
        frame,
        (x, y - tinggi - baseline - 6),
        (x + lebar + 10, y + baseline + 6),
        latar,
        -1,
    )
    cv2.putText(frame, teks, (x + 5, y + 1), FONT, skala, warna, tebal, cv2.LINE_AA)


def kotak_wajah(frame, lokasi, warna, label=None, skala_label=0.6):
    atas, kanan, bawah, kiri = lokasi
    cv2.rectangle(frame, (kiri, atas), (kanan, bawah), warna, 2)
    if label:
        teks_di_layar(
            frame,
            label,
            (kiri + 4, max(atas - 8, bawah - 8)),
            skala=skala_label,
            warna=warna,
            latar=(0, 0, 0),
        )


def perkecil(frame, skala=0.25):
    """Mengecilkan frame agar deteksi wajah jauh lebih cepat."""
    if skala >= 1:
        return frame
    return cv2.resize(frame, (0, 0), fx=skala, fy=skala)