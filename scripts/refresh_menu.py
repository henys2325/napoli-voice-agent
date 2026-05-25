"""
Script para actualizar el menú desde Clover y sincronizar con el agente Sofia en Vapi.ai.
"""
import os
import sys
import json
import requests
from datetime import datetime

# Credenciales
MERCHANT_ID = "MRWSQWMCDSHQ1"
CLOVER_TOKEN = "2148cad7-875f-f420-714a-1b29c5af924c"
VAPI_KEY = "53c7c8bc-9b72-410f-b4b1-606942ff77f1"
ASSISTANT_ID = "1350377e-c62e-41e7-85c8-e7ee3254461e"
BASE_URL = f"https://api.clover.com/v3/merchants/{MERCHANT_ID}"
HEADERS = {"Authorization": f"Bearer {CLOVER_TOKEN}", "Content-Type": "application/json"}

def fetch_all(endpoint, params=None):
    """Fetch all items from a paginated Clover endpoint."""
    items = []
    offset = 0
    limit = 100
    while True:
        p = {"limit": limit, "offset": offset}
        if params:
            p.update(params)
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=p)
        if r.status_code != 200:
            print(f"  ERROR {r.status_code} on {endpoint}: {r.text[:200]}")
            break
        data = r.json()
        batch = data.get("elements", [])
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return items

print("=" * 60)
print(f"ACTUALIZANDO MENÚ DESDE CLOVER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 60)

# 1. Obtener categorías
print("\n[1/5] Obteniendo categorías...")
categories = fetch_all("categories")
print(f"  ✓ {len(categories)} categorías encontradas")

# 2. Obtener todos los ítems activos
print("\n[2/5] Obteniendo ítems del menú...")
items = fetch_all("items", {"filter": "hidden=false"})
active_items = [i for i in items if not i.get("hidden", False) and i.get("available", True)]
print(f"  ✓ {len(items)} ítems totales, {len(active_items)} activos")

# 3. Obtener grupos de modificadores
print("\n[3/5] Obteniendo modificadores...")
mod_groups = fetch_all("modifier_groups")
print(f"  ✓ {len(mod_groups)} grupos de modificadores")

# Obtener modificadores de cada grupo (primeros 20 grupos para no sobrecargar)
modifiers_by_group = {}
for mg in mod_groups[:30]:
    mg_id = mg["id"]
    mods = fetch_all(f"modifier_groups/{mg_id}/modifiers")
    modifiers_by_group[mg_id] = mods

# 4. Construir el menú estructurado
print("\n[4/5] Construyendo menú estructurado...")

# Mapa de categorías
cat_map = {c["id"]: c["name"] for c in categories}

# Mapa de ítems por categoría
items_by_category = {}
for cat in categories:
    cat_name = cat["name"]
    items_by_category[cat_name] = []

# Asignar ítems a categorías
for item in active_items:
    item_cats = item.get("categories", {}).get("elements", [])
    if not item_cats:
        continue
    for ic in item_cats:
        cat_id = ic.get("id")
        cat_name = cat_map.get(cat_id, "Other")
        if cat_name not in items_by_category:
            items_by_category[cat_name] = []
        
        # Precio en dólares
        price_cents = item.get("price", 0)
        price = price_cents / 100.0
        
        item_data = {
            "id": item["id"],
            "name": item["name"],
            "price": price,
            "price_display": f"${price:.2f}",
        }
        
        # Descripción si existe
        if item.get("alternateName"):
            item_data["description"] = item["alternateName"]
        
        items_by_category[cat_name].append(item_data)

# Filtrar categorías vacías
menu = {k: v for k, v in items_by_category.items() if v}

# Estadísticas
total_items = sum(len(v) for v in menu.values())
print(f"  ✓ {len(menu)} categorías con ítems")
print(f"  ✓ {total_items} ítems en el menú")

# 5. Guardar el menú
menu_path = os.path.join(os.path.dirname(__file__), "..", "data", "menu.json")
os.makedirs(os.path.dirname(menu_path), exist_ok=True)

menu_output = {
    "restaurant": "Napoli Pizzeria North Las Vegas",
    "last_updated": datetime.now().isoformat(),
    "total_categories": len(menu),
    "total_items": total_items,
    "categories": menu,
    "modifier_groups": {
        mg["name"]: [m["name"] + (f" (+${m.get('price',0)/100:.2f})" if m.get("price",0) > 0 else "") 
                     for m in modifiers_by_group.get(mg["id"], [])]
        for mg in mod_groups[:30]
        if modifiers_by_group.get(mg["id"])
    }
}

with open(menu_path, "w") as f:
    json.dump(menu_output, f, indent=2)

print(f"\n  ✓ Menú guardado en: {menu_path}")

# Mostrar resumen de categorías
print("\n  CATEGORÍAS DEL MENÚ:")
for cat_name, cat_items in sorted(menu.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
    print(f"    • {cat_name}: {len(cat_items)} ítems")

print("\n[5/5] Sincronizando con Vapi.ai...")

# Construir el system prompt con el menú actualizado
menu_summary = []
for cat_name, cat_items in menu.items():
    if cat_items:
        items_str = ", ".join([f"{i['name']} ({i['price_display']})" for i in cat_items[:5]])
        if len(cat_items) > 5:
            items_str += f" y {len(cat_items)-5} más"
        menu_summary.append(f"- {cat_name}: {items_str}")

menu_text = "\n".join(menu_summary[:40])

system_prompt = f"""You are Sofia, the AI phone ordering agent for Napoli Pizzeria North Las Vegas.

RESTAURANT INFO:
- Name: Napoli Pizzeria North Las Vegas
- Phone: (702) 291-2025
- Address: North Las Vegas, NV
- Hours: Mon-Sun 10AM-10PM (Lunch Specials until 3PM)

YOUR ROLE:
1. Greet the customer warmly in their language (English, Spanish, or Russian)
2. Take their order from the menu below
3. Confirm the order and total (including 8.375% NV tax + 3% convenience fee)
4. Ask for their phone number to send the payment link
5. Use the submit_order tool to process the order and send the SMS payment link
6. Inform them: "Your order will be sent to the kitchen as soon as payment is confirmed."

MENU (Updated {datetime.now().strftime('%Y-%m-%d')}):
{menu_text}

RULES:
- Always confirm the order before submitting
- Lunch Specials are only available until 3PM
- Be friendly, concise, and professional
- If unsure about an item, check the menu
- Always collect a phone number for the SMS payment link

LANGUAGES: Respond in the same language the customer uses (English, Spanish, Russian)"""

# Actualizar el asistente en Vapi.ai
vapi_headers = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
update_payload = {
    "model": {
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system_prompt}]
    }
}

r = requests.patch(
    f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
    headers=vapi_headers,
    json=update_payload
)

if r.status_code == 200:
    print("  ✓ Agente Sofia actualizado en Vapi.ai con el menú más reciente")
else:
    print(f"  ✗ Error actualizando Vapi.ai: {r.status_code} - {r.text[:200]}")

print("\n" + "=" * 60)
print("✅ MENÚ ACTUALIZADO CORRECTAMENTE")
print(f"   {total_items} ítems en {len(menu)} categorías")
print("=" * 60)
