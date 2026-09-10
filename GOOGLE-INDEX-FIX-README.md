# বাংলা সংবাদ — Google Index Fix

Google Sheet-এর খবর এখন GitHub Actions দিয়ে static `News/<id>.html` article page হিসেবে তৈরি হবে। প্রতিটি article-এর initial HTML-এ headline, text, canonical এবং NewsArticle JSON-LD থাকবে।

## Deploy
1. এই ZIP দিয়ে GitHub repository-র ফাইল replace করুন।
2. GitHub Actions → **Build news pages and sitemaps** → **Run workflow** দিন।
3. সফল হলে `News/`, `sitemap.xml` এবং `news-sitemap.xml` আপডেট হবে।
4. Search Console-এ `sitemap.xml` submit করুন।
5. নতুন article-এর `/News/<id>.html` URL URL Inspection-এ পরীক্ষা করুন।

Google indexing তাৎক্ষণিক বা guaranteed নয়; sitemap discovery-এর সাহায্য করে, আর crawlability, canonical, content quality ও Google-এর indexing systems সিদ্ধান্তে ভূমিকা রাখে।
