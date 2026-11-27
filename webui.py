"""WebUI Sistem Absensi Wajah.

Jalankan dengan:  python webui.py --buka
Atau klik:        jalankan_webui.bat
Lalu buka:        http://127.0.0.1:5000

Fitur:
  - Dashboard modern (statistik, kehadiran hari ini, log, anggota dataset)
  - Kelola dataset (upload/drag & drop foto, ambil dari kamera, hapus)
  - Rekap absensi (filter per nama/tanggal, ekspor CSV, reset)
  - Absensi langsung lewat browser (live streaming kamera)
  - Tema gelap/terang, responsif untuk desktop dan HP
"""

import io
import os
import sys
import time
import secrets
import threading
import webbrowser
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import face_recognition
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    stream_with_context,
    url_for,
)
from PIL import Image

import wajah_dasar as wd

# ======================
# KONFIGURASI
# ======================
SKALA_FRAME = 0.35
BATAS_JENDELA = 900
MASA_KEJADIAN = 120
FILE_KUNCI = os.path.join(wd.BASE_DIR, ".webui_kunci")

app = Flask(__name__)


def buat_kunci_aplikasi():
    """Kunci flask disimpan di file agar session tidak hilang saat restart."""
    if os.path.exists(FILE_KUNCI):
        with open(FILE_KUNCI, "r") as f:
            isi = f.read().strip()
        if isi:
            return isi
    kunci = secrets.token_hex(32)
    with open(FILE_KUNCI, "w") as f:
        f.write(kunci)
    return kunci


app.secret_key = buat_kunci_aplikasi()

galeri = wd.GaleriWajah()
pencatat = wd.PencatatAbsensi()
kejadian = deque(maxlen=50)
kunci_kuncian = threading.Lock()
kunci_galeri = threading.RLock()
kunci_pencatat = threading.Lock()


# ======================
# LAYANAN KAMERA (SATU THREAD UNTUK SEMUA PEMAKAI)
# ======================
class LayananKamera:
    """Membaca frame kamera di satu thread, lalu dipakai bersama banyak permintaan."""

    def __init__(self):
        self._kunci = threading.RLock()
        self._kondisi = threading.Condition(self._kunci)
        self._kamera = None
        self._indeks = -1
        self._thread = None
        self._henti = False
        self._pembaca = 0
        self._frame = None
        self._seq = 0
        self._galat = ""

    # ---------- status ----------
    @property
    def indeks(self):
        with self._kunci:
            return self._indeks

    @property
    def galat(self):
        with self._kunci:
            return self._galat

    def aktif(self):
        with self._kunci:
            return self._kamera is not None

    def pembaca(self):
        with self._kunci:
            return self._pembaca

    # ---------- hidup/mati ----------
    def _buka(self):
        if self._kamera is not None:
            return True
        kamera, indeks = wd.buka_kamera()
        if kamera is None:
            self._galat = "Tidak ada kamera yang bisa dibuka."
            return False
        self._kamera = kamera
        self._indeks = indeks
        self._galat = ""
        self._henti = False
        return True

    def _tutup(self):
        if self._kamera is not None:
            try:
                self._kamera.release()
            except Exception:
                pass
        self._kamera = None
        self._indeks = -1
        self._frame = None

    def ambil(self):
        """Menaikkan jumlah pembaca dan menyalakan thread kamera."""
        with self._kunci:
            if not self._buka():
                return False
            self._pembaca += 1
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
            return True

    def lepas(self):
        """Menurunkan jumlah pembaca, kamera dimatikan bila tidak ada pembaca."""
        with self._kunci:
            self._pembaca = max(0, self._pembaca - 1)
            if self._pembaca == 0 and self._kamera is not None:
                self._henti = True
                self._kondisi.notify_all()

    def restart(self):
        """Memulai ulang kamera, berguna bila kamera dipakai program lain."""
        with self._kunci:
            self._tutup()
            self._henti = False
        return self.ambil()

    # ---------- thread ----------
    def _loop(self):
        while True:
            with self._kunci:
                if self._henti or self._kamera is None:
                    self._tutup()
                    self._henti = False
                    self._kondisi.notify_all()
                    return
                kamera = self._kamera

            berhasil, frame = kamera.read()
            if not berhasil or frame is None:
                time.sleep(0.02)
                continue

            with self._kunci:
                self._frame = frame
                self._seq += 1
                self._kondisi.notify_all()

    # ---------- pembacaan frame ----------
    def frame_terbaru(self, seq_min, batas_waktu=0.6):
        """Menunggu frame baru dengan nomor urut > seq_min."""
        akhir = time.time() + batas_waktu
        with self._kunci:
            while self._seq <= seq_min and time.time() < akhir:
                if self._kamera is None:
                    return None, self._seq
                self._kondisi.wait(0.05)
            if self._frame is None:
                return None, self._seq
            return self._frame.copy(), self._seq

    def snapshot(self):
        """Mengambil satu salinan frame terakhir (atau membangkitkan bila perlu)."""
        with self._kunci:
            if self._kamera is not None and self._frame is not None:
                return self._frame.copy()
        if not self.ambil():
            return None
        try:
            with self._kunci:
                if self._frame is None:
                    time.sleep(0.3)
            with self._kunci:
                return self._frame.copy() if self._frame is not None else None
        finally:
            self.lepas()


kamera = LayananKamera()

app.jinja_env.filters["basename"] = os.path.basename


@app.context_processor
def konteks_global():
    """Nilai yang selalu tersedia di semua template."""
    return {
        "kamera_aktif": kamera.aktif(),
        "jumlah_encoding_global": galeri.jumlah_arah,
    }


# ======================
# PROSES FRAME KAMERA
# ======================
def pastikan_siap():
    """Memastikan galeri wajah & pencatat absensi dimuat sekali saat startup/awal."""
    if not galeri.sudah_dimuat():
        with kunci_galeri:
            if not galeri.sudah_dimuat():
                galeri.muat(cetak_laporan=False)
    with kunci_pencatat:
        if not pencatat._sudah and os.path.exists(pencatat.path):
            pencatat.muat_yang_sudah()


def deteksi_frame_cepat(frame, tandai_absen=True, maks_lebar=480):
    """Mendeteksi wajah pada frame yang sudah di-downscale dengan cepat dan non-blocking.

    Mengembalikan daftar dict wajah dengan koordinat ternormalisasi [0..1] dan piksel.
    """
    if frame is None or frame.size == 0:
        return []

    pastikan_siap()
    tinggi_asli, lebar_asli = frame.shape[:2]
    if lebar_asli > maks_lebar:
        skala = maks_lebar / float(lebar_asli)
        kecil = cv2.resize(
            frame,
            (maks_lebar, max(1, int(round(tinggi_asli * skala)))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        kecil = frame

    tinggi_k, lebar_k = kecil.shape[:2]
    rgb = wd.bgr_ke_rgb(kecil)

    daftar_lokasi = wd.cari_wajah(rgb, upsample=1)
    daftar_encoding = encoding_semua(rgb, daftar_lokasi)

    hasil = []
    for lokasi, encoding in zip(daftar_lokasi, daftar_encoding):
        atas, kanan, bawah, kiri = lokasi
        nama, jarak = (None, None)
        if encoding is not None:
            with kunci_galeri:
                if galeri.sudah_dimuat():
                    nama, jarak = galeri.cari(encoding)

        dikenal = bool(nama)
        baru = False
        waktu_catat = None
        if dikenal:
            with kunci_pencatat:
                if tandai_absen:
                    catatan = pencatat.catat(nama)
                    if catatan and catatan["baru"]:
                        baru = True
                        waktu_catat = catatan["waktu"]
                        catat_kejadian(
                            f"ABSEN: {catatan['nama']} tercatat {catatan['waktu']}"
                        )

        keyakinan = None
        if jarak is not None:
            keyakinan = max(0, min(100, int(round((1.0 - min(jarak, 1.0)) * 100))))

        nx = max(0.0, min(1.0, kiri / float(lebar_k)))
        ny = max(0.0, min(1.0, atas / float(tinggi_k)))
        nw = max(0.0, min(1.0 - nx, (kanan - kiri) / float(lebar_k)))
        nh = max(0.0, min(1.0 - ny, (bawah - atas) / float(tinggi_k)))

        hasil.append({
            "nama": nama.upper() if dikenal else "TIDAK DIKENAL",
            "dikenal": dikenal,
            "jarak": round(jarak, 4) if jarak is not None else None,
            "keyakinan": keyakinan,
            "baru": baru,
            "waktu": waktu_catat,
            "nx": round(nx, 4),
            "ny": round(ny, 4),
            "nw": round(nw, 4),
            "nh": round(nh, 4),
            "lokasi_norm": (ny, nx + nw, ny + nh, nx),
        })

    return hasil


def gambar_anotasi(frame, daftar_wajah, batas_nama=True):
    """Menggambar bounding box hasil deteksi terakhir ke frame OpenCV."""
    if frame is None or not daftar_wajah:
        return frame
    tinggi, lebar = frame.shape[:2]
    terbaru = None
    for item in daftar_wajah:
        ny1, nx2, ny2, nx1 = item["lokasi_norm"]
        y1 = int(max(0, min(tinggi - 1, ny1 * tinggi)))
        x2 = int(max(0, min(lebar, nx2 * lebar)))
        y2 = int(max(0, min(tinggi, ny2 * tinggi)))
        x1 = int(max(0, min(lebar - 1, nx1 * lebar)))
        if item["dikenal"]:
            warna = (0, 255, 0)
            label = item["nama"] if not batas_nama else item["nama"][:22]
            if item.get("baru"):
                terbaru = item
        else:
            warna = (0, 0, 255)
            label = "TIDAK DIKENAL"
        wd.kotak_wajah(frame, (y1, x2, y2, x1), warna, label=label, skala_label=0.6)

    if terbaru is not None:
        wd.teks_di_layar(
            frame,
            f"TERCATAT: {terbaru['nama']}  {terbaru.get('waktu') or ''}",
            (20, 40), skala=0.9, warna=(0, 255, 0), tebal=2,
        )
    return frame


def proses_absensi(frame, tandai_absen=True, batas_nama=True):
    """Mendeteksi wajah pada frame, menggambar kotak, dan mencatat kehadiran.

    Mengembalikan (frame_beranotasi, daftar_hasil).
    """
    if frame is None:
        return frame, []

    pastikan_siap()
    tinggi, lebar = frame.shape[:2]
    kecil = wd.perkecil(frame, SKALA_FRAME)
    rgb = wd.bgr_ke_rgb(kecil)

    daftar_lokasi = wd.cari_wajah_bertapa(rgb)
    daftar_encoding = encoding_semua(rgb, daftar_lokasi)

    faktor = 1.0 / SKALA_FRAME if SKALA_FRAME < 1 else 1.0
    hasil = []
    terbaru = None

    for lokasi, encoding in zip(daftar_lokasi, daftar_encoding):
        nama, jarak = (None, None)
        if encoding is not None:
            with kunci_galeri:
                if galeri.sudah_dimuat():
                    nama, jarak = galeri.cari(encoding)

        if nama:
            hasil.append({
                "nama": nama.upper(),
                "dikenal": True,
                "jarak": jarak,
                "baru": False,
            })
            if tandai_absen:
                with kunci_pencatat:
                    catatan = pencatat.catat(nama)
                    if catatan and catatan["baru"]:
                        hasil[-1]["baru"] = True
                        terbaru = catatan
                        catat_kejadian(
                            f"ABSEN: {catatan['nama']} tercatat {catatan['waktu']}"
                        )
        else:
            hasil.append({
                "nama": "TIDAK DIKENAL",
                "dikenal": False,
                "jarak": jarak,
                "baru": False,
            })

    # Gambar anotasi pada frame resolusi penuh
    for lokasi, item in zip(daftar_lokasi, hasil):
        atas, kanan, bawah, kiri = lokasi
        y1 = int(max(0, min(tinggi - 1, atas * faktor)))
        x2 = int(max(0, min(lebar, kanan * faktor)))
        y2 = int(max(0, min(tinggi, bawah * faktor)))
        x1 = int(max(0, min(lebar - 1, kiri * faktor)))
        if item["dikenal"]:
            warna = (0, 255, 0)
            label = item["nama"] if not batas_nama else item["nama"][:22]
        else:
            warna = (0, 0, 255)
            label = "TIDAK DIKENAL"
        wd.kotak_wajah(frame, (y1, x2, y2, x1), warna, label=label, skala_label=0.6)

    # Kabar singkat ketika ada orang yang baru tercatat hari ini
    if terbaru is not None:
        wd.teks_di_layar(
            frame,
            f"TERCATAT: {terbaru['nama']}  {terbaru['waktu']}",
            (20, 40), skala=0.9, warna=(0, 255, 0), tebal=2,
        )

    return frame, [h for h in hasil if h["dikenal"]]


def encoding_semua(rgb, daftar_lokasi):
    """Encoding wajah untuk semua lokasi sekaligus (jauh lebih cepat)."""
    if not daftar_lokasi:
        return []
    try:
        return face_recognition.face_encodings(rgb, daftar_lokasi, model="hog")
    except Exception as e:
        print(f"Peringatan: Gagal membuat encoding: {e}")
        return []


def catat_kejadian(pesan):
    with kunci_kuncian:
        kejadian.appendleft({
            "waktu": datetime.now().strftime("%H:%M:%S"),
            "pesan": pesan,
        })


# ======================
# FILTER & UTILITAS
# ======================
def kehadiran_hari_ini():
    """Mengembalikan (tanggal_hari_ini, daftar kehadiran hari ini)."""
    tanggal = datetime.now().strftime("%Y-%m-%d")
    with kunci_pencatat:
        semua = pencatat.baca_semua()
    baris = [r for r in semua if r["tanggal"] == tanggal]
    baris.sort(key=lambda r: r["waktu"], reverse=True)
    return tanggal, baris


def saring_catatan():
    """Menerapkan filter dari query string dan mengembalikan (baris, stat)."""
    with kunci_pencatat:
        semua = pencatat.baca_semua()
    nama = (request.args.get("nama") or "").strip().upper()
    tanggal = (request.args.get("tanggal") or "").strip()
    mulai = (request.args.get("mulai") or "").strip()
    selesai = (request.args.get("selesai") or "").strip()

    baris = []
    for row in semua:
        if nama and nama not in row["nama"].upper():
            continue
        if tanggal and row["tanggal"] != tanggal:
            continue
        if mulai and row["tanggal"] < mulai:
            continue
        if selesai and row["tanggal"] > selesai:
            continue
        baris.append(row)

    baris.sort(key=lambda r: (r["tanggal"], r["waktu"]), reverse=True)

    per_nama = {}
    for row in baris:
        per_nama[row["nama"]] = per_nama.get(row["nama"], 0) + 1

    hari_ini = datetime.now().strftime("%Y-%m-%d")
    stat = {
        "nama": nama,
        "tanggal": tanggal,
        "mulai": mulai,
        "selesai": selesai,
        "jumlah_baris": len(baris),
        "jumlah_nama": len(per_nama),
        "per_nama": sorted(per_nama.items(), key=lambda x: (-x[1], x[0])),
        "ada_filter": bool(nama or tanggal or mulai or selesai),
        "total_semua": len(semua),
        "hadir_hari_ini": sum(1 for r in baris if r["tanggal"] == hari_ini),
        "tanggal_ini": hari_ini,
        "bulan_ini": hari_ini[:7],
        "maks_per_nama": max(per_nama.values(), default=1),
    }
    return baris, stat


def path_foto_aman(nama, nama_file):
    """Menyusun path foto di dalam folder dataset, menolak path di luar folder."""
    nama = wd.bersihkan_nama(nama)
    nama_file = os.path.basename(nama_file or "")
    if not nama or not nama_file:
        abort(404)
    lokasi = os.path.abspath(os.path.join(wd.PATH_DATASET, nama, nama_file))
    akar = os.path.abspath(wd.PATH_DATASET)
    if not lokasi.startswith(akar + os.sep):
        abort(404)
    return lokasi


def muat_galeri(paksa=False, cetak=False):
    with kunci_galeri:
        return galeri.muat(paksa=paksa, cetak_laporan=cetak)


# ======================
# HALAMAN
# ======================
@app.get("/")
def beranda():
    with kunci_pencatat:
        stat = pencatat.statistik()
    orang = wd.ringkasan_dataset()
    total_foto = sum(o["jumlah_foto"] for o in orang)

    tanggal_ini, hadir_hari_ini = kehadiran_hari_ini()
    nama_hadir_hari_ini = {r["nama"].upper() for r in hadir_hari_ini}
    nama_terdaftar = {o["nama"].upper() for o in orang}
    hadir_terdaftar = len(nama_hadir_hari_ini & nama_terdaftar)
    persen_hadir = round(hadir_terdaftar / len(nama_terdaftar) * 100) if nama_terdaftar else 0

    dengan_catat = []
    for o in orang:
        data = stat["per_nama"].get(o["nama"].upper())
        dengan_catat.append({
            **o,
            "total_hadir": data["total"] if data else 0,
            "hadir_bulan_ini": data["bulan_ini"] if data else 0,
            "terakhir_hadir": data["terakhir"] if data else "-",
        })

    return render_template(
        "dashboard.html",
        stat=stat,
        orang=dengan_catat,
        total_foto=total_foto,
        kamera_aktif=kamera.aktif(),
        kamera_galat=kamera.galat,
        kejadian=list(kejadian)[:8],
        waktu=datetime.now(),
        tanggal_ini=tanggal_ini,
        hadir_hari_ini=hadir_hari_ini,
        nama_hadir_hari_ini=nama_hadir_hari_ini,
        hadir_terdaftar=hadir_terdaftar,
        persen_hadir=persen_hadir,
    )


@app.get("/dataset")
def halaman_dataset():
    return render_template(
        "dataset.html",
        orang=wd.ringkasan_dataset(),
        daftar_nama=[o["nama"] for o in wd.ringkasan_dataset()],
        jumlah_encoding=galeri.jumlah_arah,
        dimuat=galeri.sudah_dimuat(),
    )


@app.post("/dataset/tambah")
def dataset_tambah():
    nama = wd.bersihkan_nama(request.form.get("nama", ""))
    if not wd.nama_valid(nama):
        flash("Nama tidak valid. Gunakan huruf/angka saja, tanpa karakter khusus.", "error")
        return redirect(url_for("halaman_dataset"))

    folder = wd.folder_orang(nama)

    baru = 0
    ditolak = 0
    alasan = []

    for berkas in request.files.getlist("foto"):
        if not berkas or not berkas.filename:
            continue

        data = berkas.read()
        if not data:
            ditolak += 1
            continue

        try:
            with Image.open(io.BytesIO(data)) as pil_img:
                img = np.ascontiguousarray(np.array(pil_img.convert("RGB"), dtype=np.uint8))
        except Exception:
            ditolak += 1
            alasan.append(f"{berkas.filename} bukan gambar yang bisa dibaca")
            continue

        if wd.encoding_wajah(img) is None:
            ditolak += 1
            alasan.append(f"{berkas.filename} wajahnya tidak terdeteksi")
            continue

        ext = os.path.splitext(berkas.filename)[1].lower()
        if ext not in wd.EKSTENSI_GAMBAR:
            ext = ".jpg"
        nama_file = f"{datetime.now():%Y%m%d_%H%M%S_%f}{ext}"
        os.makedirs(folder, exist_ok=True)
        if wd.simpan_berkas(os.path.join(folder, nama_file), data):
            baru += 1
        else:
            ditolak += 1
            alasan.append(f"{berkas.filename} gagal disimpan")

    # Jangan meninggalkan folder kosong bila tidak ada satu pun foto valid
    if baru == 0 and os.path.isdir(folder) and not os.listdir(folder):
        os.rmdir(folder)

    if baru:
        muat_galeri(paksa=True)
        pesan = f"{nama}: {baru} foto disimpan ke dataset/{nama}."
        if ditolak:
            pesan += f" {ditolak} foto ditolak ({'; '.join(alasan[:3])})."
        flash(pesan, "success")
    else:
        flash(
            f"Tidak ada foto tersimpan untuk {nama}. "
            f"{ditolak} file ditolak karena tidak terbaca atau wajahnya tidak terdeteksi.",
            "error",
        )
    return redirect(url_for("halaman_dataset"))


@app.post("/dataset/orang/hapus")
def dataset_hapus_orang():
    nama = wd.bersihkan_nama(request.form.get("nama", ""))
    if not nama:
        flash("Nama tidak ditemukan.", "error")
        return redirect(url_for("halaman_dataset"))
    if wd.hapus_folder_orang(nama):
        muat_galeri(paksa=True)
        flash(f"Data {nama} beserta seluruh fotonya dihapus dari dataset.", "success")
    else:
        flash(f"Folder {nama} tidak ditemukan.", "error")
    return redirect(url_for("halaman_dataset"))


@app.post("/dataset/foto/hapus")
def dataset_hapus_foto():
    nama = request.form.get("nama", "")
    nama_file = request.form.get("file", "")
    lokasi = path_foto_aman(nama, nama_file)
    if wd.hapus_berkas(lokasi):
        muat_galeri(paksa=True)
        flash(f"Foto {nama_file} ({wd.bersihkan_nama(nama)}) dihapus.", "success")
    else:
        flash("Foto tidak ditemukan.", "error")
    return redirect(url_for("halaman_dataset"))


@app.post("/dataset/muat-ulang")
def dataset_muat_ulang():
    muat_galeri(paksa=True, cetak=True)
    flash(f"Encoding wajah dimuat ulang: {galeri.jumlah_arah} sample.", "success")
    return redirect(url_for("halaman_dataset"))


@app.get("/foto/<nama>/<nama_file>")
def serve_foto(nama, nama_file):
    lokasi = path_foto_aman(nama, nama_file)
    if not os.path.isfile(lokasi):
        abort(404)
    return send_file(lokasi, max_age=0)


@app.get("/absensi")
def halaman_absensi():
    baris, stat = saring_catatan()
    orang = [o["nama"] for o in wd.ringkasan_dataset()]
    nama_hadir = {nama.upper() for nama, _ in stat["per_nama"]}
    belum_hadir = [n for n in orang if n.upper() not in nama_hadir]
    return render_template(
        "absensi.html",
        baris=baris,
        stat=stat,
        orang=orang,
        belum_hadir=belum_hadir,
    )


@app.get("/absensi/export")
def absensi_export():
    baris, _ = saring_catatan()
    isi = ["Nama,Tanggal,Waktu"]
    isi += [f"{r['nama']},{r['tanggal']},{r['waktu']}" for r in baris]
    buffer = io.BytesIO(("\n".join(isi) + "\n").encode("utf-8-sig"))
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        buffer,
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=f"absensi_{stempel}.csv",
    )


@app.post("/absensi/reset")
def absensi_reset():
    with kunci_pencatat:
        if os.path.exists(pencatat.path):
            cadangan = pencatat.path + ".bak"
            os.replace(pencatat.path, cadangan)
            with open(pencatat.path, "w", newline="", encoding="utf-8") as f:
                f.write(",".join(pencatat.HEADER) + "\n")
            pencatat.muat_yang_sudah()
            flash(f"Seluruh catatan absensi dikosongkan. Cadangan: {os.path.basename(cadangan)}", "success")
        else:
            flash("Belum ada file absensi untuk dikosongkan.", "error")
    return redirect(url_for("halaman_absensi"))


# ======================
# KAMERA & STREAMING
# ======================
@app.get("/kamera")
def halaman_kamera():
    _, hari_ini = kehadiran_hari_ini()
    return render_template(
        "kamera.html",
        kamera_aktif=kamera.aktif(),
        jumlah_encoding=galeri.jumlah_arah,
        daftar_nama=[o["nama"] for o in wd.ringkasan_dataset()],
        kejadian=list(kejadian)[:10],
        hari_ini=hari_ini,
    )


@app.get("/api/stream.mjpg")
def api_stream():
    """Fallback MJPEG stream dengan pemisahan loop video & worker deteksi wajah."""
    if not kamera.ambil():
        return Response(kamera.galat or "Kamera tidak tersedia", status=503,
                        mimetype="text/plain")

    pastikan_siap()

    def hasil():
        seq = 0
        kunci_lokal = threading.Lock()
        wajah_terakhir = []
        sedang_proses = False
        terakhir_deteksi = 0.0

        def jalankan_deteksi(salinan_frame):
            nonlocal wajah_terakhir, sedang_proses
            try:
                hasil_wajah = deteksi_frame_cepat(salinan_frame, tandai_absen=True, maks_lebar=420)
                with kunci_lokal:
                    wajah_terakhir = hasil_wajah
            finally:
                with kunci_lokal:
                    sedang_proses = False

        try:
            while True:
                frame, seq_baru = kamera.frame_terbaru(seq)
                if frame is None:
                    if not kamera.aktif():
                        break
                    continue
                seq = seq_baru

                sekarang = time.monotonic()
                with kunci_lokal:
                    perlu_deteksi = (not sedang_proses) and ((sekarang - terakhir_deteksi) >= 0.30)
                    if perlu_deteksi:
                        sedang_proses = True
                        terakhir_deteksi = sekarang
                    anotasi = list(wajah_terakhir)

                if perlu_deteksi:
                    threading.Thread(
                        target=jalankan_deteksi,
                        args=(frame.copy(),),
                        daemon=True,
                    ).start()

                gambar_anotasi(frame, anotasi)
                ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"X-Seq: " + str(seq).encode() + b"\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )
        finally:
            kamera.lepas()

    return Response(
        stream_with_context(hasil()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/deteksi")
def api_deteksi():
    """Menerima frame JPEG ringan (downscaled) dari browser <video> dan mengembalikan hasil deteksi."""
    berkas = request.files.get("frame")
    if not berkas:
        return jsonify({"ok": False, "pesan": "Frame tidak ditemukan."}), 400

    data = berkas.read()
    if not data:
        return jsonify({"ok": False, "pesan": "Frame kosong."}), 400

    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        return jsonify({"ok": False, "pesan": "Frame tidak dapat didekode."}), 400

    tandai = request.form.get("tandai", "1") != "0"
    mulai = time.perf_counter()
    wajah_mentah = deteksi_frame_cepat(frame, tandai_absen=tandai, maks_lebar=480)
    durasi_ms = int(round((time.perf_counter() - mulai) * 1000))

    wajah = [
        {
            "nama": w["nama"],
            "dikenal": w["dikenal"],
            "jarak": w["jarak"],
            "keyakinan": w["keyakinan"],
            "baru": w["baru"],
            "waktu": w["waktu"],
            "nx": w["nx"],
            "ny": w["ny"],
            "nw": w["nw"],
            "nh": w["nh"],
        }
        for w in wajah_mentah
    ]

    ada_baru = any(w["baru"] for w in wajah)
    _, hari_ini = kehadiran_hari_ini()
    with kunci_pencatat:
        total_catatan = pencatat.statistik()["total_catatan"]
    with kunci_kuncian:
        isi_kejadian = list(kejadian)[:10]

    return jsonify({
        "ok": True,
        "wajah": wajah,
        "ada_baru": ada_baru,
        "waktu_deteksi_ms": durasi_ms,
        "jumlah_encoding": galeri.jumlah_arah,
        "jumlah_orang": len(wd.daftar_nama_orang()),
        "hadir_hari_ini": len(hari_ini),
        "total_catatan": total_catatan,
        "hari_ini": hari_ini,
        "kejadian": isi_kejadian,
    })


@app.get("/api/pratinjau.mjpg")
def api_pratinjau():
    """Stream kamera tanpa proses deteksi, untuk halaman ambil foto dataset."""
    if not kamera.ambil():
        return Response(kamera.galat or "Kamera tidak tersedia", status=503,
                        mimetype="text/plain")

    def hasil():
        seq = 0
        try:
            while True:
                frame, seq_baru = kamera.frame_terbaru(seq)
                if frame is None:
                    if not kamera.aktif():
                        break
                    continue
                seq = seq_baru
                ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ok:
                    continue
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )
        finally:
            kamera.lepas()

    return Response(
        stream_with_context(hasil()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/tangkap")
def api_tangkap():
    """Menyimpan satu frame kamera (dari upload browser <video> atau kamera server) ke dataset/<nama>/."""
    nama = wd.bersihkan_nama(request.form.get("nama", ""))
    if not wd.nama_valid(nama):
        return jsonify({"ok": False, "pesan": "Nama tidak valid."}), 400

    berkas = request.files.get("foto")
    frame = None
    if berkas:
        data = berkas.read()
        if data:
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)

    if frame is None:
        frame = kamera.snapshot()

    if frame is None:
        return jsonify({"ok": False, "pesan": "Kamera tidak bisa diakses."}), 503

    rgb = wd.bgr_ke_rgb(frame)
    if wd.encoding_wajah(rgb) is None:
        return jsonify({
            "ok": False,
            "pesan": "Wajah tidak terdeteksi. Pastikan wajah terlihat jelas di tengah layar.",
        }), 200

    folder = wd.folder_orang(nama)
    os.makedirs(folder, exist_ok=True)
    nama_file = f"cam_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
    if not wd.simpan_foto(os.path.join(folder, nama_file), frame):
        return jsonify({"ok": False, "pesan": "Gagal menyimpan foto."}), 500

    muat_galeri(paksa=True)
    return jsonify({
        "ok": True,
        "pesan": f"Foto {nama_file} disimpan.",
        "file": nama_file,
        "jumlah": len(wd.foto_orang(nama)),
    })


@app.post("/api/kamera/restart")
def api_kamera_restart():
    if kamera.restart():
        kamera.lepas()
        return jsonify({"ok": True, "pesan": f"Kamera {kamera.indeks} dinyalakan ulang."})
    return jsonify({"ok": False, "pesan": kamera.galat or "Gagal menyalakan kamera."})


@app.get("/api/status")
def api_status():
    with kunci_pencatat:
        stat = pencatat.statistik()
    _, hari_ini = kehadiran_hari_ini()
    with kunci_kuncian:
        isi_kejadian = list(kejadian)[:10]
    return jsonify({
        "jumlah_orang": len(wd.daftar_nama_orang()),
        "jumlah_foto": sum(len(wd.foto_orang(n) ) for n in wd.daftar_nama_orang()),
        "jumlah_encoding": galeri.jumlah_arah,
        "hadir_hari_ini": stat["hadir_hari_ini"],
        "total_catatan": stat["total_catatan"],
        "kamera_aktif": kamera.aktif(),
        "kamera_indeks": kamera.indeks,
        "kamera_galat": kamera.galat,
        "kejadian": isi_kejadian,
        "hari_ini": hari_ini,
        "jumlah_hadir_hari_ini": len(hari_ini),
        "waktu_server": datetime.now().strftime("%H:%M:%S"),
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  SISTEM ABSENSI WAJAH - WEB UI")
    print("=" * 60)
    muat_galeri(paksa=True, cetak=True)
    pencatat.muat_yang_sudah()
    print(f"\nOrang terdaftar: {len(galeri.nama_unik())} | encoding: {galeri.jumlah_arah}")
    print("Buka browser di: http://127.0.0.1:5000")
    print("Tekan Ctrl+C untuk menghentikan server.\n")
    if "--buka" in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)