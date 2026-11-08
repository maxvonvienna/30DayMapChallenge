"""Austria from Scratch: 9-city iterative spatial optimization.

Input: GeoPackage of candidate polygons in EPSG:31287, columns slope, elevation.
Example:
  python 08_austria_utopia_optimize.py candidates.gpkg --layer settlement_candidates --iterations 120

Requires: geopandas, shapely, scipy, numpy, pandas, matplotlib, pyogrio.
"""
import argparse
import heapq
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial import cKDTree, distance_matrix
from shapely.geometry import LineString

N_CITIES = 9
POP_TOTAL = 9_200_000
MAX_DENSITY = 12_000
MAX_SLOPE = 20
MAX_ELEVATION = 1500
MIN_AREA_KM2 = 0.02


def prepare(gdf):
    required = {'slope', 'elevation'}
    if not required.issubset(gdf.columns):
        raise ValueError(f'Missing columns: {required - set(gdf.columns)}')
    if gdf.crs is None:
        raise ValueError('Input must have a CRS')
    gdf = gdf.to_crs(31287).copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf[gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])].copy()
    gdf = gdf.dropna(subset=['slope', 'elevation'])
    gdf['area_km2'] = gdf.geometry.area / 1e6
    gdf = gdf[(gdf.slope >= 0) & (gdf.slope <= MAX_SLOPE) &
              (gdf.elevation <= MAX_ELEVATION) & (gdf.area_km2 >= MIN_AREA_KM2)].reset_index(drop=True)
    gdf['capacity'] = np.floor(gdf.area_km2 * MAX_DENSITY).astype('int64')
    if len(gdf) < N_CITIES or gdf.capacity.sum() < POP_TOTAL:
        raise ValueError('Not enough suitable cells/capacity for the scenario')
    return gdf


def build_adjacency(gdf, tolerance=1.0):
    """Queen contiguity from polygon boundaries, not centroid proximity.
    Uses spatial index and small tolerance for numerical precision.
    """
    geoms = gdf.geometry.array
    tree = gdf.sindex
    adj = [[] for _ in range(len(gdf))]
    for i, geom in enumerate(geoms):
        for j in tree.query(geom.buffer(tolerance), predicate='intersects'):
            j = int(j)
            if j <= i:
                continue
            if geom.distance(geoms[j]) <= tolerance:
                adj[i].append(j)
                adj[j].append(i)
    return adj


def select_seeds(coords, quality, capacity, rng, n=N_CITIES):
    """Quality-weighted farthest-point initialization."""
    first = int(np.argmax(quality + rng.uniform(0, .02, len(quality))))
    seeds = [first]
    nearest = np.linalg.norm(coords - coords[first], axis=1)
    for _ in range(1, n):
        score = nearest * (.3 + .7 * quality)
        score[seeds] = -1
        idx = int(np.argmax(score))
        seeds.append(idx)
        nearest = np.minimum(nearest, np.linalg.norm(coords - coords[idx], axis=1))
    return np.array(seeds, dtype=int)


def mst_edges(center_coords):
    dist = distance_matrix(center_coords, center_coords)
    np.fill_diagonal(dist, 0)
    mst = minimum_spanning_tree(dist).tocoo()
    edges = [(int(a), int(b), float(d)) for a, b, d in zip(mst.row, mst.col, mst.data)]
    return edges, sum(e[2] for e in edges) / 1000


def allocate(seeds, coords, capacity, terrain_cost, adjacency, targets, distance_weight=0.5):
    """Simultaneous multi-source growth; every assigned cell has a path to its seed.
    Infeasible runs return None (no disconnected fallback).
    """
    n = len(coords)
    owner = np.full(n, -1, dtype=np.int16)
    pop = np.zeros(n, dtype=np.int64)
    remain = targets.copy()
    heap = []
    # Seeds are reserved before any expansion.
    for city, idx in enumerate(seeds):
        owner[idx] = city
        a = min(int(capacity[idx]), int(remain[city]))
        pop[idx] = a
        remain[city] -= a

    def push(i, city):
        if owner[i] != -1 or remain[city] <= 0:
            return
        d = np.linalg.norm(coords[i] - coords[seeds[city]]) / 1000
        heapq.heappush(heap, (float(terrain_cost[i] + distance_weight * d / 30), int(i), int(city)))

    for city, idx in enumerate(seeds):
        for j in adjacency[idx]:
            push(j, city)
    while heap and np.any(remain > 0):
        _, i, city = heapq.heappop(heap)
        if owner[i] != -1 or remain[city] <= 0:
            continue
        owner[i] = city
        a = min(int(capacity[i]), int(remain[city]))
        pop[i] = a
        remain[city] -= a
        if remain[city] > 0:
            for j in adjacency[i]:
                push(j, city)
    if np.any(remain > 0):
        return None
    return owner, pop


def evaluate(seeds, coords, capacity, terrain_cost, adjacency, targets, weights):
    allocation = allocate(seeds, coords, capacity, terrain_cost, adjacency, targets)
    if allocation is None:
        return None
    owner, pop = allocation
    used = pop > 0
    # Effective occupied area at maximum density, not full-cell footprint.
    area_km2 = pop.sum() / MAX_DENSITY
    terrain = np.average(terrain_cost[used], weights=pop[used])
    compactness_km = (np.linalg.norm(coords[used] - coords[seeds[owner[used]]], axis=1) / 1000)
    compactness = np.average(compactness_km, weights=pop[used])
    edges, network_km = mst_edges(coords[seeds])
    # Geographic coverage: penalize leaving suitable land far from every city.
    # Deterministic subsample to keep each optimization iteration affordable.
    sample = np.arange(0, len(coords), max(1, len(coords) // 3000))
    nearest_km = cKDTree(coords[seeds]).query(coords[sample], k=1)[0] / 1000
    suitability_weights = np.maximum(0.05, 1.0 - terrain_cost[sample])
    coverage_km = float(np.average(nearest_km, weights=suitability_weights))
    # Dimensionless objective terms; weights are scenario preferences, not calibrated costs.
    score = (weights['terrain'] * terrain
             + weights['compactness'] * compactness / 30
             + weights['network'] * network_km / 1000
             + weights['coverage'] * coverage_km / 100)
    return {'score': float(score), 'owner': owner, 'population': pop,
            'terrain': float(terrain), 'compactness_km': float(compactness),
            'network_km': float(network_km), 'coverage_km': coverage_km, 'occupied_area_km2': float(area_km2),
            'edges': edges, 'seeds': seeds.copy()}


def optimize(gdf, iterations=120, random_seed=42, weights=None):
    weights = weights or {'terrain': .35, 'compactness': .30, 'network': .15, 'coverage': .20}
    rng = np.random.default_rng(random_seed)
    centers = gdf.geometry.representative_point()
    coords = np.column_stack([centers.x.to_numpy(), centers.y.to_numpy()])
    capacity = gdf.capacity.to_numpy()
    slope = gdf.slope.to_numpy(float)
    elev = gdf.elevation.to_numpy(float)
    terrain_cost = .7 * slope / MAX_SLOPE + .3 * np.clip(elev, 0, None) / MAX_ELEVATION
    quality = np.clip(1 - terrain_cost, 0, 1)
    adjacency = build_adjacency(gdf)
    targets = np.full(N_CITIES, POP_TOTAL // N_CITIES, dtype=np.int64)
    targets[:POP_TOTAL % N_CITIES] += 1
    # Multiple initializations can help when mountain barriers block growth.
    current = None
    for attempt in range(20):
        seeds = select_seeds(coords, quality, capacity, rng)
        trial = evaluate(seeds, coords, capacity, terrain_cost, adjacency, targets, weights)
        if trial is not None and (current is None or trial['score'] < current['score']):
            current = trial
    if current is None:
        raise RuntimeError(
            'No feasible connected allocation found. Check terrain masks and regional capacities; try coarser grid or relax constraints.')
    initial = current
    history = [current['score']]
    # Local seed relocation: propose nearby candidate cells; accept only improvements.
    for iteration in range(iterations):
        city = int(rng.integers(N_CITIES))
        radius_m = float(rng.choice([5000, 10000, 20000, 40000]))
        distances = np.linalg.norm(coords - coords[current['seeds'][city]], axis=1)
        options = np.flatnonzero((distances > 0) & (distances <= radius_m) & (quality > .2))
        if len(options) == 0:
            history.append(current['score'])
            continue
        new_idx = int(rng.choice(options))
        if new_idx in current['seeds']:
            history.append(current['score'])
            continue
        proposed_seeds = current['seeds'].copy()
        proposed_seeds[city] = new_idx
        trial = evaluate(proposed_seeds, coords, capacity, terrain_cost, adjacency, targets, weights)
        if trial is not None and trial['score'] < current['score'] - 1e-10:
            current = trial
        history.append(current['score'])
    return initial, current, history, coords


def save_outputs(gdf, result, history, coords, outdir, initial):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    used = result['population'] > 0
    cells = gdf.loc[used].copy()
    cells['city_id'] = result['owner'][used].astype(int)
    cells['population_new'] = result['population'][used]
    cells['occupied_km2'] = cells['population_new'] / MAX_DENSITY
    cells.to_file(outdir / 'utopia.gpkg', layer='settlement_cells', driver='GPKG')
    cities = cells.dissolve(by='city_id', aggfunc={'population_new': 'sum', 'occupied_km2': 'sum'}).reset_index()
    cities['density'] = cities.population_new / cities.occupied_km2
    cities.to_file(outdir / 'utopia.gpkg', layer='city_regions', driver='GPKG', mode='a')
    seed_coords = coords[result['seeds']]
    points = gpd.GeoDataFrame({'city_id': range(N_CITIES)},
                              geometry=gpd.points_from_xy(seed_coords[:, 0], seed_coords[:, 1]), crs=31287)
    points.to_file(outdir / 'utopia.gpkg', layer='city_centers', driver='GPKG', mode='a')
    lines = gpd.GeoDataFrame({'length_km': [e[2] / 1000 for e in result['edges']]},
                             geometry=[LineString([seed_coords[a], seed_coords[b]]) for a, b, _ in result['edges']],
                             crs=31287)
    lines.to_file(outdir / 'utopia.gpkg', layer='mst_network', driver='GPKG', mode='a')
    austria = gpd.read_file("data/at_border.geojson")
    fig, ax = plt.subplots(figsize=(14, 9))
    austria.to_crs(31287).plot(
        ax=ax,
        color="#F0EEE7",
        edgecolor="#999999",
        linewidth=0.5
    )
    cities.plot(ax=ax, color='#507c72', edgecolor='#1f3e3a', linewidth=.5, alpha=.85)
    lines.plot(ax=ax, color='#c77d4d', linewidth=1.2, zorder=3)
    points.plot(ax=ax, color='#203c39', markersize=18, zorder=4)
    ax.set_axis_off()
    ax.set_aspect('equal')
    fig.patch.set_facecolor('#f6f2e8')
    fig.savefig(outdir / 'utopia_map.png', dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    fig.savefig('maps/map08.png', dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(history)
    ax.set(xlabel='Iteration', ylabel='Normalized objective', title='Optimization progress')
    fig.tight_layout()
    fig.savefig(outdir / 'optimization.png', dpi=180)
    plt.close(fig)
    summary = {'initial': {k: initial[k] for k in
                           ('score', 'terrain', 'compactness_km', 'network_km', 'coverage_km', 'occupied_area_km2')},
               'final': {k: result[k] for k in
                         ('score', 'terrain', 'compactness_km', 'network_km', 'coverage_km', 'occupied_area_km2')},
               'cities': N_CITIES, 'population': int(cells.population_new.sum()),
               'note': 'Nine equal-population regions. Coverage is mean distance of sampled suitable candidate cells to nearest city center. MST uses straight-line links; terrain-aware routing is a future extension. Occupied area is theoretical at maximum density, not exact polygon footprint.'}
    (outdir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='GeoPackage with candidate polygons')
    parser.add_argument('--layer', default=None)
    parser.add_argument('--iterations', type=int, default=120)
    parser.add_argument('--output', default='utopia_output')
    args = parser.parse_args()
    gdf = prepare(gpd.read_file(args.input, layer=args.layer))
    initial, best, history, coords = optimize(gdf, iterations=args.iterations)
    save_outputs(gdf, best, history, coords, args.output, initial)


if __name__ == '__main__':
    main()
