/* বাংলা সংবাদ — Details/Category media reliability layer.
   Data path: Google Sheet -> GitHub generated news-data.json -> static article pages.
   This script never requires the browser to talk directly to Google Sheets. */
(function(){
 'use strict';
 const DATA_URL='news-data.json';
 const REPO_RAW='https://raw.githubusercontent.com/abdurrazzak123/banglanews.2026/main/';
 function driveCandidates(raw){
   const m=String(raw||'').match(/drive\.google\.com\/(?:file\/d\/|open\?(?:[^#]*&)?id=|uc\?(?:[^#]*&)?id=|thumbnail\?(?:[^#]*&)?id=)([A-Za-z0-9_-]+)/i);
   if(!m)return [];
   const id=m[1];
   return [`https://drive.google.com/thumbnail?id=${id}&sz=w2000`,`https://drive.google.com/uc?export=view&id=${id}`];
 }
 function rawPath(raw){
   const s=String(raw||'').trim().replace(/^\.\//,'').replace(/^\/+/, '');
   if(!s||/^https?:\/\//i.test(s)||s.startsWith('data:'))return '';
   return REPO_RAW+s.split('/').map(encodeURIComponent).join('/');
 }
 function candidates(img){
   const source=img.dataset.imageSource||img.getAttribute('src')||'';
   const out=[...driveCandidates(source)];
   if(/^https?:\/\//i.test(source)&&!out.length)out.push(source);
   const rp=rawPath(source); if(rp)out.push(rp);
   try{out.push(new URL(source,document.baseURI).href)}catch(e){}
   return [...new Set(out.filter(Boolean))];
 }
 function attach(img){
   if(!img||img.dataset.mediaReliability==='1')return;
   img.dataset.mediaReliability='1';
   if(!img.dataset.imageSource)img.dataset.imageSource=img.getAttribute('src')||'';
   const list=candidates(img);
   img.dataset.mediaCandidates=JSON.stringify(list);
   img.addEventListener('error',function(){
     let i=Number(img.dataset.mediaStep||0), arr=list;
     while(i<arr.length && arr[i]===img.src)i++;
     if(i<arr.length){img.dataset.mediaStep=String(i+1);img.src=arr[i];return;}
     img.classList.add('image-load-failed');
     img.style.opacity='0.45';
   });
 }
 function scan(root=document){root.querySelectorAll('img').forEach(attach)}
 function styles(){
   if(document.getElementById('media-reliability-style'))return;
   const s=document.createElement('style');s.id='media-reliability-style';s.textContent='.image-load-failed{background:#f1f1f1;min-height:120px;object-fit:contain!important}.article-extra-image img,.article-full-image img{max-width:100%;height:auto}';document.head.appendChild(s)
 }
 function run(){styles();scan();new MutationObserver(m=>m.forEach(x=>x.addedNodes.forEach(n=>{if(n.nodeType===1)scan(n)}))).observe(document.body,{childList:true,subtree:true});}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
