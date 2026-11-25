"""Convert the raw Forbes 2026 snapshot (source/forbes2026.json) into ../data.json.

Fields used: personName, finalWorthBillions, industries[0], source, country.
The shipped data.json is the cleaned output of this script: a few long company
labels were shortened by hand so they fit the lower-third card.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(HERE, 'forbes2026.json')))['personList']['personsLists']
top = [p for p in raw if p.get('rank', 999) <= 100]
rows = sorted(top, key=lambda p: p['finalWorthBillions'])

items = []
for p in rows:
    meta = " · ".join(x.upper() for x in [p.get('source', ''), p.get('country', '')] if x)
    items.append({
        "name": p['personName'],
        "value": round(float(p['finalWorthBillions']), 1),
        "category": (p.get('industries') or [''])[0].upper(),
        "meta": meta,
    })

out = {"items": items, "total": round(sum(i['value'] for i in items), 1)}
dst = os.path.join(HERE, '..', 'data.json')
json.dump(out, open(dst, 'w'), indent=1, ensure_ascii=False)
print('wrote', dst, len(items), 'items, total', out['total'])
