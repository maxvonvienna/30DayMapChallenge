#!/usr/bin/env python3
"""Day 14 – The Map That Ate Vienna.

Read a local Austria OpenStreetMap PBF with PyOsmium and produce a four-panel
cartographic experiment with progressively increasing detail.

Install: pip install osmium geopandas shapely matplotlib numpy pyproj
Run: python day14_map_that_ate_vienna_local_pbf.py --pbf /data/austria-latest.osm.pbf

Notes:
* Uses OSM nodes and ways; multipolygon relations are not assembled.
* Closed ways are rendered as polygon outlines, not filled polygons.
* Local source file; no network calls.

**Day 14 – A Map So Detailed It Becomes the Territory | #30DayMapChallenge**

**The Map That Ate Vienna**

How much detail can a map contain before it stops being useful? Inspired by Jorge Luis Borges' *On Exactitude in Science*, this map explores the limits of cartographic representation by progressively increasing the amount of geographic information displayed.

Using OpenStreetMap data extracted from a local Austria PBF file, the same section of Vienna is mapped at four levels of detail. The first panel shows the basic urban structure of roads, railways, and waterways. The second adds buildings, parks, and land use, while the third introduces smaller infrastructure elements, barriers, and individual objects. Finally, the fourth panel attempts to show everything at once, including thousands of overlapping labels.

As the amount of information increases, the city gradually disappears beneath its own representation. What begins as a readable map turns into a dense web of lines, symbols, and text. The experiment illustrates a fundamental paradox of cartography: **a map becomes useful not by showing everything, but by deciding what to leave out.**

Created entirely with Python using local OpenStreetMap data.

#30DayMapChallenge #Day14 #Cartography #OpenStreetMap #Vienna #GIS #Python #MapGeneralization


"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import math
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle
import numpy as np
import osmium
from pyproj import Transformer
from shapely.geometry import box, LineString

CATEGORIES = {
    "roads": {"highway"},
    "rail": {"railway"},
    "buildings": {"building", "building:part"},
    "water": {"waterway", "water"},
    "green": {"landuse", "leisure", "natural"},
    "boundaries": {"barrier", "boundary"},
    "infrastructure": {"power", "man_made", "pipeline", "aerialway"},
    "pedestrian": {"footway", "sidewalk", "crossing", "kerb", "cycleway"},
}


def get_category(tags):
    keys = set(tags)
    for category, wanted in CATEGORIES.items():
        if keys & wanted:
            return category
    return "other"


class Extractor(osmium.SimpleHandler):
    def __init__(self, bbox, transformer, max_labels=18000):
        super().__init__()
        self.bbox = bbox
        self.transformer = transformer
        self.lines = {key: [] for key in [*CATEGORIES, "other"]}
        self.points = {"tree": [], "street_furniture": [], "other": []}
        self.labels = []
        self.counts = Counter()
        self.max_labels = max_labels

    def inside(self, lon, lat):
        return self.bbox[0] <= lon <= self.bbox[2] and self.bbox[1] <= lat <= self.bbox[3]

    def node(self, n):
        if not n.location.valid():
            return
        lon, lat = n.location.lon, n.location.lat
        if not self.inside(lon, lat):
            return
        tags = dict(n.tags)
        if not tags:
            return
        x, y = self.transformer.transform(lon, lat)
        if tags.get("natural") == "tree":
            category = "tree"
        elif any(k in tags for k in ("amenity", "highway", "man_made", "barrier", "power", "public_transport", "traffic_sign", "emergency", "entrance")):
            category = "street_furniture"
        else:
            category = "other"
        self.points[category].append((x, y))
        self.counts["nodes"] += 1
        if len(self.labels) < self.max_labels:
            label = tags.get("addr:housenumber") or tags.get("name") or tags.get("ref")
            if label:
                self.labels.append((x, y, str(label)[:35]))

    def way(self, w):
        if not w.tags:
            return
        try:
            coords = [(node.lon, node.lat) for node in w.nodes if node.location.valid()]
        except (osmium.InvalidLocationError, RuntimeError):
            return
        if len(coords) < 2:
            return
        # Fast bounding-box rejection. Clipping happens at plot time.
        xs, ys = zip(*coords)
        if max(xs) < self.bbox[0] or min(xs) > self.bbox[2] or max(ys) < self.bbox[1] or min(ys) > self.bbox[3]:
            return
        tags = dict(w.tags)
        category = get_category(tags)
        transformed = np.asarray([self.transformer.transform(x, y) for x, y in coords], dtype=np.float64)
        self.lines[category].append(transformed)
        self.counts["ways"] += 1
        if len(self.labels) < self.max_labels:
            label = tags.get("addr:housenumber") or tags.get("name") or tags.get("ref")
            if label:
                xy = transformed[len(transformed) // 2]
                self.labels.append((float(xy[0]), float(xy[1]), str(label)[:35]))


def plot_lines(ax, segments, color, lw, alpha=1, zorder=2):
    if segments:
        coll = LineCollection(segments, colors=color, linewidths=lw, alpha=alpha,
                              zorder=zorder, rasterized=True)
        ax.add_collection(coll)


def plot_points(ax, points, color, size, alpha=1, zorder=4):
    if points:
        arr = np.asarray(points)
        ax.scatter(arr[:, 0], arr[:, 1], s=size, c=color, alpha=alpha,
                   edgecolors="none", zorder=zorder, rasterized=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pbf", required=True, type=Path, help="Path to austria-latest.osm.pbf")
    parser.add_argument("--out", default="day14_map_that_ate_vienna.png", type=Path)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                        default=[16.361, 48.203, 16.382, 48.216], help="WGS84 bounding box")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--labels", type=int, default=12000, help="Maximum stored labels")
    parser.add_argument("--label-step", type=int, default=1, help="Use every Nth label in final panel")
    args = parser.parse_args()
    if not args.pbf.is_file():
        parser.error(f"PBF not found: {args.pbf}")
    west, south, east, north = args.bbox
    if not (west < east and south < north):
        parser.error("Invalid bounding box")

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:31287", always_xy=True)
    extractor = Extractor(args.bbox, transformer, max_labels=args.labels)
    print("Reading local PBF; this can take a while for all of Austria...")
    extractor.apply_file(str(args.pbf), locations=True, idx="flex_mem")
    print("Extracted:", dict(extractor.counts))
    print("Ways per category:", {k: len(v) for k, v in extractor.lines.items()})
    print("Points per category:", {k: len(v) for k, v in extractor.points.items()})

    corners = [transformer.transform(lon, lat) for lon in (west, east) for lat in (south, north)]
    xmin = min(c[0] for c in corners)
    xmax = max(c[0] for c in corners)
    ymin = min(c[1] for c in corners)
    ymax = max(c[1] for c in corners)
    # Keep same extent in every panel.
    stages = [
        ("01 / THE CITY", "roads, rail and waterways"),
        ("02 / THE FABRIC", "buildings, parks and land use"),
        ("03 / THE DETAILS", "barriers, utilities and urban objects"),
        ("04 / THE TERRITORY", "every mapped object and its labels"),
    ]
    plt.rcParams.update({
        "font.family": "Arial Narrow",
        "font.size": 11,
    })
    fig, axes = plt.subplots(2, 2, figsize=(15, 15), facecolor="#faf9f5")
    for i, ax in enumerate(axes.flat):
        ax.set_facecolor("#faf9f5")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#a9a9a2")
            spine.set_linewidth(0.6)
        plot_lines(ax, extractor.lines["water"], "#8ca7ad", 0.8, 0.8)
        plot_lines(ax, extractor.lines["roads"], "#555653", 0.45, 0.8)
        plot_lines(ax, extractor.lines["rail"], "#444444", 0.5, 0.8)
        if i >= 1:
            plot_lines(ax, extractor.lines["buildings"], "#252525", 0.30, 0.85)
            plot_lines(ax, extractor.lines["green"], "#9a9c90", 0.35, 0.65)
        if i >= 2:
            plot_lines(ax, extractor.lines["pedestrian"], "#444444", 0.25, 0.8)
            plot_lines(ax, extractor.lines["boundaries"], "#444444", 0.23, 0.8)
            plot_lines(ax, extractor.lines["infrastructure"], "#333333", 0.24, 0.8)
            plot_points(ax, extractor.points["tree"], "#626c60", 0.8, 0.75)
            plot_points(ax, extractor.points["street_furniture"], "#333333", 0.6, 0.6)
        if i >= 3:
            plot_lines(ax, extractor.lines["other"], "#262626", 0.26, 0.85)
            plot_points(ax, extractor.points["other"], "#222222", 0.55, 0.75)
            # Intentionally allow label collisions as the conceptual point of the map.
            for x, y, label in extractor.labels[::max(1, args.label_step)]:
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    ax.text(x, y, label, fontsize=2.7, color="#171717", alpha=0.62,
                            clip_on=True, zorder=7)
        ax.text(0.015, 0.985, stages[i][0], transform=ax.transAxes, va="top",
                fontsize=10, fontweight="bold", color="#202020",
                bbox={"facecolor": "#faf9f5", "edgecolor": "none", "pad": 3}, zorder=10)
        ax.text(0.015, 0.946, stages[i][1], transform=ax.transAxes, va="top",
                fontsize=7, color="#555555",
                bbox={"facecolor": "#faf9f5", "edgecolor": "none", "pad": 2}, zorder=10)

    fig.suptitle("THE MAP THAT ATE VIENNA", x=0.01, y=0.985, ha="left",
                 fontsize=23, fontweight="bold", color="#202020")
    fig.text(0.06, 0.953, "Day 14  /  A map so detailed it becomes the territory",
             fontsize=10, color="#555555")
    fig.text(0.06, 0.028, "Source: OpenStreetMap contributors · Local Austria PBF · EPSG:31287 · Same extent in all four panels",
             fontsize=8, color="#555555")
    fig.text(0.06, 0.013, "Inspired by Jorge Luis Borges, On Exactitude in Science · OSM ways and tagged nodes; multipolygon relations not assembled",
             fontsize=7, color="#777777")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.925, bottom=0.055, wspace=0.035, hspace=0.055)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    fig.savefig(args.out, dpi=args.dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {args.out.resolve()}")


if __name__ == "__main__":
    main()
