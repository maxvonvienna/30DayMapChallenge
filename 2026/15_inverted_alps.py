#!/usr/bin/env python3
"""Day 15 – The Inverted Alps. Real DEM, reproducible Python cartography.

Requires: pip install numpy matplotlib rasterio requests mercantile

Example:
 python day15_inverted_alps.py --out day15_inverted_alps.png
 python day15_inverted_alps.py --dem /path/to/real_dem.tif --out day15.png

Public AWS Terrain Tiles GeoTIFF elevation data, cached after first download.
The first run needs internet. If offline, supply a local DEM with --dem.

**Day 15 – Inside Out, Upside Down | #30DayMapChallenge**

**The Inverted Alps – When Mountains Become Valleys**

What if the highest peaks of the Alps became their deepest valleys? This map turns the mountainous landscape around Austria's highest peak, the Großglockner, upside down by mathematically inverting its elevation values.

Using a real digital elevation model (DEM), the terrain was transformed so that every peak becomes a depression and every valley turns into a ridge. The resulting landscape was visualized using newly calculated hillshading and contour lines, revealing a strangely familiar yet completely distorted version of the Alps. Both maps show exactly the same geographic area, allowing a direct comparison between the real and inverted terrain.

The experiment demonstrates how a simple mathematical transformation can fundamentally change our perception of a landscape. While the geographic coordinates remain unchanged, the entire topographic logic is reversed. What once dominated the horizon now lies at the bottom of a valley.

Created with Python, Rasterio, NumPy, and Matplotlib using real elevation data.

#30DayMapChallenge #Day15 #InsideOutUpsideDown #Alps #Grossglockner #Topography #GIS #Python #Cartography


"""
import argparse
from pathlib import Path
import io
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from matplotlib.ticker import FuncFormatter
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds, transform as window_transform

# Grossglockner region, WGS84 (west, south, east, north)
BBOX = (12.60, 47.00, 12.85, 47.16)


def fetch_dem(bbox, zoom, cache):
    import requests
    import mercantile
    cache.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in mercantile.tiles(*bbox, zooms=[zoom]):
        path = cache / f'z{zoom}_{t.x}_{t.y}.tif'
        if not path.exists():
            url = f'https://s3.amazonaws.com/elevation-tiles-prod/geotiff/{zoom}/{t.x}/{t.y}.tif'
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            path.write_bytes(r.content)
        paths.append(path)
    if not paths:
        raise RuntimeError('No elevation tiles intersect the bounding box')
    datasets = [rasterio.open(p) for p in paths]
    try:
        # Crop directly to geographic bbox transformed to tile CRS.
        bounds = transform_bounds('EPSG:4326', datasets[0].crs, *bbox)
        data, affine = merge(datasets, bounds=bounds, nodata=-32768)
        return data[0], affine, datasets[0].crs, -32768
    finally:
        for d in datasets: d.close()


def load_local(path, bbox):
    with rasterio.open(path) as ds:
        bounds = transform_bounds('EPSG:4326', ds.crs, *bbox)
        win = from_bounds(*bounds, transform=ds.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
        arr = ds.read(1, window=win, masked=True)
        if arr.size == 0: raise ValueError('DEM does not overlap Grossglockner bbox')
        return arr.filled(-32768).astype('float32'), window_transform(win, ds.transform), ds.crs, -32768


def reproject_utm(arr, transform, src_crs, nodata, cell=30):
    h, w = arr.shape
    src_bounds = rasterio.transform.array_bounds(h, w, transform)
    dst_crs = 'EPSG:32633'
    dst_transform, width, height = calculate_default_transform(src_crs, dst_crs, w, h, *src_bounds, resolution=cell)
    dst = np.full((height, width), -32768, dtype='float32')
    reproject(source=arr.astype('float32'), destination=dst, src_transform=transform, src_crs=src_crs,
              src_nodata=nodata, dst_transform=dst_transform, dst_crs=dst_crs, dst_nodata=-32768,
              resampling=Resampling.bilinear)
    valid = np.isfinite(dst) & (dst != -32768)
    if not valid.any(): raise ValueError('No valid DEM cells in selected region')
    return np.ma.array(dst, mask=~valid), dst_transform


def draw_map(ax, dem, trans, levels, title, subtitle):
    h, w = dem.shape
    left = trans.c;
    top = trans.f;
    right = left + w * trans.a;
    bottom = top + h * trans.e
    extent = (left / 1000, right / 1000, bottom / 1000, top / 1000)
    z = dem.filled(np.nan)
    # LightSource shades actual inverted elevations, not just a reversed colormap.
    ls = LightSource(azdeg=315, altdeg=45)
    rgb = ls.shade(np.nan_to_num(z, nan=float(dem.mean())), cmap=plt.get_cmap('Greys'),
                   vert_exag=1, dx=abs(trans.a), dy=abs(trans.e), blend_mode='overlay')
    ax.imshow(rgb, extent=extent, origin='upper', interpolation='bilinear', zorder=1)
    yy, xx = np.indices((h, w))
    X = (left + (xx + .5) * trans.a) / 1000
    Y = (top + (yy + .5) * trans.e) / 1000
    ax.contour(X, Y, z, levels=levels, colors='#403f3a', linewidths=.24, alpha=.55, zorder=2)
    ax.set_xlim(extent[:2]);
    ax.set_ylim(extent[2:]);
    ax.set_aspect('equal')
    ax.set_title(title, loc='left', fontsize=16, fontweight='bold', pad=12, color='#252522')
    ax.text(.0, 1.005, subtitle, transform=ax.transAxes, fontsize=8, color='#65645e', va='bottom')
    ax.tick_params(labelsize=7, colors='#73716c', length=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}'))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:.0f}'))
    for s in ax.spines.values(): s.set_edgecolor('#bbb8ae');s.set_linewidth(.7)
    ax.set_xlabel('Easting · km (UTM 33N)', fontsize=8, color='#65645e')
    ax.set_ylabel('Northing · km (UTM 33N)', fontsize=8, color='#65645e')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dem', type=Path, help='Optional local real DEM (GeoTIFF), any supported CRS')
    p.add_argument('--out', type=Path, default=Path('maps/map15.png'))
    p.add_argument('--cache', type=Path, default=Path('terrain_tile_cache'))
    p.add_argument('--zoom', type=int, default=11, help='AWS elevation tile zoom; 11 is moderate resolution')
    p.add_argument('--cell', type=float, default=30, help='Output cell size in metres')
    p.add_argument('--dpi', type=int, default=240)
    args = p.parse_args()
    if args.dem:
        arr, tf, crs, nodata = load_local(args.dem, BBOX)
        provenance = f'Local DEM: {args.dem.name}'
    else:
        arr, tf, crs, nodata = fetch_dem(BBOX, args.zoom, args.cache)
        provenance = f'Public AWS elevation GeoTIFF tiles · zoom {args.zoom}'
    dem, tf = reproject_utm(arr, tf, crs, nodata, args.cell)
    lo = float(dem.min());
    hi = float(dem.max())
    inverted = np.ma.array(lo + hi - dem.data, mask=np.ma.getmaskarray(dem))
    step = 100
    levels = np.arange(np.ceil(lo / step) * step, np.floor(hi / step) * step + 1, step)
    # plt.rcParams.update({'font.family': 'DejaVu Sans', 'savefig.facecolor': '#faf9f5'})
    plt.rcParams.update({
        "font.family": "Arial Narrow",
        "font.size": 11,
        "savefig.facecolor": "#ffffff"
    })
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), facecolor='#faf9f5')
    fig.subplots_adjust(left=.055, right=.985, top=.82, bottom=.14, wspace=.10)
    fig.text(.01, .955, 'THE INVERTED ALPS', fontsize=27, fontweight='bold', color='#242420')
    fig.text(.01, .916, 'DAY 15  /  INSIDE OUT, UPSIDE DOWN', fontsize=11, color='#686760')
    fig.text(.01, .882, 'Grossglockner massif · same coordinates, opposite topography', fontsize=11, color='#45443e')
    draw_map(axes[0], dem, tf, levels, '01 / THE REAL ALPS', 'Original elevation model')
    draw_map(axes[1], inverted, tf, levels, '02 / THE INVERTED ALPS', 'Summits become valleys · valleys become ridges')
    fig.text(.01, .055,
             f'Elevation inversion: z′ = {lo:.0f} + {hi:.0f} − z  |  DEM range {lo:.0f}–{hi:.0f} m  |  Contours every 100 m',
             fontsize=9, color='#4b4a45')
    fig.text(.01, .031, f'{provenance}  |  EPSG:32633  |  30DayMapChallenge', fontsize=8, color='#77746e')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    axes[0].set_axis_off()
    axes[1].set_axis_off()
    fig.savefig(args.out, dpi=args.dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f'Saved {args.out} | {dem.shape[1]} × {dem.shape[0]} pixels | elevation {lo:.1f}–{hi:.1f} m')


if __name__ == '__main__': main()
