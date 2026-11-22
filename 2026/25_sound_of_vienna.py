#!/usr/bin/env python3
"""Day 25 – The Sound of Vienna: OSM streets transformed into a graphic score.

Outputs a graphic score PNG, MIDI and CSV. Requires an internet connection on first
OSMnx download; subsequent runs use a GraphML cache.
"""
import argparse
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Ellipse
import numpy as np
import osmnx as ox
import pretty_midi

PITCHES = np.array([48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84], dtype=int)
COLORS = {'motorway':'#aa4b3d', 'trunk':'#aa4b3d', 'primary':'#b87643',
          'secondary':'#bd945a', 'tertiary':'#7a6d85', 'residential':'#303c4e',
          'living_street':'#303c4e', 'service':'#66717d', 'other':'#66717d'}

def road_type(value):
    if isinstance(value, list):
        value = value[0] if value else 'other'
    value = str(value)
    return value if value in COLORS else 'other'

def get_graph(place, cache, network_type):
    if cache.exists():
        print(f'Loading cached OSM network: {cache}')
        return ox.load_graphml(cache)
    print(f'Downloading OSM road network for {place}...')
    graph = ox.graph_from_place(place, network_type=network_type, simplify=True)
    ox.save_graphml(graph, cache)
    return graph

def extract_notes(graph, max_notes, duration_seconds, seed):
    graph = ox.project_graph(graph, to_crs='EPSG:31287')
    _, edges = ox.graph_to_gdfs(graph)
    edges = edges[edges.geometry.notna()].copy()
    edges['road_type'] = edges['highway'].map(road_type)
    edges['meters'] = edges.geometry.length
    edges = edges[edges.meters >= 15].copy()
    if edges.empty:
        raise RuntimeError('No usable road segments found.')
    # Keep a deterministic representative subset for a readable score.
    if len(edges) > max_notes:
        edges = edges.sample(n=max_notes, random_state=seed)
    midpoints = edges.geometry.interpolate(0.5, normalized=True)
    x = midpoints.x.to_numpy(dtype=float)
    y = midpoints.y.to_numpy(dtype=float)
    lengths = edges.meters.to_numpy(dtype=float)
    bounds = np.asarray(ox.graph_to_gdfs(graph, nodes=True, edges=False).total_bounds, dtype=float)
    minx, miny, maxx, maxy = bounds
    xrel = np.clip((x-minx)/max(maxx-minx, 1), 0, 1)
    yrel = np.clip((y-miny)/max(maxy-miny, 1), 0, 1)
    # Ascending north -> higher pitch; west -> earlier in time.
    pitch_idx = np.clip(np.rint(yrel*(len(PITCHES)-1)).astype(int), 0, len(PITCHES)-1)
    pitch = PITCHES[pitch_idx]
    # Quantize to a modest rhythmic vocabulary, avoiding implausibly long notes.
    length_scaled = np.clip(lengths, 20, 1000)
    durations = np.select([length_scaled < 60, length_scaled < 140,
                           length_scaled < 320, length_scaled < 600],
                          [0.20, 0.40, 0.80, 1.20], default=1.60)
    starts = xrel * (duration_seconds-2)
    rows = []
    for i, (idx, edge) in enumerate(edges.iterrows()):
        rows.append({'edge_id': str(idx), 'road_type': edge['road_type'],
                     'length_m': round(float(lengths[i]), 1),
                     'x_m': round(float(x[i]), 1), 'y_m': round(float(y[i]), 1),
                     'start_s': round(float(starts[i]), 3),
                     'duration_s': round(float(durations[i]), 3),
                     'midi_pitch': int(pitch[i]), 'pitch_idx': int(pitch_idx[i])})
    return rows

def render_score(rows, out, dpi, duration_seconds):
    fig = plt.figure(figsize=(16, 11), facecolor='#fffefa')
    ax = fig.add_axes([0.07, 0.17, 0.86, 0.65])
    ax.set_facecolor('#fffefa')
    # Five systems of five staff lines. The mapped pitches are laid across
    # the systems by north-south geography, not conventional clef notation.
    system_centers = [16, 12, 8, 4, 0]
    staff_segments = []
    for center in system_centers:
        for offset in [-0.36, -0.18, 0, 0.18, 0.36]:
            staff_segments.append([(0, center+offset), (duration_seconds, center+offset)])
    ax.add_collection(LineCollection(staff_segments, colors='#a9a7a2', linewidths=0.6, alpha=0.75, zorder=1))
    for i, center in enumerate(system_centers):
        ax.text(-1.2, center, f'{i+1:02}', ha='right', va='center', fontsize=10,
                color='#99958f', family='DejaVu Sans Mono')
    # Map pitch indices to staff systems, preserving the north-south ordering.
    n = len(PITCHES)
    for row in rows:
        rank = row['pitch_idx']/(n-1)
        system_idx = min(int((1-rank)*5), 4)
        local = (1-rank)*5-system_idx
        center = system_centers[system_idx]
        yy = center + 0.47 - np.clip(local, 0, 1)*0.94
        xx = row['start_s']
        dur = row['duration_s']
        color = COLORS[row['road_type']]
        # A short tail communicates duration; noteheads are graphic, not
        # conventional standard notation (the score is intentionally experimental).
        ax.plot([xx, min(xx+dur*1.9, duration_seconds)], [yy, yy],
                color=color, lw=1.2, alpha=0.65, zorder=2, solid_capstyle='round')
        ax.add_patch(Ellipse((xx, yy), width=0.32, height=0.14,
                             angle=-18, facecolor=color, edgecolor='none',
                             alpha=0.86, zorder=3))
    ax.set_xlim(-1.7, duration_seconds+0.4)
    ax.set_ylim(-1.1, 17.0)
    ax.axis('off')
    fig.text(0.07, 0.92, 'THE SOUND OF VIENNA', fontsize=31, weight='bold', color='#25282c')
    fig.text(0.07, 0.875, 'DAY 25  /  IS THIS A MAP?  /  #30DayMapChallenge',
             fontsize=12, color='#70757b')
    fig.text(0.07, 0.113,
             'Each note is an OpenStreetMap street segment. West → east = time; south → north = pitch; street length = duration.',
             fontsize=10.5, color='#54585d')
    fig.text(0.07, 0.087,
             'Graphic score / geographic sonification · Relative positions transformed into musical parameters · Not conventional staff notation',
             fontsize=9.2, color='#85898c')
    fig.savefig(out, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches='tight', pad_inches=0.28)
    plt.close(fig)

def render_midi(rows, out):
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    groups = [('motorway', 0), ('primary', 24), ('secondary', 40),
              ('tertiary', 48), ('residential', 11), ('other', 10)]
    instruments = {}
    for name, program in groups:
        instruments[name] = pretty_midi.Instrument(program=program, name=name)
    for row in rows:
        kind = row['road_type']
        if kind in ('motorway', 'trunk'): group='motorway'
        elif kind in ('primary',): group='primary'
        elif kind in ('secondary',): group='secondary'
        elif kind in ('tertiary',): group='tertiary'
        elif kind in ('residential', 'living_street'): group='residential'
        else: group='other'
        start = row['start_s']
        end = start + row['duration_s']
        instruments[group].notes.append(pretty_midi.Note(
            velocity=65, pitch=row['midi_pitch'], start=start, end=end))
    for inst in instruments.values():
        if inst.notes:
            midi.instruments.append(inst)
    midi.write(str(out))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--place', default='Wien, Österreich')
    parser.add_argument('--network-type', default='drive', choices=['drive', 'walk', 'bike', 'all'])
    parser.add_argument('--max-notes', type=int, default=1800)
    parser.add_argument('--duration', type=float, default=60)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dpi', type=int, default=300)
    parser.add_argument('--out', type=Path, default=Path('day25_sound_of_vienna.png'))
    parser.add_argument('--cache', type=Path, default=Path('day25_vienna_osm.graphml'))
    args = parser.parse_args()
    if args.duration <= 2 or args.max_notes < 1:
        parser.error('--duration must be > 2 and --max-notes >= 1')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    graph = get_graph(args.place, args.cache, args.network_type)
    rows = extract_notes(graph, args.max_notes, args.duration, args.seed)
    render_score(rows, args.out, args.dpi, args.duration)
    csv_path = args.out.with_suffix('.csv')
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    midi_path = args.out.with_suffix('.mid')
    render_midi(rows, midi_path)
    print(f'Created {args.out}, {csv_path}, {midi_path} ({len(rows)} notes)')

if __name__ == '__main__':
    main()
