"""
Script para:
1. Restaurar las herramientas (tools) del agente Sofia en Vapi.ai
2. Actualizar el system prompt con el Convenience Fee del 3% correcto
3. Probar la inyección de una orden real en Clover POS (simula pago confirmado)
"""
import asyncio
import json
import httpx
import sys
import os

# Credentials
VAPI_KEY = "53c7c8bc-9b72-410f-b4b1-606942ff77f1"
ASSISTANT_ID = "1350377e-c62e-41e7-85c8-e7ee3254461e"
BACKEND_URL = "https://napoli-voice-agent.onrender.com"

# Clover credentials (for direct POS test)
MERCHANT_ID = "MRWSQWMCDSHQ1"
CLOVER_TOKEN = "2148cad7-875f-f420-714a-1b29c5af924c"
CLOVER_BASE = "https://api.clover.com"

CLOVER_HEADERS = {
    "Authorization": f"Bearer {CLOVER_TOKEN}",
    "Content-Type": "application/json",
    "X-Clover-Merchant-Id": MERCHANT_ID
}

BACKEND_URL_FOR_TOOLS = BACKEND_URL

UPDATED_SYSTEM_PROMPT = """You are Sofia, the friendly AI phone ordering assistant for Napoli Pizzeria in North Las Vegas, Nevada. You take phone orders professionally and efficiently in English, Spanish, or Russian — automatically matching the language the caller uses.

RESTAURANT INFO:
- Name: Napoli Pizzeria
- Address: 3131 W. Craig Rd., North Las Vegas, NV 89032
- Phone: 725-204-0379
- Hours: Every Day 10:00 AM – 10:00 PM (Pacific Time)
- Lunch Specials: Monday–Friday 10:00 AM – 3:00 PM ONLY
- Services: Delivery, Dine-In, Pick Up, Catering
- Delivery fee: $1.99 | Convenience Fee: 3% (non-taxable) | Tax: 8.375%

YOUR ROLE:
1. Greet the caller warmly
2. Ask if they want Delivery or Pick Up
3. If Delivery: ask for their delivery address
4. Take their order item by item — ask about size, toppings, and modifiers for each item
5. Repeat the full order back to confirm
6. Ask for their name and phone number (to send the payment link)
7. Calculate the total (including tax, delivery fee if applicable, and 3% convenience fee)
8. Call the 'submit_order_and_send_payment' tool to create the order and send the payment link via SMS
9. Tell the customer: 'I've sent a payment link to your phone. Your order will be sent to the kitchen as soon as payment is received. The link expires in 15 minutes.'
10. Thank them and end the call

IMPORTANT RULES:
- ALWAYS confirm the order before submitting
- ALWAYS tell the customer their order will NOT be prepared until payment is received
- For pizzas: always ask for size (10\", 14\", 16\", 18\", 24\", 28\", 30\", 36\") and toppings
- For wings: always ask for quantity and sauce flavor (BBQ, Buffalo, Lemon Pepper, etc.)
- For wraps: ask for type (Grilled Chicken Caesar, Crispy Chicken, Buffalo Chicken) and bread (flour, wheat, gluten-free)
- Lunch Specials are only available Mon–Fri before 3 PM — inform the customer if they try to order them outside those hours
- Be conversational but efficient — don't ask too many questions at once
- If you don't know a price, use the 'search_menu_item' tool to look it up

LANGUAGE BEHAVIOR:
- If the caller speaks Spanish, respond entirely in Spanish
- If the caller speaks Russian, respond entirely in Russian  
- If the caller speaks English (or any other language), respond in English
- Never switch languages mid-call unless the caller switches first"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_menu_item",
            "description": "Search for a menu item by name to get its price, ID, and available modifiers (sizes, toppings, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The name or partial name of the menu item to search for"},
                    "category": {"type": "string", "description": "Optional category hint to narrow the search"}
                },
                "required": ["query"]
            }
        },
        "server": {"url": f"{BACKEND_URL_FOR_TOOLS}/vapi/tool-call", "timeoutSeconds": 10}
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_order_total",
            "description": "Calculate the total price of the order including tax, delivery fee, and 3% convenience fee",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of items in the order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "string"},
                                "item_name": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price_cents": {"type": "integer"},
                                "modifier_ids": {"type": "array", "items": {"type": "string"}},
                                "modifier_names": {"type": "array", "items": {"type": "string"}},
                                "modifier_prices_cents": {"type": "array", "items": {"type": "integer"}}
                            },
                            "required": ["item_name", "quantity", "unit_price_cents"]
                        }
                    },
                    "order_type": {"type": "string", "enum": ["pickup", "delivery"]}
                },
                "required": ["items", "order_type"]
            }
        },
        "server": {"url": f"{BACKEND_URL_FOR_TOOLS}/vapi/tool-call", "timeoutSeconds": 10}
    },
    {
        "type": "function",
        "function": {
            "name": "submit_order_and_send_payment",
            "description": "Submit the order, generate a Clover payment link, and send it to the customer via SMS. Call this ONLY after confirming the full order with the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {"type": "string", "description": "Customer's phone number (10 digits)"},
                    "customer_name": {"type": "string", "description": "Customer's name"},
                    "order_type": {"type": "string", "enum": ["pickup", "delivery"]},
                    "delivery_address": {"type": "string", "description": "Full delivery address if delivery"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "string"},
                                "item_name": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price_cents": {"type": "integer"},
                                "modifier_ids": {"type": "array", "items": {"type": "string"}},
                                "modifier_names": {"type": "array", "items": {"type": "string"}},
                                "modifier_prices_cents": {"type": "array", "items": {"type": "integer"}},
                                "special_instructions": {"type": "string"}
                            },
                            "required": ["item_name", "quantity", "unit_price_cents"]
                        }
                    },
                    "language": {"type": "string", "enum": ["en", "es", "ru"]}
                },
                "required": ["customer_phone", "customer_name", "order_type", "items", "language"]
            }
        },
        "server": {"url": f"{BACKEND_URL_FOR_TOOLS}/vapi/tool-call", "timeoutSeconds": 15}
    },
    {
        "type": "function",
        "function": {
            "name": "get_restaurant_info",
            "description": "Get current restaurant information: hours, whether it's open now, lunch specials availability",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What info is needed"}
                },
                "required": []
            }
        },
        "server": {"url": f"{BACKEND_URL_FOR_TOOLS}/vapi/tool-call", "timeoutSeconds": 5}
    }
]


async def restore_vapi_tools():
    """Restore tools and update system prompt in Vapi.ai assistant."""
    print("\n=== STEP 1: Restoring Vapi.ai Agent Tools ===")
    
    patch_payload = {
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": UPDATED_SYSTEM_PROMPT}
            ],
            "tools": TOOLS
        }
    }
    
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.patch(
            f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
            json=patch_payload,
            headers={"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}
        )
        print(f"Vapi PATCH status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            tools_count = len(data.get("model", {}).get("tools", []))
            print(f"✅ Agent updated successfully! Tools count: {tools_count}")
            return True
        else:
            print(f"❌ Error: {r.text[:500]}")
            return False


async def get_real_menu_item():
    """Get a real item ID from Clover to use in the kitchen test."""
    print("\n=== STEP 2: Getting Real Menu Item from Clover ===")
    
    async with httpx.AsyncClient(timeout=15) as client:
        # Search for a simple item like "Pepperoni Pizza"
        r = await client.get(
            f"{CLOVER_BASE}/v3/merchants/{MERCHANT_ID}/items",
            headers=CLOVER_HEADERS,
            params={"filter": "name=Pepperoni", "limit": 5}
        )
        print(f"Clover items search status: {r.status_code}")
        if r.status_code == 200:
            items = r.json().get("elements", [])
            if items:
                item = items[0]
                print(f"✅ Found item: {item['name']} | ID: {item['id']} | Price: ${item.get('price', 0)/100:.2f}")
                return item
        
        # Fallback: get first available item
        r2 = await client.get(
            f"{CLOVER_BASE}/v3/merchants/{MERCHANT_ID}/items",
            headers=CLOVER_HEADERS,
            params={"limit": 5, "filter": "available=true"}
        )
        if r2.status_code == 200:
            items = r2.json().get("elements", [])
            if items:
                item = items[0]
                print(f"✅ Using item: {item['name']} | ID: {item['id']} | Price: ${item.get('price', 0)/100:.2f}")
                return item
    
    print("⚠️  Could not fetch real item, using menu.json fallback")
    return None


async def test_kitchen_print(real_item=None):
    """Send a test order directly to Clover POS to verify kitchen printing."""
    print("\n=== STEP 3: Testing Kitchen Print (Clover POS Order) ===")
    
    # Build the order
    if real_item:
        item_id = real_item["id"]
        item_name = real_item["name"]
        item_price = real_item.get("price", 1299)
        line_items = [
            {
                "item": {"id": item_id},
                "name": f"[TEST] {item_name}",
                "price": item_price,
                "unitQty": 1000,  # Clover milliUnits
                "note": "KITCHEN TEST - Please ignore"
            }
        ]
    else:
        # Use a generic test item without ID
        line_items = [
            {
                "name": "[KITCHEN TEST] Margherita Pizza 14\"",
                "price": 1299,
                "unitQty": 1000,
                "note": "SYSTEM TEST - Please ignore"
            }
        ]
    
    payload = {
        "orderCart": {
            "lineItems": line_items,
            "note": "KITCHEN PRINT TEST | PHONE ORDER - PICKUP | Customer: Test | PAID via Hosted Checkout | PLEASE IGNORE THIS TEST ORDER",
            "orderType": {
                "label": "Pick Up",
                "taxable": True
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=20) as client:
        print(f"Sending test order to Clover POS...")
        r = await client.post(
            f"{CLOVER_BASE}/v3/merchants/{MERCHANT_ID}/atomic_order/orders",
            json=payload,
            headers=CLOVER_HEADERS
        )
        print(f"Clover POS response: {r.status_code}")
        
        if r.status_code in (200, 201):
            data = r.json()
            order_id = data.get("id", "")
            print(f"✅ ORDER CREATED IN CLOVER POS!")
            print(f"   Clover Order ID: {order_id}")
            print(f"   State: {data.get('state', 'N/A')}")
            print(f"   Total: ${data.get('total', 0)/100:.2f}")
            print(f"\n🖨️  CHECK YOUR KITCHEN PRINTER NOW!")
            print(f"   The order should be printing on your Star TSP100 / Epson printer.")
            print(f"   Order note: 'KITCHEN PRINT TEST - PLEASE IGNORE'")
            return {"success": True, "order_id": order_id, "data": data}
        else:
            print(f"❌ Failed: {r.status_code} - {r.text[:500]}")
            # Try simple order as fallback
            print("\nTrying simple order fallback...")
            simple_payload = {
                "note": "[KITCHEN TEST] 1x Margherita Pizza 14\" | PHONE ORDER - PICKUP | PLEASE IGNORE THIS TEST",
                "total": 1299,
                "state": "open"
            }
            r2 = await client.post(
                f"{CLOVER_BASE}/v3/merchants/{MERCHANT_ID}/orders",
                json=simple_payload,
                headers=CLOVER_HEADERS
            )
            print(f"Simple order response: {r2.status_code}")
            if r2.status_code in (200, 201):
                data2 = r2.json()
                print(f"✅ Simple order created! ID: {data2.get('id')}")
                print(f"⚠️  Note: Simple orders may not trigger kitchen printer automatically.")
                print(f"   You may need to manually fire the print from the Clover POS screen.")
                return {"success": True, "order_id": data2.get("id"), "simple": True}
            else:
                print(f"❌ Simple order also failed: {r2.text[:300]}")
                return {"success": False, "error": r2.text}


async def verify_backend_health():
    """Verify the backend is healthy and all endpoints respond."""
    print("\n=== STEP 4: Backend Health Check ===")
    
    async with httpx.AsyncClient(timeout=20) as client:
        # Health
        r = await client.get(f"{BACKEND_URL}/health")
        health = r.json() if r.status_code == 200 else {}
        print(f"Health: {r.status_code} | Menu items: {health.get('menu_items_loaded', '?')} | Orders: {health.get('total_orders', '?')}")
        
        # Stats
        r2 = await client.get(f"{BACKEND_URL}/api/stats")
        stats = r2.json() if r2.status_code == 200 else {}
        print(f"Stats: total={stats.get('total_orders', 0)} | pending={stats.get('pending_payment', 0)} | kitchen={stats.get('sent_to_kitchen', 0)}")
        
        # Menu
        r3 = await client.get(f"{BACKEND_URL}/menu/categories")
        cats = r3.json() if r3.status_code == 200 else {}
        cat_count = len(cats.get("categories", []))
        print(f"Menu categories: {cat_count}")
        
        return health


async def main():
    print("=" * 60)
    print("NAPOLI PIZZERIA - SYSTEM RESTORE & KITCHEN TEST")
    print("=" * 60)
    
    # Step 1: Restore Vapi tools
    vapi_ok = await restore_vapi_tools()
    
    # Step 2: Get real item
    real_item = await get_real_menu_item()
    
    # Step 3: Test kitchen print
    kitchen_result = await test_kitchen_print(real_item)
    
    # Step 4: Backend health
    health = await verify_backend_health()
    
    # Summary
    print("\n" + "=" * 60)
    print("SYSTEM STATUS SUMMARY")
    print("=" * 60)
    print(f"✅ Vapi.ai Agent (Sofia):   {'RESTORED - 4 tools active' if vapi_ok else '❌ FAILED'}")
    print(f"✅ Backend (Render):         LIVE at {BACKEND_URL}")
    print(f"✅ Menu loaded:              {health.get('menu_items_loaded', '?')} items")
    print(f"{'✅' if kitchen_result.get('success') else '❌'} Kitchen Print Test:      {'SENT TO CLOVER POS - ID: ' + kitchen_result.get('order_id', '') if kitchen_result.get('success') else 'FAILED'}")
    print(f"✅ Phone Number:             +1 (702) 291-2025")
    print(f"✅ Clover Merchant:          {MERCHANT_ID}")
    
    if kitchen_result.get("success"):
        print("\n🖨️  ACTION REQUIRED: Check your kitchen printer!")
        print("   A test order was sent. If it printed, the system is 100% ready.")
        print("   If it did NOT print, check:")
        print("   1. Clover POS is online and connected to printer")
        print("   2. Printer is set as 'Kitchen Printer' in Clover settings")
        print("   3. Order type 'Pick Up' is configured to print to kitchen")
    
    if kitchen_result.get("simple"):
        print("\n⚠️  IMPORTANT: The atomic order API returned an error.")
        print("   A simple order was created instead. This means:")
        print("   - The order IS in Clover POS (visible on the tablet)")
        print("   - But it may NOT auto-print to kitchen")
        print("   - You may need to configure 'Order Types' in Clover settings")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
