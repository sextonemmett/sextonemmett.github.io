"""Render monthly ACLED events using the research project's existing local subset.

Usage: python3 scripts/build_south_sudan_animation.py /path/to/south_sudan_pockets_of_peace
Requires Pillow. Source event records remain outside the public website repository.
"""
import calendar
import csv
import json
import math
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[1] / 'assets/work'
W, H, SCALE = 900, 760, 2
BG, INK, MUTED = '#f8f7f3', '#292d29', '#62685f'
COLORS = {'National': '#bd493c', 'Local': '#237f87'}
VIOLENT = {'Battles', 'Explosions/Remote violence', 'Violence against civilians'}

def read_csv(name):
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

local_ids = {r['event_id_cnty'] for r in read_csv('data/acled_local/acled_local_interactions_subset.csv')}
events = []
for r in read_csv('data/acled/acled_South_Sudan.csv'):
    if '2021-01-01' <= r['event_date'] <= '2025-12-31' and r['event_type'] in VIOLENT:
        events.append(dict(month=r['event_date'][:7], x=float(r['longitude']), y=float(r['latitude']),
                           deaths=float(r['fatalities']), group='Local' if r['event_id_cnty'] in local_ids else 'National'))
assert events
boundaries = json.loads((SOURCE / 'data/boundaries/boundaries_1.geojson').read_text())
rings = []
for feature in boundaries['features']:
    g = feature['geometry']
    polygons = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    rings.extend(polygon[0] for polygon in polygons)
xs = [p[0] for ring in rings for p in ring]
ys = [p[1] for ring in rings for p in ring]
# Equirectangular view corrected for longitude distance at South Sudan's mid-latitude.
coslat = math.cos(math.radians((min(ys)+max(ys))/2))
scale = min(800/((max(xs)-min(xs))*coslat), 465/(max(ys)-min(ys)))
center_x, center_y = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2

def point(x,y):
    return ((450+(x-center_x)*coslat*scale)*SCALE, (365-(y-center_y)*scale)*SCALE)

def font(size, bold=False):
    path = Path('/System/Library/Fonts/Supplemental') / ('Arial Bold.ttf' if bold else 'Arial.ttf')
    return ImageFont.truetype(str(path) if path.exists() else 'DejaVuSans.ttf', size*SCALE)

def text(draw, xy, value, size=20, fill=INK, bold=False):
    draw.text((xy[0]*SCALE,xy[1]*SCALE),value,font=font(size,bold),fill=fill)

def radius(deaths):
    # Circle area is proportional to fatalities, with a minimum for 0–1 deaths.
    return 3.2*math.sqrt(max(deaths,1))

frames=[]
for year in range(2021,2026):
    for month in range(1,13):
        key=f'{year}-{month:02d}'
        subset=[e for e in events if e['month']==key]
        im=Image.new('RGB',(W*SCALE,H*SCALE),BG)
        d=ImageDraw.Draw(im)
        text(d,(30,22),'SOUTH SUDAN',24,bold=True)
        text(d,(30,58),'Conflict events · monthly',20,fill=MUTED)
        text(d,(690,25),f'{calendar.month_abbr[month]} {year}',28,bold=True)
        for ring in rings:
            d.polygon([point(*p[:2]) for p in ring],fill='#e6e9df',outline='#a5ad9c',width=2)
        overlay=Image.new('RGBA',im.size)
        od=ImageDraw.Draw(overlay)
        for e in sorted(subset,key=lambda e:e['deaths'],reverse=True):
            x,y=point(e['x'],e['y']); r=radius(e['deaths'])*SCALE
            color=COLORS[e['group']]
            rgb=tuple(bytes.fromhex(color[1:]))
            od.ellipse((x-r,y-r,x+r,y+r),fill=(*rgb,175),outline=(*rgb,255),width=2)
        im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB'); d=ImageDraw.Draw(im)
        for label,x in [('National',36),('Local',190)]:
            d.ellipse(((x)*SCALE,624*SCALE,(x+14)*SCALE,638*SCALE),fill=COLORS[label])
            text(d,(x+23,619),label,20)
        text(d,(350,619),'Fatalities',18,fill=MUTED)
        for val,x in [(1,465),(10,560),(100,685)]:
            r=radius(val); cy=632
            d.ellipse(((x-r)*SCALE,(cy-r)*SCALE,(x+r)*SCALE,(cy+r)*SCALE),outline=MUTED,width=2)
            text(d,(x+r+9,621),str(val),18,fill=MUTED)
        text(d,(30,677),'Source: ACLED · National/local classification from project analysis',17,fill=MUTED)
        text(d,(30,704),'Dot area scales with reported fatalities; 0–1 use a minimum visible size.',17,fill=MUTED)
        d.rectangle((30*SCALE,744*SCALE,870*SCALE,748*SCALE),fill='#dcded5')
        i=len(frames)
        d.rectangle((30*SCALE,744*SCALE,(30+840*(i+1)/60)*SCALE,748*SCALE),fill='#416347')
        frames.append(im.resize((W,H),Image.Resampling.LANCZOS))
frames[0].save(OUT/'south-sudan-conflict-events-poster.png')
# Shared palette prevents flickering across frames.
palette=frames[0].quantize(colors=128)
indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
indexed[0].save(OUT/'south-sudan-conflict-events.gif',save_all=True,append_images=indexed[1:],
                duration=[650]*59+[1600],loop=0,optimize=True,disposal=2)
print(f'Rendered 60 monthly frames from {len(events)} events; {sum(e["group"]=="Local" for e in events)} local.')
print(f'GIF size: {(OUT/"south-sudan-conflict-events.gif").stat().st_size/1024/1024:.2f} MB')
