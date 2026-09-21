/* বাংলা সংবাদ — per-news social share counter */
(function(){
"use strict";

var cfg = window.BN_SHARE_CONFIG || {};
var endpoint = String(cfg.endpoint || "").trim();
var placeholder = "PASTE_YOUR_GOOGLE_APPS_SCRIPT_EXEC_URL_HERE";
var page = window.BN_DETAIL_SHARE || {};

var bars = document.querySelectorAll(".social-share-bar[data-news-id]");
if (!bars.length) return;

var newsId = String(
  (bars[0] && bars[0].getAttribute("data-news-id")) || page.id || ""
).trim();

var articleUrl = String(page.url || window.location.href);
var title = String(page.title || document.title || "বাংলা সংবাদ");

function ready(){
  return endpoint && endpoint !== placeholder && newsId;
}

function setTotal(n){
  n = Number(n);
  if (!Number.isFinite(n) || n < 0) n = 0;

  document.querySelectorAll("[data-share-total]").forEach(function(el){
    el.textContent = Math.floor(n).toLocaleString("bn-BD");
  });
}

function request(action, network){
  if (!ready()) return Promise.resolve(null);

  var u = endpoint +
    (endpoint.indexOf("?") >= 0 ? "&" : "?") +
    "action=" + encodeURIComponent(action) +
    "&newsId=" + encodeURIComponent(newsId) +
    (network ? "&network=" + encodeURIComponent(network) : "");

  return fetch(u, {
    method: "GET",
    mode: "cors",
    cache: "no-store",
    keepalive: true
  })
  .then(function(r){
    return r.ok ? r.json() : null;
  })
  .catch(function(){
    return null;
  });
}

function refresh(){
  if (!ready()) {
    setTotal(0);
    return;
  }

  request("get", "").then(function(d){
    if (d && typeof d.total !== "undefined") {
      setTotal(d.total);
    }
  });
}

function enc(v){
  return encodeURIComponent(v);
}

function shareUrl(n){
  var p = cfg.profiles && cfg.profiles[n];
  if (p) return p;

  var u = enc(articleUrl);
  var t = enc(title);

  if (n === "facebook") {
    return "https://www.facebook.com/sharer/sharer.php?u=" + u;
  }

  if (n === "instagram") {
    return "https://www.instagram.com/";
  }

  if (n === "x" || n === "twitter") {
    return "https://twitter.com/intent/tweet?url=" + u + "&text=" + t;
  }

  if (n === "youtube") {
    return "https://www.youtube.com/";
  }

  if (n === "threads") {
    return "https://www.threads.net/intent/post?text=" + t + "%20" + u;
  }

  if (n === "tiktok") {
    return "https://www.tiktok.com/";
  }

  if (n === "whatsapp") {
    return "https://wa.me/?text=" + t + "%20" + u;
  }

  if (n === "messenger") {
    return "https://www.messenger.com/";
  }

  return "#";
}

function count(n){
  if (!ready()) return Promise.resolve(null);

  return request("increment", n).then(function(d){
    if (d && typeof d.total !== "undefined") {
      setTotal(d.total);
    } else {
      refresh();
    }
    return d;
  });
}

function bindButton(b){
  var n = b.getAttribute("data-share-network");

  if (n === "share") {
    b.addEventListener("click", function(e){
      e.preventDefault();

      if (navigator.share) {
        navigator.share({
          title: title,
          text: title,
          url: articleUrl
        }).then(function(){
          count("share");
        }).catch(function(){});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(articleUrl)
          .then(function(){
            count("share");
            alert("নিউজের লিংক কপি হয়েছে");
          })
          .catch(function(){});
      }
    });

    return;
  }

  b.addEventListener("click", function(e){
    e.preventDefault();

    var url = shareUrl(n);

    /*
     * Open the destination immediately from the user's click.
     * Then update the counter without navigating away from the news page.
     * This prevents WhatsApp/Facebook/etc. navigation from cancelling the
     * counter request on mobile browsers.
     */
    var opened = false;

    try {
      var w = window.open(url, "_blank", "noopener,noreferrer");
      opened = !!w;
    } catch (err) {}

    count(n);

    /* Fallback for browsers that block new tabs/windows. */
    if (!opened) {
      setTimeout(function(){
        window.location.href = url;
      }, 150);
    }
  });
}

document
  .querySelectorAll(".social-share-icon[data-share-network]")
  .forEach(function(b){
    var n = b.getAttribute("data-share-network");

    if (n !== "share") {
      b.setAttribute("href", shareUrl(n));
      b.setAttribute("target", "_blank");
      b.setAttribute("rel", "noopener noreferrer");
    }

    bindButton(b);
  });

refresh();

})();
