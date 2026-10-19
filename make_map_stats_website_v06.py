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
import string

import geopandas as gpd
import pandas as pd
import os

# ---------------- CONFIG: edit these ----------------
results_dir = "C:/Users/kibby/Files/base_data/maisrc/mn_es_data"
code_dir = "C:/Users/kibby/Files/maisrc"
SHAPEFILE = os.path.join(results_dir, "1_pebat_lakes_zonal_stats.gpkg") # path to your .shp (keep .dbf/.shx/.prj beside it)
OUTPUT = os.path.join(code_dir, "docs", "index.html")
STATE_CSV =  os.path.join(results_dir, "1_pebat_statewide_zonal_stats.csv")

MAP_TITLE = "PEBAT Lake Services Explorer"
LABEL_PARTS = ["lake_nm", "cnty_nm"]  # columns combined into the zone name, e.g. "Big Rice, Cass"
                                      # (matched case-insensitively; empty values are skipped)
LABEL_FIELD = None          # only used if LABEL_PARTS is empty: a single column to use as the name
EXTRA_POPUP_FIELDS = []     # other columns to show in the click popup, e.g. ["REGION"]
SIMPLIFY_TOLERANCE = 0.0001 # degrees; raise to shrink big files, 0 to disable

# Optional: define metrics yourself instead of auto-detecting. Example:
METRICS_MANUAL = {
    "Bird Watching":  {"mean": "average_bird_watching", "sum": "sum_bird_watching"},
    'Carbon':   {'mean': 'average_carbon', 'sum': 'sum_carbon'},
    'Drinking Water Protection':   {'mean': 'average_gwn', 'sum': 'sum_gwn'},
    'Lake Recreation':   {'mean': 'average_lake_rec', 'sum': 'sum_lake_rec'},
    'Pheasant Hunting':   {'mean': 'average_pheasant_hunting', 'sum': 'sum_pheasant_hunting'},
    'Pollination':   {'mean': 'average_pollination', 'sum': 'sum_pollination'},
    'Population':   {'mean': 'average_population', 'sum': 'sum_population'},
    'Risk Of Change':   {'mean': 'average_risk_of_change', 'sum': 'sum_risk_of_change'},
    'Trails':   {'mean': 'average_trails', 'sum': 'sum_trails'},
    'Trout Angling':  {'mean': 'average_trout_angling', 'sum': 'sum_trout_angling'},
    'Wild Rice':   {'mean': 'average_wild_rice', 'sum': 'sum_wild_rice'}
}
CATEGORIES = {
    "Ecosystem Services": ["bird_watching", "carbon", "gwn", "lake_rec",
                           "pheasant_hunting", "pollination", "trails", "trout_angling",
                           "wild_rice"],
    "Additional Considerations": ["population", "risk_of_change"],
}
# Any detected metric not listed above goes into an "Other" category.
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
 
 
def norm(name):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
 
 
cat_lookup = {norm(n): cat for cat, names in CATEGORIES.items() for n in names}
 
 
def stat_stem(col):
    """'average_gwn' / 'sum_gwn' / 'gwn_mean' -> 'gwn'"""
    m = SUFFIX.match(col) or PREFIX.match(col)
    return m["m"] if m else col
 
 
def category_for(label, cols):
    # Try the display name first, then the short name inside the column names
    for key in [label, *(stat_stem(c) for c in cols.values())]:
        if norm(key) in cat_lookup:
            return cat_lookup[norm(key)]
    return "Other"
 
 
category_of = {label: category_for(label, cols) for label, cols in metrics.items()}
category_order = [c for c in CATEGORIES if c in category_of.values()]
if "Other" in category_of.values():
    category_order.append("Other")
    print("Metrics not listed in CATEGORIES (placed in 'Other'):",
          ", ".join(m for m, c in category_of.items() if c == "Other"))
 
stat_cols = {c for m in metrics.values() for c in m.values()}
 
 
def load_state_averages(path):
    """Return {shapefile mean column: statewide average} from the CSV."""
    df = pd.read_csv(path)
    col_lookup = {norm(c): c for c in stat_cols}
    label_lookup = {norm(label): cols["mean"] for label, cols in metrics.items() if "mean" in cols}
    # Short names inside the column names, e.g. average_gwn / sum_gwn -> "gwn"
    stem_lookup = {
        norm(stat_stem(c)): cols["mean"]
        for cols in metrics.values() if "mean" in cols
        for c in cols.values()
    }
    target = lambda name: (col_lookup.get(norm(str(name)))
                           or label_lookup.get(norm(str(name)))
                           or stem_lookup.get(norm(str(name))))
    out, unmatched = {}, []
 
    # Wide layout: one column per index, first row holds the averages
    wide_cols = [c for c in df.columns if target(c)]
    for c in wide_cols:
        val = pd.to_numeric(df[c], errors="coerce").iloc[0] if len(df) else float("nan")
        if pd.notna(val):                      # missing values are skipped
            out[target(c)] = float(val)
    if not wide_cols:
        # Long layout: first column = index name, next column with numbers = average
        name_col = df.columns[0]
        numeric = {c: pd.to_numeric(df[c], errors="coerce") for c in df.columns[1:]}
        value_col = next((c for c, s in numeric.items() if s.notna().any()), None)
        if value_col is None:
            raise SystemExit(f"Could not find a numeric column of averages in {path}.")
        for name, val in zip(df[name_col], numeric[value_col]):
            t = target(name)
            if not t:
                unmatched.append(str(name))
            elif pd.notna(val):                # missing values are skipped
                out[t] = float(val)
 
    missing = [label for label, cols in metrics.items() if "mean" in cols and cols["mean"] not in out]
    if missing:
        print("Statewide average missing or blank (will show n/a) for:", ", ".join(missing))
    if unmatched:
        print("CSV rows that matched no metric:", ", ".join(unmatched))
    return {k: v for k, v in out.items() if k in {c.get("mean") for c in metrics.values()}}
 
 
if STATE_CSV:
    try:
        state_avg = load_state_averages(STATE_CSV)
    except FileNotFoundError:
        raise SystemExit(f"STATE_CSV file not found: {STATE_CSV}")
else:
    state_avg = {}
 
 
def find_col(name):
    lookup = {c.lower(): c for c in attr_cols}
    if name.lower() not in lookup:
        raise SystemExit(f'Column "{name}" not found. Columns present:\n  ' + ", ".join(attr_cols))
    return lookup[name.lower()]
 
 
def clean(value):
    """'big rice' -> 'Big Rice'; blank/missing -> ''."""
    if value is None or str(value).strip().lower() in ("", "nan", "none"):
        return ""
    return string.capwords(str(value).strip())
 
 
if LABEL_PARTS:
    part_cols = [find_col(p) for p in LABEL_PARTS]
    gdf["zone_label"] = gdf[part_cols].apply(
        lambda row: ", ".join(p for p in (clean(v) for v in row) if p), axis=1
    )
    label_field = "zone_label"
else:
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
  .search { width: 230px; }
  .search label { display: block; font-weight: 600; margin-bottom: 3px; }
  .search select { width: 100%; padding: 4px; font-size: 13px; margin-bottom: 6px; }
  .search .row { display: flex; gap: 4px; }
  .search input { flex: 1; min-width: 0; padding: 4px 6px; font-size: 13px; }
  .search button { padding: 4px 10px; font-size: 13px; cursor: pointer; }
  #s-out { margin-top: 6px; max-height: 180px; overflow-y: auto; color: #444; }
  #s-out a { display: block; padding: 3px 2px; color: #1d4ed8; text-decoration: none; border-bottom: 1px solid #eee; }
  #s-out a:hover { background: #eef4ff; }
  .mini { margin: 6px 0 2px; font-size: 12px; color: #444; }
  .mini i { display: inline-block; width: 10px; height: 10px; margin: 0 4px 0 8px; vertical-align: middle; }
  .mini i:first-child { margin-left: 0; }
  .cat { font-weight: 600; background: #f3f3f3; padding: 2px 4px; margin-top: 8px; }
  .crow { margin: 5px 0; padding: 2px 4px; border-radius: 3px; }
  .crow.active { background: #fff3cd; }
  .cname { display: flex; justify-content: space-between; font-weight: 600; }
  .cname .diff { font-weight: 400; color: #555; }
  .bl { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
  .track { flex: 1; height: 9px; background: #eee; border-radius: 2px; overflow: hidden; }
  .fill { height: 100%; }
  .fill.lake { background: #2563eb; }
  .fill.state { background: #9ca3af; }
  .bl span { width: 34px; text-align: right; font-variant-numeric: tabular-nums; }
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
const STATE_AVG = __STATE_AVG__;           // { mean column: statewide average }
const CATEGORY_OF = __CATEGORY_OF__;       // { metric label: category }
const CATEGORY_ORDER = __CATEGORY_ORDER__; // categories in display order
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
 
const metricsIn = cat => Object.keys(METRICS).filter(m => CATEGORY_OF[m] === cat);
let category = CATEGORY_ORDER[0];
let metric = metricsIn(category)[0];
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
 
const isNum = v => v !== null && v !== undefined && !isNaN(v);
const pct = v => Math.max(0, Math.min(1, v)) * 100;   // indices run 0-1
const f2 = v => isNum(v) ? Number(v).toFixed(2) : "n/a";
 
function barLine(cls, v) {
  return '<div class="bl"><div class="track">'
    + (isNum(v) ? '<div class="fill ' + cls + '" style="width:' + pct(v) + '%"></div>' : "")
    + "</div><span>" + f2(v) + "</span></div>";
}
 
function chartRow(label, lake, state, active) {
  let diff = "";
  if (isNum(lake) && isNum(state)) {
    const d = Number((lake - state).toFixed(2));
    diff = '<span class="diff">' + (d > 0 ? "+" : "") + d.toFixed(2) + " vs state</span>";
  }
  return '<div class="crow' + (active ? " active" : "") + '"><div class="cname"><span>' + esc(label)
    + "</span>" + diff + "</div>" + barLine("lake", lake) + barLine("state", state) + "</div>";
}
 
function popupHtml(p) {
  let h = "<b>" + esc(zoneName(p)) + "</b>";
  EXTRA_FIELDS.forEach(k => { h += "<br>" + esc(k) + ": " + esc(p[k]); });
  h += '<div class="mini"><i style="background:#2563eb"></i>This lake'
    + '<i style="background:#9ca3af"></i>State average (scale 0&ndash;1)</div>';
  let any = false;
  for (const cat of CATEGORY_ORDER) {
    const rows = metricsIn(cat).filter(m => METRICS[m].mean);   // sums aren't 0-1, so only averages are charted
    if (!rows.length) continue;
    any = true;
    if (CATEGORY_ORDER.length > 1) h += '<div class="cat">' + esc(cat) + "</div>";
    for (const label of rows) {
      const col = METRICS[label].mean;
      h += chartRow(label, p[col], STATE_AVG[col], label === metric);
    }
  }
  if (!any) h += "<div>No zonal averages available to chart.</div>";
  return h;
}
 
const layer = L.geoJSON(DATA, {
  style: styleFor,
  onEachFeature: (f, lyr) => {
    lyr.bindPopup(() => popupHtml(f.properties), { minWidth: 290, maxWidth: 380, maxHeight: 380 });
    lyr.bindTooltip(() => esc(zoneName(f.properties)) + ": " + fmt(f.properties[currentCol()]), { sticky: true });
    lyr.on({
      mouseover: e => e.target.setStyle({ weight: 3, color: "#000" }),
      mouseout: e => layer.resetStyle(e.target)
    });
  }
}).addTo(map);
map.fitBounds(layer.getBounds());
 
/* ---------- Search (lake name or address) ---------- */
const zones = [];
layer.eachLayer(l => zones.push({ label: zoneName(l.feature.properties), layer: l, feature: l.feature }));
 
function selectZone(z) {
  map.fitBounds(z.layer.getBounds(), { maxZoom: 14 });
  z.layer.openPopup();
}
window.openZone = i => selectZone(zones[i]);
 
const polysOf = g => g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
 
function inRing(pt, ring) {
  let c = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) c = !c;
  }
  return c;
}
function inPolygon(pt, rings) {
  if (!inRing(pt, rings[0])) return false;
  for (let k = 1; k < rings.length; k++) if (inRing(pt, rings[k])) return false;
  return true;
}
function segDist2(p, a, b, k) {
  const ax = a[0] * k, ay = a[1], bx = b[0] * k, by = b[1], px = p[0] * k, py = p[1];
  const dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy;
  let t = len2 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  return (px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2;
}
// Zone containing the point, or else the closest one (distance in meters, approximate)
function nearestZone(lng, lat) {
  const k = Math.cos(lat * Math.PI / 180), pt = [lng, lat];
  let best = null;
  zones.forEach((z, i) => {
    const polys = polysOf(z.feature.geometry);
    if (polys.some(p => inPolygon(pt, p))) {
      if (!best || best.d2 > 0) best = { i, d2: 0 };
      return;
    }
    for (const poly of polys) for (const ring of poly) for (let s = 1; s < ring.length; s++) {
      const d2 = segDist2(pt, ring[s - 1], ring[s], k);
      if (!best || d2 < best.d2) best = { i, d2 };
    }
  });
  return best && { i: best.i, meters: Math.sqrt(best.d2) * 111320, inside: best.d2 === 0 };
}
const fmtDist = m => m < 160 ? Math.round(m * 3.28084) + " ft" : (m / 1609.34).toFixed(1) + " mi";
 
const search = L.control({ position: "topleft" });
search.onAdd = () => {
  const div = L.DomUtil.create("div", "panel search");
  div.innerHTML =
    '<label for="s-mode">Search by</label>' +
    '<select id="s-mode"><option value="lake">Lake name</option><option value="addr">Address</option></select>' +
    '<div class="row"><input id="s-q" type="text" placeholder="Type a lake name" autocomplete="off">' +
    '<button id="s-go" type="button">Go</button></div><div id="s-out"></div>';
  L.DomEvent.disableClickPropagation(div);
  L.DomEvent.disableScrollPropagation(div);
  return div;
};
search.addTo(map);
 
const sMode = document.getElementById("s-mode");
const sQ = document.getElementById("s-q");
const sGo = document.getElementById("s-go");
const sOut = document.getElementById("s-out");
let addrMarker = null;
 
function lakeMatches() {
  const q = sQ.value.trim().toLowerCase();
  if (!q) return [];
  const hits = [];
  zones.forEach((z, i) => { if (z.label.toLowerCase().includes(q)) hits.push(i); });
  hits.sort((a, b) => {
    const sa = zones[a].label.toLowerCase().startsWith(q) ? 0 : 1;
    const sb = zones[b].label.toLowerCase().startsWith(q) ? 0 : 1;
    return sa - sb || zones[a].label.localeCompare(zones[b].label);
  });
  return hits;
}
 
function renderLakeList() {
  if (!sQ.value.trim()) { sOut.innerHTML = ""; return; }
  const hits = lakeMatches();
  if (!hits.length) { sOut.textContent = "No matching lakes"; return; }
  sOut.innerHTML = hits.slice(0, 8).map(i => '<a href="#" data-i="' + i + '">' + esc(zones[i].label) + "</a>").join("")
    + (hits.length > 8 ? "<div>+ " + (hits.length - 8) + " more. Keep typing to narrow.</div>" : "");
}
 
async function searchAddress() {
  const q = sQ.value.trim();
  if (!q) return;
  sOut.textContent = "Searching...";
  const b = layer.getBounds();
  const viewbox = [b.getWest(), b.getNorth(), b.getEast(), b.getSouth()].join(",");
  try {
    const r = await fetch("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&viewbox="
      + viewbox + "&q=" + encodeURIComponent(q));
    const res = await r.json();
    if (!res.length) { sOut.textContent = "Address not found. Try adding the city and state."; return; }
    const lat = +res[0].lat, lng = +res[0].lon;
    const near = nearestZone(lng, lat);
    let html = "<b>" + esc(res[0].display_name) + "</b>";
    if (near) {
      const name = esc(zones[near.i].label);
      html += "<br>" + (near.inside ? "Inside <b>" + name + "</b>."
        : "Nearest lake: <b>" + name + "</b>, about " + fmtDist(near.meters) + " away.")
        + '<br><a href="#" onclick="openZone(' + near.i + ');return false">Show lake stats</a>';
    }
    if (addrMarker) addrMarker.remove();
    addrMarker = L.marker([lat, lng]).addTo(map).bindPopup(html, { maxWidth: 280 });
    map.setView([lat, lng], Math.max(map.getZoom(), 13));
    addrMarker.openPopup();
    sOut.textContent = "Found: " + res[0].display_name;
  } catch (err) {
    sOut.textContent = "Address search failed. Check your connection and try again.";
  }
}
 
function runSearch() {
  if (sMode.value === "addr") { searchAddress(); return; }
  const hits = lakeMatches();
  if (hits.length) selectZone(zones[hits[0]]);
  renderLakeList();
}
 
sMode.addEventListener("change", () => {
  sQ.placeholder = sMode.value === "addr" ? "Street, city, state" : "Type a lake name";
  sOut.innerHTML = "";
  if (sMode.value === "lake") renderLakeList();
});
sQ.addEventListener("input", () => { if (sMode.value === "lake") renderLakeList(); });
sQ.addEventListener("keydown", e => { if (e.key === "Enter") runSearch(); });
sGo.addEventListener("click", runSearch);
sOut.addEventListener("click", e => {
  const a = e.target.closest("a[data-i]");
  if (a) { e.preventDefault(); selectZone(zones[+a.dataset.i]); }
});
 
/* ---------- Controls (1. metric, 2. statistic) ---------- */
const catSel = document.createElement("select");
const metricSel = document.createElement("select");
const statSel = document.createElement("select");
 
function fillMetricOptions() {
  const list = metricsIn(category);
  metricSel.innerHTML = list.map(m => "<option>" + esc(m) + "</option>").join("");
  metric = list.includes(metric) ? metric : list[0];
  metricSel.value = metric;
}
 
function fillStatOptions() {
  const avail = Object.keys(STAT_NAMES).filter(s => METRICS[metric][s]);
  statSel.innerHTML = avail.map(s => '<option value="' + s + '">' + STAT_NAMES[s] + "</option>").join("");
  stat = avail.includes(stat) ? stat : avail[0];
  statSel.value = stat;
}
 
const controls = L.control({ position: "topright" });
controls.onAdd = () => {
  const div = L.DomUtil.create("div", "panel controls");
  div.innerHTML = "<h3>__TITLE__</h3>";
  const addRow = (text, sel) => {
    const l = document.createElement("label");
    l.textContent = text;
    div.appendChild(l);
    div.appendChild(sel);
  };
  let n = 1;
  if (CATEGORY_ORDER.length > 1) {
    catSel.innerHTML = CATEGORY_ORDER.map(c => "<option>" + esc(c) + "</option>").join("");
    catSel.value = category;
    addRow((n++) + ". Choose a category", catSel);
  }
  addRow((n++) + ". Choose your metric", metricSel);
  addRow((n++) + ". Choose average or sum", statSel);
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
 
catSel.addEventListener("change", () => {
  category = catSel.value;
  fillMetricOptions();
  fillStatOptions();
  refresh();
});
metricSel.addEventListener("change", () => { metric = metricSel.value; fillStatOptions(); refresh(); });
statSel.addEventListener("change", () => { stat = statSel.value; refresh(); });
 
fillMetricOptions();
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
    .replace("__STATE_AVG__", json.dumps(state_avg))
    .replace("__CATEGORY_OF__", json.dumps(category_of))
    .replace("__CATEGORY_ORDER__", json.dumps(category_order))
    .replace("__LABEL__", json.dumps(label_field))
    .replace("__EXTRA__", json.dumps(EXTRA_POPUP_FIELDS))
)
 
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
 
print(f"Saved {OUTPUT}: {len(gdf)} zones, {len(metrics)} metrics -> {', '.join(metrics)}")