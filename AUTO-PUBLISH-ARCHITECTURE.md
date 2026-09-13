# বাংলা সংবাদ — Auto Publish + Social + Search (Final Architecture)

## 1. Final flow

Google Sheet → `generate_static_news.py` → `news/<ID>.html` → GitHub Pages → `auto-publish.yml` → Facebook Page + Instagram + X + YouTube.

The website remains static and fast. API secrets are **never** stored in HTML/JavaScript or the public repository; GitHub Actions Secrets are used for publishing credentials.

## 2. What is already included

- Responsive detail pages with four ad slots preserved.
- Detail-page Search UI using `news-data.json`.
- Facebook/X/WhatsApp/Telegram/share/copy controls.
- Automatic injection of `detail-tools.js` for future generated news pages.
- `automation/auto_publish.py` for platform publishing.
- `.github/workflows/auto-publish.yml` for automatic publishing after new news pages are generated.
- `social-publish-state.json` to prevent duplicate posts and allow retry per platform.
- Optional `automation/video_generator.py` for a simple 16:9 MP4 from the article image/title so a new article can also become a YouTube video.

## 3. Duplicate protection

The current News 2–31 pages are seeded as `skipped_existing`, so the first GitHub Actions run will **not** blast the existing 30 articles onto social media.

When a new Sheet row creates News 32, it is not in the state file, so the publisher processes it once. A platform failure is recorded separately and can be retried without reposting platforms that already succeeded.

## 4. Required GitHub Actions Secrets

Set these in **Repository → Settings → Secrets and variables → Actions**.

### Facebook Page / Instagram
- `META_PAGE_ID`
- `META_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`

The Instagram publisher expects a public featured-image URL and an eligible Instagram professional account connected to the Meta setup.

### X
- `X_ACCESS_TOKEN`

The token must be authorized for posting with the X API. The code uses the X API v2 post endpoint.

### YouTube
- `YOUTUBE_ACCESS_TOKEN`

This must be an OAuth 2.0 access token authorized for YouTube upload. For long-running automation, use a refresh-token based OAuth flow to obtain fresh access tokens rather than storing a short-lived token permanently.

YouTube only publishes when `social-video/<NEWS_ID>.mp4` exists. If it does not, the state records `waiting_for_video` instead of pretending that a text article is a YouTube video.

## 5. Optional GitHub Actions Variables

- `META_GRAPH_VERSION` — set the Meta Graph API version you have approved for your app.
- `YOUTUBE_PRIVACY_STATUS` — normally `public`, but start with `private`/`unlisted` while testing.
- `AUTO_YOUTUBE_VIDEO` — `true` to generate the simple 16:9 article video automatically.

## 6. First test — safe mode

Run **Actions → Auto Publish - Facebook Instagram X YouTube → Run workflow** with `dry_run=true`.

This validates the article payload without posting.

Then use a real new test article (e.g. News 32) and enable only the platforms you have authorized.

## 7. Important YouTube rule

YouTube's official Data API uses OAuth for write operations, and `videos.insert` uploads an actual video file. Google currently notes that uploads from unverified API projects created after 28 July 2020 are restricted to private viewing until the project passes the required audit. See the official documentation before switching automated uploads to public.

## 8. Security rules

Never put any access token, refresh token, client secret, password, or cookie in:
- HTML
- `detail-tools.js`
- `news-data.json`
- `ads-data.json`
- Google Sheet public cells
- this repository's committed files

Use GitHub Actions Secrets instead.
