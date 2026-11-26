(() => {
  const dialog = document.getElementById('file-preview-dialog');
  if (!dialog) return;

  const $ = id => document.getElementById(id);
  const stage   = $('preview-stage');
  const titleEl = $('preview-title');
  const dlTop   = $('preview-download');
  const infoBtn = $('preview-info');
  const manage  = $('pv-manage');

  const IMG   = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
  const VID   = ['mp4', 'webm'];
  const FRAME = ['txt', 'csv'];    

  const PDFJS_URL    = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
  const PDFJS_WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  let bypass = false;      
  let lastSource = null;    
  let currentItem = null;
  let session = 0;         
  let pdfCleanup = null;
  let pdfjsPromise = null;

  const itemOf = el => el.closest('.file-row, .file-grid-card');
  const extOf = name => {
    const i = name.lastIndexOf('.');
    return i < 0 ? '' : name.slice(i + 1).toLowerCase();
  };

    function setPanel(show) {
    dialog.classList.toggle('panel-hidden', !show);
    if (infoBtn) infoBtn.setAttribute('aria-pressed', String(show));
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
  }

  function fillDetails(item, name, downloadUrl) {
    const d = item.dataset;
    setText('pv-name', name);
    setText('pv-type', d.fileType || '—');
    setText('pv-size', d.fileSizeLabel || '—');
    setText('pv-created', d.fileCreated || '—');
    setText('pv-modified', d.fileModifiedLabel || '—');
    setText('pv-location', d.fileLocation || '—');
    const dl = $('pv-download');
    if (dl) dl.href = downloadUrl;
  }

  function notice(text, href) {
    const box = document.createElement('div');
    box.className = 'preview-fallback';
    const p = document.createElement('p');
    p.textContent = text;
    box.appendChild(p);
    if (href) {
      const a = document.createElement('a');
      a.href = href;
      a.textContent = 'Download file';
      box.appendChild(a);
    }
    return box;
  }

  function resetStage() {
    session++;
    if (pdfCleanup) { pdfCleanup(); pdfCleanup = null; }
    stage.classList.remove('is-pdf');
    stage.replaceChildren();
  }

  function loadPdfJs() {
    if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
    if (!pdfjsPromise) {
      pdfjsPromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = PDFJS_URL;
        s.onload = () => {
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
          resolve(window.pdfjsLib);
        };
        s.onerror = () => { pdfjsPromise = null; reject(new Error('pdf.js gagal dimuat')); };
        document.head.appendChild(s);
      });
    }
    return pdfjsPromise;
  }

  async function showPdf(url, downloadUrl, name, my) {
    stage.classList.add('is-pdf');
    stage.replaceChildren(notice('Memuat PDF…'));

    let lib;
    try {
      lib = await loadPdfJs();
    } catch (e) {
      
      if (my !== session) return;
      stage.classList.remove('is-pdf');
      const f = document.createElement('iframe');
      f.title = name;
      f.src = url + '#toolbar=0&navpanes=0';
      stage.replaceChildren(f);
      return;
    }

    let doc;
    try {

      doc = await lib.getDocument({
        url, withCredentials: true, disableRange: true, disableStream: true
      }).promise;
    } catch (err) {
      if (my !== session) return;
      stage.classList.remove('is-pdf');
      stage.replaceChildren(notice('PDF tidak dapat dimuat (' + (err && err.message || err) + ').', downloadUrl));
      return;
    }
    if (my !== session) { doc.destroy(); return; }
    buildPdfViewer(doc, my);
  }

  async function buildPdfViewer(doc, my) {
    const first = await doc.getPage(1);
    if (my !== session) { doc.destroy(); return; }
    const base = first.getViewport({ scale: 1 });

    const scroll  = document.createElement('div');
    scroll.className = 'pv-pdf-scroll';
    const pagesEl = document.createElement('div');
    pagesEl.className = 'pv-pages';
    const bar = document.createElement('div');
    bar.className = 'pv-toolbar';
    bar.innerHTML =
      '<button type="button" data-a="prev" aria-label="Halaman sebelumnya">‹</button>' +
      '<span class="pv-pageinfo"><span data-r="cur">1</span> / ' + doc.numPages + '</span>' +
      '<button type="button" data-a="next" aria-label="Halaman berikutnya">›</button>' +
      '<span class="pv-sep"></span>' +
      '<button type="button" data-a="out" aria-label="Perkecil">−</button>' +
      '<span class="pv-zoom" data-r="zoom">100%</span>' +
      '<button type="button" data-a="in" aria-label="Perbesar">+</button>' +
      '<button type="button" data-a="fit" aria-label="Sesuaikan lebar" title="Sesuaikan lebar">⤢</button>';

    const wraps = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const w = document.createElement('div');
      w.className = 'pv-page';
      w.dataset.page = i;
      pagesEl.appendChild(w);
      wraps.push(w);
    }
    scroll.appendChild(pagesEl);
    stage.replaceChildren(scroll, bar);

    const curEl  = bar.querySelector('[data-r="cur"]');
    const zoomEl = bar.querySelector('[data-r="zoom"]');
    const fitScale = () => Math.min(Math.max((scroll.clientWidth - 48) / base.width, 0.4), 1.4);
    let scale = fitScale();

    async function renderPage(wrap) {
      if (my !== session) return;
      const key = String(scale);
      if (wrap.dataset.rendered === key) return;
      wrap.dataset.rendered = key;
      try {
        if (wrap._task) wrap._task.cancel();
        const page = await doc.getPage(+wrap.dataset.page);
        if (my !== session || wrap.dataset.rendered !== key) return;
        const vp  = page.getViewport({ scale });
        const dpr = window.devicePixelRatio || 1;
        const canvas = document.createElement('canvas');   // kanvas baru tiap render
        canvas.width  = Math.floor(vp.width * dpr);
        canvas.height = Math.floor(vp.height * dpr);
        wrap.style.width  = vp.width + 'px';
        wrap.style.height = vp.height + 'px';
        wrap._task = page.render({
          canvasContext: canvas.getContext('2d'),
          viewport: vp,
          transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null
        });
        await wrap._task.promise;
        if (my === session && wrap.dataset.rendered === key) wrap.replaceChildren(canvas);
      } catch (e) {
        if (!e || e.name !== 'RenderingCancelledException') console.error(e);
      }
    }

    const io = new IntersectionObserver(entries => {
      entries.forEach(en => { if (en.isIntersecting) renderPage(en.target); });
    }, { root: scroll, rootMargin: '800px 0px' });

    function applyScale() {
      wraps.forEach(w => {
        w.style.width  = base.width * scale + 'px';
        w.style.height = base.height * scale + 'px';
        w.dataset.rendered = '';
      });
      io.disconnect();
      wraps.forEach(w => io.observe(w));
      zoomEl.textContent = Math.round(scale * 100) + '%';
    }

    function setScale(s) {
      const ratio = scroll.scrollTop / Math.max(scroll.scrollHeight, 1);
      scale = Math.min(Math.max(s, 0.3), 4);
      applyScale();
      scroll.scrollTop = ratio * scroll.scrollHeight;
    }

    function currentPage() {
      const mid = scroll.scrollTop + scroll.clientHeight / 3;
      let cur = 1;
      for (const w of wraps) {
        if (w.offsetTop <= mid) cur = +w.dataset.page; else break;
      }
      return cur;
    }

    let ticking = false;
    scroll.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => { ticking = false; curEl.textContent = currentPage(); });
    });

    bar.addEventListener('click', e => {
      const b = e.target.closest('button[data-a]');
      if (!b) return;
      const a = b.dataset.a;
      if (a === 'prev' || a === 'next') {
        const t = Math.min(Math.max(currentPage() + (a === 'next' ? 1 : -1), 1), doc.numPages);
        scroll.scrollTo({ top: wraps[t - 1].offsetTop - 16, behavior: 'smooth' });
      } else if (a === 'in')  setScale(scale * 1.25);
      else if (a === 'out')   setScale(scale / 1.25);
      else if (a === 'fit')   setScale(fitScale());
    });

    pdfCleanup = () => {
      io.disconnect();
      wraps.forEach(w => { if (w._task) w._task.cancel(); });
      doc.destroy();
    };

    applyScale();
  }

  // ---------- buka preview ----------
  function openPreview(item) {
    const opener = item.querySelector('.file-open-button');
    const name = opener ? opener.dataset.openFile : '';
    const downloadUrl = item.dataset.downloadUrl;
    const previewUrl = downloadUrl.replace(/\/download\/?$/, '/preview/');
    const ext = extOf(name);

    resetStage();
    currentItem = item;
    titleEl.textContent = name;
    dlTop.href = downloadUrl;
    fillDetails(item, name, downloadUrl);
    setPanel(window.innerWidth >= 900);
    if (!dialog.open) dialog.showModal();

    if (ext === 'pdf') { showPdf(previewUrl, downloadUrl, name, session); return; }

    let node;
    if (IMG.includes(ext)) {
      node = document.createElement('img');
      node.alt = name;
      node.src = previewUrl;
    } else if (VID.includes(ext)) {
      node = document.createElement('video');
      node.controls = true;
      node.autoplay = true;
      node.src = previewUrl;
    } else if (FRAME.includes(ext)) {
      node = document.createElement('iframe');
      node.title = name;
      node.src = previewUrl;
    } else {
      node = notice(
        ext ? 'Preview belum tersedia untuk file .' + ext + '.' : 'Preview belum tersedia untuk file ini.',
        downloadUrl);
    }
    stage.replaceChildren(node);
  }

  // ---------- event ----------
  // Capture phase: dijalankan sebelum handler files-ui.js
  document.addEventListener('click', e => {
    if (bypass) return;

    const trigger = e.target.closest('.context-trigger[data-context-type="file"]');
    if (trigger) { lastSource = itemOf(trigger); return; }

    const openBtn = e.target.closest('.file-open-button');
    if (openBtn) {
      const item = itemOf(openBtn);
      if (item) {
        e.preventDefault();
        e.stopImmediatePropagation();
        openPreview(item);
      }
      return;
    }

    const act = e.target.closest('#file-context-menu [data-context-action="open"]');
    if (act && lastSource) {
      e.preventDefault();
      e.stopImmediatePropagation();
      $('file-context-menu').hidden = true;
      openPreview(lastSource);
    }
  }, true);

  if (infoBtn) {
    infoBtn.addEventListener('click', () => setPanel(dialog.classList.contains('panel-hidden')));
  }

  if (manage) {
    manage.addEventListener('click', () => {
      const opener = currentItem && currentItem.querySelector('.file-open-button');
      dialog.close();
      if (opener) {
        bypass = true;
        opener.click();
      bypass = false;
      }
    });
  }

  $('preview-close').addEventListener('click', () => dialog.close());
  stage.addEventListener('click', e => { if (e.target === stage) dialog.close(); });
  dialog.addEventListener('close', resetStage);   // stop video, batalkan render, bebaskan memori
})();