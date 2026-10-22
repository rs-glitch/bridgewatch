import io
import zipfile

import polars as pl

from bridgewatch import panel

HEADER = list(panel.COLUMNS)


def _row(**over):
    base = dict.fromkeys(HEADER, "")
    base.update({"STATE_CODE_001": "19", "STRUCTURE_NUMBER_008": "000000000001234", "RECORD_TYPE_005A": "1",
                 "LAT_016": "41353000", "LONG_017": "093370000", "DECK_COND_058": "7", "SUPERSTRUCTURE_COND_059": "6",
                 "SUBSTRUCTURE_COND_060": "5", "CULVERT_COND_062": "N", "ADT_029": "000350", "STRUCTURE_LEN_MT_049": "20",
                 "DECK_WIDTH_MT_052": "8.5", "OPEN_CLOSED_POSTED_041": "A", "OWNER_022": "02", "STRUCTURE_TYPE_043B": "2"})
    base["FEATURES_DESC_006A"] = "'MILL CREEK              '"
    base.update(over)
    return base


def _file(rows, extra_text="'500' SO GUADALUPE RD     '"):
    # mimic the NBI layout: quoted free-text field with a stray apostrophe inside it
    head = ",".join([*HEADER, "EXTRA_FREE_TEXT"])
    lines = [head] + [",".join([*(r[c] for c in HEADER), extra_text]) for r in rows]
    return ("\n".join(lines) + "\n").encode("latin-1")


def test_dms_conversion():
    df = pl.DataFrame({"lat_raw": ["41353000", "00000000", ""], "lon_raw": ["093370000", "000000000", ""]})
    out = df.select(panel._dms("lat_raw", 2).alias("lat"), (-panel._dms("lon_raw", 3)).alias("lon"))
    assert abs(out["lat"][0] - (41 + 35 / 60 + 30 / 3600)) < 1e-9
    assert abs(out["lon"][0] + (93 + 37 / 60)) < 1e-9
    assert out["lat"][1] is None and out["lon"][2] is None


def test_type_panel_derives_condition_and_filters_record_type():
    rows = [_row(), _row(STRUCTURE_NUMBER_008="X2", DECK_COND_058="4"), _row(STRUCTURE_NUMBER_008="X3", RECORD_TYPE_005A="2")]
    df, bad = panel._read_state_file(_file(rows))
    assert bad == 0
    out = panel.type_panel(df, 2015)
    assert out.height == 2  # the record type 2 row is a route under the bridge, not a bridge
    first = out.row(0, named=True)
    assert first["bridge_id"] == "19-000000000001234"
    assert first["lowest_rating"] == 5 and first["condition"] == "Fair"
    assert first["culvert"] is None and first["adt"] == 350 and first["owner"] == "2"
    assert abs(first["deck_area_m2"] - 170.0) < 1e-9
    assert first["crosses"] == "MILL CREEK"
    assert out.row(1, named=True)["condition"] == "Poor"


def test_malformed_rows_are_counted_not_kept():
    good = _file([_row()])
    broken = good + b"19,short,row\n"
    df, bad = panel._read_state_file(broken)
    assert df.height == 1 and bad == 1


def test_build_year_end_to_end(tmp_path, monkeypatch):
    raw, out = tmp_path / "raw", tmp_path / "panel"
    raw.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IA15.txt", _file([_row(), _row(STRUCTURE_NUMBER_008="X2")]))
    (raw / "2015del.zip").write_bytes(buf.getvalue())
    monkeypatch.setattr(panel, "RAW", raw)
    monkeypatch.setattr(panel, "PANEL", out)
    log = panel.build_year(2015)
    assert log["bridges"] == 2 and log["with_location"] == 2
    assert pl.read_parquet(out / "nbi_2015.parquet")["year"].unique().to_list() == [2015]
