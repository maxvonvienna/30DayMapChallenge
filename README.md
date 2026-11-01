# 30 Day Map Challenge

My contributions to the [#30DayMapChallenge](https://30daymapchallenge.com/), a daily mapping challenge held every November. Each day has a theme, and each map is built in a Jupyter notebook with Python.

## Maps

### 2026

| Day | Theme | Notebook | Title |
|----:|-------|----------|-------|
| 1 | Points | [`01_points.ipynb`](2026/01_points.ipynb) | A City Park, One Tree at a Time |
| 2 | Lines | [`02_lines.ipynb`](2026/02_lines.ipynb) | Cycling through Vienna — one line at a time! |

#### Day 1: Points, *A City Park, One Tree at a Time*

Vienna's Stadtpark, one tree at a time. Each circle is a single tree, sized by the diameter of its canopy. Data comes from the City of Vienna's tree register (`ogdwien:BAUMKATOGD`), loaded directly from the [Open Government Data Wien](https://data.wien.gv.at/) WFS service.

#### Day 2: Lines, *Cycling through Vienna — one line at a time!*

Vienna's cycling network, stripped of streets and buildings. Major routes are drawn in dark blue, smaller connecting routes in light blue. Data comes from the City of Vienna's cycling network dataset (`ogdwien:RADNETZOGD`), loaded from the same WFS service.

## Project Structure

```
.
├── 2026/
│   ├── 01_points.ipynb   # one notebook per day: NN_<theme>.ipynb
│   ├── 02_lines.ipynb
│   └── maps/             # rendered PNGs (git-ignored)
├── pyproject.toml
└── uv.lock
```

## Setup

The project uses [uv](https://docs.astral.sh/uv/) and requires Python 3.14 or newer.

```bash
uv sync
```

Then open a notebook in Jupyter, DataSpell, or VS Code, using the `.venv` kernel. Each notebook writes its output to `<year>/maps/`.

### Dependencies

- [geopandas](https://geopandas.org/): reading and processing geodata
- [matplotlib](https://matplotlib.org/): rendering the maps
- [pyarrow](https://arrow.apache.org/docs/python/): Parquet I/O
- [ipykernel](https://ipython.readthedocs.io/): Jupyter kernel

## Data Sources

- **City of Vienna, Open Government Data**: [data.wien.gv.at](https://data.wien.gv.at/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de)
