"""One-shot seeder for us_zip_codes.

Downloads the GeoNames US postal-code dataset (public domain, CC-BY) and bulk-inserts
it into Supabase. Safe to re-run — uses upsert on zip.

Usage:
    python -m app.db.seed_zips
"""
from __future__ import annotations

import io
import sys
import zipfile
from typing import Iterator

import httpx

from app.db.supabase_client import get_supabase

SOURCE_URL = "https://download.geonames.org/export/zip/US.zip"
BATCH_SIZE = 1000


def _parse_rows(data: bytes) -> Iterator[dict]:
    """GeoNames US.txt is tab-delimited, no header.

    Columns (per geonames readme.txt for postal codes):
        0  country_code
        1  postal_code
        2  place_name (city)
        3  admin_name1 (state name)
        4  admin_code1 (state abbr)
        5  admin_name2 (county)
        6  admin_code2
        7  admin_name3
        8  admin_code3
        9  latitude
        10 longitude
        11 accuracy
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("US.txt") as fh:
            for line in io.TextIOWrapper(fh, encoding="utf-8"):
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 11:
                    continue
                try:
                    lat = float(parts[9]) if parts[9] else None
                    lng = float(parts[10]) if parts[10] else None
                except ValueError:
                    lat = lng = None
                yield {
                    "zip": parts[1],
                    "city": parts[2] or None,
                    "state": parts[3] or None,
                    "state_abbr": parts[4] or None,
                    "lat": lat,
                    "lng": lng,
                }


def _chunks(iterable, size):
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def main() -> int:
    print(f"Downloading {SOURCE_URL} ...", flush=True)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(SOURCE_URL)
        resp.raise_for_status()

    sb = get_supabase()
    total = 0
    for batch in _chunks(_parse_rows(resp.content), BATCH_SIZE):
        sb.table("us_zip_codes").upsert(batch, on_conflict="zip").execute()
        total += len(batch)
        print(f"  seeded {total} zips...", flush=True)

    print(f"Done. {total} rows upserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
