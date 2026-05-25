"""
Build AI-optimized menu JSON from Clover inventory data.
"""
import json
import requests

MERCHANT_ID = "MRWSQWMCDSHQ1"
API_TOKEN = "2148cad7-875f-f420-714a-1b29c5af924c"
BASE = f"https://api.clover.com/v3/merchants/{MERCHANT_ID}"
HEADERS = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

def get_all(endpoint, params=None):
    results = []
    offset = 0
    limit = 100
    while True:
        p = {"limit": limit, "offset": offset}
        if params:
            p.update(params)
        r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=p, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        elements = data.get('elements', [])
        results.extend(elements)
        if len(elements) < limit:
            break
        offset += limit
    return results

def build_ai_context(menu, mod_groups):
    lines = []
    lines.append("=== NAPOLI PIZZERIA MENU ===")
    lines.append("Address: 3131 W. Craig Rd., North Las Vegas, NV 89032")
    lines.append("Hours: Every Day 10:00 AM - 10:00 PM (Pacific Time)")
    lines.append("Lunch Specials: Mon-Fri 10:00 AM - 3:00 PM ONLY (includes FREE soda)")
    lines.append("Delivery fee: $1.99 | Card fee: $1.00 | Tax: 8.25%")
    lines.append("Services: Delivery, Dine-In, Pick Up, Catering")
    lines.append("")

    for cat_name, cat_data in sorted(menu['categories'].items()):
        items = cat_data['items']
        if not items:
            continue
        lines.append(f"\n--- {cat_name.upper()} ---")
        for item in sorted(items, key=lambda x: x['name']):
            price_str = f"${item['price_usd']:.2f}" if item['price_usd'] > 0 else "price varies by size"
            lines.append(f"  {item['name']}: {price_str} [ID:{item['id']}]")
            for mg_id in item.get('modifier_group_ids', []):
                if mg_id in mod_groups:
                    mg = mod_groups[mg_id]
                    req = "REQUIRED" if mg['min_required'] > 0 else "optional"
                    opts = ", ".join([
                        o['name'] + (f"(+${o['price_usd']:.2f})" if o['price_usd'] > 0 else "")
                        for o in mg['options'][:20]
                    ])
                    lines.append(f"    -> {mg['name']} ({req}): {opts}")
    return "\n".join(lines)

print("Building AI-optimized menu from Clover...")

categories = get_all("categories")
items = get_all("items", {"expand": "categories,modifierGroups"})
mod_groups_raw = get_all("modifier_groups", {"expand": "modifiers"})

mod_groups = {}
for mg in mod_groups_raw:
    mods = mg.get('modifiers', {}).get('elements', [])
    mod_groups[mg['id']] = {
        'id': mg['id'],
        'name': mg['name'],
        'min_required': mg.get('minRequired', 0),
        'max_allowed': mg.get('maxAllowed', 0),
        'options': [
            {
                'id': m['id'],
                'name': m['name'],
                'price_cents': m.get('price', 0),
                'price_usd': round(m.get('price', 0) / 100, 2)
            }
            for m in mods
        ]
    }

menu = {
    "restaurant": {
        "name": "Napoli Pizzeria",
        "merchant_id": MERCHANT_ID,
        "address": "3131 W. Craig Rd., North Las Vegas, NV 89032",
        "phone": "725-204-0379",
        "website": "napolipizzerianorthlasvegas.com",
        "hours": "Every Day 10:00 AM - 10:00 PM",
        "timezone": "America/Los_Angeles",
        "lunch_specials_hours": "Monday-Friday 10:00 AM - 3:00 PM",
        "delivery_fee_cents": 199,
        "card_fee_cents": 100,
        "tax_rate": 0.0825
    },
    "categories": {},
    "modifier_groups": mod_groups,
    "summary": {
        "total_categories": len(categories),
        "total_items": len(items),
        "total_modifier_groups": len(mod_groups)
    }
}

for item in items:
    if item.get('hidden', False):
        continue
    item_cats = item.get('categories', {}).get('elements', [])
    item_mods = item.get('modifierGroups', {}).get('elements', [])
    item_data = {
        'id': item['id'],
        'name': item['name'],
        'price_cents': item.get('price', 0),
        'price_usd': round(item.get('price', 0) / 100, 2),
        'modifier_group_ids': [m['id'] for m in item_mods],
        'available': item.get('available', True)
    }
    if item_cats:
        for cat in item_cats:
            cat_name = cat.get('name', 'Other')
            if cat_name not in menu['categories']:
                menu['categories'][cat_name] = {'id': cat.get('id', ''), 'items': []}
            menu['categories'][cat_name]['items'].append(item_data)
    else:
        if 'Other' not in menu['categories']:
            menu['categories']['Other'] = {'id': '', 'items': []}
        menu['categories']['Other']['items'].append(item_data)

with open('/home/ubuntu/napoli-voice-agent/config/menu.json', 'w') as f:
    json.dump(menu, f, indent=2)
print(f"✅ menu.json saved ({len(menu['categories'])} categories, {len(mod_groups)} modifier groups)")

ai_context = build_ai_context(menu, mod_groups)
with open('/home/ubuntu/napoli-voice-agent/config/menu_ai_context.txt', 'w') as f:
    f.write(ai_context)
print("✅ menu_ai_context.txt saved")
print("\nDone! Menu files ready.")
