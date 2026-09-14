# Banglasangbad — Final Google Sheet → GitHub News Pipeline

এই প্যাকেজটি বর্তমান সাইটের ডিজাইন না বদলে pipeline ঠিক করার জন্য।

## Replace

1. `.github/workflows/update-news-sitemap.yml`
   - প্যাকেজের `.github-workflow.yml` ফাইলের নাম/কনটেন্ট ব্যবহার করুন।
2. `tools/news_preflight.py`
3. `tools/patch_generator.py`
4. `requirements.txt` (যদি না থাকে)

## গুরুত্বপূর্ণ

বর্তমান generator-এ Google Sheet-এর Image/Video column mapping ভুল ছিল:
A ID, B Category, C Headline, D Details, E Image-1, F Date,
G Video, H Image-2, I Image-3, J Keyword.

এই package সেই mapping ঠিক করে।

## One small workflow addition

`Generate static news`-এর আগে `Patch generator` step দিতে হবে:

    - name: Patch generator compatibility
      run: python tools/patch_generator.py

অর্থাৎ workflow-এর order হবে:
Checkout → Python → BeautifulSoup → Preflight → Patch generator → Generate → Validate → Commit.

## Expected output

news/31.html
news/32.html
...

assets/news/31-1.jpg
assets/news/31-2.jpg
assets/news/31-3.jpg

Google Sheet-এর row ID-ই detail-page ID হবে।

## Safety

Preflight ব্যর্থ হলে workflow থেমে যাবে এবং পুরোনো live generated pages untouched থাকবে।
