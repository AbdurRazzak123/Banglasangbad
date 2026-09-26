from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
VERSION = os.getenv('META_GRAPH_VERSION', 'v26.0')
BASE = f'https://graph.facebook.com/{VERSION}'


def fail(message: str) -> None:
    print(f'META PREFLIGHT FAILED: {message}')
    raise SystemExit(1)


def get_json(url: str, **kwargs):
    kwargs.setdefault('timeout', 30)
    r = requests.get(url, **kwargs)
    try:
        data = r.json()
    except Exception:
        data = {'raw': r.text[:500]}
    if not r.ok:
        # Never print the token or request query string.
        raise RuntimeError(f'HTTP {r.status_code}: {data}')
    return data


def main() -> None:
    token = os.getenv('META_PAGE_ACCESS_TOKEN', '').strip()
    page_id = os.getenv('META_PAGE_ID', '').strip()
    ig_id = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID', '').strip()

    if not token:
        fail('META_PAGE_ACCESS_TOKEN is missing.')
    if not page_id:
        fail('META_PAGE_ID is missing.')
    if not ig_id:
        fail('INSTAGRAM_BUSINESS_ACCOUNT_ID is missing.')

    try:
        page = get_json(
            f'{BASE}/{page_id}',
            params={
                'fields': 'id,name,instagram_business_account',
                'access_token': token,
            },
        )
    except Exception as exc:
        fail(
            'Facebook Page validation failed. The Page access token may be expired/invalid '
            'or may not have the required Page access. Details: ' + str(exc)
        )

    if str(page.get('id', '')).strip() != page_id:
        fail('META_PAGE_ID does not match the Page returned by Meta.')

    linked_ig = str(((page.get('instagram_business_account') or {}).get('id') or '')).strip()
    if linked_ig and linked_ig != ig_id:
        fail('INSTAGRAM_BUSINESS_ACCOUNT_ID does not match the Instagram Business account linked to the configured Page.')

    try:
        ig = get_json(
            f'{BASE}/{ig_id}',
            params={
                'fields': 'id,username',
                'access_token': token,
            },
        )
    except Exception as exc:
        fail(
            'Instagram account validation failed. Check the Page token and Instagram Business account connection. '
            'Details: ' + str(exc)
        )

    if str(ig.get('id', '')).strip() != ig_id:
        fail('Instagram account ID validation failed.')

    print(f"META PREFLIGHT OK: Page={page_id}, Instagram={ig_id}, Graph={VERSION}")


if __name__ == '__main__':
    main()
