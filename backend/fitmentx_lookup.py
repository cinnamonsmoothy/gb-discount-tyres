"""One-request FitmentX vehicle-year lookup.

Run in IDLE/F5 (defaults to Peugeot 107, 2008):
    python fitmentx_lookup.py

Run for another vehicle:
    python fitmentx_lookup.py toyota yaris 2009

Run as HTTP API (suitable for Cloud Run):
    uvicorn fitmentx_lookup:app --host 0.0.0.0 --port 8080
    GET http://localhost:8080/fitment?make=toyota&model=yaris&year=2009

Requires: pip install requests beautifulsoup4 fastapi uvicorn

Important: Parses public year-level summaries, NOT individually verified trim data.
This is a wrapper around the HTML page, not FitmentX's official API.
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query

BASE_URL = "https://www.fitmentx.com/vehicles"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
PROXY_HOST = "brd.superproxy.io:44445"
PROXY_USER = "brd-customer-hl_24c9fd95-zone-data_center"

app = FastAPI(title="Vehicle Tyre & Wheel Lookup", version="1.0")


class FitmentLookupError(Exception):
    """A fitment page was inaccessible or did not contain expected data."""


def proxy_settings() -> dict[str, str] | None:
    """Use the local Bright Data password when present; never put it in source code."""
    password = os.environ.get("BRIGHTDATA_PROXY_PASSWORD")
    if not password:
        env_file = Path(__file__).with_name(".env.local")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("BRIGHTDATA_PROXY_PASSWORD="):
                    password = line.partition("=")[2].strip()
                    break
    if not password:
        return None
    proxy = f"http://{PROXY_USER}:{quote(password, safe='')}@{PROXY_HOST}"
    return {"http": proxy, "https": proxy}


def slug(value: str) -> str:
    """Converts 'Land Rover' -> 'land-rover'; '107' -> '107'."""
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold().strip()).strip("-")
    if not result:
        raise ValueError("Make and model must not be empty")
    return result


def first_match(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_vehicle_html(html: str, make: str, model: str, year: int, url: str) -> dict[str, Any]:
    """Extract only the vehicle-year summary (not footer or unrelated tyres)."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    text = main.get_text(" ", strip=True)
    title = soup.title.get_text(" ", strip=True) if soup.title else None

    if "factory tire sizes" not in text.lower() and "factory / oe tire sizes" not in text.lower():
        raise FitmentLookupError("Expected tyre-fitment summary not found (page changed or challenge served)")

    # Restrict tyre matching to the labelled *Factory / OE tire sizes* section.
    # This prevents mistakenly capturing unrelated sizes from the footer.
    tyre_section = first_match(
        r"Factory\s*/\s*OE\s+tire\s+sizes\s*(.*?)(?:Exact availability varies|Wheel specifications|Configuration summaries)",
        text,
        re.IGNORECASE | re.DOTALL,
    ) or ""

    tyre_re = re.compile(r"\b(\d{3})\s*/\s*(\d{2,3})\s*(ZR|R)\s*(\d{2}(?:\.\d)?)\b", re.IGNORECASE)
    tyre_sizes = sorted({
        f"{m.group(1)}/{m.group(2)}{m.group(3).upper()}{m.group(4)}"
        for m in tyre_re.finditer(tyre_section)
    })

    # Only use the summary wheel-specifications section; do not harvest unrelated footer labels.
    wheel_section = first_match(
        r"Wheel specifications\s*(.*?)(?:Configuration summaries|Filter by region|Choose generation|Choose trim|Browse model years)",
        text,
        re.IGNORECASE | re.DOTALL,
    ) or ""

    pcd = first_match(r"Bolt pattern\s*/\s*PCD\s*(\d{1,2}\s*[x×]\s*\d{2,3}(?:\.\d+)?)", wheel_section)
    if pcd:
        pcd = re.sub(r"\s*[x×]\s*", "x", pcd)
    centre_bore = first_match(r"Cent(?:er|re) bore\s*(\d+(?:\.\d+)?)", wheel_section)
    thread = first_match(r"Thread size\s*(M\s*\d+\s*[x×]\s*\d+(?:\.\d+)?)", wheel_section)
    if thread:
        thread = re.sub(r"\s*[x×]\s*", " x ", thread).replace("M ", "M")

    trim_count = first_match(r"(\d+)\s+trim\s*/\s*market records", text)
    fitment_count = first_match(r"(\d+)\s+fitment rows", text)
    market_count = first_match(r"(\d+)\s+market filters available", text)

    # These fields cover *potential* OE sizes for a model/year, not a trim-specific guarantee.
    return {
        "make": make,
        "model": model,
        "year": year,
        "oe_tyre_sizes": tyre_sizes,
        "pcd": pcd,
        "centre_bore_mm": float(centre_bore) if centre_bore else None,
        "thread_size": thread,
        "trim_market_records": int(trim_count) if trim_count else None,
        "advertised_fitment_rows": int(fitment_count) if fitment_count else None,
        "market_count": int(market_count) if market_count else None,
        "page_title": title,
        "source_url": url,
        "scope": "vehicle_year_summary",
        "exact_trim_verified": False,
        "warning": "Tyre sizes can vary by trim, market and front/rear configuration. Verify the vehicle's fitted tyre size before sale.",
    }


def get_vehicle_fitment(make: str, model: str, year: int) -> dict[str, Any]:
    """Exactly ONE outgoing HTTP GET per lookup, using requests (no Selenium)."""
    if not 1885 <= year <= 2100:
        raise ValueError("Year must be between 1885 and 2100")
    make_slug, model_slug = slug(make), slug(model)
    url = f"{BASE_URL}/{make_slug}/{model_slug}/{year}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=(5, 20), proxies=proxy_settings())
    except requests.RequestException as exc:
        raise FitmentLookupError(f"Could not fetch vehicle page: {exc}") from exc

    if response.status_code == 404:
        raise LookupError(f"No vehicle-year page found for {make} {model} {year}")
    if response.status_code in (401, 403, 429):
        raise FitmentLookupError(f"Source declined the request (HTTP {response.status_code})")
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise FitmentLookupError(f"Source returned HTTP {response.status_code}") from exc

    return parse_vehicle_html(response.text, make_slug, model_slug, year, url)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/fitment")
def fitment(
    make: str = Query(..., min_length=1),
    model: str = Query(..., min_length=1),
    year: int = Query(..., ge=1885, le=2100),
) -> dict[str, Any]:
    try:
        return get_vehicle_fitment(make, model, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FitmentLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Look up one make/model/year using one HTTP GET")
    parser.add_argument("make", nargs="?", default="peugeot")
    parser.add_argument("model", nargs="?", default="107")
    parser.add_argument("year", nargs="?", type=int, default=2008)
    args = parser.parse_args()

    print(f"Fetching {args.year} {args.make} {args.model}...", flush=True)
    try:
        print(json.dumps(get_vehicle_fitment(args.make, args.model, args.year), indent=2), flush=True)
    except (ValueError, LookupError, FitmentLookupError) as exc:
        print(f"ERROR: {exc}", flush=True)
