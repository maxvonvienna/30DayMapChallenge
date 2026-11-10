"""Reproducible synthetic urban-growth simulation and cartographic export.

"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch, Rectangle
from scipy.ndimage import gaussian_filter, distance_transform_edt, binary_dilation

SEED = 100
rng = np.random.default_rng(SEED)
n = 320
y, x = np.mgrid[0:n, 0:n]
river_x = 153 + 27 * np.sin(y / 39) + 8 * np.sin(y / 15)
river = np.abs(x - river_x) < (3.2 + 1.2 * np.sin(y / 26) ** 2)
river_buffer = np.abs(x - river_x) < 10
hills = gaussian_filter(rng.normal(size=(n, n)), 28)
hills = (hills - hills.min()) / (hills.max() - hills.min())
protected = ((x - 55) ** 2 / 45 ** 2 + (y - 254) ** 2 / 49 ** 2 < 1) | (
            (x - 266) ** 2 / 38 ** 2 + (y - 66) ** 2 / 49 ** 2 < 1)
blocked = river_buffer | protected | (hills > 0.87)
cx, cy = 112, 157
angles = np.deg2rad([0, 31, 68, 112, 154, 205, 244, 285, 326])
roads = np.zeros((n, n), bool)
for a in angles:
    t = np.linspace(0, 310, 1300)
    xx = cx + t * np.cos(a) + 4 * np.sin(t / 28 + a * 3)
    yy = cy + t * np.sin(a) + 3 * np.sin(t / 35 + a)
    ix = np.rint(xx).astype(int);
    iy = np.rint(yy).astype(int)
    ok = (ix >= 0) & (ix < n) & (iy >= 0) & (iy < n)
    roads[iy[ok], ix[ok]] = True
roads = binary_dilation(roads, iterations=2)
roads[river_buffer] = False
road_distance = distance_transform_edt(~roads)
urban = np.zeros((n, n), bool)
for px, py, r in [(112, 157, 13), (69, 105, 4), (221, 210, 4), (230, 105, 3)]:
    urban |= ((x - px) ** 2 + (y - py) ** 2 < r * r)
urban &= ~blocked
snapshots = [urban.copy()]
for decade in range(1, 11):
    proximity = gaussian_filter(urban.astype(float), sigma=7)
    proximity /= max(proximity.max(), 1e-9)
    adjacency = binary_dilation(urban, iterations=4) & ~urban
    satellite = np.exp(-((x - 221) ** 2 + (y - 210) ** 2) / (2 * 38 ** 2)) + np.exp(
        -((x - 230) ** 2 + (y - 105) ** 2) / (2 * 35 ** 2))
    road_bonus = np.exp(-road_distance / 12)
    noise = gaussian_filter(rng.random((n, n)), 1.8)
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    suitability = (0.43 * proximity + 0.22 * road_bonus + 0.16 * (1 - hills) + 0.10 * noise + 0.09 * satellite)
    suitability -= 0.12 * np.maximum(0, decade - 5) / 5 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * 25 ** 2))
    eligible = adjacency & ~blocked
    count = min(int(urban.sum() * (0.13 + 0.012 * decade)), int(eligible.sum()))
    vals = np.where(eligible, suitability, -np.inf).ravel()
    if count:
        selected = np.argpartition(vals, -count)[-count:]
        urban.ravel()[selected] = True
    snapshots.append(urban.copy())
arrival = np.full((n, n), np.nan)
arrival[snapshots[0]] = 0
for decade in range(1, 11):
    arrival[snapshots[decade] & ~snapshots[decade - 1]] = decade

BG = '#f7f3e8';
INK = '#153b3d';
MUTED = '#607573';
WATER = '#83b9c2';
GREEN = '#9ab89a'
COLORS = ['#592b4d', '#b74751', '#d85b50', '#e97750', '#ef9556', '#f2af5c', '#f6c66f', '#f8d891', '#f9e4b2', '#f9edcf',
          '#fff5df']
CMAP = ListedColormap(COLORS)
NORM = BoundaryNorm(np.arange(-.5, 11.5), len(COLORS))
plt.rcParams.update({'font.family': 'DejaVu Serif', 'savefig.facecolor': BG})
fig = plt.figure(figsize=(16, 10), facecolor=BG)
# Left editorial panel and one large main map
fig.text(.045, .925, '100 YEARS OF', fontsize=18, color=INK, weight='bold')
fig.text(.045, .862, 'URBAN GROWTH', fontsize=29, color=INK, weight='bold')
fig.text(.046, .815, '1925 — 2025', fontsize=19, color=INK, style='italic')
fig.text(.046, .750,
         'A synthetic city expands from a compact\nriver settlement into a polycentric\nurban region over ten decades.',
         fontsize=10, color=INK, linespacing=1.6)
fig.add_artist(plt.Line2D([.046, .286], [.715, .715], transform=fig.transFigure, color=INK, lw=.8))
fig.text(.046, .679, 'FIRST DEVELOPED', fontsize=11, color=INK, weight='bold')
for j, col in enumerate(COLORS):
    ypos = .647 - j * .027
    fig.patches.append(
        Rectangle((.047, ypos - .005), .021, .018, transform=fig.transFigure, facecolor=col, edgecolor=INK, lw=.3))
    label = '≤ 1925' if j == 0 else f'{1916 + j * 10}–{1925 + j * 10}'
    fig.text(.078, ypos, label, fontsize=8.4, color=INK)

fig.text(.046, .302, 'LANDSCAPE', fontsize=11, color=INK, weight='bold')
for i, (col, lab) in enumerate([(WATER, 'River'), (GREEN, 'Protected landscape'), ('#d0c7ae', 'Terrain contours')]):
    yy = .277 - i * .026
    fig.patches.append(
        Rectangle((.047, yy - .004), .021, .015, transform=fig.transFigure, facecolor=col, edgecolor=INK, lw=.3))
    fig.text(.078, yy, lab, fontsize=8.5, color=INK)
fig.add_artist(plt.Line2D([.046, .286], [.184, .184], transform=fig.transFigure, color=INK, lw=.8))
counts = [int(s.sum()) for s in snapshots]
fig.text(.046, .153, 'URBAN FOOTPRINT', fontsize=10, color=INK, weight='bold')
fig.text(.046, .122, f'1925  {counts[0]:,} cells', fontsize=9, color=INK)
fig.text(.046, .100, f'1975  {counts[5]:,} cells', fontsize=9, color=INK)
fig.text(.046, .078, f'2025  {counts[10]:,} cells', fontsize=9, color=INK)
fig.text(.046, .044, f'{counts[10] / counts[0]:.1f}× growth  ·  illustrative simulation', fontsize=8, color=MUTED)

ax = fig.add_axes([.315, .085, .647, .825]);
ax.set_facecolor(BG)
ax.contour(hills, levels=np.linspace(.12, .88, 23), colors='#c9c1ac', linewidths=.42, alpha=.8, origin='lower',
           zorder=1)
ax.imshow(np.ma.masked_where(~protected, protected), origin='lower', cmap=ListedColormap([GREEN]), alpha=.65,
          interpolation='nearest', zorder=2)
ax.imshow(np.ma.masked_where(~roads, roads), origin='lower', cmap=ListedColormap(['#a2a69a']), alpha=.48,
          interpolation='nearest', zorder=3)
ax.imshow(np.ma.masked_where(~river, river), origin='lower', cmap=ListedColormap([WATER]), interpolation='nearest',
          zorder=4)
ax.imshow(np.ma.masked_invalid(arrival), origin='lower', cmap=CMAP, norm=NORM, interpolation='nearest', zorder=5)
ax.set_xlim(0, n);
ax.set_ylim(0, n);
ax.set_xticks([]);
ax.set_yticks([])
for spine in ax.spines.values(): spine.set_color(INK);spine.set_linewidth(.85)
ax.text(112, 141, 'HISTORIC CORE', ha='center', fontsize=8, color=INK, weight='bold',
        bbox=dict(facecolor=BG, edgecolor='none', alpha=.91, pad=3), zorder=8)
ax.annotate('SATELLITE CENTRE', xy=(221, 210), xytext=(205, 244), fontsize=7.8, color=INK,
            arrowprops=dict(arrowstyle='-', lw=.7, color=INK), zorder=8)
ax.annotate('SATELLITE CENTRE', xy=(230, 105), xytext=(233, 77), fontsize=7.8, color=INK,
            arrowprops=dict(arrowstyle='-', lw=.7, color=INK), zorder=8)
ax.text(303, 303, 'N ↑', ha='right', va='top', color=INK, fontsize=12, weight='bold', zorder=8)
# Three small panels show cumulative growth, using the same simulation and color scale.
for i, idx in enumerate([0, 5, 10]):
    bx = fig.add_axes([.348 + i * .145, .108, .129, .143], facecolor=BG)
    bx.contour(hills, levels=np.linspace(.2, .8, 9), colors='#d2cbb9', linewidths=.22, origin='lower')
    bx.imshow(np.ma.masked_where(~river, river), origin='lower', cmap=ListedColormap([WATER]), interpolation='nearest')
    bx.imshow(np.ma.masked_invalid(np.where(snapshots[idx], arrival, np.nan)), origin='lower', cmap=CMAP, norm=NORM,
              interpolation='nearest')
    bx.set_xlim(0, n);
    bx.set_ylim(0, n);
    bx.set_xticks([]);
    bx.set_yticks([])
    for spine in bx.spines.values(): spine.set_color(INK);spine.set_linewidth(.65)
    bx.text(.05, .93, str(1925 + 10 * idx), transform=bx.transAxes, va='top', fontsize=9, weight='bold', color=INK,
            bbox=dict(facecolor=BG, alpha=.9, edgecolor='none', pad=2))
fig.text(.965, .043, '30DAYMAPCHALLENGE  /  DAY 10  /  PROMPTING ONLY', ha='right', fontsize=8, color=MUTED)
fig.text(.315, .044, 'SYNTHETIC GEOGRAPHY  ·  FIXED RANDOM SEED 100  ·  NOT TO SCALE', fontsize=7.5, color=MUTED)
output = Path(__file__).parent / "maps" / "map10.png"
fig.savefig(output, dpi=300, facecolor=BG, bbox_inches='tight', pad_inches=.13)
plt.close(fig)
print(f'Exported: {output} ({output.stat().st_size:,} bytes)')
print('Urban cells:', {1925: counts[0], 1975: counts[5], 2025: counts[10]})
