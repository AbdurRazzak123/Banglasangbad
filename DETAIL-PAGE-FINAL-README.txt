# Banglasangbad — Detail News Page Final

এই প্যাকেজে মূল ডিজাইন/মেনু/কার্ড/SEO কাঠামো না বদলে নিউজ Detail flow ঠিক করা হয়েছে।

আরও পড়ুন → news/ID.html
উদাহরণ: Sheet ID 29 → news/29.html

`details.html?id=29`-ও আলাদা fallback/detail viewer হিসেবে রাখা আছে।

Detail page:
- Headline, category, date
- Details/D column-এর সম্পূর্ণ লেখা; কোনো preview/truncation নয়
- Image 1, Image 2, Image 3
- Video
- ঠিক ৪টি ad slot: TOP, MIDDLE TOP, MIDDLE BOTTOM, BOTTOM
- Ads GitHub-এর ads-data.json থেকে আসে
- News GitHub-এর news-data.json থেকে আসে
- Google Sheet থেকে সরাসরি website runtime fetch করে না
- Google Sheet ID অপরিবর্তিত থাকে

নোট: `details.html/news/29.html` একটি valid GitHub Pages file URL নয়, কারণ `details.html` একই সঙ্গে file এবং directory হতে পারে না। কার্যকর static URL হলো `news/29.html`; `details.html?id=29` fallback viewer-ও রাখা আছে।
