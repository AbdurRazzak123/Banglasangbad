# Google Sheet → GitHub → Website

This package keeps the existing website HTML/CSS/layout and changes only the data path.

Flow:
Google Sheet → GitHub Actions (every 5 minutes) → `news-data.json` / `ads-data.json` → Website

- News keeps the Sheet row order and all 10 columns.
- Ads keeps the Sheet rows and existing ad-position logic.
- Public Google Drive images are copied into `news-media/` when GitHub Actions can download them; otherwise the original image URL is retained.
- The website does not request the Google Sheet directly.
- The existing `news/` article generation and sitemap behavior is retained.

Upload the **contents of this package directly into the repository root** (do not create an extra `test-1` folder).
