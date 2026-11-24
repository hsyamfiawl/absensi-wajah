/* =========================================================
   Absensi Wajah - interaksi UI
   ========================================================= */
(function () {
  'use strict';

  const html = document.documentElement;
  const tombolTema = document.querySelectorAll('[data-tema]');
  const labelTema = document.querySelector('[data-label-tema]');
  const metaTema = document.querySelector('meta[name="theme-color"]');

  /* ---------- tema terang / gelap ---------- */
  function terapkanTema(tema, simpan) {
    html.setAttribute('data-theme', tema);
    if (simpan) {
      try { localStorage.setItem('tema-webui', tema); } catch (e) {}
      try {
        const url = new URL(window.location.href);
        if (url.searchParams.has('tema')) {
          url.searchParams.delete('tema');
          window.history.replaceState({}, '', url);
        }
      } catch (e) {}
    }
    if (labelTema) {
      labelTema.textContent = tema === 'dark' ? 'Mode terang' : 'Mode gelap';
    }
    if (metaTema) {
      metaTema.setAttribute('content', tema === 'dark' ? '#071018' : '#f3f7fb');
    }
  }

  terapkanTema(html.getAttribute('data-theme') === 'light' ? 'light' : 'dark', false);

  tombolTema.forEach(function (tombol) {
    tombol.addEventListener('click', function () {
      const baru = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      terapkanTema(baru, true);
    });
  });

  /* ---------- jam & tanggal ---------- */
  const jam = document.querySelectorAll('[data-jam]');
  const tanggal = document.querySelectorAll('[data-tanggal]');

  function perbaruiWaktu() {
    const sekarang = new Date();
    const teksJam = sekarang.toLocaleTimeString('id-ID', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    const teksTanggal = sekarang.toLocaleDateString('id-ID', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
    jam.forEach(function (el) { el.textContent = teksJam; });
    tanggal.forEach(function (el) { el.textContent = teksTanggal; });
  }

  perbaruiWaktu();
  setInterval(perbaruiWaktu, 1000);

  /* ---------- sidebar mobile ---------- */
  const sisi = document.getElementById('sisi');
  const tirai = document.getElementById('tirai');
  const tombolMenu = document.getElementById('tombol-menu');

  function tutupMenu() {
    if (!sisi) return;
    sisi.classList.remove('terbuka');
    if (tirai) tirai.classList.remove('aktif');
    if (tombolMenu) tombolMenu.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  function bukaMenu() {
    if (!sisi) return;
    sisi.classList.add('terbuka');
    if (tirai) tirai.classList.add('aktif');
    if (tombolMenu) tombolMenu.setAttribute('aria-expanded', 'true');
    if (window.innerWidth <= 1024) document.body.style.overflow = 'hidden';
  }

  if (tombolMenu) {
    tombolMenu.addEventListener('click', function () {
      if (sisi && sisi.classList.contains('terbuka')) tutupMenu();
      else bukaMenu();
    });
  }

  if (tirai) tirai.addEventListener('click', tutupMenu);

  if (sisi) {
    sisi.querySelectorAll('nav a').forEach(function (tautan) {
      tautan.addEventListener('click', tutupMenu);
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') tutupMenu();
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 1024) tutupMenu();
  });

  /* ---------- notifikasi toast ---------- */
  const areaToast = document.getElementById('toast-area');

  window.aturStatusKameraSisi = function (aktif, encoding) {
    const titik = document.getElementById('titik-kamera-sisi');
    const teks = document.getElementById('teks-kamera-sisi');
    const jumlah = document.getElementById('teks-encoding-sisi');
    if (titik) titik.className = 'titik ' + (aktif ? 'hidup' : 'mati');
    if (teks) teks.textContent = aktif ? 'Kamera aktif' : 'Kamera standby';
    if (jumlah && typeof encoding === 'number') jumlah.textContent = encoding;
  };

  function tutupToast(toast) {
    if (!toast || toast.classList.contains('keluar')) return;
    toast.classList.add('keluar');
    setTimeout(function () { toast.remove(); }, 260);
  }

  function siapkanToast(toast) {
    if (!toast || toast.dataset.siap === '1') return;
    toast.dataset.siap = '1';
    const tombol = toast.querySelector('[data-tutup-toast]');
    if (tombol) tombol.addEventListener('click', function () { tutupToast(toast); });
    setTimeout(function () { tutupToast(toast); }, 6500);
  }

  document.querySelectorAll('.toast').forEach(siapkanToast);

  window.tampilkanToast = function (pesan, kategori) {
    if (!areaToast) return;
    const jenis = kategori === 'error' ? 'error' : 'success';
    const toast = document.createElement('div');
    toast.className = 'toast ' + jenis;
    toast.setAttribute('role', 'status');

    const ikon = document.createElement('span');
    ikon.className = 'toast-ikon';
    ikon.innerHTML = '<svg class="ikon" aria-hidden="true"><use href="#i-' +
      (jenis === 'error' ? 'alert' : 'check-circle') + '"></use></svg>';

    const isi = document.createElement('div');
    isi.className = 'toast-isi';
    isi.textContent = pesan || '';

    const tutup = document.createElement('button');
    tutup.className = 'toast-tutup';
    tutup.type = 'button';
    tutup.setAttribute('aria-label', 'Tutup notifikasi');
    tutup.innerHTML = '&times;';

    toast.append(ikon, isi, tutup);
    areaToast.appendChild(toast);
    siapkanToast(toast);
  };

  /* ---------- konfirmasi form ---------- */
  document.querySelectorAll('form[data-konfirmasi]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      const pesan = form.getAttribute('data-konfirmasi') || 'Lanjutkan tindakan ini?';
      if (!window.confirm(pesan)) {
        e.preventDefault();
      }
    });
  });

  /* ---------- animasi angka statistik ---------- */
  const kurangiGerak = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!kurangiGerak) {
    document.querySelectorAll('.stat-angka').forEach(function (el) {
      const teks = (el.textContent || '').trim();
      if (!/^\d+$/.test(teks)) return;
      const target = parseInt(teks, 10);
      if (target <= 0 || target > 100000) return;
      const mulai = performance.now();
      const durasi = 650;
      function langkah(waktu) {
        const progres = Math.min(1, (waktu - mulai) / durasi);
        const halus = 1 - Math.pow(1 - progres, 3);
        el.textContent = Math.round(target * halus);
        if (progres < 1) requestAnimationFrame(langkah);
        else el.textContent = target;
      }
      el.textContent = '0';
      requestAnimationFrame(langkah);
    });
  }
})();
