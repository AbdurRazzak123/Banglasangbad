/* বাংলা সংবাদ — GitHub-only media helper
   News media is already copied into the repository during the build. */
(function(){
  function fixLocalMedia(){
    document.querySelectorAll('img[data-news-image]').forEach(img=>{
      const src=img.getAttribute('data-news-image');
      if(src) img.src=src;
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',fixLocalMedia,{once:true});
  else fixLocalMedia();
})();
