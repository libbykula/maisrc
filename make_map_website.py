"""
Turn a shapefile into a clickable Leaflet web map (OpenStreetMap basemap).

Install:   pip install geopandas folium
Run:       python make_map.py
Output:    index.html  (upload to GitHub Pages / Netlify / Cloudflare Pages)
"""

import geopandas as gpd
import folium
import os

# ---------------- CONFIG: edit these ----------------
results_dir = "C:/Users/kibby/Files/base_data/maisrc/mn_es_data"
code_dir = "C:/Users/kibby/Files/maisrc"

SHAPEFILE = os.path.join(results_dir, "1_pebat_lakes_zonal_stats.gpkg") # path to your .shp (keep .dbf/.shx/.prj beside it)
OUTPUT = os.path.join(code_dir, "docs", "index.html")
TITLE_FIELD = None            # column to use as the hover label, e.g. "NAME" (None = first column)
POPUP_FIELDS = None           # list of columns to show on click, e.g. ["NAME", "POP", "AREA"]
                              # (None = all columns)
SIMPLIFY_TOLERANCE = 0.0001   # degrees; raise to shrink big files, set to 0 to disable
# ----------------------------------------------------

# 1. Read and reproject to WGS84 (lat/lon), which Leaflet requires
gdf = gpd.read_file(SHAPEFILE)
if gdf.crs is None:
    raise SystemExit("Shapefile has no CRS (.prj missing). Set one with gdf.set_crs(...)")
gdf = gdf.to_crs(epsg=4326)

# 2. Optionally simplify geometry so the page loads fast
if SIMPLIFY_TOLERANCE:
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

# 3. Decide which columns to show
attr_cols = [c for c in gdf.columns if c != "geometry"]
popup_cols = POPUP_FIELDS or attr_cols
title_col = TITLE_FIELD or attr_cols[0]

# Datetime columns can't be serialized to JSON; convert them to text
for c in attr_cols:
    if str(gdf[c].dtype).startswith("datetime"):
        gdf[c] = gdf[c].astype(str)

# 4. Build the map, centered on the data
minx, miny, maxx, maxy = gdf.total_bounds
m = folium.Map(tiles="OpenStreetMap", control_scale=True)
m.fit_bounds([[miny, minx], [maxy, maxx]])

# 5. Add the shapefile layer with hover label, click popup, and highlight on hover
folium.GeoJson(
    gdf[attr_cols + ["geometry"]],
    name="Shapefile",
    style_function=lambda f: {"color": "#2563eb", "weight": 2, "fillColor": "#3b82f6", "fillOpacity": 0.25},
    highlight_function=lambda f: {"weight": 4, "fillOpacity": 0.5},
    tooltip=folium.GeoJsonTooltip(fields=[title_col], labels=False),
    popup=folium.GeoJsonPopup(fields=popup_cols, aliases=popup_cols, max_width=350),
).add_to(m)

folium.LayerControl().add_to(m)

# 6. Save a standalone HTML file
m.save(OUTPUT)
print(f"Saved {OUTPUT} with {len(gdf)} features. Open it in a browser to test.")
