import polars as pl

from bridgewatch import linking


def _rec(bid, year, **kw):
    r = {"bridge_id": bid, "structure_number": bid.split("-")[1], "year": year, "state_code": "45", "county_code": "001",
         "year_built": 1960, "material": "1", "design_type": "04", "main_spans": 2, "length_m": 18.3, "deck_width_m": 9.6,
         "lat": 34.0, "lon": -81.0, "lowest_rating": 6}
    return r | kw


def _run(tmp_path, rows):
    df = pl.DataFrame(rows)
    for y in df["year"].unique():
        df.filter(pl.col("year") == y).write_parquet(tmp_path / f"nbi_{y}.parquet")
    stats = linking.build_links(tmp_path, tmp_path / "links.parquet", tmp_path / "map.parquet")
    m = dict(pl.read_parquet(tmp_path / "map.parquet").iter_rows())
    return stats, m


def test_renumbering_is_linked_and_replacement_is_not(tmp_path):
    rows = [
        # renumbered with identical description
        _rec("45-A1", 2004), _rec("45-A1", 2005), _rec("45-Z9", 2006), _rec("45-Z9", 2007),
        # padding change only
        _rec("45-0087", 2004, lat=34.5, length_m=40.0), _rec("45-0087", 2005, lat=34.5, length_m=40.0),
        _rec("45-00087", 2006, lat=34.5, length_m=40.0),
        # replaced: same spot, new structure built in the transition year, wider -> must NOT link
        _rec("45-OLD", 2004, lat=35.0, length_m=61.3, deck_width_m=14.2), _rec("45-OLD", 2005, lat=35.0, length_m=61.3, deck_width_m=14.2),
        _rec("45-NEW", 2006, lat=35.0, length_m=66.4, deck_width_m=26.2, year_built=2005),
    ]
    _, m = _run(tmp_path, rows)
    assert m["45-Z9"] == "45-A1"
    assert m["45-00087"] == "45-0087"
    assert m["45-NEW"] == "45-NEW"


def test_ambiguous_description_without_location_is_not_linked(tmp_path):
    rows = [_rec("45-A", 2004, lat=None, lon=None), _rec("45-B", 2004, lat=None, lon=None),
            _rec("45-C", 2005, lat=None, lon=None), _rec("45-D", 2005, lat=None, lon=None)]
    _, m = _run(tmp_path, rows)
    assert m["45-C"] == "45-C" and m["45-D"] == "45-D"
