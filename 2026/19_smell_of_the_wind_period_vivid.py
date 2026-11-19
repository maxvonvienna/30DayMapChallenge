#!/usr/bin/env python3
"""Day 19: multi-hour illustrative wind-plume frequency map (NOT measured odor)."""
import argparse
import json
import math
from pathlib import Path
import geopandas as gpd
import numpy as np
import requests
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lon',type=float,required=True)
    p.add_argument('--lat',type=float,required=True)
    p.add_argument('--start-date',required=True)
    p.add_argument('--end-date',required=True)
    p.add_argument('--extent-km',type=float,default=7.5)
    p.add_argument('--resolution-m',type=float,default=50)
    p.add_argument('--threshold',type=float,default=.10,help='Threshold of each hourly plume index (0..1)')
    p.add_argument('--out',default='2026/maps/day19_smell_frequency.png')
    p.add_argument('--gamma',type=float,default=0.4,help='PowerNorm gamma (<1 emphasizes low positive frequencies)')
    p.add_argument('--cache-dir',default='2026/data/day19_cache')
    a=p.parse_args()
    if not (0<a.threshold<1): p.error('--threshold must be between 0 and 1')
    if a.gamma <= 0: p.error('--gamma must be positive')
    cache=Path(a.cache_dir);cache.mkdir(exist_ok=True,parents=True)
    path=cache/f'wind_period_{a.start_date}_{a.end_date}_{a.lat:.4f}_{a.lon:.4f}.json'
    if path.exists(): data=json.loads(path.read_text(encoding='utf-8'))
    else:
        response=requests.get(ARCHIVE,params=dict(latitude=a.lat,longitude=a.lon,start_date=a.start_date,end_date=a.end_date,hourly='wind_speed_10m,wind_direction_10m',timezone='Europe/Vienna'),timeout=120)
        response.raise_for_status();data=response.json();path.write_text(json.dumps(data),encoding='utf-8')
    hourly=data['hourly']
    transformer=Transformer.from_crs('EPSG:4326','EPSG:31287',always_xy=True)
    x0,y0=transformer.transform(a.lon,a.lat)
    radius=a.extent_km*1000
    xs=np.arange(x0-radius,x0+radius+a.resolution_m,a.resolution_m)
    ys=np.arange(y0-radius,y0+radius+a.resolution_m,a.resolution_m)
    X,Y=np.meshgrid(xs,ys);rx=X-x0;ry=Y-y0
    exceed=np.zeros(X.shape,dtype=np.uint32)
    sum_index=np.zeros(X.shape,dtype=np.float64)
    n=0;calm=0;missing=0
    for speed,from_dir in zip(hourly['wind_speed_10m'],hourly['wind_direction_10m']):
        if speed is None or from_dir is None: missing+=1;continue
        if speed<0.5: calm+=1;continue
        angle=math.radians((float(from_dir)+180)%360)
        dx,dy=math.sin(angle),math.cos(angle)
        along=rx*dx+ry*dy
        cross=rx*dy-ry*dx
        down=np.maximum(along,0)
        sigma=np.maximum(40.0,0.12*down**.9)
        # Relative plume shape, normalized independently for each hour.
        plume=np.exp(-.5*(cross/sigma)**2)/(sigma+25)*np.exp(-down/5500)
        plume[along<=0]=0
        maximum=plume.max()
        if maximum>0: plume/=maximum
        exceed+=(plume>=a.threshold)
        sum_index+=plume
        n+=1
    if n==0: raise RuntimeError('No usable wind hours found')
    frequency=100*exceed/n
    average=sum_index/n
    cmap=LinearSegmentedColormap.from_list('smell',[
        '#fff3b0', '#ffca3a', '#ff924c', '#f94144',
        '#bc2a6a', '#702c91', '#30123b'
    ])
    cmap.set_bad('#ffffff')
    frequency_plot=np.ma.masked_less_equal(frequency, 0)
    fig=plt.figure(figsize=(11,11),facecolor='#ffffff')
    ax=fig.add_axes([.08,.16,.84,.69],facecolor='#ffffff')

    gdf = gpd.read_file('2026/data/vienna_districts_lines.geojson')
    gdf = gdf.to_crs('EPSG:31287')
    gdf.plot(ax=ax, linewidth=0.7, color='black')

    im=ax.imshow(frequency_plot,origin='lower',extent=(xs[0],xs[-1],ys[0],ys[-1]),
                 cmap=cmap,norm=PowerNorm(gamma=a.gamma,vmin=0,vmax=100),
                 interpolation='nearest', alpha=0.8)
    ax.scatter([x0],[y0],s=85,c='black',edgecolors='white',linewidths=1.5,zorder=5)
    ax.annotate('SOURCE',(x0,y0),xytext=(8,8),textcoords='offset points',fontsize=9,weight='bold')
    ax.set_aspect('equal');ax.axis('off')

    fig.text(.08,.955,'THE SMELL OF THE WIND',fontsize=26,fontweight='bold',color='#222')
    #fig.text(.08,.915,f'Day 19 / Senses: Smell  ·  {a.start_date} to {a.end_date}',fontsize=12,color='#666')
    fig.text(.08,.915,f'Hourly hypothetical plume frequency  ·  {n:,} valid wind hours',fontsize=11,color='#666')
    cax=fig.add_axes([.26,.11,.50,.018]);cb=fig.colorbar(im,cax=cax,orientation='horizontal')
    cb.set_label(f'Hours exceeding relative plume index {a.threshold:.2f} (%)',fontsize=10)
    cb.set_ticks([0, 1, 2, 5, 10, 20, 40, 60, 80, 100])
    cb.ax.tick_params(labelsize=8)
    fig.text(.08,.052,f'Wind: Open-Meteo historical modeled 10 m wind  |  {calm} calm hours excluded  |  {missing} missing hours',fontsize=8,color='#777')
    fig.text(.08,.032,'Illustrative frequency, NOT measured odor, odor hours, or exposure. Assumes constant emissions and flat terrain.',fontsize=8,color='#777')
    fig.savefig(a.out,dpi=300,facecolor=fig.get_facecolor());plt.close(fig)
    np.savez_compressed(Path(a.out).with_suffix('.npz'),frequency_pct=frequency,mean_relative_index=average,x=xs,y=ys)
    Path(a.out).with_suffix('.json').write_text(json.dumps(dict(start_date=a.start_date,end_date=a.end_date,valid_hours=n,calm_excluded=calm,missing_hours=missing,threshold=a.threshold,gamma=a.gamma,source_lon=a.lon,source_lat=a.lat),indent=2),encoding='utf-8')
    print(f'Wrote {a.out}; {n} valid hours; {calm} calm hours excluded')
if __name__=='__main__':main()
