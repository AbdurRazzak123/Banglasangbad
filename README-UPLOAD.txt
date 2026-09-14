FINAL LAST GENERATOR — Banglasangbad

Replace only:
Tools/generate_static_news.py

Key behavior:
- Details pages remain News/ID.html; IDs are not changed.
- Home-style main container and right sidebar.
- Right sidebar: 14 items total, 2 newest per category across 7 categories.
- Each sidebar item shows thumbnail, headline, and category name; clicking opens that item's own Details page.
- Six Home-style category cards remain and open their own Details pages.
- Ads are read from the Ads tab of the SAME Google Sheet as Bangla News.
- Four Details ad slots: Top, Middle top, Middle bottom, Bottom.
- Existing ads-data.json is preserved if the Ads tab cannot be read.
- Existing social links remain.
- Do not delete .github/workflows or other Tools files.
