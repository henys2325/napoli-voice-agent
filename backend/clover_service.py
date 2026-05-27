"""
Clover POS Service
Handles:
  - Hosted Checkout session creation (payment links)
  - Order creation in Clover POS (after payment)
  - Order status queries
"""
import os
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MERCHANT_ID = os.getenv("CLOVER_MERCHANT_ID", "MRWSQWMCDSHQ1")
API_TOKEN = os.getenv("CLOVER_API_TOKEN", "1f1dc027-8644-7f11-666d-08053fecb46b")
BASE_URL = os.getenv("CLOVER_BASE_URL", "https://api.clover.com")
ECOMM_BASE = os.getenv("CLOVER_ECOMM_BASE_URL", "https://api.clover.com")  # Production Clover API

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "X-Clover-Merchant-Id": MERCHANT_ID
}


class CloverService:

    async def create_checkout_session(
        self,
        customer_phone: str,
        customer_name: str,
        items: List[Dict],
        tax_rate: int = 825000
    ) -> Dict:
        """
        Create a Clover Hosted Checkout session and return the payment URL.
        tax_rate: 8.25% = 825000 (Clover uses integer where 10% = 1000000)
        """
        # Split customer name
        parts = customer_name.strip().split(" ", 1)
        first_name = parts[0] if parts else "Customer"
        last_name = parts[1] if len(parts) > 1 else ""

        # Build line items with tax
        line_items = []
        for item in items:
            li = {
                "name": item["name"][:127],
                "price": item["price"],
                "unitQty": item.get("unitQty", 1),
            }
            if item.get("note"):
                li["note"] = item["note"][:255]
            if tax_rate and item["name"] not in ("Delivery Fee", "Convenience Fee (3%)", "Card Processing Fee"):
                li["taxRates"] = [{"name": "NV Tax 8.375%", "rate": tax_rate}]
            line_items.append(li)

        backend_url = os.getenv("BACKEND_URL", "https://napoli-voice-agent.onrender.com")
        payload = {
            "customer": {
                "firstName": first_name,
                "lastName": last_name,
                "phoneNumber": customer_phone.replace("+", "").replace("-", "").replace(" ", "")
            },
            "tips": {"enabled": True},
            "shoppingCart": {
                "lineItems": line_items
            },
            "redirectUrls": {
                "success": f"{backend_url}/payment/success",
                "failure": f"{backend_url}/payment/failure",
            }
        }

        # Production: https://api.clover.com/invoicingcheckoutservice/v1/checkouts
        # Sandbox:    https://apisandbox.dev.clover.com/invoicingcheckoutservice/v1/checkouts
        ecomm_base = os.getenv("CLOVER_ECOMM_BASE_URL", "https://api.clover.com")
        url = f"{ecomm_base}/invoicingcheckoutservice/v1/checkouts"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=payload, headers=HEADERS)
                logger.info(f"Clover Checkout response: {r.status_code} {r.text[:300]}")
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "success": True,
                        "href": data.get("href", ""),
                        "checkoutSessionId": data.get("checkoutSessionId", ""),
                        "expirationTime": data.get("expirationTime", "")
                    }
                else:
                    return {"success": False, "error": r.text, "status_code": r.status_code}
        except Exception as e:
            logger.error(f"Clover checkout error: {e}")
            return {"success": False, "error": str(e)}

    async def create_pos_order(self, order: Dict) -> Dict:
        """
        Create an order in Clover POS after payment is confirmed.
        Uses the atomic order endpoint for a single API call.
        """
        items = order.get("items", [])
        order_type = order.get("order_type", "pickup")
        customer_name = order.get("customer_name", "Phone Order")
        delivery_address = order.get("delivery_address", "")

        # Build line items for Clover POS
        clover_line_items = []
        for item in items:
            li = {
                "item": {"id": item["item_id"]},
                "name": item["item_name"],
                "price": item["unit_price_cents"],
                "unitQty": item.get("quantity", 1) * 1000,  # Clover uses milliUnits
            }
            # Add modifiers
            if item.get("modifier_ids"):
                li["modifications"] = [
                    {"modifier": {"id": mid}} for mid in item["modifier_ids"]
                ]
            if item.get("special_instructions"):
                li["note"] = item["special_instructions"][:255]
            clover_line_items.append(li)

        # Order note
        note_parts = [f"PHONE ORDER - {order_type.upper()}"]
        if customer_name:
            note_parts.append(f"Customer: {customer_name}")
        if delivery_address:
            note_parts.append(f"Delivery to: {delivery_address}")
        note_parts.append(f"Phone: {order.get('customer_phone', 'N/A')}")
        note_parts.append(f"PAID via Hosted Checkout")

        payload = {
            "orderCart": {
                "lineItems": clover_line_items,
                "note": " | ".join(note_parts)[:255],
                "orderType": {
                    "label": order_type.capitalize(),
                    "taxable": True
                }
            }
        }

        url = f"{BASE_URL}/v3/merchants/{MERCHANT_ID}/atomic_order/orders"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=payload, headers=HEADERS)
                logger.info(f"Clover POS order response: {r.status_code} {r.text[:500]}")
                if r.status_code in (200, 201):
                    data = r.json()
                    clover_order_id = data.get("id", "")
                    logger.info(f"Clover POS order created: {clover_order_id}")
                    return {"success": True, "clover_order_id": clover_order_id, "data": data}
                else:
                    # Fallback: try simple order creation
                    return await self._create_simple_order(order, note_parts)
        except Exception as e:
            logger.error(f"Clover POS order error: {e}")
            return {"success": False, "error": str(e)}

    async def _create_simple_order(self, order: Dict, note_parts: List[str]) -> Dict:
        """Fallback: create a simple order without line items (manual entry)."""
        items = order.get("items", [])
        total_cents = order.get("total_cents", 0)

        # Build a readable order summary
        items_summary = []
        for item in items:
            qty = item.get("quantity", 1)
            name = item.get("item_name", "Item")
            mods = ", ".join(item.get("modifier_names", []))
            line = f"{qty}x {name}"
            if mods:
                line += f" ({mods})"
            items_summary.append(line)

        full_note = " | ".join(note_parts) + " | ITEMS: " + "; ".join(items_summary)

        payload = {
            "note": full_note[:255],
            "total": total_cents,
            "state": "open"
        }

        url = f"{BASE_URL}/v3/merchants/{MERCHANT_ID}/orders"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=payload, headers=HEADERS)
                if r.status_code in (200, 201):
                    data = r.json()
                    return {"success": True, "clover_order_id": data.get("id", ""), "data": data}
                else:
                    return {"success": False, "error": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_order(self, clover_order_id: str) -> Optional[Dict]:
        """Get a Clover order by ID."""
        url = f"{BASE_URL}/v3/merchants/{MERCHANT_ID}/orders/{clover_order_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=HEADERS)
                if r.status_code == 200:
                    return r.json()
        except Exception as e:
            logger.error(f"Get order error: {e}")
        return None

    async def get_recent_orders(self, limit: int = 20) -> List[Dict]:
        """Get recent orders from Clover POS."""
        url = f"{BASE_URL}/v3/merchants/{MERCHANT_ID}/orders"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=HEADERS, params={"limit": limit})
                if r.status_code == 200:
                    return r.json().get("elements", [])
        except Exception as e:
            logger.error(f"Get orders error: {e}")
        return []
