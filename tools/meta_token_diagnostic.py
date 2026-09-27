from __future__ import annotations

import os
import sys
import json
import requests


META_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
META_BASE = f"https://graph.facebook.com/{META_VERSION}"


def get_json(url, params):
    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw_response": response.text[:2000]
            }

        return response.status_code, data

    except requests.RequestException as exc:
        return None, {
            "request_error": str(exc)
        }


def print_result(title, status, data):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    if status == 200:
        print("STATUS: OK")
    elif status is None:
        print("STATUS: REQUEST FAILED")
    else:
        print(f"STATUS: FAILED (HTTP {status})")

    print(json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ))


def main():

    page_id = os.getenv("META_PAGE_ID", "").strip()
    page_token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv(
        "INSTAGRAM_BUSINESS_ACCOUNT_ID",
        ""
    ).strip()

    print("=" * 70)
    print("BANGLA SANGBAD - META TOKEN DIAGNOSTIC")
    print("=" * 70)
    print()
    print("IMPORTANT:")
    print("This diagnostic does NOT publish anything.")
    print("It only performs GET requests.")
    print()

    # ---------------------------------------------------------
    # Basic environment check
    # ---------------------------------------------------------

    print("CONFIGURATION")
    print("-" * 70)

    print(
        "META_GRAPH_VERSION:",
        META_VERSION
    )

    print(
        "META_PAGE_ID:",
        "SET" if page_id else "MISSING"
    )

    print(
        "META_PAGE_ACCESS_TOKEN:",
        "SET" if page_token else "MISSING"
    )

    print(
        "INSTAGRAM_BUSINESS_ACCOUNT_ID:",
        "SET" if ig_id else "MISSING"
    )

    if not page_token:
        print()
        print("ERROR: META_PAGE_ACCESS_TOKEN is missing.")
        sys.exit(1)

    if not page_id:
        print()
        print("ERROR: META_PAGE_ID is missing.")
        sys.exit(1)

    # ---------------------------------------------------------
    # 1. Test Page Access Token + Page ID
    # ---------------------------------------------------------

    status, data = get_json(
        f"{META_BASE}/{page_id}",
        {
            "fields": "id,name",
            "access_token": page_token,
        },
    )

    print_result(
        "1. FACEBOOK PAGE TOKEN TEST",
        status,
        data,
    )

    facebook_ok = (
        status == 200
        and isinstance(data, dict)
        and data.get("id")
    )

    # ---------------------------------------------------------
    # 2. Check token metadata / permissions
    # ---------------------------------------------------------

    status_token, token_data = get_json(
        f"{META_BASE}/debug_token",
        {
            "input_token": page_token,
            "access_token": page_token,
        },
    )

    print_result(
        "2. META TOKEN DEBUG TEST",
        status_token,
        token_data,
    )

    # ---------------------------------------------------------
    # 3. Test Instagram Business Account
    # ---------------------------------------------------------

    instagram_ok = False

    if not ig_id:
        print()
        print("=" * 70)
        print("3. INSTAGRAM BUSINESS ACCOUNT TEST")
        print("=" * 70)
        print("STATUS: SKIPPED")
        print("INSTAGRAM_BUSINESS_ACCOUNT_ID is missing.")
    else:

        status_ig, ig_data = get_json(
            f"{META_BASE}/{ig_id}",
            {
                "fields": (
                    "id,"
                    "username,"
                    "name,"
                    "profile_picture_url"
                ),
                "access_token": page_token,
            },
        )

        print_result(
            "3. INSTAGRAM BUSINESS ACCOUNT TEST",
            status_ig,
            ig_data,
        )

        instagram_ok = (
            status_ig == 200
            and isinstance(ig_data, dict)
            and ig_data.get("id")
        )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL DIAGNOSTIC RESULT")
    print("=" * 70)

    if facebook_ok:
        print("FACEBOOK PAGE TOKEN: OK")
    else:
        print("FACEBOOK PAGE TOKEN: FAILED")

    if ig_id:
        if instagram_ok:
            print("INSTAGRAM ACCOUNT ACCESS: OK")
        else:
            print("INSTAGRAM ACCOUNT ACCESS: FAILED")
    else:
        print("INSTAGRAM ACCOUNT ACCESS: NOT TESTED")

    if facebook_ok and (not ig_id or instagram_ok):
        print()
        print("META DIAGNOSTIC: PASS")
        print("No publishing action was performed.")
        sys.exit(0)

    print()
    print("META DIAGNOSTIC: FAILED")
    print("Check the error object above.")
    sys.exit(2)


if __name__ == "__main__":
    main()
