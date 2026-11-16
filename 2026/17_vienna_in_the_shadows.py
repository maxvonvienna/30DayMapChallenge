#!/usr/bin/env python3
"""Day 17 | Vienna in the Shadows.

Real OSM building footprints from a local Austria PBF, or a user-supplied
GeoPackage/FlatGeobuf. Simulates direct-sun building shadows for a chosen day.

Outputs a PNG map, a GeoTIFF of estimated shadow hours and a CSV summary.
The model assumes vertical extrusions of flat roofs over level ground. It does
not include terrain, vegetation, roof forms, or mutual building shading of roofs.
Buildings without a known height use a clearly reported fallback estimate.
"""
import argparse
import csv
import math
import re
from datetime import date
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pvlib
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.affinity import translate
from shapely.geometry import Polygon, box
from shapely.ops import transform as shapely_transform, unary_union

DEFAULT_BBOX = (16.357, 48.199, 16.389, 48.221)  # lon/lat; Vienna center


def height_from_tags(tags, fallback, level_height):
    """Prefer measured OSM height; otherwise estimate from building levels."""
    def parse_meters(s):
        if not s:
            return None
        s = str(s).strip().lower().replace(',', '.')
        m = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(m|meters?|metres?)?', s)
        if m:
            return float(m.group(1))
        m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:ft|feet|')", s)
        if m:
            return float(m.group(1)) * .3048
        return None

    h = parse_meters(tags.get('height'))
    if h is not None and 2 <= h <= 300:
        return h, 'height'
    levels = tags.get('building:levels')
    try:
        lv = float(str(levels).replace(',', '.'))
        if .5 <= lv <= 70:
            return lv * level_height, 'levels_estimate'
    except (TypeError, ValueError):
        pass
    return fallback, 'fallback_estimate'


def load_pbf(pbf, bbox, fallback, level_height):
    try:
        import osmium
    except ImportError as e:
        raise SystemExit('Install PyOsmium: pip install osmium') from e

    window = box(*bbox)
    features = []

    class Handler(osmium.SimpleHandler):
        def way(self, w):
            if 'building' not in w.tags or w.tags.get('building') == 'no':
                return
            if not w.is_closed():
                return
            try:
                coords = [(n.lon, n.lat) for n in w.nodes]
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or not poly.intersects(window):
                    return
                tags = dict(w.tags)
                height, source = height_from_tags(tags, fallback, level_height)
                features.append({'geometry': poly, 'height_m': height,
                                 'height_source': source, 'osm_id': w.id})
            except (ValueError, RuntimeError, osmium.InvalidLocationError):
                return

    handler = Handler()
    handler.apply_file(str(pbf), locations=True)
    if not features:
        raise ValueError('No building footprints in PBF for requested bbox')
    return gpd.GeoDataFrame(features, geometry='geometry', crs=4326)


def load_vector(path, height_col, fallback, level_height):
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError('Input building layer must have a defined CRS')
    if height_col in gdf.columns:
        values = pd.to_numeric(gdf[height_col], errors='coerce')
        valid = values.between(2, 300)
        gdf['height_m'] = values.where(valid, fallback)
        gdf['height_source'] = np.where(valid, 'height', 'fallback_estimate')
    else:
        gdf['height_m'] = fallback
        gdf['height_source'] = 'fallback_estimate'
    return gdf


def shadow_polygon(poly, dx, dy):
    """Union of the footprint and side faces projected onto horizontal ground.

    For simple building prisms with a flat roof, this is the ground shadow.
    """
    shifted = translate(poly, xoff=dx, yoff=dy)
    pieces = [poly, shifted]
    if poly.geom_type == 'Polygon':
        polygons = [poly]
    elif poly.geom_type == 'MultiPolygon':
        polygons = list(poly.geoms)
    else:
        return None
    for p in polygons:
        coords = list(p.exterior.coords)
        for a, b in zip(coords[:-1], coords[1:]):
            pieces.append(Polygon([a, b, (b[0]+dx, b[1]+dy), (a[0]+dx, a[1]+dy)]))
    return unary_union(pieces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--pbf', type=Path, help='Local austria-latest.osm.pbf')
    source.add_argument('--buildings', type=Path, help='Building GPKG/FGB with height attribute')
    parser.add_argument('--height-column', default='height_m')
    parser.add_argument('--bbox', type=float, nargs=4, default=DEFAULT_BBOX,
                        metavar=('MINLON','MINLAT','MAXLON','MAXLAT'))
    parser.add_argument('--date', default='2026-12-21', help='YYYY-MM-DD')
    parser.add_argument('--start', default='08:00', help='Local Vienna time')
    parser.add_argument('--end', default='16:00', help='Local Vienna time')
    parser.add_argument('--step-minutes', type=int, default=15)
    parser.add_argument('--resolution', type=float, default=5, help='Raster metres per pixel')
    parser.add_argument('--fallback-height', type=float, default=12,
                        help='Estimated height in metres where no height/levels available')
    parser.add_argument('--level-height', type=float, default=3.2)
    parser.add_argument('--out', type=Path, default=Path('day17_vienna_shadows.png'))
    parser.add_argument('--dpi', type=int, default=300)
    args = parser.parse_args()

    if args.resolution <= 0 or args.step_minutes <= 0:
        parser.error('Resolution and step-minutes must be positive')
    if not (args.bbox[0] < args.bbox[2] and args.bbox[1] < args.bbox[3]):
        parser.error('Invalid bounding box')

    transformer = Transformer.from_crs(4326, 31287, always_xy=True)
    reverse = Transformer.from_crs(31287, 4326, always_xy=True)
    study_wgs = box(*args.bbox)
    study = shapely_transform(transformer.transform, study_wgs)
    xmin, ymin, xmax, ymax = study.bounds
    # Geometry transformed from geographic bounding box; use its projected envelope.
    raster_bounds = box(xmin, ymin, xmax, ymax)
    ncols = math.ceil((xmax-xmin)/args.resolution)
    nrows = math.ceil((ymax-ymin)/args.resolution)
    if nrows*ncols > 15_000_000:
        parser.error('Raster exceeds 15 million pixels: increase --resolution or reduce --bbox')
    affine = from_origin(xmin, ymax, args.resolution, args.resolution)

    if args.pbf:
        print('Reading building footprints from local PBF (this may take a while)...', flush=True)
        buildings = load_pbf(args.pbf, args.bbox, args.fallback_height, args.level_height)
    else:
        buildings = load_vector(args.buildings, args.height_column,
                                args.fallback_height, args.level_height)
        buildings = buildings.to_crs(4326)
        buildings = buildings[buildings.intersects(study_wgs)].copy()

    buildings = buildings.to_crs(31287)
    buildings = buildings[buildings.geometry.notna() & ~buildings.geometry.is_empty].copy()
    buildings = buildings[buildings.geometry.geom_type.isin(['Polygon','MultiPolygon'])].copy()
    buildings = buildings[buildings.intersects(raster_bounds)].copy()
    if buildings.empty:
        raise ValueError('No valid buildings in study area')
    buildings['geometry'] = buildings.geometry.map(lambda p: p if p.is_valid else p.buffer(0))
    buildings = buildings[~buildings.geometry.is_empty]
    print('Buildings:', len(buildings))
    print('Height source:', buildings.height_source.value_counts().to_dict())

    # Sample at the middle of each interval; times are timezone-aware.
    day = date.fromisoformat(args.date)
    t0 = pd.Timestamp(f'{day} {args.start}', tz='Europe/Vienna')
    t1 = pd.Timestamp(f'{day} {args.end}', tz='Europe/Vienna')
    if t1 <= t0:
        parser.error('--end must be later than --start')
    times = pd.date_range(t0, t1, freq=f'{args.step_minutes}min', inclusive='left')
    times = times + pd.Timedelta(minutes=args.step_minutes/2)
    center_x, center_y = (xmin+xmax)/2, (ymin+ymax)/2
    lon, lat = reverse.transform(center_x, center_y)
    sun = pvlib.solarposition.get_solarposition(times, latitude=lat, longitude=lon)

    # Count shadowed samples; every interval contributes equal minutes.
    counts = np.zeros((nrows, ncols), dtype=np.uint16)
    building_mask = rasterize(((geom, 1) for geom in buildings.geometry),
                              out_shape=counts.shape, transform=affine,
                              fill=0, dtype='uint8').astype(bool)
    shapes = list(zip(buildings.geometry, buildings.height_m.astype(float)))
    daylight_samples = 0
    for idx, (_, pos) in enumerate(sun.iterrows(), start=1):
        altitude = float(pos['apparent_elevation'])
        if altitude <= 0:
            continue
        daylight_samples += 1
        azimuth = math.radians(float(pos['azimuth']))  # clockwise from north
        tangent = math.tan(math.radians(altitude))
        polys = []
        for geom, h in shapes:
            length = h / tangent
            dx = -length * math.sin(azimuth)
            dy = -length * math.cos(azimuth)
            shadow = shadow_polygon(geom, dx, dy)
            if shadow is not None and shadow.intersects(raster_bounds):
                polys.append((shadow, 1))
        if polys:
            mask = rasterize(polys, out_shape=counts.shape, transform=affine,
                             fill=0, dtype='uint8', all_touched=False)
            counts += mask
        print(f'[{idx}/{len(sun)}] {sun.index[idx-1].strftime("%H:%M")} '
              f'sun altitude={altitude:.1f}°', flush=True)

    hours = counts.astype('float32') * args.step_minutes / 60
    hours[building_mask] = np.nan  # roof insolation is NOT modelled
    hours[~rasterize([(study, 1)], out_shape=counts.shape,
                     transform=affine, fill=0, dtype='uint8').astype(bool)] = np.nan

    args.out.parent.mkdir(parents=True, exist_ok=True)
    import rasterio
    tif_path = args.out.with_suffix('.tif')
    with rasterio.open(tif_path, 'w', driver='GTiff', height=nrows, width=ncols,
                       count=1, dtype='float32', crs='EPSG:31287', transform=affine,
                       nodata=-9999, compress='deflate') as dst:
        dst.write(np.where(np.isfinite(hours), hours, -9999).astype('float32'), 1)
        dst.update_tags(description='Estimated direct-sun building shadow hours',
                        simulation_date=args.date, sample_minutes=args.step_minutes,
                        caveat='Flat terrain, extruded buildings; unknown heights estimated')

    bg = '#f8f7f3'
    fig, ax = plt.subplots(figsize=(12, 11), facecolor=bg)
    ax.set_facecolor(bg)
    # Sequential grey scale: brighter = little shadow; black = prolonged shadow.
    cmap = plt.get_cmap('Greys', 8).copy()
    cmap.set_bad(bg)
    upper = max(1, daylight_samples * args.step_minutes / 60)
    img = ax.imshow(hours, extent=(xmin, xmax, ymin, ymax), origin='upper',
                    cmap=cmap, vmin=0, vmax=upper, interpolation='nearest', zorder=1)
    # buildings.boundary.plot(ax=ax, color='#151515', linewidth=.16, alpha=.85, zorder=3)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.subplots_adjust(left=.035, right=.965, bottom=.12, top=.86)
    fig.text(.06, .955, 'VIENNA IN THE SHADOWS', fontsize=24, fontweight='bold', color='#171717')
    fig.text(.06, .916, f'Day 17 / Light & Dark  ·  {day.strftime("%d %B %Y")}',
             fontsize=11, color='#666666')
    fig.text(.06, .885, f'Estimated building-shadow duration  ·  {args.start}–{args.end} CET/CEST',
             fontsize=10, color='#666666')
    cax = fig.add_axes([.15, .095, .7, .017])
    cb = fig.colorbar(img, cax=cax, orientation='horizontal')
    cb.set_label('Hours in building shadow (ground only)', fontsize=10)
    cb.outline.set_visible(False)
    fig.text(.06, .038,
             f'OSM / local building footprints · {len(buildings):,} buildings · '
             f'{args.resolution:g} m raster · {args.step_minutes}-minute samples',
             fontsize=8, color='#777777')
    fig.text(.06, .020,
             'Simplified model: flat ground and extruded buildings; unknown heights estimated; no trees or terrain.',
             fontsize=8, color='#777777')
    fig.savefig(args.out, dpi=args.dpi, facecolor=bg)
    plt.close(fig)

    csv_path = args.out.with_suffix('.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        for k, v in {
            'buildings': len(buildings),
            'height_from_osm': int((buildings.height_source == 'height').sum()),
            'height_from_levels': int((buildings.height_source == 'levels_estimate').sum()),
            'height_fallback': int((buildings.height_source == 'fallback_estimate').sum()),
            'sun_above_horizon_samples': daylight_samples,
            'sample_minutes': args.step_minutes,
            'shadowed_ground_share_pct': round(100 * np.mean(hours[np.isfinite(hours)] > 0), 2),
        }.items():
            writer.writerow([k, v])
    print(f'Created: {args.out}, {tif_path}, {csv_path}')

if __name__ == '__main__':
    main()
