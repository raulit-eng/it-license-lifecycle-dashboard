"""Evolve the IT asset & license sample data by one day.

Usage: python3 evolve.py ASSETS.csv LICENSES.csv OUT_DIR YYYY-MM-DD [ACTIVITY.json]
Writes OUT_DIR/assets-<date>.csv and OUT_DIR/licenses-<date>.csv, and, when
ACTIVITY.json is given, adds the day's events to that log.
Seeded by the date, so re-running the same day gives the same result.
"""
import csv, os, random, sys, datetime as dt

assets_in, licenses_in, out_dir, today_s = sys.argv[1:5]
T = dt.date.fromisoformat(today_s)
rnd = random.Random(today_s)

MODELS = {
    'Laptop': [('Dell Latitude 5440', 1349), ('Lenovo ThinkPad T14 Gen 5', 1449), ('MacBook Pro 14"', 1999), ('HP EliteBook 840 G11', 1399)],
    'Desktop': [('Dell OptiPlex 7020', 999), ('HP EliteDesk 800 G9', 1049)],
    'Server': [('Dell PowerEdge R760', 12400), ('HPE ProLiant DL380 Gen11', 10900)],
    'Network': [('Cisco Meraki MS250-48 switch', 4600), ('FortiGate 120G firewall', 4300), ('Ubiquiti U7 Pro access point', 189)],
    'Monitor': [('Dell P2725H 27"', 299), ('LG 34" UltraWide', 549)],
    'Printer': [('HP LaserJet Pro 4001dn', 349), ('Brother MFC-L8905CDW', 649)],
    'Phone': [('iPhone 16', 799), ('Samsung Galaxy S25', 799)],
}
LIFE = {'Laptop': 4, 'Desktop': 5, 'Server': 5, 'Network': 6, 'Monitor': 6, 'Printer': 5, 'Phone': 3}
WARR = {'Laptop': 3, 'Desktop': 3, 'Server': 5, 'Network': 5, 'Monitor': 3, 'Printer': 1, 'Phone': 1}
DEPTS = ['Finance', 'HR', 'Operations', 'Sales', 'IT', 'Engineering']
LOCS = ['HQ - Palmdale', 'Branch - Lancaster']


def add_years(d, y):
    try:
        return d.replace(year=d.year + y)
    except ValueError:
        return d.replace(year=d.year + y, day=28)


def read(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


assets, licenses = read(assets_in), read(licenses_in)
a_fields, l_fields = list(assets[0].keys()), list(licenses[0].keys())
next_tag = max(int(a['asset_tag'].split('-')[1]) for a in assets) + 1
log = []


def new_device(cat, dept=None):
    global next_tag
    name, cost = rnd.choice(MODELS[cat])
    row = dict(asset_tag=f'AST-{next_tag}', name=name, category=cat,
               department=dept or ('IT' if cat in ('Server', 'Network') else rnd.choice(DEPTS)),
               location=rnd.choice(LOCS), purchase_date=T.isoformat(),
               warranty_end=add_years(T, WARR[cat]).isoformat(),
               lifecycle_end=add_years(T, LIFE[cat]).isoformat(), cost=cost, status='In use')
    next_tag += 1
    return row


# --- Assets ---
kept = []
for a in assets:
    overdue = (T - dt.date.fromisoformat(a['lifecycle_end'])).days
    if overdue > 0 and rnd.random() < 0.12:  # replace devices past refresh, a few at a time
        repl = new_device(a['category'], a['department'])
        log.append(f"Replaced {a['asset_tag']} ({a['name']}) with {repl['asset_tag']}")
        kept.append(repl)
        continue
    if a['status'] == 'In repair' and rnd.random() < 0.3:
        a['status'] = 'In use'
    elif a['status'] == 'In use' and rnd.random() < 0.004:
        a['status'] = 'In repair'
    elif a['status'] == 'Spare' and rnd.random() < 0.05:
        a['status'] = 'In use'
    kept.append(a)
assets = kept
spares = [a for a in assets if a['status'] == 'Spare']
if spares and rnd.random() < 0.1:  # retire an old spare now and then
    old = min(spares, key=lambda a: a['purchase_date'])
    assets.remove(old)
    log.append(f"Retired spare {old['asset_tag']} ({old['name']})")
if rnd.random() < 0.25:  # occasional new hire / new equipment
    cat = rnd.choices(['Laptop', 'Monitor', 'Phone', 'Desktop'], [5, 3, 2, 1])[0]
    d = new_device(cat)
    assets.append(d)
    log.append(f"Added {d['asset_tag']} ({d['name']})")

# --- Licenses ---
for l in licenses:
    total, used = int(l['seats_total']), int(l['seats_used'])
    used = max(1, min(total, used + rnd.choice([-1, 0, 0, 0, 1])))
    renew = dt.date.fromisoformat(l['renewal_date'])
    days = (renew - T).days
    renews = (days <= 0 and l['auto_renew'] == 'Yes') or (days < 0 and rnd.random() < 0.25)
    if renews:
        if used / total < 0.8:  # true-up: trim seats to usage plus a small buffer
            total = max(used + 2, round(used * 1.1))
        cost = round(int(l['annual_cost']) * rnd.uniform(1.0, 1.08) * total / int(l['seats_total']))
        l['annual_cost'] = cost
        l['renewal_date'] = add_years(renew, 1).isoformat()
        log.append(f"Renewed {l['product']} to {l['renewal_date']} at ${cost:,}")
    l['seats_total'], l['seats_used'] = total, used

os.makedirs(out_dir, exist_ok=True)
for name, rows, fields in (('assets', assets, a_fields), ('licenses', licenses, l_fields)):
    with open(os.path.join(out_dir, f'{name}-{today_s}.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
if len(sys.argv) > 5:  # optional activity log: newest day first, last 60 days kept
    import json
    path = sys.argv[5]
    try:
        with open(path) as f:
            activity = json.load(f)
    except (FileNotFoundError, ValueError):
        activity = []
    activity = [d for d in activity if d.get('date') != today_s]
    activity.insert(0, {'date': today_s, 'devices': len(assets), 'events': log or ['No lifecycle changes today']})
    with open(path, 'w') as f:
        json.dump(activity[:60], f, indent=1)
print(f'{len(assets)} assets, {len(licenses)} licenses')
print('\n'.join(log) or 'no lifecycle events today')
