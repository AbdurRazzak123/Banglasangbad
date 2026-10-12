# Facebook Publish Diagnostic (read-only)

This workflow checks the website/article/image URLs, Meta Page token and Page ID, selected permission statuses, existing post metadata (when a post ID is supplied), and an unauthenticated request to the post permalink (when a post URL is supplied or returned by the Graph API).

It does **not** publish, edit, delete, or comment on anything. It never prints the access token.

## Run it

1. Upload `tools/facebook_diagnostic.py` and `.github/workflows/facebook-diagnostic.yml` to the same paths in the `Banglasangbad` GitHub repository. You can also upload `FACEBOOK-DIAGNOSTIC-README.md` for reference.
2. Open **Actions → Facebook Publish Diagnostic (Read Only) → Run workflow**.
3. Enter `25` in `news_id` if you want to test news 25.
4. Paste the exact URL of the affected Facebook post into `post_url` (recommended). If you know the Graph API post ID, enter it in `post_id` too. A news article ID is not a Facebook post ID.
5. Run the workflow and read the log output.

The workflow expects these existing GitHub secrets: `META_PAGE_ID` and `META_PAGE_ACCESS_TOKEN`. Optional repository variable: `SITE_BASE_URL`.

## Reading the public visibility result

The script fetches the permalink without an access token or login cookies. A login wall, error response, or Facebook interstitial means public visibility was **not confirmed**; it does not by itself prove the post is private because Facebook can block automated requests. An HTTP 200 response is only a positive signal, not absolute proof. If the result is inconclusive, open the same permalink in a private/incognito browser or ask someone who is not an admin of the Page to open it.
