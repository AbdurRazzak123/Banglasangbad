/* বাংলা সংবাদ — UNIVERSAL MEDIA RELIABILITY LAYER v6
   Works on root/category/detail pages and on GitHub Pages project repos.
   Local images: current Pages URL -> RAW main/master -> GitHub raw fallbacks -> relative.
   Google Drive images: thumbnail -> googleusercontent -> Drive download/view.
*/
(function(){
  'use strict';
  const VERSION='20260913-media-universal-v6';
  const TRANSPARENT='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

  function repoInfo(){
    const host=String(location.hostname||'').toLowerCase();
    if(!host.endsWith('.github.io'))return null;
    const parts=location.pathname.split('/').filter(Boolean);
    const owner=host.split('.')[0];
    const repo=parts[0]||'';
    return owner&&repo?{owner,repo}:null;
  }
  function repoBase(){
    const info=repoInfo();
    if(info)return '/'+info.repo+'/';
    return location.pathname.includes('/news/')?'../':'./';
  }
  function cleanPath(raw){return String(raw||'').trim().replace(/^\.\//,'').replace(/^\/+/,'');}
  function fileName(raw){const s=cleanPath(raw).split(/[?#]/)[0];const p=s.split('/');return p[p.length-1]||'';}
  function driveId(raw){
    const s=String(raw||'').trim();
    const patterns=[
      /drive\.google\.com\/file\/d\/([A-Za-z0-9_-]+)/i,
      /drive\.google\.com\/(?:open|uc|thumbnail)\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /drive\.usercontent\.google\.com\/[^?#]*\?(?:[^#]*&)?id=([A-Za-z0-9_-]+)/i,
      /(?:^|[?&])id=([A-Za-z0-9_-]{10,})(?:[&#]|$)/i
    ];
    for(const p of patterns){const m=s.match(p);if(m)return m[1];}
    return '';
  }
  function driveCandidates(raw){
    const id=driveId(raw);if(!id)return [];
    return [
      `https://drive.google.com/thumbnail?id=${id}&sz=w2000`,
      `https://lh3.googleusercontent.com/d/${id}=w2000`,
      `https://drive.usercontent.google.com/download?id=${id}&export=view&confirm=t`,
      `https://drive.google.com/uc?export=view&id=${id}`,
      `https://drive.google.com/uc?export=download&id=${id}`
    ];
  }
  function isRemote(s){return /^(?:https?:|data:|blob:)/i.test(String(s||''));}
  function localCandidates(raw){
    const clean=cleanPath(raw);if(!clean||isRemote(clean))return [];
    const name=fileName(clean);if(!name)return [];
    if(!/^(?:assets\/news|news-media|news-images|images\/news)\//i.test(clean))return [];
    const encName=encodeURIComponent(name),out=[];
    const info=repoInfo();
    // 1) Same-origin GitHub Pages path. This is the most natural URL for the deployed site.
    out.push(repoBase()+'assets/news/'+encName);
    // 2) GitHub RAW fallback for the current repository.
    if(info){
      const owner=encodeURIComponent(info.owner),repo=encodeURIComponent(info.repo);
      out.push(`https://raw.githubusercontent.com/${owner}/${repo}/main/assets/news/${encName}`);
      out.push(`https://raw.githubusercontent.com/${owner}/${repo}/master/assets/news/${encName}`);
      out.push(`https://github.com/${owner}/${repo}/raw/refs/heads/main/assets/news/${encName}`);
      out.push(`https://github.com/${owner}/${repo}/raw/refs/heads/master/assets/news/${encName}`);
      out.push(`https://cdn.jsdelivr.net/gh/${owner}/${repo}@main/assets/news/${encName}`);
      out.push(`https://cdn.jsdelivr.net/gh/${owner}/${repo}@master/assets/news/${encName}`);
      out.push(`https://media.githubusercontent.com/media/${owner}/${repo}/main/assets/news/${encName}`);
    }
    // 3) Relative fallbacks, including pages opened from /news/.
    out.push('./assets/news/'+encName);
    out.push('../assets/news/'+encName);
    try{out.push(new URL(clean,document.baseURI).href);}catch(e){}
    return [...new Set(out)];
  }
  function candidates(img){
    const source=img.dataset.imageSource||img.getAttribute('src')||'';
    const out=[];const drives=driveCandidates(source);
    if(drives.length)out.push(...drives);
    else if(isRemote(source))out.push(source);
    out.push(...localCandidates(source));
    return [...new Set(out.filter(Boolean))];
  }
  function mark(img){
    if(!img||img.dataset.mediaUniversal==='1')return;
    img.dataset.mediaUniversal='1';
    if(!img.dataset.imageSource){
      const current=img.getAttribute('src')||'';
      if(current&&current!==TRANSPARENT)img.dataset.imageSource=current;
    }
    const source=img.dataset.imageSource||'';
    const list=candidates(img);
    if(!list.length)return;
    img.dataset.mediaCandidates=JSON.stringify(list);
    let current=img.getAttribute('src')||'';
    let idx=list.findIndex(x=>x===current);
    if(idx<0)idx=0;
    const fail=()=>{
      let n=Number(img.dataset.mediaIndex||idx)+1;
      while(n<list.length&&list[n]===img.currentSrc)n++;
      if(n<list.length){img.dataset.mediaIndex=String(n);img.src=list[n];}
      else{img.classList.add('image-load-failed');}
    };
    img.addEventListener('error',fail);
    // For Drive/local asset sources, start with our known-good candidate chain.
    if(driveCandidates(source).length || /^(?:\.?\/?assets\/news|news-media|news-images|images\/news)\//i.test(source)){
      idx=0;img.dataset.mediaIndex='0';
      if(current!==list[0])img.src=list[0];
    }else{
      img.dataset.mediaIndex=String(idx);
    }
  }
  function scan(root){
    const scope=root&&root.querySelectorAll?root:document;
    scope.querySelectorAll('img[data-image-source],img').forEach(mark);
    if(root&&root.tagName==='IMG')mark(root);
  }
  function run(){
    if(!document.getElementById('media-universal-style')){
      const s=document.createElement('style');s.id='media-universal-style';
      s.textContent='.image-load-failed{background:#f1f1f1;object-fit:contain!important;} .article-extra-image img,.article-full-image img{max-width:100%;height:auto;}';
      document.head.appendChild(s);
    }
    scan(document);
    if(document.body)new MutationObserver(ms=>ms.forEach(m=>m.addedNodes.forEach(n=>{if(n.nodeType===1)scan(n);}))).observe(document.body,{childList:true,subtree:true});
    document.documentElement.dataset.mediaLoader=VERSION;
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
