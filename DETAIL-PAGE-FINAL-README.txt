# Banglasangbad — Detail News Page Fix

এই build-এ Detail Page-এর আসল flow ঠিক করা হয়েছে।

আরও পড়ুন → News/ID.html
উদাহরণ: Sheet ID 29 → News/29.html
উদাহরণ: Sheet ID 30 → details.html?id=30

ID Google Sheet-এর মতোই থাকবে; ID পরিবর্তন/নতুন ID তৈরি হবে না।

Detail page-এ:
- Headline, category, date
- Details/D column-এর সম্পূর্ণ লেখা; কোনো preview/truncation নেই
- Image 1, Image 2, Image 3
- Video থাকলে video
- ঠিক ৪টি ad slot: TOP, MIDDLE TOP, MIDDLE BOTTOM, BOTTOM
- News data GitHub-এর news-data.json থেকে আসে
- Ads data GitHub-এর ads-data.json থেকে আসে
- Website runtime সরাসরি Google Sheet পড়ে না
- Google Sheet → GitHub Actions → Website flow বজায় থাকে

মূল design/header/menu/footer/SEO কাঠামো অযথা বদলানো হয়নি।

গুরুত্বপূর্ণ: News/29.html বৈধ URL নয়। কারণ details.html একটি file। এই build-এর Detail URL হলো News/29.html।
