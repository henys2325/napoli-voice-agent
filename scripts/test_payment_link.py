"""
Genera un link de pago de prueba con Clover Hosted Checkout
"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ['CLOVER_MERCHANT_ID'] = 'MRWSQWMCDSHQ1'
os.environ['CLOVER_API_TOKEN'] = '2148cad7-875f-f420-714a-1b29c5af924c'
os.environ['CLOVER_BASE_URL'] = 'https://api.clover.com'
os.environ['CLOVER_ECOMM_BASE_URL'] = 'https://api.clover.com'

from clover_service import CloverService

# Subtotal: $21.98, Convenience Fee 3% = $0.66, Tax 8.375% on food = $1.84, Total = $24.48
items = [
    {"name": "Italian Pizza 14 inch", "price": 1899, "unitQty": 1, "note": "Extra Cheese, Thin Crust"},
    {"name": "Coca-Cola 20oz", "price": 299, "unitQty": 1},
    {"name": "Convenience Fee (3%)", "price": 66, "unitQty": 1, "note": "Non-taxable"}
]

async def run():
    clover = CloverService()
    print("=== Generando Clover Hosted Checkout Link ===")
    print("Pedido:")
    print("  - Italian Pizza 14 inch (Extra Cheese) ......... $18.99")
    print("  - Coca-Cola 20oz ................................  $2.99")
    print("  - Convenience Fee (3%) .........................  $0.66")
    print("  - Tax NV 8.375% (on food only) .................  $1.84")
    print("  - TOTAL ........................................  $24.48")
    print()

    result = await clover.create_checkout_session(
        customer_phone="+17022912025",
        customer_name="Test Customer",
        items=items,
        tax_rate=837500  # 8.375% NV tax
    )

    if result.get("success"):
        print(f"✅ LINK DE PAGO GENERADO:")
        print(f"   {result.get('href')}")
        print()
        print(f"Session ID: {result.get('checkoutSessionId')}")
        print(f"Expira: {result.get('expirationTime')}")
    else:
        print(f"❌ Error: {result.get('error')}")
        print(f"   Status: {result.get('status_code')}")

asyncio.run(run())
