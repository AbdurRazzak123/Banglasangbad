/* বাংলা সংবাদ — LIVE GOOGLE SHEET IMAGE SYNC v1
   Sheet is the primary source for article images.
   Columns: ID, Category, Headline, Details, Image 1, Date, Video, Image 2, Image 3, Keyword
*/
(function(){
  'use strict';
  const SHEET_ID='1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg';
  const SHEET_NAME='Bangla News';
  const CACHE_KEY='bangla-news-sheet-image-cache-v1';
  const TTL=2*60*1000;

  function norm(v){return String(v??'').trim();}
  function normId(v){
    const x=norm(v);
    return /^\d+(?:\.0+)?$/.test(x)?String(parseInt(x,10)):x;
  }
  function driveId(raw){
    const s=norm(raw);
    const p=[
      /drive\.google\.com\/file\/d\/([A-Za-z0-9_-]+)/i,
      /drive\.google\.com\/(?:open|uc|thumbnail)\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.usercontent\.google\.com\/[^?#]*\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /(?:^|[?&])id=([A-Za-z0-9_-]{10,})(?:[&#]|$)/i
    ];
    for(const re of p){const m=s.match(re);if(m)return m[1];}
    return '';
  }
  function imageCandidates(raw){
    const s=norm(raw); if(!s)return [];
    const id=driveId(s);
    if(id) return [
      `https://drive.google.com/thumbnail?id=${id}&sz=w2000`,
      `https://lh3.googleusercontent.com/d/${id}=w2000`,
      `https://drive.usercontent.google.com/download?id=${id}&export=view&confirm=t`,
      `https://drive.google.com/uc?export=view&id=${id}`,
      `https://drive.google.com/uc?export=download&id=${id}`
    ];
    if(/^(https?:|data:|blob:)/i.test(s)) return [s];
    let p=s.replace(/^\.?\//,'').replace(/^\/+/,'');
    const name=p.split(/[?#]/)[0].split('/').pop();
    if(!name)return [];
    const m=location.pathname.match(/^\/([^/]+)(?:\/|$)/);
    const repo=m?m[1]:'';
    const owner=String(location.hostname||'').split('.')[0];
    const out=[];
    if(repo) out.push('/'+repo+'/assets/news/'+encodeURIComponent(name));
    if(owner&&repo){
      out.push(`https://raw.githubusercontent.com/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/main/assets/news/${encodeURIComponent(name)}`);
      out.push(`https://raw.githubusercontent.com/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/master/assets/news/${encodeURIComponent(name)}`);
    }
    out.push(new URL(p.replace(/^assets\//,'')==='news/'+name?'assets/news/'+name:p,document.baseURI).href);
    return [...new Set(out)];
  }
  function setImage(img, raw){
    const c=imageCandidates(raw);
    if(!c.length){ img.style.display='none'; return; }
    img.dataset.sheetImage='1';
    img.dataset.sheetImageSource=raw;
    img.style.display='';
    let i=0;
    const next=()=>{
      if(i>=c.length){img.style.display='none';return;}
      const u=c[i++];
      img.onerror=next;
      if(img.src!==u) img.src=u;
    };
    next();
  }
  function parseGViz(text){
    const t=String(text||'').trim();
    try{
      const j=JSON.parse(t);
      if(j && j.table && Array.isArray(j.table.rows)) return j.table.rows;
    }catch(e){}
    const m=t.match(/google\.visualization\.Query\.setResponse\(([\s\S]*)\);?\s*$/);
    if(m){try{const j=JSON.parse(m[1]);return j.table?.rows||[];}catch(e){}}
    return [];
  }
  function rowValue(row,i){
    const c=row && row.c && row.c[i];
    return c && c.v!=null ? String(c.v) : '';
  }
  async function loadRows(){
    const url=`https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json&sheet=${encodeURIComponent(SHEET_NAME)}&tq=${encodeURIComponent('select *')}`;
    try{
      const r=await fetch(url,{cache:'no-store',mode:'cors'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const rows=parseGViz(await r.text());
      if(rows.length){localStorage.setItem(CACHE_KEY,JSON.stringify({t:Date.now(),rows}));return rows;}
    }catch(e){}
    try{
      const c=JSON.parse(localStorage.getItem(CACHE_KEY)||'null');
      if(c&&Array.isArray(c.rows))return c.rows;
    }catch(e){}
    return [];
  }
  function buildMap(rows){
    const map=new Map();
    rows.forEach(r=>{
      const id=normId(rowValue(r,0)); if(!id)return;
      map.set(id,{
        image1:rowValue(r,4), image2:rowValue(r,7), image3:rowValue(r,8)
      });
    });
    return map;
  }
  function inferId(img){
    const el=img.closest('[data-news-id]');
    if(el) return normId(el.getAttribute('data-news-id'));
    const card=img.closest('[id^="news-"]');
    if(card) return normId(card.id.replace(/^news-/,''));
    const src=img.getAttribute('data-image-source')||img.getAttribute('src')||'';
    const m=src.match(/(?:^|\/)([^/]+?)-(1|2|3)\.(?:jpe?g|png|webp|gif)(?:[?#]|$)/i);
    if(m)return normId(m[1]);
    const path=location.pathname.match(/\/news\/([^/]+)\.html$/i);
    return path?normId(path[1]):'';
  }
  function inferSlot(img){
    const explicit=norm(img.getAttribute('data-sheet-image-slot'));
    if(explicit)return explicit;
    const src=img.getAttribute('data-image-source')||img.getAttribute('src')||'';
    const m=src.match(/-(1|2|3)\.(?:jpe?g|png|webp|gif)(?:[?#]|$)/i);
    return m?m[1]:'1';
  }
  function sync(map){
    document.querySelectorAll('img[data-image-source], img[data-sheet-image-slot]').forEach(img=>{
      const id=inferId(img), slot=inferSlot(img);
      const n=map.get(id);
      if(!n)return;
      const raw=slot==='2'?n.image2:slot==='3'?n.image3:n.image1;
      setImage(img,raw);
    });
  }
  async function run(){
    const rows=await loadRows();
    if(rows.length)sync(buildMap(rows));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
