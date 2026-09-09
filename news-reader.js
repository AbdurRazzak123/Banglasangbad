/* Banglasangbad — original homepage-safe news reader
   Uses GitHub-generated news-data.json. The existing homepage HTML/CSS is preserved.
*/
(function () {
  'use strict';
  const DATA_URL = 'news-data.json?v=' + Date.now();
  const PREVIEW_LINES = 7;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normId = v => { const s=String(v??'').trim(); return /^\d+\.0+$/.test(s)?s.split('.')[0]:s; };
  const lineParts = text => {
    const raw = String(text ?? '').trim();
    if (!raw) return [];
    const explicit = raw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
    if (explicit.length > 1) return explicit;
    const words = raw.split(/\s+/);
    const lines = []; let line = '';
    words.forEach(word => {
      const candidate = line ? line + ' ' + word : word;
      if (Array.from(candidate).length > 78 && line) { lines.push(line); line = word; }
      else line = candidate;
    });
    if (line) lines.push(line);
    return lines;
  };
  const imageUrl = v => {
    const raw = String(v || '').trim();
    if (!raw) return '';
    const m = raw.match(/drive\.google\.com\/(?:file\/d\/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)/i);
    return m ? `https://drive.google.com/thumbnail?id=${m[1]}&sz=w2000` : raw;
  };
  const previewText = text => { const lines=lineParts(text); return lines.length > PREVIEW_LINES ? lines.slice(0, PREVIEW_LINES).join('\n') + '…' : lines.join('\n'); };
  const remainderText = text => { const lines=lineParts(text); return lines.length > PREVIEW_LINES ? lines.slice(PREVIEW_LINES).join('\n').trim() : ''; };
  const selectedId = () => normId(new URLSearchParams(location.search).get('id') || '');

  function renderMain(list) {
    const box = document.getElementById('news-container');
    if (!box || !list.length) return;
    const sid = selectedId();
    const main = list.find(n => normId(n.id) === sid) || list[list.length - 1];
    const rest = remainderText(main.text);
    const img = imageUrl(main.image);

    const image = img ? `<div class="news-image-top"><img src="${esc(img)}" alt="${esc(main.title)}" loading="eager" onerror="this.style.display='none'"></div>` : '';
    box.innerHTML = `<div class="vertical-news-block" id="news-${esc(normId(main.id))}">
      ${image}
      <div class="news-text-bottom">
        <span class="category-tag">${esc(main.category || 'সংবাদ')}</span>
        <div class="breaking-news-date">${esc(main.date || '')}</div>
        <h3>${esc(main.title)}</h3>
        <p class="home-summary">${esc(previewText(main.text) || 'এই সংবাদের বিস্তারিত তথ্য পাওয়া যায়নি।')}</p>
        <a href="news/${encodeURIComponent(normId(main.id))}.html" class="read-more-btn breaking-detail-btn">আরও পড়ুন</a>
      </div>
    </div>`;

    const breaking = document.querySelector('.breaking .ticker-track');
    if (breaking) breaking.textContent = main.title || '';



    if (sid) {
      history.replaceState(null, '', 'index.html?id=' + encodeURIComponent(normId(main.id)));
      setTimeout(() => box.scrollIntoView({behavior:'smooth', block:'start'}), 120);
    }
  }

  function renderLatest(list) {
    const box = document.getElementById('latest-news-container');
    if (!box) return;
    box.innerHTML = [...list].reverse().map(n => {
      const id = normId(n.id);
      return `<div class="latest-item"><a href="index.html?id=${encodeURIComponent(id)}">🔺 ${esc(n.title)}</a></div>`;
    }).join('');
  }

  fetch(DATA_URL, {cache:'no-store'})
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(data => {
      const list = Array.isArray(data) ? data : (Array.isArray(data.articles) ? data.articles : []);
      if (!list.length) throw new Error('No news data');
      renderMain(list);
      renderLatest(list);
    })
    .catch(err => {
      console.error('GitHub news loading failed:', err);
      const box = document.getElementById('news-container');
      if (box) box.innerHTML = '<div style="padding:30px;text-align:center;color:#888">খবর এই মুহূর্তে লোড করা যাচ্ছে না।</div>';
    });
})();
