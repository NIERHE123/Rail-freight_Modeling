"""
build_distances.py - AMORE project: yard coordinates + rail distance matrix

What it does
  1. Reads the yards from AMORE_network_data.xlsx (sheet "Yards").
  2. Finds each yard's coordinates with OpenStreetMap (Nominatim geocoding),
     unless you already typed latitude/longitude into the sheet.
  3. Downloads the German railway network from OpenStreetMap with OSMnx
     (lecture 4, slides 26-27) and computes the shortest RAIL distance
     between every pair of model yards with NetworkX.
  4. Yard pairs that are not connected in the rail graph get the straight-line distance
     x the median ratio (rail km / straight-line km) of the pairs that are connected,
     so the factor comes from the data itself.
  5. Only if the rail download fails completely (or with --fallback) does it use the
     detour factor from the Assumptions sheet. That factor has no source: use those
     distances for quick tests only, not for results in the report.

Output
  yard_coordinates.csv       one row per yard with lat/lon
  distance_matrix_km.csv     yard x yard distances in km
  distance_method.txt        which method was used (rail graph or fallback)

How to run (on your own laptop, internet needed)
  pip install osmnx networkx pandas openpyxl scikit-learn
  python build_distances.py              # model yards only (column "In model network?" = 1)
  python build_distances.py --all        # all 28 yards
  python build_distances.py --fallback   # skip the rail download (fast, quick tests only)

Notes
  - The Germany-wide rail download is large: expect 10-30 minutes and a few GB of RAM
    the first time. OSMnx caches it, so later runs are fast.
  - If a yard is not found by geocoding, type its lat/lon into the Yards sheet
    (columns H and I) and run again.
"""

import argparse
import math
import sys
import time

import pandas as pd

XLSX = "AMORE_network_data.xlsx"


def read_inputs(use_all: bool):
    yards = pd.read_excel(XLSX, sheet_name="Yards", header=0)
    yards["Rank"] = pd.to_numeric(yards["Rank"], errors="coerce")
    yards = yards[yards["Yard"].notna() & yards["Rank"].notna()].copy()
    yards["Rank"] = yards["Rank"].astype(int)
    if not use_all:
        n = int(pd.read_excel(XLSX, sheet_name="Assumptions", header=None).iloc[7, 1])  # top N yards
        yards = yards[yards["Rank"] <= n]
    detour = float(pd.read_excel(XLSX, sheet_name="Assumptions", header=None).iloc[6, 1])
    return yards.reset_index(drop=True), detour


def geocode(yards: pd.DataFrame) -> pd.DataFrame:
    import osmnx as ox

    lats, lons = [], []
    for _, r in yards.iterrows():
        lat, lon = r.get("Latitude"), r.get("Longitude")
        if pd.notna(lat) and pd.notna(lon):
            lats.append(float(lat)); lons.append(float(lon)); continue
        query = f"{r['Geocode query (edit if lookup fails)']}, Deutschland"
        try:
            lat, lon = ox.geocode(query)
            print(f"  found  {r['Yard']:<26} {lat:.4f}, {lon:.4f}")
        except Exception:
            lat, lon = float("nan"), float("nan")
            print(f"  MISSING {r['Yard']:<25} -> type lat/lon into the Yards sheet")
        lats.append(lat); lons.append(lon)
        time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    yards = yards.copy()
    yards["Latitude"], yards["Longitude"] = lats, lons
    return yards


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def fallback_matrix(yards, detour):
    names = list(yards["Yard"])
    m = pd.DataFrame(0.0, index=names, columns=names)
    for i, a in yards.iterrows():
        for j, b in yards.iterrows():
            if i != j:
                m.iloc[i, j] = round(haversine_km(a.Latitude, a.Longitude, b.Latitude, b.Longitude) * detour, 1)
    return m


def median_ratio(m, yards):
    """Median of rail km / straight-line km over the yard pairs connected in the rail graph."""
    ratios = []
    for i, a in yards.iterrows():
        for j, b in yards.iterrows():
            if i != j and pd.notna(m.iloc[i, j]):
                straight = haversine_km(a.Latitude, a.Longitude, b.Latitude, b.Longitude)
                if straight > 0:
                    ratios.append(m.iloc[i, j] / straight)
    ratios.sort()
    n = len(ratios)
    return (ratios[n // 2] + ratios[(n - 1) // 2]) / 2, n


def rail_matrix(yards):
    import networkx as nx
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.requests_timeout = 600
    # main-line rail only: no sidings, yards, spurs or crossovers
    rail_filter = '["railway"="rail"]["service"!~"siding|yard|spur|crossover"]'
    print("Downloading German rail network from OpenStreetMap (first run is slow)...")
    G = ox.graph_from_place("Germany", custom_filter=rail_filter, simplify=True, retain_all=True)
    G = ox.convert.to_undirected(G)
    print(f"  rail graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    nodes = ox.distance.nearest_nodes(G, X=list(yards["Longitude"]), Y=list(yards["Latitude"]))
    names = list(yards["Yard"])
    m = pd.DataFrame(float("nan"), index=names, columns=names)
    for i, src in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(G, src, weight="length")
        for j, dst in enumerate(nodes):
            m.iloc[i, j] = round(lengths.get(dst, float("nan")) / 1000.0, 1)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="use all 28 yards")
    ap.add_argument("--fallback", action="store_true", help="skip rail download, use straight line x detour")
    args = ap.parse_args()

    yards, detour = read_inputs(args.all)
    print(f"{len(yards)} yards selected")
    yards = geocode(yards)
    yards[["Rank", "Yard", "Latitude", "Longitude"]].to_csv("yard_coordinates.csv", index=False)

    if yards[["Latitude", "Longitude"]].isna().any().any():
        sys.exit("Some yards have no coordinates - fill them in the Yards sheet and run again.")

    method = (f"straight-line distance x detour factor {detour} from the Assumptions sheet "
              "(no source: quick tests only, not for results in the report)")
    if args.fallback:
        m = fallback_matrix(yards, detour)
    else:
        try:
            m = rail_matrix(yards)
            gaps = int(m.isna().sum().sum())
            if gaps:
                ratio, n_pairs = median_ratio(m, yards)
                print(f"  {gaps} pairs are not connected in the rail graph -> straight-line x {ratio:.3f} "
                      f"(median rail/straight-line ratio of {n_pairs} connected pairs)")
                m = m.fillna(fallback_matrix(yards, ratio))
                method = (f"OSM rail graph (shortest path); {gaps} unconnected pairs filled with straight-line x "
                          f"{ratio:.3f}, the median rail/straight-line ratio of the {n_pairs} connected pairs")
            else:
                method = "OSM rail graph (shortest path along main-line track)"
        except Exception as e:
            print(f"  rail download failed ({e}); using the unsourced detour factor - quick tests only")
            m = fallback_matrix(yards, detour)

    m.to_csv("distance_matrix_km.csv")
    with open("distance_method.txt", "w", encoding="utf-8") as f:
        f.write(method + "\n")
    print(f"Done. Method: {method}")
    print("Files: yard_coordinates.csv, distance_matrix_km.csv, distance_method.txt")


if __name__ == "__main__":
    main()
