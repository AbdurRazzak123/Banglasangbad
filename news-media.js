/* Bangla Sangbad — News-ID based image engine
   Sheet -> news-data.json -> News ID -> Google Drive share URL -> image.
   No Image Radar. No build-time image download required.
*/
(function () {
  'use strict';

  const DATA_URL = (location.pathname.includes('/news/') ? '../news-data.json' : 'news-data.json');
  const cache = new Map();
  let rowsPromise = null;

  function normId(v) {
    return String(v == null ? '' : v).trim().replace(/\.0+$/, '');
  }

  function driveId(url) {
    const s = String(url || '').trim();
    const patterns = [
      /drive\.google\.com\/file\/d\/([A-Za-z0-9_-]+)/i,
      /drive\.google\.com\/open\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.google\.com\/uc\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.google\.com\/thumbnail\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.usercontent\.google\.com\/download\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.googleusercontent\.com\/download\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /lh3\.googleusercontent\.com\/d\/([A-Za-z0-9_-]+)/i
    ];
    for (const p of patterns) {
      const m = s.match(p);
      if (m) return m[1];
    }
    try {
      const u = new URL(s);
      const id = u.searchParams.get('id');
      if (id && /^[A-Za-z0-9_-]+$/.test(id)) return id;
    } catch (_) {}
    return '';
  }

  function imageCandidates(raw) {
    const source = String(raw || '').trim();
    if (!source) return [];
    const out = [];
    const id = driveId(source);
    if (id) {
      // Multiple Drive delivery routes: if one is blocked, the next can work.
      out.push(`https://drive.google.com/thumbnail?id=${encodeURIComponent(id)}&sz=w2000`);
      out.push(`https://drive.google.com/uc?export=view&id=${encodeURIComponent(id)}`);
      out.push(`https://drive.google.com/uc?export=download&id=${encodeURIComponent(id)}`);
      out.push(`https://drive.usercontent.google.com/download?id=${encodeURIComponent(id)}&export=view&confirm=t`);
    } else if (/^https?:\/\//i.test(source)) {
      out.push(source);
    } else if (source && !source.startsWith('data:')) {
      try { out.push(new URL(source, document.baseURI).href); } catch (_) {}
    }
    return [...new Set(out)];
  }

  function rowsFromPayload(payload) {
    const rows = payload && payload.table && Array.isArray(payload.table.rows) ? payload.table.rows : [];
    return rows.map(r => {
      const c = Array.isArray(r.c) ? r.c : [];
      const val = i => c[i] && c[i].v != null ? String(c[i].v).trim() : '';
      // Current sheet order used by the site. Prefer explicit headers if available in future.
      return {
        id: normId(val(0)),
        image: val(4), image2: val(6), image3: val(7)
      };
    }).filter(x => x.id);
  }

  async function loadRows() {
    if (!rowsPromise) {
      rowsPromise = fetch(DATA_URL, { cache: 'no-store' })
        .then(r => { if (!r.ok) throw new Error('news-data.json HTTP ' + r.status); return r.json(); })
        .then(rowsFromPayload)
        .catch(() => []);
    }
    return rowsPromise;
  }

  function currentNewsId(img) {
    const explicit = img && (img.dataset.newsId || img.getAttribute('data-news-id'));
    if (explicit) return normId(explicit);
    const path = location.pathname;
    const m = path.match(/\/news\/([^/]+)\.html$/i);
    return m ? normId(decodeURIComponent(m[1])) : '';
  }

  function localFallback(source) {
    const s = String(source || '').trim();
    if (!s || /^https?:\/\//i.test(s) || s.startsWith('data:')) return '';
    return s.replace(/^\.\//, '').replace(/^\//, '');
  }

  function githubRaw(path) {
    const clean = localFallback(path);
    if (!clean || !location.hostname.endsWith('github.io')) return '';
    const owner = location.hostname.split('.')[0];
    const parts = location.pathname.split('/').filter(Boolean);
    if (!parts.length) return '';
    const repo = parts[0];
    return `https://raw.githubusercontent.com/${owner}/${repo}/main/${clean.split('/').map(encodeURIComponent).join('/')}`;
  }

  function setImage(img, raw, id) {
    if (!img || img.dataset.newsImageBound === '1') return;
    img.dataset.newsImageBound = '1';
    img.dataset.newsId = id || img.dataset.newsId || '';
    const candidates = imageCandidates(raw);
    const local = localFallback(raw);
    if (local) candidates.push(img.closest('[data-local-image-base]') ? new URL(local, document.baseURI).href : githubRaw(local));
    const list = [...new Set(candidates.filter(Boolean))];
    if (!list.length) return;

    img.dataset.imageSource = String(raw || '');
    img.dataset.imageCandidates = JSON.stringify(list);
    let index = 0;

    const fail = () => {
      index += 1;
      if (index < list.length) {
        img.src = list[index];
      } else {
        img.classList.add('image-load-failed');
        img.removeAttribute('src');
        img.setAttribute('data-image-error', '1');
      }
    };
    img.addEventListener('error', fail);
    img.src = list[0];
  }

  function placeholder(img) {
    if (!img.getAttribute('alt')) img.setAttribute('alt', 'সংবাদের ছবি');
    img.classList.add('news-image-loading');
  }

  async function hydrateImage(img, rows) {
    if (!img || img.dataset.newsImageHydrated === '1') return;
    img.dataset.newsImageHydrated = '1';
    placeholder(img);
    const id = currentNewsId(img);
    if (!id) return;
    const row = rows.find(x => normId(x.id) === id);
    if (!row) return;
    // Image URL is selected by NEWS ID. Drive ID is only used inside the delivery URL.
    const idx = Number(img.dataset.imageIndex || 0);
    const source = (idx === 2 ? row.image3 : idx === 1 ? row.image2 : row.image) || img.dataset.imageSource || img.getAttribute('src') || '';
    setImage(img, source, id);
  }

  async function scan(root) {
    const rows = await loadRows();
    const images = [];
    if (root && root.matches && root.matches('img')) images.push(root);
    if (root && root.querySelectorAll) images.push(...root.querySelectorAll('img[data-news-id], .news-image img, .news-image-top img, .article-full-image img, .article-extra-image img, .category-latest-thumb img'));
    if (!images.length && root === document) images.push(...document.querySelectorAll('img'));
    images.forEach(img => hydrateImage(img, rows));
  }

  function installStyle() {
    if (document.getElementById('news-media-engine-style')) return;
    const style = document.createElement('style');
    style.id = 'news-media-engine-style';
    style.textContent = `
      .news-image-top,.article-full-image,.news-image,.article-extra-image{overflow:hidden;position:relative;}
      .news-image-top,.article-full-image,.news-image{aspect-ratio:16/9;}
      .news-image-top img,.article-full-image img,.news-image img{width:100%;height:100%;display:block;object-fit:cover;}
      .article-extra-image{aspect-ratio:16/9;}
      .article-extra-image img{width:100%;height:100%;display:block;object-fit:cover;}
      img.news-image-loading{background:linear-gradient(90deg,#eee 25%,#f7f7f7 37%,#eee 63%);background-size:400% 100%;animation:newsImgShimmer 1.2s infinite;}
      img.image-load-failed{background:#eee;object-fit:contain!important;}
      @keyframes newsImgShimmer{0%{background-position:100% 0}100%{background-position:-100% 0}}
    `;
    document.head.appendChild(style);
  }

  function boot() {
    installStyle();
    scan(document);
    const observer = new MutationObserver(mutations => mutations.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) scan(n); })));
    if (document.body) observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
