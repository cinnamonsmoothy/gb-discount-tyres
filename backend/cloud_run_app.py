"""Cloud Run API for registration-to-possible-tyre-sizes lookup."""

import os
import re

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fitmentx_lookup import FitmentLookupError, get_vehicle_fitment

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # GitHub Pages or a future custom domain can call this public endpoint.
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
PLATE_URL = "https://mycarplate.online/api/v1/vehicle"


class RegistrationRequest(BaseModel):
    registration: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/vehicle")
def vehicle_lookup(body: RegistrationRequest):
    registration = re.sub(r"\s+", "", body.registration).upper()
    if not re.fullmatch(r"[A-Z0-9]{2,8}", registration):
        raise HTTPException(400, "Enter a valid UK registration.")

    key = os.getenv("MYCARPLATE_API_KEY")
    if not key:
        raise HTTPException(503, "Registration lookup is not configured.")

    try:
        response = requests.get(
            PLATE_URL,
            params={"plate": registration, "country": "UK"},
            headers={"X-API-Key": key, "Accept": "application/json"},
            timeout=(5, 12),
        )
        plate = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(502, "Registration lookup is temporarily unavailable.") from exc

    if response.status_code == 404:
        raise HTTPException(404, "No vehicle was found for that registration.")
    if response.status_code == 429:
        raise HTTPException(429, "The registration lookup limit has been reached.")
    if not response.ok or plate.get("success") is False:
        raise HTTPException(502, "Registration lookup is temporarily unavailable.")

    car = plate.get("data") or {}
    make = str(car.get("make") or "").strip()
    model = str(car.get("model") or "").strip()
    year = str(car.get("year") or "").strip()
    version = str(car.get("version") or "").strip()
    result = {
        "registration": registration,
        "make": make,
        "model": model,
        "year": year,
        "version": version,
        "selectedTrim": "",
        "trims": [],
        "fitments": [],
        "fitmentSource": "SIZE NOT CONFIRMED",
        "fitmentMessage": "We found your car, but could not check possible tyre sizes. Confirm the size on the tyre sidewall or call us.",
    }

    if not make or not model or not re.fullmatch(r"\d{4}", year):
        return result

    try:
        fitment = get_vehicle_fitment(make, model, int(year))
    except (FitmentLookupError, LookupError, ValueError):
        return result

    sizes = fitment.get("oe_tyre_sizes") or []
    if sizes:
        result["fitments"] = sizes
        result["fitmentSource"] = "MODEL-YEAR OPTIONS"
        result["fitmentMessage"] = (
            "Possible OE sizes for this model and year across trims and markets. "
            "This does not confirm the size fitted to your car. Check the tyre sidewall before ordering."
        )
    return result
