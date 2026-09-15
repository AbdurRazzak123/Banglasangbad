(function(){
  'use strict';
  if(window.__BanglaSongbadGlobalSearch) return;
  window.__BanglaSongbadGlobalSearch=true;
  const base = (document.body && document.body.dataset.siteBase) || './';
  const root = document.createElement('div');
  root.className='bs-global-search-wrap';
  root.innerHTML=`<div class="bs-global-search" role="search"><input id="bs-global-search-input" type="search" placeholder="নিউজ খুঁজুন..." aria-label="নিউজ খুঁজুন"><button id="bs-global-search-btn" type="button">সার্চ</button><div id="bs-global-search-results" class="bs-global-search-results"></div></div>`;
  const nav=document.querySelector('.nav');
  if(nav) nav.insertAdjacentElement('afterend',root); else document.body.insertBefore(root,document.body.firstChild);
  const css=document.createElement('style');
  css.textContent=`
  .bs-global-search-wrap{max-width:1200px;margin:10px auto;padding:0 12px;box-sizing:border-box}
  .bs-global-search{position:relative;display:flex;gap:7px;max-width:680px;margin:0 auto;background:#fff;border:1px solid #d7dee7;border-radius:10px;padding:5px;box-shadow:0 2px 8px rgba(16,42,67,.06)}
  .bs-global-search input{flex:1;min-width:0;border:0;outline:0;padding:9px 11px;font:600 14px/1.3 Arial,"Noto Sans Bengali",sans-serif;background:transparent}
  .bs-global-search button{border:0;border-radius:7px;background:#d71920;color:#fff;font-weight:800;padding:0 15px;cursor:pointer}
  .bs-global-search-results{display:none;position:absolute;z-index:99999;left:0;right:0;top:52px;background:#fff;border:1px solid #d7dee7;border-radius:10px;box-shadow:0 12px 28px rgba(0,0,0,.16);max-height:360px;overflow:auto}
  .bs-global-search-results a{display:block;padding:10px 13px;border-bottom:1px solid #eef1f4;text-decoration:none;color:#17202a;font-weight:700;font-size:14px;line-height:1.45}
  .bs-global-search-results a:hover{background:#fff5f6;color:#d71920}
  .bs-global-search-results small{font-weight:600;color:#667085}
  @media(max-width:768px){.bs-global-search-wrap{margin:8px auto}.bs-global-search button{padding:0 12px;font-size:12px}.bs-global-search input{font-size:13px}}
  `;
  document.head.appendChild(css);
  const input=root.querySelector('#bs-global-search-input'), btn=root.querySelector('#bs-global-search-btn'), results=root.querySelector('#bs-global-search-results');
  let items=[];
  function normalizeId(v){const s=String(v||'').trim();return /^\d+(?:\.0+)?$/.test(s)?String(parseInt(s,10)):s;}
  function render(){
    const q=input.value.trim().toLowerCase(); results.innerHTML='';
    if(!q){results.style.display='none';return;}
    const found=items.filter(x=>(x.title+' '+x.category+' '+x.keywords).toLowerCase().includes(q)).slice(0,10);
    if(!found.length){results.innerHTML='<div style="padding:14px;font-weight:700;color:#667085">কোনো সংবাদ পাওয়া যায়নি।</div>';results.style.display='block';return;}
    found.forEach(x=>{const a=document.createElement('a');a.href=base+'news/'+encodeURIComponent(normalizeId(x.id))+'.html';a.innerHTML='<strong>'+escapeHtml(x.title)+'</strong><br><small>'+escapeHtml(x.category)+'</small>';results.appendChild(a);});
    results.style.display='block';
  }
  function escapeHtml(s){return String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  fetch((base==='./'?'news-data.json':base+'news-data.json'),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(data=>{
    const rows=data&&data.table&&data.table.rows||[];
    items=rows.map(r=>{const c=r.c||[];return{id:c[0]&&c[0].v,category:(c[1]&&c[1].v)||'',title:(c[2]&&c[2].v)||'',keywords:(c[9]&&c[9].v)||''};}).filter(x=>x.id&&x.title);
  }).catch(()=>{});
  input.addEventListener('input',render);btn.addEventListener('click',render);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();const first=results.querySelector('a');if(first)location.href=first.href;else render();}});
  document.addEventListener('click',e=>{if(!root.contains(e.target))results.style.display='none';});
})();
