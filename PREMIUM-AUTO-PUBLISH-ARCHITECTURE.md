# Bangla Sangbad — Premium Social Publishing Architecture

## Scope
Production workflow is intentionally limited to Facebook Page + Instagram Business Account.

## Guarantees implemented in code
- Google Sheet remains the source of news records.
- A generated `/news/<id>.html` page is checked before social publishing.
- Social images are committed and publicly checked before Meta publishing.
- Facebook post text contains the exact article URL only.
- No Facebook comment is created.
- Instagram never receives a website URL.
- Instagram long articles automatically use a carousel so the Details field is not silently truncated by the caption limit.
- Per-platform state prevents successful platforms from being republished.
- Existing Facebook post IDs are reused when a previous run already created the post but failed afterward.
- Instagram containers are waited on until they are publishable.
- Meta credentials are validated before any article is attempted.
- Git state is pushed with fetch/rebase/push retries to reduce concurrent workflow races.

## Secrets
- `META_PAGE_ID`
- `META_PAGE_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ACCOUNT_ID`

## Variables
- `SITE_BASE_URL`
- `META_GRAPH_VERSION`

No credential is committed to the repository.
