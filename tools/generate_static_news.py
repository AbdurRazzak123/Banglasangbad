#!/usr/bin/env python3

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from html import escape


# ============================================================
# CONFIG
# ============================================================

SHEET_ID = "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg"
SHEET_NAME = "Bangla News"

BASE_URL = "https://abdurrazzak123.github.io/Banglasangbad/"

ROOT = Path(__file__).resolve().parents[1]

NEWS_DIR = ROOT / "news"

NEWS_JSON = ROOT / "news-data.json"

SITEMAP_FILE = ROOT / "sitemap.xml"

NEWS_SITEMAP_FILE = ROOT / "news-sitemap.xml"


COLUMNS = [
    "ID",
    "Category",
    "Headline",
    "Details",
    "Image-1",
    "Date",
    "Video",
    "Image-2",
    "Image-3",
    "Keyword",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""

    if isinstance(value, dict):
        if "f" in value:
            value = value["f"]
