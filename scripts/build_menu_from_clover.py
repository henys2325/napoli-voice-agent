#!/usr/bin/env python3
"""
Build complete menu JSON from Clover API with real prices and modifiers.
This replaces the old menu.json with accurate data from Clover POS.
"""
import requests
import json
import os
import sys

MERCHANT_ID = "MRWSQWMCDSHQ1"
API_TOKEN = "2148cad7-875f-f420-714a-1b29c5af924c"
BASE_URL = "https://api.clover.com"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def clover_get(path, params=None):
    url = f"{BASE_URL}/v3/merchants/{MERCHANT_ID}/{path}"
    all_items = []
    offset = 0
    limit = 200
    while True:
        p = {"limit": limit, "offset": offset}
        if params:
            p.update(params)
        r = requests.get(url, headers=HEADERS, params=p, timeout=30)
        if r.status_code != 200:
            print(f"  ERROR {r.status_code}: {r.text[:200]}")
            break
        data = r.json()
        elements = data.get("elements", [])
        all_items.extend(elements)
        if len(elements) < limit:
            break
        offset += limit
    return all_items

def build_menu():
    print("=== Building Napoli Pizzeria Menu from Clover ===\n")

    # 1. Get categories
    print("Fetching categories...")
    categories_raw = clover_get("categories", {"expand": "items"})
    print(f"  Found {len(categories_raw)} categories")

    # 2. Get all items with prices
    print("Fetching all items...")
    items_raw = clover_get("items", {"expand": "categories,modifierGroups,tags"})
    print(f"  Found {len(items_raw)} items")

    # 3. Get modifier groups
    print("Fetching modifier groups...")
    mod_groups_raw = clover_get("modifier_groups", {"expand": "modifiers"})
    print(f"  Found {len(mod_groups_raw)} modifier groups")

    # 4. Get modifiers
    print("Fetching modifiers...")
    modifiers_raw = clover_get("modifiers")
    print(f"  Found {len(modifiers_raw)} modifiers")

    # Build item lookup
    item_lookup = {}
    for item in items_raw:
        item_lookup[item["id"]] = item

    # Build modifier group lookup
    mg_lookup = {}
    for mg in mod_groups_raw:
        mg_lookup[mg["id"]] = mg

    # Build modifier lookup
    mod_lookup = {}
    for mod in modifiers_raw:
        mod_lookup[mod["id"]] = mod

    # Build menu structure
    menu = {
        "restaurant": {
            "name": "Napoli Pizzeria",
            "address": "3131 W. Craig Rd., North Las Vegas, NV 89032",
            "phone": "725-204-0379",
            "hours": "Every Day 10:00 AM – 10:00 PM (Pacific Time)",
            "lunch_special_hours": "Monday–Friday 10:00 AM – 3:00 PM",
            "delivery_fee": 1.99,
            "convenience_fee_pct": 0.03,
            "tax_rate": 0.08375,
            "pickup_special": "16\" 1 Topping $12.99"
        },
        "categories": {},
        "modifier_groups": {}
    }

    # Process categories
    active_categories = 0
    for cat in categories_raw:
        cat_name = cat.get("name", "").strip()
        if not cat_name:
            continue

        cat_items_raw = cat.get("items", {}).get("elements", [])
        cat_items = []

        for ci in cat_items_raw:
            item_id = ci.get("id")
            item = item_lookup.get(item_id, ci)

            # Get price in dollars
            price_cents = item.get("price", 0)
            price = price_cents / 100.0

            # Get modifier group IDs
            mg_ids = []
            for mg_ref in item.get("modifierGroups", {}).get("elements", []):
                mg_id = mg_ref.get("id")
                if mg_id:
                    mg_ids.append(mg_id)

            cat_items.append({
                "id": item_id,
                "name": item.get("name", "").strip(),
                "price": price,
                "description": item.get("alternateName", "") or "",
                "modifier_group_ids": mg_ids,
                "available": not item.get("hidden", False),
            })

        if cat_items:
            menu["categories"][cat_name] = {
                "id": cat.get("id"),
                "name": cat_name,
                "items": cat_items
            }
            active_categories += 1

    # Process modifier groups with their modifiers
    for mg in mod_groups_raw:
        mg_id = mg.get("id")
        mg_name = mg.get("name", "").strip()

        mods = []
        for mod in mg.get("modifiers", {}).get("elements", []):
            mod_price_cents = mod.get("price", 0)
            mods.append({
                "id": mod.get("id"),
                "name": mod.get("name", "").strip(),
                "price": mod_price_cents / 100.0,
                "available": not mod.get("available", True) == False,
            })

        menu["modifier_groups"][mg_id] = {
            "id": mg_id,
            "name": mg_name,
            "selection_type": mg.get("selectionType", "SINGLE"),
            "min_required": mg.get("minRequired", 0),
            "max_allowed": mg.get("maxAllowed", 1),
            "modifiers": mods
        }

    print(f"\n=== MENU SUMMARY ===")
    print(f"Active categories: {active_categories}")
    print(f"Total modifier groups: {len(menu['modifier_groups'])}")

    total_items = sum(len(c["items"]) for c in menu["categories"].values())
    print(f"Total items: {total_items}")

    # Show categories with item counts
    print("\nCategories:")
    for cat_name, cat_data in sorted(menu["categories"].items()):
        items = cat_data["items"]
        priced = [i for i in items if i["price"] > 0]
        print(f"  {cat_name}: {len(items)} items ({len(priced)} with prices)")

    return menu

def main():
    menu = build_menu()

    # Save to config/menu.json
    output_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'menu.json')
    with open(output_path, 'w') as f:
        json.dump(menu, f, indent=2)
    print(f"\n✅ Menu saved to {output_path}")

    # Also save a backup
    backup_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'menu_clover_backup.json')
    with open(backup_path, 'w') as f:
        json.dump(menu, f, indent=2)
    print(f"✅ Backup saved to {backup_path}")

if __name__ == "__main__":
    main()
