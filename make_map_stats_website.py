"""
Shapefile with zonal statistics -> interactive Leaflet map with two dropdowns:
    1. Choose your metric
    2. Choose zonal average (mean) or zonal sum

Install:   pip install geopandas
Run:       python make_map_stats.py
Output:    index.html  (self-contained; put it in your /docs folder for GitHub Pages)

HOW COLUMNS ARE DETECTED
Columns are paired into metrics by name. These all work:
    pop_mean / pop_sum        (metric "pop")
    pop_avg   / pop_sum
    mean_pop  / sum_pop
If your columns are named differently, fill in METRICS_MANUAL below instead.
Note: shapefile column names are capped at 10 characters, so check yours
weren't truncated (e.g. "rainfall_m" instead of "rainfall_mean").
"""

import json
import re

import geopandas as gpd
import os

# ---------------- CONFIG: edit these ----------------
results_dir = "C:/Users/kibby/Files/base_data/maisrc/mn_es_data"
code_dir = "C:/Users/kibby/Files/maisrc"

SHAPEFILE = os.path.join(results_dir, "1_pebat_lakes_zonal_stats.gpkg") # path to your .shp (keep .dbf/.shx/.prj beside it)
OUTPUT = os.path.join(code_dir, "docs", "index.html")

MAP_TITLE = "Zonal Statistics Explorer"
LABEL_FIELD = None          # column used as the zone name, e.g. "NAME" (None = first non-stat column)
EXTRA_POPUP_FIELDS = []     # other columns to show in the click popup, e.g. ["REGION"]
SIMPLIFY_TOLERANCE = 0.0001 # degrees; raise to shrink big files, 0 to disable

# Optional: define metrics yourself instead of auto-detecting. Example:
METRICS_MANUAL = {
    "Bird Watching":  {"mean": "average_bird_watching", "sum": "sum_bird_watching"},
    "Lake Recreation": {"mean": "average_lake_rec", "sum": "sum_lake_rec"},
}
# METRICS_MANUAL = None
# ----------------------------------------------------

STAT_ALIASES = {"mean": "mean", "avg": "mean", "average": "mean", "sum": "sum"}
SUFFIX = re.compile(r"^(?P<m>.+?)[_ ]?(?P<s>mean|avg|average|sum)$", re.I)
PREFIX = re.compile(r"^(?P<s>mean|avg|average|sum)[_ ]?(?P<m>.+)$", re.I)


def detect_metrics(columns):
    found = {}
    for col in columns:
        match = SUFFIX.match(col) or PREFIX.match(col)
        if not match:
            continue
        key = match["m"].strip("_ ").lower()
        stat = STAT_ALIASES[match["s"].lower()]
        label = match["m"].strip("_ ").replace("_", " ")
        entry = found.setdefault(key, {"label": label})
        entry[stat] = col
    return {v.pop("label"): v for v in found.values()}


gdf = gpd.read_file(SHAPEFILE)
if gdf.crs is None:
    raise SystemExit("Shapefile has no CRS (.prj missing). Set one with gdf.set_crs(...).")
gdf = gdf.to_crs(epsg=4326)
if SIMPLIFY_TOLERANCE:
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

attr_cols = [c for c in gdf.columns if c != "geometry"]
metrics = METRICS_MANUAL or detect_metrics(attr_cols)
if not metrics:
    raise SystemExit(
        "No mean/sum column pairs found. Columns present:\n  "
        + ", ".join(attr_cols)
        + "\nFill in METRICS_MANUAL at the top of the script."
    )

stat_cols = {c for m in metrics.values() for c in m.values()}
label_field = LABEL_FIELD or next((c for c in attr_cols if c not in stat_cols), None)
keep = [c for c in dict.fromkeys([label_field, *EXTRA_POPUP_FIELDS, *sorted(stat_cols)]) if c]
gdf = gdf[keep + ["geometry"]]
for c in keep:
    if str(gdf[c].dtype).startswith("datetime"):
        gdf[c] = gdf[c].astype(str)

geojson = gdf.to_json().replace("</", "<\\/")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html, body, #map { height: 100%; margin: 0; }
  body { font-family: system-ui, sans-serif; }
  .panel { background: #fff; padding: 10px 12px; border-radius: 6px;
           box-shadow: 0 1px 6px rgba(0,0,0,.3); font-size: 13px; line-height: 1.4; }
  .controls { width: 230px; }
  .controls h3 { margin: 0 0 8px; font-size: 15px; }
  .controls label { display: block; font-weight: 600; margin: 8px 0 3px; }
  .controls select { width: 100%; padding: 4px; font-size: 13px; }
  .legend i { display: inline-block; width: 16px; height: 12px; margin-right: 6px;
              vertical-align: middle; border: 1px solid #999; }
  .legend .title { font-weight: 600; margin-bottom: 4px; }
  table.pop { border-collapse: collapse; margin-top: 4px; }
  table.pop th, table.pop td { padding: 2px 8px; text-align: right; border-bottom: 1px solid #eee; }
  table.pop th:first-child, table.pop td:first-child { text-align: left; }
  table.pop tr.active td { background: #fff3cd; font-weight: 600; }
</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = __GEOJSON__;
const METRICS = __METRICS__;       // { label: { mean: column, sum: column } }
const LABEL_FIELD = __LABEL__;
const EXTRA_FIELDS = __EXTRA__;
const STAT_NAMES = { mean: "Zonal average", sum: "Zonal sum" };
const COLORS = ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"];

const map = L.map("map");
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = v => (v === null || v === undefined || isNaN(v)) ? "n/a"
  : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });

let metric = Object.keys(METRICS)[0];
let stat = null;
let breaks = [];
let vmin = 0, vmax = 0;

const currentCol = () => METRICS[metric][stat];
const zoneName = p => (LABEL_FIELD && p[LABEL_FIELD] !== null) ? p[LABEL_FIELD] : "Zone";

function computeBreaks() {
  const vals = DATA.features.map(f => f.properties[currentCol()])
    .filter(v => v !== null && v !== undefined && !isNaN(v)).sort((a, b) => a - b);
  vmin = vals[0]; vmax = vals[vals.length - 1];
  const n = COLORS.length, b = [];
  for (let i = 1; i < n; i++) b.push(vals[Math.floor(i * vals.length / n)]);
  breaks = [...new Set(b)].filter(v => v !== undefined);
}

function classIndex(v) {
  let i = 0;
  while (i < breaks.length && v >= breaks[i]) i++;
  return i;
}
const classColor = i => COLORS[breaks.length ? Math.round(i * (COLORS.length - 1) / breaks.length) : 0];

function styleFor(f) {
  const v = f.properties[currentCol()];
  const bad = v === null || v === undefined || isNaN(v);
  return { color: "#555", weight: 1, fillOpacity: 0.75, fillColor: bad ? "#cccccc" : classColor(classIndex(v)) };
}

function popupHtml(p) {
  let h = "<b>" + esc(zoneName(p)) + "</b>";
  EXTRA_FIELDS.forEach(k => { h += "<br>" + esc(k) + ": " + esc(p[k]); });
  h += '<table class="pop"><tr><th></th><th>Average</th><th>Sum</th></tr>';
  for (const [label, cols] of Object.entries(METRICS)) {
    h += "<tr" + (label === metric ? ' class="active"' : "") + "><td>" + esc(label) + "</td><td>"
      + (cols.mean ? fmt(p[cols.mean]) : "&ndash;") + "</td><td>"
      + (cols.sum ? fmt(p[cols.sum]) : "&ndash;") + "</td></tr>";
  }
  return h + "</table>";
}

const layer = L.geoJSON(DATA, {
  style: styleFor,
  onEachFeature: (f, lyr) => {
    lyr.bindPopup(() => popupHtml(f.properties), { maxWidth: 380 });
    lyr.bindTooltip(() => esc(zoneName(f.properties)) + ": " + fmt(f.properties[currentCol()]), { sticky: true });
    lyr.on({
      mouseover: e => e.target.setStyle({ weight: 3, color: "#000" }),
      mouseout: e => layer.resetStyle(e.target)
    });
  }
}).addTo(map);
map.fitBounds(layer.getBounds());

/* ---------- Controls (1. metric, 2. statistic) ---------- */
const metricSel = document.createElement("select");
const statSel = document.createElement("select");

function fillStatOptions() {
  const avail = Object.keys(STAT_NAMES).filter(s => METRICS[metric][s]);
  statSel.innerHTML = avail.map(s => '<option value="' + s + '">' + STAT_NAMES[s] + "</option>").join("");
  stat = avail.includes(stat) ? stat : avail[0];
  statSel.value = stat;
}

const controls = L.control({ position: "topright" });
controls.onAdd = () => {
  const div = L.DomUtil.create("div", "panel controls");
  div.innerHTML = "<h3>__TITLE__</h3><label>1. Choose your metric</label>";
  metricSel.innerHTML = Object.keys(METRICS).map(m => "<option>" + esc(m) + "</option>").join("");
  div.appendChild(metricSel);
  const l2 = document.createElement("label");
  l2.textContent = "2. Choose average or sum";
  div.appendChild(l2);
  div.appendChild(statSel);
  L.DomEvent.disableClickPropagation(div);
  return div;
};
controls.addTo(map);

/* ---------- Legend ---------- */
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => L.DomUtil.create("div", "panel legend");
legend.addTo(map);

function updateLegend() {
  const edges = [vmin, ...breaks, vmax];
  let h = '<div class="title">' + esc(metric) + " &ndash; " + STAT_NAMES[stat].toLowerCase() + "</div>";
  for (let i = 0; i < edges.length - 1; i++) {
    h += '<div><i style="background:' + classColor(i) + '"></i>' + fmt(edges[i]) + " &ndash; " + fmt(edges[i + 1]) + "</div>";
  }
  h += '<div><i style="background:#ccc"></i>No data</div>';
  legend.getContainer().innerHTML = h;
}

function refresh() {
  computeBreaks();
  layer.setStyle(styleFor);
  updateLegend();
}

metricSel.addEventListener("change", () => { metric = metricSel.value; fillStatOptions(); refresh(); });
statSel.addEventListener("change", () => { stat = statSel.value; refresh(); });

fillStatOptions();
refresh();
</script>
</body>
</html>
"""

html = (
    TEMPLATE.replace("__TITLE__", MAP_TITLE)
    .replace("__GEOJSON__", geojson)
    .replace("__METRICS__", json.dumps(metrics))
    .replace("__LABEL__", json.dumps(label_field))
    .replace("__EXTRA__", json.dumps(EXTRA_POPUP_FIELDS))
)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Saved {OUTPUT}: {len(gdf)} zones, {len(metrics)} metrics -> {', '.join(metrics)}")
