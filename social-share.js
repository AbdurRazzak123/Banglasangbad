/* বাংলা সংবাদ — per-news social share counter */
(function(){
"use strict";
var cfg=window.BN_SHARE_CONFIG||{}, endpoint=String(cfg.endpoint||"").trim(), placeholder="PASTE_YOUR_GOOGLE_APPS_SCRIPT_EXEC_URL_HERE", page=window.BN_DETAIL_SHARE||{}, bar=document.querySelector(".social-share-bar[data-news-id]");
if(!bar)return;
var newsId=String(bar.getAttribute("data-news-id")||page.id||"").trim(), totalEl=bar.querySelector("[data-share-total]"), buttons=bar.querySelectorAll("[data-share-network]"), articleUrl=String(page.url||window.location.href), title=String(page.title||document.title||"বাংলা সংবাদ");
function ready(){return endpoint&&endpoint!==placeholder;}
function setTotal(n){n=Number(n);if(!Number.isFinite(n)||n<0)n=0;if(totalEl)totalEl.textContent=Math.floor(n).toLocaleString("bn-BD");}
function request(action,network){if(!ready()||!newsId)return Promise.resolve(null);var u=endpoint+(endpoint.indexOf("?")>=0?"&":"?")+"action="+encodeURIComponent(action)+"&newsId="+encodeURIComponent(newsId)+(network?"&network="+encodeURIComponent(network):"");return fetch(u,{method:"GET",mode:"cors",cache:"no-store"}).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;});}
function refresh(){if(!ready()){setTotal(0);return;}request("get","").then(function(d){if(d&&typeof d.total!=="undefined")setTotal(d.total);});}
function enc(v){return encodeURIComponent(v);}
function shareUrl(n){var p=cfg.profiles&&cfg.profiles[n];if(p)return p;var u=enc(articleUrl),t=enc(title);if(n==="facebook")return "https://www.facebook.com/sharer/sharer.php?u="+u;if(n==="instagram")return "https://www.instagram.com/";if(n==="x"||n==="twitter")return "https://twitter.com/intent/tweet?url="+u+"&text="+t;if(n==="youtube")return "https://www.youtube.com/";if(n==="threads")return "https://www.threads.net/intent/post?text="+t+"%20"+u;if(n==="tiktok")return "https://www.tiktok.com/";return "#";}
function count(n){if(!ready())return;request("increment",n).then(function(d){if(d&&typeof d.total!=="undefined")setTotal(d.total);else refresh();});}
buttons.forEach(function(b){var n=b.getAttribute("data-share-network");if(n==="share"){b.addEventListener("click",function(){if(navigator.share){navigator.share({title:title,text:title,url:articleUrl}).then(function(){count("share");}).catch(function(){});}else if(navigator.clipboard){navigator.clipboard.writeText(articleUrl).then(function(){count("share");alert("নিউজের লিংক কপি হয়েছে");});}});}else{b.setAttribute("href",shareUrl(n));b.addEventListener("click",function(){count(n);});}});
refresh();
})();
