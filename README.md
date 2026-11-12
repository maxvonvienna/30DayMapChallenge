# 30 Day Map Challenge

My contributions to the [#30DayMapChallenge](https://30daymapchallenge.com/), a daily mapping challenge held every November. Each day has a theme. Most maps are built in a Jupyter notebook with Python, and some are made in QGIS.

All finished maps are on my website: [aim.wien/blog/30-day-map-challenge-2026](https://aim.wien/blog/30-day-map-challenge-2026/).

## Maps

### 2026

| Day | Theme | Notebook | Title |
|----:|-------|----------|-------|
| 1 | Points | [`01_points.ipynb`](2026/01_points.ipynb) | A City Park, One Tree at a Time |
| 2 | Lines | [`02_lines.ipynb`](2026/02_lines.ipynb) | Cycling through Vienna — one line at a time! |
| 3 | Polygons | [`03_polygons.ipynb`](2026/03_polygons.ipynb) | Vienna's Stadtpark — a city landscape built from polygons! |
| 4 | My Data | [`04_cluster.ipynb`](2026/04_cluster.ipynb) | Where do plastic surgeons cluster in Vienna? |
| 5 | Senses: Sight | [`05_sight.ipynb`](2026/05_sight.ipynb) | Can you see Vienna's St. Stephen's Cathedral from where you stand? |
| 6 | Vintage | [`06_vintage.ipynb`](2026/06_vintage.ipynb) | Vienna, two centuries ago |
| 7 | 10 Minutes | [`07_10minute.ipynb`](2026/07_10minute.ipynb) | Austria, connected by lines |
| 8 | Utopia | [`08_utopia_dem.ipynb`](2026/08_utopia_dem.ipynb) | Austria from Scratch — what if we could redesign an entire country? |
| 9 | Urban–Rural | [`09_urban-rural.ipynb`](2026/09_urban-rural.ipynb) | The Invisible City — Mapping Austria's Settlement Structure |
| 10 | Prompting Only | [`10_prompted.py`](2026/10_prompted.py) | 100 Years of Urban Growth (1925–2025) |
| 11 | Senses: Sound | [`11_sound.ipynb`](2026/11_sound.ipynb) | Can you hear the city? Mapping railway noise in Vienna |
| 12 | Power | [`12_power.ipynb`](2026/12_power.ipynb) | Solar power in Vienna's districts |

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

#### Day 6: Vintage, *Vienna, two centuries ago*

Vienna in the early 19th century, before the Ringstraße, when it was still a fortified city ringed by open land, gardens, fields and the suburbs that later became part of the city. The map is styled after historical cartography, with fine linework, muted colours and subtle textures. It is based on the Franziscan Cadastre (Franziszeischer Kataster), loaded from the City of Vienna's WFS service (`ogdwien:FRANZKATOGD`).

This map was made in QGIS, not Python. The project is `2026/06_vintage.qgz`, and the notebook holds only the description.

#### Day 7: 10 Minutes, *Austria, connected by lines*

A map made in ten minutes: Austria's electricity transmission network and nothing else. With no borders, cities or labels, the power lines become an almost abstract drawing of the country. The simplified network (1,891 line segments) is stored in `2026/07_10minute.gpkg`. Its source attributes credit BEV and the grid operators, including APG and several regional network companies. The notebook shows the rendered map.

#### Day 8: Utopia, *Austria from Scratch — what if we could redesign an entire country?*

A thought experiment that ignores existing cities, roads and borders and moves Austria's population of about 9.2 million into nine newly planned urban regions of equal size. Austria is split into the 1 km cells of Statistik Austria's regional statistical grid. Each cell gets the mean slope and elevation of a 10 m Digital Terrain Model derived from airborne laser scanning. Only cells with a slope of at most 20° and an elevation of at most 1,500 m qualify, and density is capped at 12,000 inhabitants per km². The cities grow outward from seed cells, preferring flat, low terrain. An iterative optimization (200 iterations for the final map) then relocates the seeds one at a time and keeps a move only if it improves a combined score of terrain, compactness, network length and coverage of the suitable land. The cities are linked by a minimum spanning tree of straight lines between their centres. This is a deliberate thought experiment, not a planning proposal.

The notebook prepares the candidate cells and contains a first single-pass version. The final map comes from `08_austria_utopia_optimize.py`. See [Setup](#setup).

#### Day 9: Urban–Rural, *The Invisible City — Mapping Austria's Settlement Structure*

Where does the city end and the countryside begin? This map leaves out administrative boundaries and population figures and looks only at buildings. For each of the 1.35 million cells of Statistik Austria's 250 m grid, a continuous urbanity index combines building density (40 %), built-up share of the cell (35 %) and the median distance to the nearest neighbouring building (25 %). Each measure is scaled between its 5th and 95th percentile first. The result shows cities as dark cores and valleys and transport corridors as fine branching lines, with a gradual transition from urban to rural rather than a sharp border.

The building statistics per grid cell are computed in PostGIS with `2026/09.sql`. See [Setup](#setup).

#### Day 10: Prompting Only, *100 Years of Urban Growth (1925–2025)*

What happens when AI takes over the entire mapmaking process? This map follows a fictional city through 100 years of growth, from a compact settlement to a sprawling urban landscape. A synthetic cellular growth model expands the city from its existing settlements along transport connections, held back by a river, hills and protected areas. Every step, from generating the data and running the simulation to the cartographic styling and export, was done by ChatGPT using Python, NumPy, SciPy and Matplotlib. There is no real-world geodata and no manual editing, just prompting.

The map comes from `2026/10_prompted.py`, which uses a fixed random seed and writes `maps/map10.png`. The description is in `2026/_prompted.ipynb`.

#### Day 11: Senses: Sound, *Can you hear the city? Mapping railway noise in Vienna*

The invisible geography of railway noise around Wien Hauptbahnhof, at the centre of the map. Coloured zones show railway noise exposure from Austria's 2022 strategic noise mapping (day-evening-night indicator, Lden), and black building footprints show the dense city around the tracks. The noise follows the railway corridors but spreads well beyond the tracks into the surrounding neighbourhoods. The noise zones are loaded as an image from the noise mapping WMS (`2022_SCHIENE_24H_ZONEN_OE`), and the buildings from the City of Vienna's WFS service (`ogdwien:FMZKGEBOGD`).

#### Day 12: Power, *Solar power in Vienna's districts*

How much solar power is installed in each of Vienna's 23 districts, relative to their size? Each solar installation from the City of Vienna's solar dataset (`ogdwien:SOLARANLAGLSTGOGD`) is assigned to exactly one district using a point inside its outline. The installed capacity is summed per district and divided by the district's area in hectares. District boundaries come from `ogdwien:BEZIRKSGRENZEOGD`.

## Hashtags

All hashtags used across the maps, without the per-day `#DayN` tags:

```
#30DayMapChallenge #Points #Lines #Polygons #MyData #Senses #Sight #Vintage #10Minutes #Vienna #Austria #Stadtpark #Stephansdom #GIS #GeoData #Geospatial #OpenData #Cartography #HistoricalCartography #MinimalistCartography #SpatialAnalysis #Viewshed #DBSCAN #Python #GeoPandas #UrbanGreen #UrbanHistory #CyclingInfrastructure #HealthcareGeography #ElectricityGrid #Utopia #SpatialOptimization #UrbanPlanning #RegionalDevelopment #UrbanRural #SettlementPatterns #UrbanMorphology #PromptingOnly #UrbanGrowth #Sound #NoisePollution #Power #SolarEnergy
```

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
│   ├── 06_vintage.ipynb  # description only
│   ├── 06_vintage.qgz    # QGIS project for Day 6
│   ├── 07_10minute.ipynb
│   ├── 07_10minute.gpkg  # power line data for Day 7
│   ├── 08_utopia_dem.ipynb
│   ├── 08_austria_utopia_optimize.py  # 9-city optimization for Day 8
│   ├── 09_urban-rural.ipynb
│   ├── 09.sql            # PostGIS building statistics for Day 9
│   ├── 09_download.py    # downloads the 250 m grid and building footprints for Day 9
│   ├── 10_prompted.py    # synthetic urban-growth simulation and map for Day 10
│   ├── _prompted.ipynb   # description for Day 10
│   ├── 11_sound.ipynb
│   ├── 12_power.ipynb
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

Day 6 is a QGIS project. Open `2026/06_vintage.qgz` in [QGIS](https://qgis.org/); it streams its data from the WFS service, so you need an internet connection.

Day 8's final map comes from the optimization script. Run it from `2026/`:

```bash
cd 2026
uv run python 08_austria_utopia_optimize.py data/austria_candidates.gpkg \n    --layer settlement_candidates --iterations 200 --output data/utopia_9_cities
```

The input is a GeoPackage of 1 km candidate cells with `slope` and `elevation` columns. The script writes `utopia.gpkg` (settlement cells, city regions, city centres and the network), `utopia_map.png`, `optimization.png` and `summary.json` to the output folder, and it saves the map as `maps/map08.png`. Both the input `data/austria_candidates.gpkg` and the result in `data/utopia_9_cities/` are included in the repository.

Day 9 needs a PostgreSQL/PostGIS database with the building footprints and the 250 m grid. `09_download.py` downloads both: the grid from Statistik Austria's WFS service to `data/raster_250m.gpkg`, and the building footprints from BEV's Digital Landscape Model (DLM) to `data/buildings.gpkg`. `09.sql` builds materialized views with the number of buildings, built-up share and nearest-neighbour distances per grid cell. The joined result is exported to `data/buildings_grid.gpkg`, which the notebook reads. This file is about 320 MB and is not included in the repository. The notebook draws the 1.35 million cells as a single raster image instead of individual polygons, which takes seconds instead of more than a minute.

### Dependencies

- [geopandas](https://geopandas.org/): reading and processing geodata
- [matplotlib](https://matplotlib.org/): rendering the maps
- [pyarrow](https://arrow.apache.org/docs/python/): Parquet I/O
- [rasterio](https://rasterio.readthedocs.io/): reading the elevation rasters and rendering the Day 9 grid
- [scikit-learn](https://scikit-learn.org/): DBSCAN clustering
- [scipy](https://scipy.org/): spatial index and minimum spanning tree for Day 8, growth simulation for Day 10
- [requests](https://requests.readthedocs.io/) and [geojson](https://github.com/jazzband/geojson): loading data from the WFS and WMS services
- [tqdm](https://tqdm.github.io/): progress bar for the viewshed analysis
- [ipykernel](https://ipython.readthedocs.io/): Jupyter kernel

## Data Sources

- **City of Vienna, Open Government Data**: [data.wien.gv.at](https://data.wien.gv.at/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de)
- **BEV (Bundesamt für Eich- und Vermessungswesen), airborne laser scanning**: DSM and DTM from [data.bev.gv.at](https://data.bev.gv.at/)
- **ÖGK (Österreichische Gesundheitskasse)**: physician data for Day 4
- **BEV and Austrian grid operators (APG and regional network companies)**: power line data for Day 7
- **Land Kärnten, Digital Terrain Model (DGM) of Austria**: 10 m × 10 m terrain heights from airborne laser scanning, GeoTIFF in EPSG:31287, used for slope and elevation in Day 8
- **BEV, Digital Landscape Model (DLM)**: building footprints for Day 9
- **Austrian strategic noise mapping 2022**: railway noise zones (Lden) for Day 11, via the WMS at `inspire.lfrz.gv.at`
- **Statistik Austria**: 1 km regional statistical grid (Regionalstatistisches Raster) and the national border for Day 8, and the 250 m grid for Day 9
