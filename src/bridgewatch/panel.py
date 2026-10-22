"""Build the bridge-year panel: one row per bridge per NBI year, typed and with derived fields.

Input: data/raw/{year}del.zip (one comma-delimited file per state, quote character "'").
Output: data/panel/nbi_{year}.parquet, plus data/panel/build_log.json with row counts per year.

Only record type 1 rows are kept (the route carried *on* the structure); type 2 rows describe routes passing under it.
The first 119 columns are identical in every year 1992-2025; the last few columns differ by year and are not used.
"""

import csv
import io
import json
import zipfile

import polars as pl

from .paths import PANEL, RAW

# Raw NBI column -> panel name. Kept as text first, typed below.
COLUMNS = {
    "STATE_CODE_001": "state_code",
    "STRUCTURE_NUMBER_008": "structure_number",
    "RECORD_TYPE_005A": "record_type",
    "COUNTY_CODE_003": "county_code",
    "FEATURES_DESC_006A": "crosses",
    "FACILITY_CARRIED_007": "carries",
    "LOCATION_009": "location_desc",
    "LAT_016": "lat_raw",
    "LONG_017": "lon_raw",
    "DETOUR_KILOS_019": "detour_km",
    "MAINTENANCE_021": "maintainer",
    "OWNER_022": "owner",
    "FUNCTIONAL_CLASS_026": "functional_class",
    "YEAR_BUILT_027": "year_built",
    "TRAFFIC_LANES_ON_028A": "lanes_on",
    "ADT_029": "adt",
    "YEAR_ADT_030": "year_adt",
    "DESIGN_LOAD_031": "design_load",
    "DEGREES_SKEW_034": "skew_deg",
    "HISTORY_037": "historic_significance",
    "OPEN_CLOSED_POSTED_041": "posting_status",
    "SERVICE_ON_042A": "service_on",
    "SERVICE_UND_042B": "service_under",
    "STRUCTURE_KIND_043A": "material",
    "STRUCTURE_TYPE_043B": "design_type",
    "MAIN_UNIT_SPANS_045": "main_spans",
    "APPR_SPANS_046": "approach_spans",
    "MAX_SPAN_LEN_MT_048": "max_span_m",
    "STRUCTURE_LEN_MT_049": "length_m",
    "DECK_WIDTH_MT_052": "deck_width_m",
    "VERT_CLR_OVER_MT_053": "vert_clr_over_m",
    "VERT_CLR_UND_REF_054A": "vert_clr_under_ref",
    "VERT_CLR_UND_054B": "vert_clr_under_m",
    "DECK_COND_058": "deck",
    "SUPERSTRUCTURE_COND_059": "superstructure",
    "SUBSTRUCTURE_COND_060": "substructure",
    "CHANNEL_COND_061": "channel",
    "CULVERT_COND_062": "culvert",
    "OPR_RATING_METH_063": "operating_rating_method",
    "OPERATING_RATING_064": "operating_rating_t",
    "INV_RATING_METH_065": "inventory_rating_method",
    "INVENTORY_RATING_066": "inventory_rating_t",
    "STRUCTURAL_EVAL_067": "structural_eval",
    "POSTING_EVAL_070": "posting_eval",
    "WATERWAY_EVAL_071": "waterway_eval",
    "WORK_PROPOSED_075A": "work_proposed",
    "IMP_LEN_MT_076": "improvement_length_m",
    "DATE_OF_INSPECT_090": "inspection_date",
    "INSPECT_FREQ_MONTHS_091": "inspection_interval_mo",
    "FRACTURE_092A": "fracture_critical_insp",
    "UNDWATER_LOOK_SEE_092B": "underwater_insp",
    "BRIDGE_IMP_COST_094": "bridge_cost_k",
    "TOTAL_IMP_COST_096": "total_cost_k",
    "YEAR_OF_IMP_097": "year_cost_estimate",
    "STRAHNET_HIGHWAY_100": "strahnet",
    "HIGHWAY_SYSTEM_104": "nhs",
    "YEAR_RECONSTRUCTED_106": "year_reconstructed",
    "DECK_STRUCTURE_TYPE_107": "deck_type",
    "SURFACE_TYPE_108A": "wearing_surface",
    "MEMBRANE_TYPE_108B": "membrane",
    "DECK_PROTECTION_108C": "deck_protection",
    "PERCENT_ADT_TRUCK_109": "truck_pct",
    "NATIONAL_NETWORK_110": "national_truck_network",
    "SCOUR_CRITICAL_113": "scour_code",
    "FUTURE_ADT_114": "future_adt",
}

TEXT = ["crosses", "carries", "location_desc"]
RATINGS = ["deck", "superstructure", "substructure", "culvert"]  # 0-9; "N" = not applicable
INTS = ["year_built", "lanes_on", "adt", "year_adt", "skew_deg", "main_spans", "approach_spans", "inspection_interval_mo",
        "bridge_cost_k", "total_cost_k", "year_cost_estimate", "year_reconstructed", "truck_pct", "future_adt"]
FLOATS = ["detour_km", "max_span_m", "length_m", "deck_width_m", "vert_clr_over_m", "vert_clr_under_m", "operating_rating_t",
          "inventory_rating_t", "improvement_length_m"]


def _read_state_file(raw: bytes) -> tuple[pl.DataFrame, int]:
    """Parse one state file. Python's csv reader is used because free-text fields (items 6A, 7, 9) sometimes contain stray
    apostrophes, which strict CSV parsers reject. Rows whose field count does not match the header are dropped and counted."""
    rows = csv.reader(io.StringIO(raw.decode("latin-1")), quotechar="'")
    header = [h.strip() for h in next(rows)]
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        raise ValueError(f"missing NBI columns: {missing[:5]}")
    idx = [header.index(c) for c in COLUMNS]
    width, cols, bad = len(header), [[] for _ in idx], 0
    for r in rows:
        if len(r) != width:
            if r:
                bad += 1
            continue
        for out, i in zip(cols, idx, strict=True):
            out.append(r[i].strip())
    df = pl.DataFrame(dict(zip(COLUMNS.values(), cols, strict=True)), schema=dict.fromkeys(COLUMNS.values(), pl.String))
    # free text is fixed-width and quoted with apostrophes; strip the padding and any stray quote marks
    return df.with_columns([pl.col(c).str.strip_chars(" '").str.replace_all(r"\s{2,}", " ") for c in TEXT]), bad


def _dms(col: str, deg_digits: int) -> pl.Expr:
    """NBI stores latitude as DDMMSSss and longitude as DDDMMSSss (hundredths of seconds). 0 or blank = unknown."""
    s = pl.col(col).str.zfill(deg_digits + 6)
    deg = s.str.slice(0, deg_digits).cast(pl.Float64, strict=False)
    mins = s.str.slice(deg_digits, 2).cast(pl.Float64, strict=False)
    secs = s.str.slice(deg_digits + 2, 4).cast(pl.Float64, strict=False) / 100
    v = deg + mins / 60 + secs / 3600
    return pl.when((v > 0) & (mins < 60) & (secs < 60)).then(v).otherwise(None)


def type_panel(df: pl.DataFrame, year: int) -> pl.DataFrame:
    df = df.filter(pl.col("record_type") == "1").drop("record_type")
    df = df.with_columns(
        pl.lit(year, pl.Int16).alias("year"),
        pl.col("state_code").str.zfill(2),
        *[pl.col(c).cast(pl.Int8, strict=False).alias(c) for c in RATINGS],
        *[pl.col(c).cast(pl.Float64, strict=False).cast(pl.Int64, strict=False).alias(c) for c in INTS],
        *[pl.col(c).cast(pl.Float64, strict=False).alias(c) for c in FLOATS],
        _dms("lat_raw", 2).alias("lat"),
        (-_dms("lon_raw", 3)).alias("lon"),  # western hemisphere
        pl.col("owner").str.strip_chars_start("0"),
        pl.col("design_type").str.zfill(2),
    ).drop("lat_raw", "lon_raw")
    df = df.with_columns(
        (pl.col("state_code") + "-" + pl.col("structure_number")).alias("bridge_id"),
        pl.min_horizontal(RATINGS).alias("lowest_rating"),
        (pl.col("length_m") * pl.col("deck_width_m")).alias("deck_area_m2"),
    ).with_columns(
        pl.when(pl.col("lowest_rating") <= 4).then(pl.lit("Poor"))
        .when(pl.col("lowest_rating") <= 6).then(pl.lit("Fair"))
        .when(pl.col("lowest_rating").is_not_null()).then(pl.lit("Good"))
        .otherwise(None).alias("condition"),
    )
    # A structure number should appear once per state per year; keep the first if a state file repeats one.
    return df.unique(subset=["bridge_id"], keep="first", maintain_order=True)


def build_year(year: int) -> dict:
    src = RAW / f"{year}del.zip"
    frames, files, bad = [], 0, 0
    with zipfile.ZipFile(src) as z:
        for name in sorted(z.namelist()):
            if name.lower().endswith(".txt"):
                df, b = _read_state_file(z.read(name))
                frames.append(df)
                files, bad = files + 1, bad + b
    raw = pl.concat(frames, how="vertical")
    out = type_panel(raw, year)
    PANEL.mkdir(parents=True, exist_ok=True)
    out.write_parquet(PANEL / f"nbi_{year}.parquet", compression="zstd")
    return {"year": year, "state_files": files, "raw_rows": raw.height, "malformed_rows_dropped": bad, "bridges": out.height,
            "with_location": int(out["lat"].is_not_null().sum()), "rated": int(out["lowest_rating"].is_not_null().sum())}


def build(years) -> list[dict]:
    log_path = PANEL / "build_log.json"
    PANEL.mkdir(parents=True, exist_ok=True)
    log = {r["year"]: r for r in (json.loads(log_path.read_text()) if log_path.exists() else [])}
    for y in years:
        log[y] = build_year(y)
        print(json.dumps(log[y]), flush=True)
        log_path.write_text(json.dumps([log[k] for k in sorted(log)], indent=1))
    return [log[k] for k in sorted(log)]
