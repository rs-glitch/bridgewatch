"""Cost inputs for Q2 (repair / replace / close).

Replacement unit cost ($/ft² of deck area) by state and system (NHS / non-NHS): FHWA "Bridge Replacement Unit Costs 2025"
(https://www.fhwa.dot.gov/bridge/nbi/sd2025.cfm), column "Cost Used For 2025 Estimates". FHWA's own table assumes
rehabilitation costs 68% of replacement; we use the same ratio. Missing states fall back to the national median.

Detour cost per vehicle-mile = operating cost + time cost at an assumed detour speed. Federal values (2024 dollars) as listed in
Caltrans' "Cal-B/C federal comparison of value matrix 2026", which reproduces USDOT BCA guidance:
  light-duty operating cost $0.505/mi, commercial truck $1.23/mi, all-purpose travel time $29.15 per vehicle-hour,
  truck travel time $37.20 per vehicle-hour.
[verify against the USDOT Benefit-Cost Analysis Guidance 2025 Update before quoting outside this repo]
"""

import html
import json
import re
import urllib.request
from statistics import median

from .paths import DATA, RAW

UNIT_COST_URL = "https://www.fhwa.dot.gov/bridge/nbi/sd2025.cfm"
UNIT_COSTS = DATA / "unit_costs_2025.json"
REHAB_SHARE = 0.68
M2_TO_FT2 = 10.7639

DETOUR = {
    "car_cost_per_mile": 0.505, "truck_cost_per_mile": 1.23,
    "car_time_value_per_hour": 29.15, "truck_time_value_per_hour": 37.20,
    "detour_speed_mph": 40.0,  # assumption: rural/collector detour roads
    "dollar_year": 2024,
}

STATE_FIPS = {"Alabama": "01", "Alaska": "02", "Arizona": "04", "Arkansas": "05", "California": "06", "Colorado": "08",
              "Connecticut": "09", "Delaware": "10", "District of Columbia": "11", "Florida": "12", "Georgia": "13", "Hawaii": "15",
              "Idaho": "16", "Illinois": "17", "Indiana": "18", "Iowa": "19", "Kansas": "20", "Kentucky": "21", "Louisiana": "22",
              "Maine": "23", "Maryland": "24", "Massachusetts": "25", "Michigan": "26", "Minnesota": "27", "Mississippi": "28",
              "Missouri": "29", "Montana": "30", "Nebraska": "31", "Nevada": "32", "New Hampshire": "33", "New Jersey": "34",
              "New Mexico": "35", "New York": "36", "North Carolina": "37", "North Dakota": "38", "Ohio": "39", "Oklahoma": "40",
              "Oregon": "41", "Pennsylvania": "42", "Rhode Island": "44", "South Carolina": "45", "South Dakota": "46",
              "Tennessee": "47", "Texas": "48", "Utah": "49", "Vermont": "50", "Virginia": "51", "Washington": "53",
              "West Virginia": "54", "Wisconsin": "55", "Wyoming": "56", "Puerto Rico": "72"}


def _num(s: str):
    s = s.replace(",", "").replace("$", "").strip()
    return float(s) if re.fullmatch(r"\d+(\.\d+)?", s) else None


def fetch_unit_costs() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    src = RAW / "sd2025.html"
    if not src.exists():
        req = urllib.request.Request(UNIT_COST_URL, headers={"User-Agent": "bridgewatch/0.1"})
        src.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    page = src.read_text(encoding="utf-8", errors="ignore")
    out = {"source": UNIT_COST_URL, "rehab_share": REHAB_SHARE, "nhs": {}, "non_nhs": {}}
    for system, table in zip(("nhs", "non_nhs"), re.findall(r"<table.*?</table>", page, re.S)[:2], strict=True):
        for row in re.findall(r"<tr.*?</tr>", table, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[hd].*?</t[hd]>", row, re.S)]
            if len(cells) >= 7 and cells[0] in STATE_FIPS and _num(cells[6]):
                out[system][STATE_FIPS[cells[0]]] = _num(cells[6])  # "Cost Used For 2025 Estimates", $/ft²
    for system in ("nhs", "non_nhs"):
        out[f"{system}_national_median"] = median(out[system].values())
    UNIT_COSTS.write_text(json.dumps(out, indent=1))
    return out


def unit_costs() -> dict:
    return json.loads(UNIT_COSTS.read_text()) if UNIT_COSTS.exists() else fetch_unit_costs()


def replacement_cost(state_code: str, nhs: bool, deck_area_m2: float, uc: dict | None = None) -> float:
    uc = uc or unit_costs()
    system = "nhs" if nhs else "non_nhs"
    per_ft2 = uc[system].get(state_code, uc[f"{system}_national_median"])
    return per_ft2 * deck_area_m2 * M2_TO_FT2


def detour_cost_per_day(adt: float, detour_km: float, truck_pct: float) -> float:
    """Extra user cost per day if the bridge is closed: every crossing drives the detour instead."""
    miles = detour_km / 1.609344
    hours = miles / DETOUR["detour_speed_mph"]
    t = min(max(truck_pct or 0, 0), 100) / 100
    per_vehicle = ((1 - t) * (DETOUR["car_cost_per_mile"] * miles + DETOUR["car_time_value_per_hour"] * hours)
                   + t * (DETOUR["truck_cost_per_mile"] * miles + DETOUR["truck_time_value_per_hour"] * hours))
    return max(adt or 0, 0) * per_vehicle
