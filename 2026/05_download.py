"""Download the DSM and DTM for Day 5, clipped to Vienna's first district.

The BEV tiles cover 50 x 50 km (8-9 GB each). They are tiled GeoTIFFs, so only
the blocks that intersect the district are fetched, via HTTP range requests.
"""
import argparse
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask

BASE_DIR = Path(__file__).resolve().parent
DISTRICT = BASE_DIR / "data" / "innere_stadt.geojson"

TILE_URL = (
    "https://data.bev.gv.at/download/ALS/{model}/20250915/"
    "ALS_{model}_CRS3035RES50000mN2800000E4750000.tif"
)
MODELS = {"DSM": "dsm.tif", "DTM": "dtm.tif"}

GDAL_OPTIONS = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": 3,
    "GDAL_HTTP_RETRY_DELAY": 2,
}


def clip_tile(url, district, output):
    with rasterio.open(url) as src:
        geometry = district.to_crs(src.crs).geometry.union_all()
        data, transform = mask(src, [geometry], crop=True)

        profile = src.profile
        profile.update(
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            transform=transform,
            compress="lzw",
        )

    # Write to a temporary file so a failed run leaves no partial raster behind.
    temporary = output.with_name(f"{output.stem}.tmp{output.suffix}")

    with rasterio.open(temporary, "w", **profile) as dst:
        dst.write(data)

    temporary.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "data")
    parser.add_argument("--force", action="store_true", help="overwrite existing rasters")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    district = gpd.read_file(DISTRICT)

    with rasterio.Env(**GDAL_OPTIONS):
        for model, filename in MODELS.items():
            output = args.output_dir / filename

            if output.exists() and not args.force:
                print(f"skipped {output} (exists, use --force to overwrite)")
                continue

            clip_tile(TILE_URL.format(model=model), district, output)
            print(f"saved: {output}")


if __name__ == "__main__":
    main()
