#!/usr/bin/env python3
"""Day 24 — The Hidden Backbone of Vienna.

OSM road network + sampled, length-weighted edge betweenness centrality.
Outputs a high-resolution PNG, GeoPackage of road segments and a JSON summary.

Install: pip install osmnx networkx geopandas matplotlib numpy pandas pyproj
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.collections import LineCollection
import networkx as nx
import numpy as np
import osmnx as ox

LOG = logging.getLogger('backbone')


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--place', default='Wien, Österreich', help='OSM geocoding place')
    p.add_argument('--network-type', default='drive', choices=['drive', 'drive_service', 'walk', 'bike', 'all'])
    p.add_argument('--sources', type=int, default=350, help='Sampled origin nodes')
    p.add_argument('--targets', type=int, default=100, help='Sampled destinations per origin')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--min-percentile', type=float, default=75.0, help='Show colored segments above percentile of positive scores')
    p.add_argument('--dpi', type=int, default=300)
    p.add_argument('--out', default='day24_hidden_backbone_vienna.png')
    p.add_argument('--cache', default='day24_vienna_osm.graphml')
    p.add_argument('--no-cache', action='store_true')
    return p.parse_args()


def fetch_graph(args):
    cache = Path(args.cache)
    if cache.exists() and not args.no_cache:
        LOG.info('Reading cached OSM graph: %s', cache)
        graph = ox.load_graphml(cache)
    else:
        LOG.info('Downloading OSM road network for %s', args.place)
        graph = ox.graph_from_place(args.place, network_type=args.network_type, simplify=True,
                                    retain_all=False)
        ox.save_graphml(graph, cache)
    LOG.info('OSM graph: %s nodes, %s directed edges', graph.number_of_nodes(), graph.number_of_edges())
    return ox.project_graph(graph, to_crs='EPSG:31287')


def to_routing_graph(multidigraph):
    """Undirected simple graph: retain shortest parallel edge by projected length.

    Undirected connectivity is an explicit modeling assumption. This measures
    geometric network importance, not legally permitted one-way driving routes.
    """
    routing = nx.Graph()
    routing.add_nodes_from(multidigraph.nodes)
    for u, v, attrs in multidigraph.edges(data=True):
        if u == v:
            continue
        length = float(attrs.get('length', 0.0))
        if not np.isfinite(length) or length <= 0:
            continue
        if not routing.has_edge(u, v) or length < routing[u][v]['weight']:
            routing.add_edge(u, v, weight=length)
    largest = max(nx.connected_components(routing), key=len)
    return routing.subgraph(largest).copy()


def sample_centrality(graph, n_sources, n_targets, seed):
    """Sample OD pairs; count edges along shortest length-weighted paths.

    Scores are fractions of successfully sampled OD paths. Not the exact
    Brandes betweenness statistic and not a traffic assignment model.
    """
    rng = np.random.default_rng(seed)
    nodes = np.array(list(graph.nodes), dtype=object)
    sources = rng.choice(nodes, size=min(n_sources, len(nodes)), replace=False)
    counts = Counter()
    path_count = 0
    for i, source in enumerate(sources, 1):
        # One Dijkstra search per origin; target paths retrieved from its tree.
        paths = nx.single_source_dijkstra_path(graph, source, weight='weight')
        reachable = [n for n in paths if n != source]
        if not reachable:
            continue
        target_ids = rng.choice(len(reachable), size=min(n_targets, len(reachable)), replace=False)
        for idx in target_ids:
            path = paths[reachable[int(idx)]]
            for a, b in zip(path[:-1], path[1:]):
                counts[frozenset((a, b))] += 1
            path_count += 1
        if i % 25 == 0 or i == len(sources):
            LOG.info('Processed %s/%s origins; %s OD paths', i, len(sources), path_count)
    if path_count == 0:
        raise RuntimeError('No paths could be sampled.')
    return {key: count / path_count for key, count in counts.items()}, path_count


def segments(geometry):
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == 'LineString':
        return [np.asarray(geometry.coords)[:, :2]]
    if geometry.geom_type == 'MultiLineString':
        return [np.asarray(line.coords)[:, :2] for line in geometry.geoms]
    return []


def make_plot(edges, percentile, dpi, output, paths, n_sources, n_targets):
    scores = edges['centrality'].to_numpy(dtype=float)
    positive = scores[scores > 0]
    if not len(positive):
        raise RuntimeError('All road segments have zero estimated centrality.')
    cutoff = float(np.percentile(positive, percentile))
    selected = edges[edges['centrality'] >= cutoff].copy()
    LOG.info('Highlighting %s of %s OSM edge records (cutoff %.7f)', len(selected), len(edges), cutoff)

    cmap = LinearSegmentedColormap.from_list('backbone', ['#ffe7a0', '#ffc35a', '#fb833d', '#dc3a34', '#871b42'])
    vmin = cutoff
    vmax = float(np.percentile(selected['centrality'], 99.5))
    if vmax <= vmin:
        vmax = float(selected['centrality'].max())
    if vmax <= vmin:
        vmax = vmin + 1e-12
    norm = Normalize(vmin=vmin, vmax=vmax, clip=True)

    fig = plt.figure(figsize=(12, 12), facecolor='#fbfbfa')
    ax = fig.add_axes([0.035, 0.12, 0.93, 0.76])
    ax.set_facecolor('#fbfbfa')

    # All OSM segments in quiet gray.
    all_lines = []
    for geom in edges.geometry:
        all_lines.extend(segments(geom))
    ax.add_collection(LineCollection(all_lines, colors='#d7d9dc', linewidths=0.35, alpha=0.85, zorder=1))

    highlight_lines, colors, widths = [], [], []
    for row in selected.itertuples():
        strength = float(norm(row.centrality))
        for line in segments(row.geometry):
            highlight_lines.append(line)
            colors.append(cmap(strength))
            widths.append(0.65 + 1.9 * strength)
    ax.add_collection(LineCollection(highlight_lines, colors=colors, linewidths=widths,
                                     alpha=0.92, capstyle='round', zorder=3))

    bounds = edges.total_bounds
    xmin, ymin, xmax, ymax = bounds
    pad = max(xmax - xmin, ymax - ymin) * 0.035
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_aspect('equal')
    ax.axis('off')

    fig.text(0.055, 0.955, 'THE HIDDEN BACKBONE OF VIENNA', fontsize=24, weight='bold', color='#202126')
    fig.text(0.057, 0.924, 'Day 24  /  Network  /  #30DayMapChallenge', fontsize=11, color='#646970')
    fig.text(0.057, 0.092, 'LENGTH-WEIGHTED NETWORK CENTRALITY', fontsize=11, weight='bold', color='#30343b')
    fig.text(0.057, 0.070, 'Brighter streets appear on more sampled shortest paths.', fontsize=10, color='#666a70')
    fig.text(0.057, 0.049, f'OpenStreetMap road network  |  {paths:,} sampled OD paths  |  Undirected routing assumption',
             fontsize=9, color='#74777c')
    fig.text(0.057, 0.031, 'Estimated structural importance, not traffic volume or travel demand.', fontsize=9, color='#74777c')
    cax = fig.add_axes([0.64, 0.075, 0.29, 0.015])
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation='horizontal')
    cb.set_ticks([vmin, vmax])
    cb.set_ticklabels(['Lower', 'Higher'])
    cb.ax.tick_params(labelsize=8, length=0)
    cb.outline.set_visible(False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    return cutoff


def main():
    args = arguments()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    if args.sources < 1 or args.targets < 1:
        raise ValueError('--sources and --targets must be positive.')
    if not 0 <= args.min_percentile <= 100:
        raise ValueError('--min-percentile must be in [0, 100].')
    graph = fetch_graph(args)
    routing = to_routing_graph(graph)
    LOG.info('Routing graph: %s nodes, %s undirected edges', routing.number_of_nodes(), routing.number_of_edges())
    centrality, paths = sample_centrality(routing, args.sources, args.targets, args.seed)
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True).reset_index()
    # Parallel OSM edge records share a graph-level centrality score.
    edges['centrality'] = [centrality.get(frozenset((u, v)), 0.0) for u, v in zip(edges['u'], edges['v'])]
    output = Path(args.out)
    cutoff = make_plot(edges, args.min_percentile, args.dpi, output, paths, args.sources, args.targets)
    gpkg = output.with_suffix('.gpkg')
    # OSM metadata may contain lists; export only stable fields.
    export = edges[['u', 'v', 'key', 'centrality', 'geometry']].copy()
    export.to_file(gpkg, layer='road_centrality', driver='GPKG')
    summary = dict(place=args.place, network_type=args.network_type, crs=str(edges.crs),
                   nodes=routing.number_of_nodes(), edges=routing.number_of_edges(),
                   sampled_sources=min(args.sources, routing.number_of_nodes()),
                   targets_per_source=args.targets, od_paths=paths, seed=args.seed,
                   highlight_percentile=args.min_percentile, cutoff=cutoff,
                   interpretation='Fraction of sampled origin-destination shortest paths using an edge; undirected length-weighted network')
    summary_path = output.with_suffix('.json')
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    LOG.info('Saved %s, %s, %s', output, gpkg, summary_path)


if __name__ == '__main__':
    main()
