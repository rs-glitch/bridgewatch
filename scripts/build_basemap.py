"""Build the built-in basemap used when no tile server is reachable (e.g. the hosted page).

    uv run python scripts/build_basemap.py

Sources (downloaded to data/basemap_src/ on first run):
- US Census state and county boundaries via us-atlas 3.0.1 (ISC licence, Census data is public domain)
- Natural Earth 1:10m roads, rivers, lakes and populated places (public domain)

Writes web/basemap/{us_states,counties,roads,water,places}.geojson with coordinates rounded to 0.001° (about 100 m).
"""

import itertools
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "data" / "basemap_src", ROOT / "web" / "basemap"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
SOURCES = {
    "states-10m.json": "https://unpkg.com/us-atlas@3.0.1/states-10m.json",
    "counties-10m.json": "https://unpkg.com/us-atlas@3.0.1/counties-10m.json",
    **{f"{n}.geojson": f"{NE}{n}.geojson" for n in ("ne_10m_roads", "ne_10m_rivers_lake_centerlines", "ne_10m_rivers_north_america",
                                                   "ne_10m_lakes", "ne_10m_lakes_north_america", "ne_10m_populated_places_simple")},
}
# US incl. Alaska, Hawaii, Puerto Rico; rivers and lakes outside it are dropped
BBOX = (-180.0, 15.0, -60.0, 72.0)
DP = 3


def fetch(name):
    path = SRC / name
    if not path.exists():
        SRC.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SOURCES[name], path)
    return json.loads(path.read_text())


def line(pts):
    out = []
    for x, y in pts:
        p = [round(x, DP), round(y, DP)]
        if not out or p != out[-1]:
            out.append(p)
    return out


def polygon(rings):
    """Rounded rings, dropping any that collapse below a triangle; empty if the outer ring collapses."""
    out = [line(r) for r in rings]
    return [] if len(out[0]) < 4 else [r for r in out if len(r) >= 4]


def round_geom(g):
    """Round to DP decimals; return None when nothing drawable is left."""
    t, c = g["type"], g["coordinates"]
    if t == "LineString":
        c = line(c)
        c = c if len(c) > 1 else []
    elif t == "MultiLineString":
        c = [r for r in (line(r) for r in c) if len(r) > 1]
    elif t == "Polygon":
        c = polygon(c)
    elif t == "MultiPolygon":
        c = [q for q in (polygon(p) for p in c) if q]
    return {"type": t, "coordinates": c} if c else None


def coords(g):
    c = g["coordinates"]
    if g["type"] == "Point":
        yield c
    elif g["type"] == "LineString":
        yield from c
    elif g["type"] in ("MultiLineString", "Polygon"):
        for r in c:
            yield from r
    else:
        for p in c:
            for r in p:
                yield from r


def in_bbox(g):
    return any(BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3] for x, y in coords(g))


def topo_features(topo, obj):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for a in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx
            y += dy
            pts.append([x * sx + tx, y * sy + ty])
        arcs.append(pts)

    def ring(ids):
        out = []
        for i in ids:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            out += a if not out else a[1:]
        return out

    for g in topo["objects"][obj]["geometries"]:
        if g["type"] == "Polygon":
            c = [ring(r) for r in g["arcs"]]
        elif g["type"] == "MultiPolygon":
            c = [[ring(r) for r in p] for p in g["arcs"]]
        else:
            continue
        yield g["id"], g.get("properties", {}), {"type": g["type"], "coordinates": c}


def label_point(geom):
    """Area-weighted centroid of the largest outer ring."""
    rings = [geom["coordinates"][0]] if geom["type"] == "Polygon" else [p[0] for p in geom["coordinates"]]
    best, best_a = None, 0.0
    for r in rings:
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in itertools.pairwise(r):
            k = x0 * y1 - x1 * y0
            a += k
            cx += (x0 + x1) * k
            cy += (y0 + y1) * k
        if abs(a) > best_a:
            best_a, best = abs(a), [round(cx / (3 * a), DP), round(cy / (3 * a), DP)]
    return best


def write(name, features):
    path = OUT / f"{name}.geojson"
    features = drawable(features)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"{path.relative_to(ROOT)}: {len(features):,} features, {path.stat().st_size / 2**20:.1f} MB")


def feat(geom, **props):
    return {"type": "Feature", "properties": props, "geometry": round_geom(geom)}


def drawable(features):
    return [f for f in features if f["geometry"]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write("us_states", [feat(g, fips=i, name=p["name"]) for i, p, g in topo_features(fetch("states-10m.json"), "states")])

    counties = list(topo_features(fetch("counties-10m.json"), "counties"))
    write("counties", [feat(g, fips=i) for i, _, g in counties])

    roads = [f for f in fetch("ne_10m_roads.geojson")["features"]
             if f["properties"]["sov_a3"] == "USA" and f["properties"]["type"] != "Ferry Route"]
    write("roads", [feat(f["geometry"], kind="interstate" if f["properties"]["level"] == "Interstate" else
                         "major" if f["properties"]["type"] in ("Major Highway", "Beltway") else "minor",
                         ref=(f["properties"].get("label") or "").strip()) for f in roads])

    water = []
    for src in ("ne_10m_lakes.geojson", "ne_10m_lakes_north_america.geojson"):
        water += [feat(f["geometry"], kind="lake") for f in fetch(src)["features"] if in_bbox(f["geometry"])]
    for src in ("ne_10m_rivers_lake_centerlines.geojson", "ne_10m_rivers_north_america.geojson"):
        water += [feat(f["geometry"], kind="river", rank=f["properties"].get("scalerank") or 10)
                  for f in fetch(src)["features"] if f["geometry"] and in_bbox(f["geometry"])]
    write("water", water)

    places = [{"type": "Feature", "properties": {"name": p["name"], "kind": "city", "minzoom": round(p["min_zoom"], 1),
                                                  "pop": p["pop_max"]},
               "geometry": {"type": "Point", "coordinates": [round(p["longitude"], DP), round(p["latitude"], DP)]}}
              for p in (f["properties"] for f in fetch("ne_10m_populated_places_simple.geojson")["features"])
              if p["adm0_a3"] == "USA"]
    places += [{"type": "Feature", "properties": {"name": p.get("name", ""), "kind": "county", "minzoom": 7.5},
                "geometry": {"type": "Point", "coordinates": label_point(g)}} for _, p, g in counties if p.get("name")]
    write("places", places)


if __name__ == "__main__":
    main()
