import numpy as np
import geopandas as gpd
import rasterio

from shapely.geometry import Point
from rasterio.warp import reproject, Resampling
from rasterio.features import geometry_mask
from tqdm import tqdm

DSM = "data/dsm.tif"
DTM = "data/dtm.tif"
DISTRICT = "data/innere_stadt.geojson"
DOM = "data/stephansdom.geojson"

OUTPUT = "data/stephansdom_visibility.gpkg"

GRID_SPACING = 5.0
EYE_HEIGHT = 1.6
MAX_GROUND_DIFFERENCE = 2.0
TARGET_SPACING = 5.0


def sample_raster(data, transform, x, y):
    row, col = rasterio.transform.rowcol(transform, x, y)

    if (
            row < 0 or col < 0
            or row >= data.shape[0]
            or col >= data.shape[1]
    ):
        return np.nan

    return float(data[row, col])


def line_of_sight(
        x1, y1, z1,
        x2, y2, z2,
        dsm, transform,
        step=0.5
):
    distance = np.hypot(x2 - x1, y2 - y1)

    if distance == 0:
        return True

    n = max(2, int(np.ceil(distance / step)))

    t = np.arange(1, n) / n

    xs = x1 + t * (x2 - x1)
    ys = y1 + t * (y2 - y1)
    zs = z1 + t * (z2 - z1)

    rows, cols = rasterio.transform.rowcol(
        transform, xs, ys
    )

    rows = np.asarray(rows)
    cols = np.asarray(cols)

    valid = (
            (rows >= 0)
            & (cols >= 0)
            & (rows < dsm.shape[0])
            & (cols < dsm.shape[1])
    )

    if not valid.all():
        return False

    heights = dsm[rows, cols]

    if not np.isfinite(heights).all():
        return False

    return bool(np.all(heights < zs))


with rasterio.open(DSM) as src:
    dsm = src.read(1, masked=True).filled(np.nan)
    transform = src.transform
    crs = src.crs
    shape = dsm.shape

    if not crs.is_projected:
        raise ValueError("DSM must have metric CRS.")

    if not np.isclose(abs(transform.a), 1.0):
        print("Info: DSM resolution not 1 m.")

    with rasterio.open(DTM) as dtm_src:
        dtm = np.full(shape, np.nan, dtype=np.float32)

        reproject(
            source=rasterio.band(dtm_src, 1),
            destination=dtm,
            src_transform=dtm_src.transform,
            src_crs=dtm_src.crs,
            src_nodata=dtm_src.nodata,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )

district = gpd.read_file(DISTRICT).to_crs(crs)
dom = gpd.read_file(DOM).to_crs(crs)

district_geom = district.geometry.union_all()
dom_geom = dom.geometry.union_all()

dom_mask = geometry_mask(
    [dom_geom],
    transform=transform,
    out_shape=shape,
    invert=True
)

target_points = []

minx, miny, maxx, maxy = dom_geom.bounds

for x in np.arange(minx, maxx, TARGET_SPACING):
    for y in np.arange(miny, maxy, TARGET_SPACING):
        if not dom_geom.covers(Point(x, y)):
            continue

        z = sample_raster(dsm, transform, x, y)

        if np.isfinite(z):
            target_points.append((x, y, z + 0.5))

if not target_points:
    raise ValueError("No valid targetpoints on Target.")

print(f"target points: {len(target_points)}")

minx, miny, maxx, maxy = district_geom.bounds

observers = []

for x in np.arange(minx, maxx, GRID_SPACING):
    for y in np.arange(miny, maxy, GRID_SPACING):
        p = Point(x, y)

        if not district_geom.covers(p):
            continue

        if dom_geom.covers(p):
            continue

        ground = sample_raster(dtm, transform, x, y)
        surface = sample_raster(dsm, transform, x, y)

        if not np.isfinite(ground) or not np.isfinite(surface):
            continue

        if surface - ground > MAX_GROUND_DIFFERENCE:
            continue

        observers.append((x, y, ground + EYE_HEIGHT))

print(f"observing points: {len(observers)}")

results = []

for x, y, z in tqdm(observers):
    n_visible = 0

    for tx, ty, tz in target_points:
        if line_of_sight(
                x, y, z,
                tx, ty, tz,
                dsm,
                transform,
                step=0.5
        ):
            n_visible += 1

    results.append({
        "geometry": Point(x, y),
        "visible": int(n_visible > 0),
        "n_visible": n_visible
    })

gdf = gpd.GeoDataFrame(results, crs=crs)

gdf.to_file(
    OUTPUT,
    layer="visibility",
    driver="GPKG"
)

print(gdf["visible"].value_counts())
print(f"saved: {OUTPUT}")
