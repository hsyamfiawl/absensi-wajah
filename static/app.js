/* =========================================================
   Absensi Wajah - Interaksi, Motion, Audio & Theme Engine
   ========================================================= */
(function () {
  'use strict';

  const html = document.documentElement;
  const metaColorScheme = document.querySelector('meta[name="color-scheme"]');
  const metaTema = document.querySelector('meta[name="theme-color"]');
  const tombolTema = document.querySelectorAll('[data-tema]');
  const labelTema = document.querySelector('[data-label-tema]');
  const mediaGelap = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const kurangiGerak = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- tema terang / gelap (mengikuti color-scheme & override lokal) ---------- */
  function preferensiSistem() {
    if (!mediaGelap) return 'dark';
    return mediaGelap.matches ? 'dark' : 'light';
  }

  function terapkanTampilanTema(tema, metaContent) {
    html.setAttribute('data-theme', tema);
    if (metaColorScheme && metaContent) {
      metaColorScheme.setAttribute('content', metaContent);
    }
    if (labelTema) {
      labelTema.textContent = tema === 'dark' ? 'Mode terang' : 'Mode gelap';
    }
    if (metaTema) {
      metaTema.setAttribute('content', tema === 'dark' ? '#050911' : '#f4f7fb');
    }
  }

  function sinkronkanTemaDariStorage() {
    let tersimpan = null;
    try { tersimpan = localStorage.getItem('tema-webui'); } catch (e) {}
    if (tersimpan === 'light' || tersimpan === 'dark') {
      terapkanTampilanTema(tersimpan, tersimpan);
    } else {
      terapkanTampilanTema(preferensiSistem(), 'light dark');
    }
  }

  sinkronkanTemaDariStorage();

  tombolTema.forEach(function (tombol) {
    tombol.addEventListener('click', function () {
      const sekarang = html.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
      const target = sekarang === 'dark' ? 'light' : 'dark';
      const sistem = preferensiSistem();

      if (target === sistem) {
        try { localStorage.removeItem('tema-webui'); } catch (e) {}
        terapkanTampilanTema(target, 'light dark');
      } else {
        try { localStorage.setItem('tema-webui', target); } catch (e) {}
        terapkanTampilanTema(target, target);
      }

      try {
        const url = new URL(window.location.href);
        if (url.searchParams.has('tema')) {
          url.searchParams.delete('tema');
          window.history.replaceState({}, '', url);
        }
      } catch (e) {}
    });
  });

  if (mediaGelap && mediaGelap.addEventListener) {
    mediaGelap.addEventListener('change', function () {
      let tersimpan = null;
      try { tersimpan = localStorage.getItem('tema-webui'); } catch (e) {}
      if (tersimpan !== 'light' && tersimpan !== 'dark') {
        terapkanTampilanTema(preferensiSistem(), 'light dark');
      }
    });
  }

  window.addEventListener('storage', function (e) {
    if (e.key === 'tema-webui') sinkronkanTemaDariStorage();
  });

  /* ---------- jam & tanggal real-time ---------- */
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

  /* ---------- header elevation & tombol kembali ke atas ---------- */
  const topbar = document.getElementById('topbar');
  const sentinel = document.getElementById('scroll-sentinel');
  const btnKeAtas = document.getElementById('tombol-ke-atas');

  if (sentinel && 'IntersectionObserver' in window) {
    const observerScroll = new IntersectionObserver(function (entries) {
      const tergulir = !entries[0].isIntersecting;
      if (topbar) topbar.classList.toggle('tergulir', tergulir);
      if (btnKeAtas) btnKeAtas.hidden = !tergulir;
    }, { threshold: 0 });
    observerScroll.observe(sentinel);
  }

  if (btnKeAtas) {
    btnKeAtas.addEventListener('click', function () {
      window.scrollTo({
        top: 0,
        behavior: kurangiGerak ? 'auto' : 'smooth'
      });
    });
  }

  /* ---------- scroll-reveal staggered motion ---------- */
  const elemenReveal = document.querySelectorAll('[data-reveal]');
  if (!kurangiGerak && 'IntersectionObserver' in window && elemenReveal.length) {
    const revealObs = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('tampil');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.01 });

    elemenReveal.forEach(function (el) {
      el.classList.add('siap-reveal');
      revealObs.observe(el);
    });

    window.addEventListener('beforeprint', function () {
      elemenReveal.forEach(function (el) { el.classList.add('tampil'); });
    });
  } else {
    elemenReveal.forEach(function (el) { el.classList.add('tampil'); });
  }

  /* ---------- pointer spotlight halus pada kartu ---------- */
  if (!kurangiGerak && window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    const targetSpotlight = document.querySelectorAll('.stat-kartu, .panel, .hero');
    targetSpotlight.forEach(function (kartu) {
      let framePending = false;
      kartu.addEventListener('pointermove', function (e) {
        if (framePending) return;
        framePending = true;
        requestAnimationFrame(function () {
          const rect = kartu.getBoundingClientRect();
          kartu.style.setProperty('--mx', (e.clientX - rect.left) + 'px');
          kartu.style.setProperty('--my', (e.clientY - rect.top) + 'px');
          framePending = false;
        });
      }, { passive: true });
    });
  }

  /* ---------- audio feedback sintetis (Web Audio API) ---------- */
  let audioCtx = null;
  window.bunyikanChime = function (jenis) {
    try {
      const AudioCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtor) return;
      if (!audioCtx) audioCtx = new AudioCtor();
      if (audioCtx.state === 'suspended') audioCtx.resume();

      const now = audioCtx.currentTime;
      const mainTone = function (freq, start, dur, vol) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, start);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(vol, start + 0.018);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(start);
        osc.stop(start + dur + 0.02);
      };

      if (jenis === 'sukses') {
        mainTone(784.0, now, 0.14, 0.09);        // G5
        mainTone(1046.5, now + 0.09, 0.24, 0.11); // C6
      } else if (jenis === 'galat') {
        mainTone(330, now, 0.14, 0.08);
        mainTone(261.6, now + 0.1, 0.2, 0.08);
      } else {
        mainTone(660, now, 0.08, 0.04);
      }
    } catch (e) {}
  };

  /* ---------- notifikasi toast dengan pause saat hover/focus ---------- */
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
    const anims = typeof toast.getAnimations === 'function' ? toast.getAnimations() : [];
    if (!anims.length || kurangiGerak) {
      toast.remove();
      return;
    }
    setTimeout(function () { toast.remove(); }, 280);
  }

  function siapkanToast(toast, durasi) {
    if (!toast || toast.dataset.siap === '1') return;
    toast.dataset.siap = '1';
    const tombol = toast.querySelector('[data-tutup-toast]');
    if (tombol) tombol.addEventListener('click', function () { tutupToast(toast); });

    let sisa = durasi || 5500;
    let timer = null;
    let mulai = Date.now();

    function jadwalkan() {
      clearTimeout(timer);
      mulai = Date.now();
      timer = setTimeout(function () { tutupToast(toast); }, sisa);
    }

    function jeda() {
      clearTimeout(timer);
      sisa = Math.max(1000, sisa - (Date.now() - mulai));
    }

    toast.addEventListener('pointerenter', jeda);
    toast.addEventListener('focusin', jeda);
    toast.addEventListener('pointerleave', jadwalkan);
    toast.addEventListener('focusout', jadwalkan);
    jadwalkan();
  }

  document.querySelectorAll('.toast').forEach(function (t) { siapkanToast(t, 6500); });

  window.tampilkanToast = function (pesan, kategori, opsi) {
    if (!areaToast) return;
    const jenis = kategori === 'error' ? 'error' : 'success';
    const conf = opsi || {};
    const toast = document.createElement('div');
    toast.className = 'toast ' + jenis;
    toast.setAttribute('role', 'status');

    const ikon = document.createElement('span');
    ikon.className = 'toast-ikon';
    ikon.innerHTML = '<svg class="ikon" aria-hidden="true"><use href="#i-' +
      (jenis === 'error' ? 'alert' : 'check-circle') + '"></use></svg>';

    const isi = document.createElement('div');
    isi.className = 'toast-isi';
    const judul = document.createElement('strong');
    judul.textContent = pesan || '';
    isi.appendChild(judul);
    if (conf.subteks) {
      const sub = document.createElement('p');
      sub.textContent = conf.subteks;
      isi.appendChild(sub);
    }

    const tutup = document.createElement('button');
    tutup.className = 'toast-tutup';
    tutup.type = 'button';
    tutup.setAttribute('aria-label', 'Tutup notifikasi');
    tutup.innerHTML = '&times;';

    toast.append(ikon, isi, tutup);
    areaToast.appendChild(toast);
    siapkanToast(toast, conf.durasi || 5200);
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
  if (!kurangiGerak) {
    document.querySelectorAll('.stat-angka').forEach(function (el) {
      const teks = (el.textContent || '').trim();
      if (!/^\d+$/.test(teks)) return;
      const target = parseInt(teks, 10);
      if (target <= 0 || target > 100000) return;
      const mulai = performance.now();
      const durasi = 520;
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
