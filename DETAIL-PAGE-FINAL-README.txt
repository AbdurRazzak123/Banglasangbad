FINAL DETAILS FLOW

1. Index/category six cards and right-side latest headlines open news/details page.
2. Details page is cloned from the Home layout and contains four ad slots: TOP, MIDDLE TOP (directly below headline), MIDDLE BOTTOM, BOTTOM.
3. Every details-page six-card and right-side headline links to its own category page with ?news=ID.
4. Category page reads ?news=ID and opens that complete article inside the main container; it is not overwritten by the category newest article.
5. News images use local GitHub media first, with raw-GitHub/Drive fallback logic.
6. Google Sheet data is synced to GitHub news-data.json by the existing GitHub Action; the browser does not depend on a direct Google Sheet request.
