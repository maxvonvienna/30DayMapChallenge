# 30 Day Map Challenge

My contributions to the [#30DayMapChallenge](https://30daymapchallenge.com/), a daily mapping challenge held every November. Each day has a theme, and each map is built in a Jupyter notebook with Python.

## Maps

### 2026

| Day | Theme | Notebook | Title |
|----:|-------|----------|-------|
| 1 | Points | [`01_points.ipynb`](2026/01_points.ipynb) | A City Park, One Tree at a Time |
| 2 | Lines | [`02_lines.ipynb`](2026/02_lines.ipynb) | Cycling through Vienna — one line at a time! |
| 3 | Polygons | [`03_polygons.ipynb`](2026/03_polygons.ipynb) | Vienna's Stadtpark — a city landscape built from polygons! |
| 4 | My Data | [`04_cluster.ipynb`](2026/04_cluster.ipynb) | Where do plastic surgeons cluster in Vienna? |
| 5 | Senses: Sight | [`05_sight.ipynb`](2026/05_sight.ipynb) | Can you see Vienna's St. Stephen's Cathedral from where you stand? |

#### Day 1: Points, *A City Park, One Tree at a Time*

Vienna's Stadtpark, one tree at a time. Each circle is a single tree, sized by the diameter of its canopy. Data comes from the City of Vienna's tree register (`ogdwien:BAUMKATOGD`), loaded directly from the [Open Government Data Wien](https://data.wien.gv.at/) WFS service.

#### Day 2: Lines, *Cycling through Vienna — one line at a time!*

Vienna's cycling network, stripped of streets and buildings. Major routes are drawn in dark blue, smaller connecting routes in light blue. Data comes from the City of Vienna's cycling network dataset (`ogdwien:RADNETZOGD`), loaded from the same WFS service.

#### Day 3: Polygons, *Vienna's Stadtpark — a city landscape built from polygons!*

The Stadtpark as a mosaic of polygons: water, green space, traffic areas and buildings, with no labels or map symbols. Data comes from the City of Vienna's multi-purpose map layers (`ogdwien:FMZK*OGD`), loaded from the same WFS service.

#### Day 4: My Data, *Where do plastic surgeons cluster in Vienna?*

The 130 physicians specializing in plastic surgery in Vienna, clustered with DBSCAN (500 m neighbourhood, at least 5 points per core point). This finds four clusters holding 45 physicians, concentrated in and around the central districts. The other 85 are not assigned to any cluster and appear as grey dots. Physician data comes from the ÖGK and is stored in `2026/data/plastic_surgery.geojson`.

#### Day 5: Senses: Sight, *Can you see Vienna's St. Stephen's Cathedral from where you stand?*

A viewshed of Vienna's first district. Observer points on a 5 m grid, at an eye height of 1.6 m, are tested for a line of sight to the cathedral against a 1 m Digital Surface Model and Digital Terrain Model. Points where the surface is more than 2 m above the ground, such as those on buildings, are skipped. Of the 44,327 points tested, 1,742 can see the cathedral (green) and the rest cannot (red). The elevation models come from BEV's airborne laser scanning data, and building footprints from `ogdwien:FMZKGEBOGD`.

This is the only map that needs a separate analysis step. See [Setup](#setup).

## Project Structure

```
.
├── 2026/
│   ├── 01_points.ipynb   # one notebook per day: NN_<theme>.ipynb
│   ├── 02_lines.ipynb
│   ├── 03_polygons.ipynb
│   ├── 04_cluster.ipynb
│   ├── 05_sight.ipynb
│   ├── 05_download.py    # downloads the elevation rasters for Day 5
│   ├── 05_sight.py       # viewshed analysis for Day 5
│   ├── data/             # input data and analysis results
│   └── maps/             # rendered PNGs (git-ignored)
├── pyproject.toml
└── uv.lock
```

## Setup

The project uses [uv](https://docs.astral.sh/uv/) and requires Python 3.14 or newer.

```bash
uv sync
```

Then open a notebook in Jupyter, DataSpell, or VS Code, using the `.venv` kernel. Each notebook writes its output to `<year>/maps/`. Paths are relative, so run notebooks with `2026/` as the working directory.

Day 5 reads a precomputed result. To regenerate it, download the elevation rasters and run the analysis from `2026/`:

```bash
cd 2026
uv run python 05_download.py
uv run python 05_sight.py
```

`05_download.py` clips the DSM and DTM to the first district and saves them as `data/dsm.tif` and `data/dtm.tif`, fetching only the part of each 50 km tile it needs. It skips rasters that already exist unless you pass `--force`. `05_sight.py` then writes `data/stephansdom_visibility.gpkg`, which `05_sight.ipynb` plots.

### Dependencies

- [geopandas](https://geopandas.org/): reading and processing geodata
- [matplotlib](https://matplotlib.org/): rendering the maps
- [pyarrow](https://arrow.apache.org/docs/python/): Parquet I/O
- [rasterio](https://rasterio.readthedocs.io/): reading the elevation rasters
- [scikit-learn](https://scikit-learn.org/): DBSCAN clustering
- [tqdm](https://tqdm.github.io/): progress bar for the viewshed analysis
- [ipykernel](https://ipython.readthedocs.io/): Jupyter kernel

## Data Sources

- **City of Vienna, Open Government Data**: [data.wien.gv.at](https://data.wien.gv.at/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de)
- **BEV (Bundesamt für Eich- und Vermessungswesen), airborne laser scanning**: DSM and DTM from [data.bev.gv.at](https://data.bev.gv.at/)
- **ÖGK (Österreichische Gesundheitskasse)**: physician data for Day 4
