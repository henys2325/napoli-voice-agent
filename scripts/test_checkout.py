"""
Test Clover Hosted Checkout payment link generation.
Run this to verify the checkout flow works before deploying.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from clover_service import CloverService

async def test_checkout():
    clover = CloverService()

    print("Testing Clover Hosted Checkout...")
    print("=" * 50)

    # Simulate a pizza order
    test_items = [
        {
            "name": "Hand Tossed 14\" Pizza - Pepperoni",
            "price": 2249,   # $22.49
            "unitQty": 1,
            "note": "Extra sauce, well done"
        },
        {
            "name": "Bone-In Wings (10 pc) - BBQ",
            "price": 2320,   # $23.20
            "unitQty": 1,
            "note": "Extra crispy"
        },
        {
            "name": "2-Liter Coca Cola",
            "price": 399,    # $3.99
            "unitQty": 1,
            "note": ""
        },
        {
            "name": "Delivery Fee",
            "price": 199,
            "unitQty": 1,
            "note": ""
        },
        {
            "name": "Card Processing Fee",
            "price": 100,
            "unitQty": 1,
            "note": ""
        }
    ]

    result = await clover.create_checkout_session(
        customer_phone="7025551234",
        customer_name="John Smith",
        items=test_items,
        tax_rate=837500  # Real merchant tax rate: 8.375%
    )

    print(f"Result: {result}")
    if result.get("success"):
        print(f"\n✅ SUCCESS!")
        print(f"   Payment URL: {result['href']}")
        print(f"   Session ID: {result['checkoutSessionId']}")
        print(f"\n   Open this URL in your browser to test the payment flow.")
    else:
        print(f"\n❌ FAILED: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_checkout())
