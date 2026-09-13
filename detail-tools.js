/* বাংলা সংবাদ — detail page share tools only.
   Search is intentionally handled by the same site-search.js used on home/category pages. */
(function(){
  'use strict';
  if(window.__BanglaSongbadDetailShareLoaded)return;
  window.__BanglaSongbadDetailShareLoaded=true;
  const title=(document.querySelector('h1.home-feature-title')?.textContent||document.title||'বাংলা সংবাদ').trim();
  const url=location.href;
  const esc=s=>String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function copy(){
    if(navigator.clipboard)navigator.clipboard.writeText(url).then(()=>alert('নিউজের লিংক কপি হয়েছে।'));
    else{const t=document.createElement('textarea');t.value=url;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();alert('নিউজের লিংক কপি হয়েছে।');}
  }
  async function share(){if(navigator.share){try{await navigator.share({title,text:title,url});return;}catch(e){}}copy();}
  function social(type){
    const u=encodeURIComponent(url),t=encodeURIComponent(title);
    if(type==='facebook')window.open('https://www.facebook.com/sharer/sharer.php?u='+u,'_blank','noopener,noreferrer,width=680,height=620');
    else if(type==='twitter')window.open('https://twitter.com/intent/tweet?url='+u+'&text='+t,'_blank','noopener,noreferrer,width=680,height=620');
    else if(type==='youtube'){copy();window.open('https://www.youtube.com/','_blank','noopener,noreferrer');}
    else if(type==='instagram'){copy();window.open('https://www.instagram.com/','_blank','noopener,noreferrer');}
  }
  const h1=document.querySelector('h1.home-feature-title');
  if(!h1)return;
  const old=document.querySelector('.bs-share');if(old)old.remove();
  const box=document.createElement('div');box.className='bs-share';
  box.innerHTML=`<span class="bs-share-label">শেয়ার করুন:</span><a href="#" class="bs-facebook">Facebook</a><a href="#" class="bs-twitter">Twitter/X</a><button type="button" class="bs-native">📱 শেয়ার</button><a href="#" class="bs-youtube">YouTube</a><a href="#" class="bs-instagram">Instagram</a><button type="button" class="bs-copy">লিংক কপি</button>`;
  h1.insertAdjacentElement('afterend',box);
  const css=document.createElement('style');css.textContent='.bs-share{max-width:1200px;margin:10px auto 22px;padding:0 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.bs-share-label{font:800 14px/1.4 sans-serif;color:#344054}.bs-share a,.bs-share button{border:0;text-decoration:none;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;border-radius:8px;padding:8px 11px;font:800 13px/1 sans-serif;min-height:34px}.bs-facebook{background:#1877f2;color:#fff}.bs-twitter{background:#111;color:#fff}.bs-native{background:#0b2d3a;color:#fff}.bs-youtube{background:#ff0033;color:#fff}.bs-instagram{background:#d62976;color:#fff}.bs-copy{background:#eef2f6;color:#182230}@media(max-width:768px){.bs-share{padding:0 12px}.bs-share a,.bs-share button{padding:8px 10px;font-size:12px}}';document.head.appendChild(css);
  box.querySelector('.bs-facebook').onclick=e=>{e.preventDefault();social('facebook')};
  box.querySelector('.bs-twitter').onclick=e=>{e.preventDefault();social('twitter')};
  box.querySelector('.bs-native').onclick=e=>{e.preventDefault();share()};
  box.querySelector('.bs-youtube').onclick=e=>{e.preventDefault();social('youtube')};
  box.querySelector('.bs-instagram').onclick=e=>{e.preventDefault();social('instagram')};
  box.querySelector('.bs-copy').onclick=copy;
})();
