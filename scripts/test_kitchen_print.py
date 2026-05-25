"""
Script de prueba de impresión en cocina.
Crea una orden de prueba real en Clover POS via el backend de Render
y verifica que se procese correctamente.
"""
import requests
import json
import time
from datetime import datetime

BACKEND_URL = "https://napoli-voice-agent.onrender.com"

print("=" * 60)
print("TEST DE IMPRESIÓN EN COCINA — NAPOLI PIZZERIA")
print(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# Orden de prueba con ítems de diferentes categorías
# para probar las diferentes impresoras (Pizza, Cocina, Bebidas)
test_order = {
    "customer_phone": "+17252040379",  # Número del restaurante para prueba
    "customer_name": "TEST KITCHEN PRINT",
    "order_type": "pickup",
    "items": [
        {
            "name": "Italian Pizza 14\"",
            "quantity": 1,
            "price": 18.99,
            "modifiers": ["Extra Cheese", "Well Done"],
            "notes": "PRUEBA IMPRESORA PIZZA"
        },
        {
            "name": "Wings 10 pc",
            "quantity": 1,
            "price": 14.99,
            "modifiers": ["Buffalo Sauce"],
            "notes": "PRUEBA IMPRESORA COCINA"
        },
        {
            "name": "Coca-Cola 20oz",
            "quantity": 1,
            "price": 2.99,
            "modifiers": [],
            "notes": "PRUEBA IMPRESORA BEBIDAS"
        }
    ],
    "special_instructions": "*** ORDEN DE PRUEBA - NO PREPARAR ***",
    "test_mode": True
}

print("\n[1/3] Enviando orden de prueba al backend...")
print(f"  Ítems: {len(test_order['items'])}")
for item in test_order['items']:
    print(f"  • {item['name']} x{item['quantity']} — ${item['price']:.2f}")
    if item['modifiers']:
        print(f"    Modificadores: {', '.join(item['modifiers'])}")

# Llamar al endpoint de tool-call del backend (simula lo que hace Vapi)
tool_payload = {
    "message": {
        "type": "tool-calls",
        "toolCallList": [
            {
                "id": f"test-{int(time.time())}",
                "type": "function",
                "function": {
                    "name": "submit_order_and_send_payment",
                    "arguments": json.dumps({
                        "customer_phone": test_order["customer_phone"],
                        "customer_name": test_order["customer_name"],
                        "order_type": test_order["order_type"],
                        "items": test_order["items"],
                        "special_instructions": test_order["special_instructions"]
                    })
                }
            }
        ]
    }
}

try:
    print("\n[2/3] Llamando al endpoint del agente de voz...")
    r = requests.post(
        f"{BACKEND_URL}/vapi/tool-call",
        json=tool_payload,
        timeout=60
    )
    
    print(f"  HTTP Status: {r.status_code}")
    
    if r.status_code == 200:
        response_data = r.json()
        print(f"  ✅ Respuesta recibida")
        
        # Extraer el resultado del tool
        results = response_data.get("results", [])
        if results:
            result = results[0]
            result_content = result.get("result", "{}")
            if isinstance(result_content, str):
                try:
                    result_data = json.loads(result_content)
                except:
                    result_data = {"raw": result_content}
            else:
                result_data = result_content
            
            print(f"\n  RESULTADO DEL TOOL:")
            print(f"  {json.dumps(result_data, indent=4)}")
            
            # Verificar si se creó la orden
            order_id = result_data.get("order_id") or result_data.get("clover_order_id")
            payment_link = result_data.get("payment_link") or result_data.get("checkout_url")
            
            if order_id:
                print(f"\n  ✅ ORDEN CREADA EN CLOVER")
                print(f"     Order ID: {order_id}")
            
            if payment_link:
                print(f"\n  ✅ LINK DE PAGO GENERADO")
                print(f"     URL: {payment_link}")
        else:
            print(f"  Respuesta completa: {json.dumps(response_data, indent=2)[:500]}")
    else:
        print(f"  ❌ Error: {r.text[:300]}")
        
except requests.exceptions.Timeout:
    print("  ⚠️  Timeout — el servidor tardó más de 60 segundos")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Verificar las órdenes recientes en el backend
print("\n[3/3] Verificando órdenes recientes en el sistema...")
try:
    r = requests.get(f"{BACKEND_URL}/vapi/orders", timeout=20)
    if r.status_code == 200:
        orders = r.json()
        if isinstance(orders, list):
            print(f"  ✅ {len(orders)} orden(es) en el sistema")
            for order in orders[-3:]:  # Últimas 3
                print(f"  • ID: {order.get('id','?')} | Estado: {order.get('status','?')} | {order.get('created_at','?')[:19]}")
        else:
            print(f"  Respuesta: {orders}")
    else:
        # Probar endpoint alternativo
        r2 = requests.get(f"{BACKEND_URL}/orders", timeout=20)
        print(f"  /orders status: {r2.status_code} — {r2.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("INSTRUCCIONES PARA VERIFICAR LA IMPRESIÓN:")
print("  1. Revisa tu Clover POS — debe aparecer una nueva orden")
print("  2. La orden tiene el nombre 'TEST KITCHEN PRINT'")
print("  3. Verifica que se imprimió en las impresoras de cocina")
print("  4. Si ves la orden en Clover = el sistema funciona ✅")
print("  5. Puedes cancelar/void la orden de prueba en Clover")
print("=" * 60)
