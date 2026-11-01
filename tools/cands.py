"""Historique mensuel de quelques actions candidates -> data/analyse/cands.json (outil ponctuel)."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo
out = {}
for t in sys.argv[1].split(','):
    m = yahoo.chart(t, 'depuis2006', '1mo')
    if not m or not m.get('timestamp'):
        print(t, 'rien'); continue
    mm = {}
    for ts, c in zip(m['timestamp'], m['indicators']['quote'][0]['close']):
        if c is None: continue
        d = dt.datetime.utcfromtimestamp(ts + 43200)
        if d.year >= 2006: mm[f'{d.year}-{d.month}'] = round(c, 4)
    out[t] = mm
os.makedirs('data/analyse', exist_ok=True)
json.dump(out, open('data/analyse/cands.json', 'w'), separators=(',', ':'))
print(len(out))
