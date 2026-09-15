(function(){
  'use strict';
  if (window.__BanglaSongbadDetailTools) return;
  window.__BanglaSongbadDetailTools = true;

  const BASE = '../';
  const title = (document.querySelector('h1')?.textContent || document.title || 'বাংলা সংবাদ').trim();
  const url = location.href;

  const style = document.createElement('style');
  style.id = 'banglasangbad-detail-tools-style';
  style.textContent = `
    .bs-social-tools{max-width:1200px;margin:10px auto 18px;padding:0 12px;display:flex;gap:10px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
    .bs-search{position:relative;display:flex;align-items:center;gap:7px;background:#fff;border:1px solid #dbe2ea;border-radius:999px;padding:4px 6px 4px 13px;box-shadow:0 2px 8px rgba(16,42,67,.06);margin-left:auto}
    .bs-search input{border:0;outline:0;width:190px;font:600 14px/1.3 sans-serif;color:#17202a;background:transparent}
    .bs-search button{border:0;border-radius:50%;width:34px;height:34px;cursor:pointer;background:#0b2d3a;color:#fff;font-size:16px}
    .bs-search-results{position:absolute;z-index:9999;top:45px;left:0;right:0;background:#fff;border:1px solid #dbe2ea;border-radius:12px;box-shadow:0 12px 28px rgba(0,0,0,.14);max-height:330px;overflow:auto;display:none}
    .bs-search-results a{display:block;padding:10px 12px;border-bottom:1px solid #f0f2f5;color:#182230;text-decoration:none;font:700 13px/1.45 sans-serif}
    .bs-search-results a:last-child{border-bottom:0}.bs-search-results a:hover{background:#fff5f6;color:#d90429}
    .bs-share{max-width:1200px;margin:0 auto 22px;padding:0 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .bs-share-label{font:800 14px/1.4 sans-serif;color:#344054;margin-right:3px}
    .bs-share a,.bs-share button{border:0;text-decoration:none;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:5px;border-radius:8px;padding:8px 11px;font:800 13px/1 sans-serif;min-height:34px;box-sizing:border-box}
    .bs-facebook{background:#1877f2;color:#fff}.bs-twitter{background:#111;color:#fff}.bs-native{background:#0b2d3a;color:#fff}.bs-youtube{background:#ff0033;color:#fff}.bs-instagram{background:#d62976;color:#fff}.bs-copy{background:#eef2f6;color:#182230}
    .bs-social-links{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
    .bs-social-links a{font:800 12px/1 sans-serif;text-decoration:none;border:1px solid #e2e8f0;border-radius:999px;padding:7px 10px;color:#334155;background:#fff}
    @media(max-width:768px){
      .bs-social-tools{padding:0 12px;margin:8px auto 13px;display:block}
      .bs-search{width:100%;box-sizing:border-box}.bs-search input{width:100%;min-width:0}
      .bs-share{padding:0 12px;margin-bottom:18px;justify-content:flex-start}.bs-share a,.bs-share button{padding:8px 10px;font-size:12px}
    }
  `;
  document.head.appendChild(style);

  function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function go(url){location.href=url;}
  function copy(){
    if(navigator.clipboard){navigator.clipboard.writeText(url).then(()=>alert('নিউজের লিংক কপি হয়েছে।'));}
    else{const t=document.createElement('textarea');t.value=url;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();alert('নিউজের লিংক কপি হয়েছে।');}
  }
  async function nativeShare(){
    if(navigator.share){try{await navigator.share({title:title,text:title,url:url});return;}catch(e){}}
    copy();
  }
  function openSocial(type){
    const u=encodeURIComponent(url), t=encodeURIComponent(title);
    const links={
      facebook:'https://www.facebook.com/sharer/sharer.php?u='+u,
      twitter:'https://twitter.com/intent/tweet?url='+u+'&text='+t,
    };
    if(links[type]) window.open(links[type],'_blank','noopener,noreferrer,width=680,height=620');
    else if(type==='youtube'){copy(); window.open('https://www.youtube.com/','_blank','noopener,noreferrer');}
    else if(type==='instagram'){copy(); window.open('https://www.instagram.com/','_blank','noopener,noreferrer');}
  }

  const header=document.querySelector('.header-inner');
  if(header){
    header.querySelectorAll('.bs-social-tools, .bs-detail-search-wrap, .bs-search').forEach(el=>el.remove());
    const tools=document.createElement('div'); tools.className='bs-social-tools bs-detail-search-wrap';
    tools.innerHTML=`<div class="bs-search" role="search"><input id="bs-search-input" type="search" placeholder="নিউজ খুঁজুন..." aria-label="নিউজ খুঁজুন"><button id="bs-search-btn" type="button" aria-label="সার্চ">⌕</button><div id="bs-search-results" class="bs-search-results"></div></div>`;
    header.appendChild(tools);
    const input=tools.querySelector('#bs-search-input'), results=tools.querySelector('#bs-search-results');
    let items=[];
    fetch(BASE+'news-data.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(data=>{
      const rows=Array.isArray(data)?data:(data?.table?.rows||[]);
      items=rows.map(r=>{const c=r.c||[];return {id:c[0]?.v,cat:c[1]?.v||'',title:c[2]?.v||''};}).filter(x=>x.id!==undefined&&x.id!==null&&String(x.id).trim()&&x.title);
    }).catch(()=>{});
    function search(){
      const q=input.value.trim().toLowerCase(); results.innerHTML='';
      if(!q){results.style.display='none';return;}
      const found=items.filter(x=>(x.title+' '+x.cat).toLowerCase().includes(q)).slice(0,8);
      if(!found.length){results.innerHTML='<div style="padding:12px;font:600 13px sans-serif;color:#667085">কোনো সংবাদ পাওয়া যায়নি</div>';results.style.display='block';return;}
      found.forEach(x=>{const a=document.createElement('a');a.href=encodeURIComponent(String(x.id))+'.html';a.innerHTML='<strong>'+esc(x.title)+'</strong><br><small>'+esc(x.cat)+'</small>';results.appendChild(a);});
      results.style.display='block';
    }
    input.addEventListener('input',search);
    input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();search();}});
    tools.querySelector('#bs-search-btn').addEventListener('click',search);
    document.addEventListener('click',e=>{if(!tools.contains(e.target))results.style.display='none';});
  }

  const h1=document.querySelector('h1.home-feature-title');
  if(h1){
    const share=document.createElement('div'); share.className='bs-share';
    share.innerHTML=`<span class="bs-share-label">শেয়ার করুন:</span>
      <a href="#" class="bs-facebook" aria-label="Facebook-এ শেয়ার করুন">Facebook</a>
      <a href="#" class="bs-twitter" aria-label="Twitter/X-এ শেয়ার করুন">Twitter/X</a>
      <button class="bs-native" type="button" aria-label="মোবাইলে শেয়ার করুন">📱 শেয়ার</button>
      <a href="#" class="bs-youtube" aria-label="YouTube-এ লিংক শেয়ার/খুলুন">YouTube</a>
      <a href="#" class="bs-instagram" aria-label="Instagram-এ লিংক শেয়ার/খুলুন">Instagram</a>
      <button class="bs-copy" type="button" aria-label="লিংক কপি করুন">লিংক কপি</button>`;
    h1.insertAdjacentElement('afterend',share);
    share.querySelector('.bs-facebook').onclick=e=>{e.preventDefault();openSocial('facebook');};
    share.querySelector('.bs-twitter').onclick=e=>{e.preventDefault();openSocial('twitter');};
    share.querySelector('.bs-native').onclick=e=>{e.preventDefault();nativeShare();};
    share.querySelector('.bs-youtube').onclick=e=>{e.preventDefault();openSocial('youtube');};
    share.querySelector('.bs-instagram').onclick=e=>{e.preventDefault();openSocial('instagram');};
    share.querySelector('.bs-copy').onclick=copy;
  }
})();
