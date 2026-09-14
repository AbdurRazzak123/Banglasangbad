import json, os, re, urllib.parse, urllib.request
from pathlib import Path

SHEET_ID = os.environ.get("NEWS_SHEET_ID", "1gX73WskIs3D-8IcyPJ24NT0xn1KIEJSjMXOF9nCQqTg")
SHEET_NAME = os.environ.get("NEWS_SHEET_NAME", "Bangla News")

url = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
    f"?tqx=out:json&sheet={urllib.parse.quote(SHEET_NAME)}"
    f"&tq={urllib.parse.quote('select *')}"
)

req = urllib.request.Request(url, headers={"User-Agent": "Banglasangbad-Preflight/1.0"})
with urllib.request.urlopen(req, timeout=45) as r:
    raw = r.read().decode("utf-8")

m = re.search(r"google\.visualization\.Query\.setResponse\((.*)\);?\s*$", raw, re.S)
if not m:
    raise SystemExit("ERROR: Google Sheet response could not be parsed.")

data = json.loads(m.group(1))
rows = data.get("table", {}).get("rows", [])

if not rows:
    raise SystemExit(f"ERROR: Sheet '{SHEET_NAME}' returned zero rows.")

valid = []
for n, row in enumerate(rows, 1):
    c = row.get("c", [])
    def cell(i):
        return str(c[i].get("v", "") if i < len(c) and c[i] else "").strip()
    ident, headline = cell(0), cell(2)
    if ident and headline:
        valid.append((ident, headline))

if not valid:
    raise SystemExit(
        "ERROR: Google Sheet returned rows, but no row contains both ID (column A) "
        "and Headline (column C). Check the sheet name and column order."
    )

print(f"Google Sheet OK: {len(rows)} rows received; {len(valid)} valid news rows.")
print("First valid ID:", valid[0][0])
print("First valid headline:", valid[0][1][:100])
