"""
Napoli Pizzeria — Voice AI Agent Backend
FastAPI server that handles:
  - Vapi.ai voice agent tool calls (order management)
  - Clover POS order creation
  - Clover Hosted Checkout payment link generation
  - Twilio SMS sending
  - Payment webhook processing
  - Dashboard API
"""
import os
import json
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

import sys
sys.path.insert(0, os.path.dirname(__file__))
from clover_service import CloverService
from sms_service import SMSService
from stripe_service import StripeService
from order_store import OrderStore
from email_service import send_new_order_alert, send_order_to_kitchen_alert

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── Keep-Alive (prevents Render free tier cold starts) ──────
async def _keep_alive_loop():
    """Ping self every 4 minutes to prevent Render from sleeping the instance."""
    import httpx
    port = int(os.getenv("APP_PORT", 8000))
    url = f"http://localhost:{port}/health"
    await asyncio.sleep(60)  # Wait for server to fully start
    while True:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.get(url)
            logger.debug("Keep-alive ping OK")
        except Exception as e:
            logger.debug(f"Keep-alive ping failed: {e}")
        await asyncio.sleep(240)  # Every 4 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_keep_alive_loop())
    logger.info("Keep-alive background task started (interval: 4 min)")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# ─── App Init ───────────────────────────────────────────────
app = FastAPI(
    title="Napoli Pizzeria Voice AI Agent",
    description="Backend for AI phone ordering system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Services ───────────────────────────────────────────────
clover = CloverService()
sms = SMSService()
stripe_svc = StripeService()
store = OrderStore()

# Load menu
MENU_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'menu.json')
with open(MENU_PATH) as f:
    MENU = json.load(f)

# ─── Pydantic Models ────────────────────────────────────────

class OrderItem(BaseModel):
    item_id: str
    item_name: str
    quantity: int = 1
    unit_price_cents: int
    modifier_ids: List[str] = []
    modifier_names: List[str] = []
    modifier_prices_cents: List[int] = []
    special_instructions: Optional[str] = None

class CreateOrderRequest(BaseModel):
    call_id: str
    customer_phone: str
    customer_name: Optional[str] = None
    order_type: str = "pickup"   # pickup | delivery
    delivery_address: Optional[str] = None
    items: List[OrderItem]
    language: str = "en"         # en | es | ru

class VapiToolCall(BaseModel):
    """Vapi sends tool calls in this format"""
    message: Dict[str, Any]

# ─── Health Check ───────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Napoli Voice AI Agent", "timestamp": datetime.now(timezone.utc).isoformat()}

# ─── Menu Endpoints ─────────────────────────────────────────

@app.get("/menu")
async def get_menu():
    """Return the full menu for the AI agent or dashboard."""
    return MENU

@app.get("/menu/categories")
async def get_categories():
    return {"categories": list(MENU["categories"].keys())}

@app.get("/menu/search")
async def search_menu(q: str):
    """Search menu items by name (used by AI agent)."""
    results = []
    for cat_name, cat_data in MENU["categories"].items():
        for item in cat_data["items"]:
            if q.lower() in item["name"].lower():
                results.append({**item, "category": cat_name})
    return {"results": results, "count": len(results)}

# ─── Vapi Tool Call Handler ─────────────────────────────────

@app.post("/vapi/tool-call")
async def handle_vapi_tool_call(request: Request, background_tasks: BackgroundTasks):
    """
    Main endpoint for Vapi.ai tool calls.
    The AI agent calls this when it needs to:
      - look up menu items
      - calculate order totals
      - submit the order and send payment link
      - check payment status
    """
    body = await request.json()
    logger.info(f"Vapi tool call received: {json.dumps(body, indent=2)[:500]}")

    message = body.get("message", {})
    # Support both Vapi formats: toolCalls (new) and toolCallList (legacy)
    tool_calls = message.get("toolCalls", []) or message.get("toolCallList", [])

    results = []
    for tc in tool_calls:
        tool_name = tc.get("function", {}).get("name", "")
        args_raw = tc.get("function", {}).get("arguments", "{}")
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        call_id = tc.get("id", str(uuid.uuid4()))

        logger.info(f"Tool: {tool_name} | Args: {args}")

        try:
            if tool_name == "search_menu_item":
                result = await tool_search_menu_item(args)
            elif tool_name == "calculate_order_total":
                result = await tool_calculate_total(args)
            elif tool_name == "submit_order_and_send_payment":
                result = await tool_submit_order(args, message, background_tasks)
            elif tool_name == "check_payment_status":
                result = await tool_check_payment(args)
            elif tool_name == "get_restaurant_info":
                result = await tool_restaurant_info(args)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool error {tool_name}: {e}")
            result = {"error": str(e)}

        results.append({
            "toolCallId": call_id,
            "result": json.dumps(result)
        })

    return {"results": results}

# ─── Tool Implementations ───────────────────────────────────

async def tool_search_menu_item(args: dict) -> dict:
    """Search for a menu item by name and return its ID and price."""
    query = args.get("query", "").lower()
    category_hint = args.get("category", "").lower()
    matches = []

    for cat_name, cat_data in MENU["categories"].items():
        if category_hint and category_hint not in cat_name.lower():
            continue
        for item in cat_data["items"]:
            if query in item["name"].lower():
                # Get modifier groups
                mods = []
                for mg_id in item.get("modifier_group_ids", []):
                    if mg_id in MENU["modifier_groups"]:
                        mg = MENU["modifier_groups"][mg_id]
                        mods.append({
                            "group_id": mg_id,
                            "group_name": mg["name"],
                            "required": mg["min_required"] > 0,
                            "options": mg["options"][:20]
                        })
                matches.append({
                    "id": item["id"],
                    "name": item["name"],
                    "price_usd": item["price_usd"],
                    "category": cat_name,
                    "modifier_groups": mods
                })

    if not matches:
        return {"found": False, "message": f"No items found matching '{query}'"}
    return {"found": True, "items": matches[:5]}


async def tool_calculate_total(args: dict) -> dict:
    """Calculate order total including tax, delivery fee, card fee."""
    items = args.get("items", [])
    order_type = args.get("order_type", "pickup")

    subtotal = 0
    line_items = []
    for item in items:
        # Accept unit_price_cents (int cents), unit_price (float dollars), or price (float dollars) from Vapi
        if "unit_price_cents" in item:
            item_price = int(item["unit_price_cents"])
        elif "unit_price" in item:
            raw = float(item["unit_price"])
            item_price = int(raw * 100) if raw < 1000 else int(raw)
        elif "price" in item:
            raw = float(item["price"])
            item_price = int(raw * 100) if raw < 1000 else int(raw)
        else:
            item_price = 0
        mod_total = sum(item.get("modifier_prices_cents", []))
        qty = item.get("quantity", 1)
        line_total = (item_price + mod_total) * qty
        subtotal += line_total
        # Accept both item_name and name
        display_name = item.get("item_name") or item.get("name", "Item")
        line_items.append({
            "name": display_name,
            "quantity": qty,
            "unit_price_usd": round(item_price / 100, 2),
            "modifiers_usd": round(mod_total / 100, 2),
            "line_total_usd": round(line_total / 100, 2)
        })

    delivery_fee = 199 if order_type == "delivery" else 0
    convenience_fee = int(subtotal * 0.03)  # 3% Convenience Fee (not taxable)
    tax = int(subtotal * 0.08375)           # 8.375% NV tax on food only (not on fees)
    total = subtotal + delivery_fee + convenience_fee + tax

    return {
        "line_items": line_items,
        "subtotal_usd": round(subtotal / 100, 2),
        "delivery_fee_usd": round(delivery_fee / 100, 2),
        "convenience_fee_usd": round(convenience_fee / 100, 2),
        "tax_usd": round(tax / 100, 2),
        "total_usd": round(total / 100, 2),
        "total_cents": total
    }


async def tool_submit_order(args: dict, message: dict, background_tasks: BackgroundTasks) -> dict:
    """
    Submit the order: create pending record, generate payment link, send SMS.
    Does NOT push to Clover yet — that happens after payment confirmation.
    """
    customer_phone = args.get("customer_phone", "")
    customer_name = args.get("customer_name", "Customer")
    order_type = args.get("order_type", "pickup")
    delivery_address = args.get("delivery_address", "")
    items = args.get("items", [])
    language = args.get("language", "en")
    call_id = message.get("call", {}).get("id", str(uuid.uuid4()))

    if not customer_phone:
        return {"success": False, "error": "Customer phone number is required to send payment link."}

    if not items:
        return {"success": False, "error": "No items in the order."}

    # Calculate total
    total_data = await tool_calculate_total({"items": items, "order_type": order_type})
    total_cents = total_data["total_cents"]

    # Build checkout line items
    checkout_items = []
    for item in items:
        # Accept unit_price_cents (int cents), unit_price (float dollars), or price (float dollars) from Vapi
        if "unit_price_cents" in item:
            item_price = int(item["unit_price_cents"])
        elif "unit_price" in item:
            raw = float(item["unit_price"])
            item_price = int(raw * 100) if raw < 1000 else int(raw)
        elif "price" in item:
            raw = float(item["price"])
            item_price = int(raw * 100) if raw < 1000 else int(raw)
        else:
            item_price = 0
        mod_total = sum(item.get("modifier_prices_cents", []))
        mod_names = ", ".join(item.get("modifier_names", []))
        note = item.get("special_instructions", "")
        if mod_names:
            note = f"{mod_names}. {note}".strip(". ")
        # Accept both item_name and name
        display_name = item.get("item_name") or item.get("name", "Item")
        checkout_items.append({
            "name": display_name,
            "price": item_price + mod_total,
            "unitQty": item.get("quantity", 1),
            "note": note[:100] if note else ""
        })

    # Add fees
    if order_type == "delivery":
        checkout_items.append({"name": "Delivery Fee", "price": 199, "unitQty": 1, "note": ""})
    # 3% Convenience Fee (not taxable — added as separate line item with no taxRates)
    def _item_price_cents(item):
        if "unit_price_cents" in item:
            return int(item["unit_price_cents"])
        elif "unit_price" in item:
            raw = float(item["unit_price"])
            return int(raw * 100) if raw < 1000 else int(raw)
        elif "price" in item:
            raw = float(item["price"])
            return int(raw * 100) if raw < 1000 else int(raw)
        return 0
    convenience_fee_cents = int(sum(
        (_item_price_cents(item) + sum(item.get("modifier_prices_cents", []))) * item.get("quantity", 1)
        for item in items
    ) * 0.03)
    checkout_items.append({"name": "Convenience Fee (3%)", "price": convenience_fee_cents, "unitQty": 1, "note": "Non-taxable"})

    # Generate Stripe Payment Link
    order_id_temp = str(uuid.uuid4())
    checkout_result = await stripe_svc.create_payment_link(
        customer_phone=customer_phone,
        customer_name=customer_name,
        items=checkout_items,
        total_cents=total_cents,
        order_type=order_type,
        order_id=order_id_temp,
        language=language
    )

    if not checkout_result.get("success"):
        # Fallback to Clover if Stripe fails
        logger.warning(f"Stripe failed, trying Clover: {checkout_result.get('error')}")
        checkout_result = await clover.create_checkout_session(
            customer_phone=customer_phone,
            customer_name=customer_name,
            items=checkout_items,
            tax_rate=837500
        )
        if not checkout_result.get("success"):
            return {"success": False, "error": f"No se pudo generar el link de pago: {checkout_result.get('error')}"}

    payment_url = checkout_result["href"]
    session_id = checkout_result["checkoutSessionId"]

    # Save pending order
    order_record = {
        "order_id": str(uuid.uuid4()),
        "call_id": call_id,
        "session_id": session_id,
        "status": "pending_payment",
        "customer_phone": customer_phone,
        "customer_name": customer_name,
        "order_type": order_type,
        "delivery_address": delivery_address,
        "items": items,
        "total_cents": total_cents,
        "total_usd": total_data["total_usd"],
        "payment_url": payment_url,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    store.save_order(session_id, order_record)

    # Send SMS in background
    background_tasks.add_task(
        sms.send_payment_link,
        phone=customer_phone,
        customer_name=customer_name,
        total_usd=total_data["total_usd"],
        payment_url=payment_url,
        language=language
    )

    # Notify manager of new order
    background_tasks.add_task(send_new_order_alert, order_record)

    logger.info(f"Order created. Session: {session_id} | Total: ${total_data['total_usd']} | Phone: {customer_phone}")

    total_fmt = f"${total_data['total_usd']:.2f}"
    if language == "es":
        msg = f"Link de pago enviado por SMS al {customer_phone}. Total: {total_fmt}. Tu pedido será enviado a la cocina en cuanto se confirme el pago."
    elif language == "ru":
        msg = f"Ссылка для оплаты отправлена на {customer_phone}. Сумма: {total_fmt}. Заказ будет отправлен на кухню после подтверждения оплаты."
    else:
        msg = f"Payment link sent via SMS to {customer_phone}. Total: {total_fmt}. The order will be sent to the kitchen as soon as payment is confirmed."

    return {
        "success": True,
        "message": msg,
        "total_usd": total_data["total_usd"],
        "total_formatted": total_fmt,
        "session_id": session_id
    }


async def tool_check_payment(args: dict) -> dict:
    """Check if a payment has been completed for a session."""
    session_id = args.get("session_id", "")
    order = store.get_order_by_session(session_id)
    if not order:
        return {"found": False, "message": "Order not found."}
    return {
        "found": True,
        "status": order["status"],
        "paid": order["status"] == "paid",
        "total_usd": order["total_usd"]
    }


async def tool_restaurant_info(args: dict) -> dict:
    """Return restaurant info: hours, address, phone."""
    info = MENU["restaurant"]
    from datetime import datetime
    import pytz
    tz = pytz.timezone(info["timezone"])
    now = datetime.now(tz)
    hour = now.hour
    weekday = now.weekday()  # 0=Mon, 6=Sun
    is_open = 10 <= hour < 22
    lunch_available = (weekday < 5) and (10 <= hour < 15)

    return {
        "name": info["name"],
        "address": info["address"],
        "phone": info["phone"],
        "hours": info["hours"],
        "is_open_now": is_open,
        "lunch_specials_available": lunch_available,
        "lunch_specials_hours": info["lunch_specials_hours"],
        "services": ["Delivery", "Dine-In", "Pick Up", "Catering"]
    }

# ─── Payment Webhook (Clover) ────────────────────────────────

@app.post("/webhook/payment")
async def payment_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Clover sends a webhook here when a Hosted Checkout payment is completed.
    We then push the order to Clover POS.
    """
    body = await request.json()
    logger.info(f"Payment webhook received: {json.dumps(body)[:500]}")

    event_type = body.get("type", "")
    data = body.get("object", body.get("data", {}))

    # Clover HCO webhook sends checkoutSessionId on payment success
    session_id = (
        data.get("checkoutSessionId") or
        body.get("checkoutSessionId") or
        data.get("metadata", {}).get("checkoutSessionId", "")
    )

    if not session_id:
        logger.warning("Webhook received without session_id")
        return {"received": True}

    order = store.get_order_by_session(session_id)
    if not order:
        logger.warning(f"No order found for session {session_id}")
        return {"received": True}

    if order["status"] == "paid":
        logger.info(f"Order {session_id} already processed")
        return {"received": True}

    # Mark as paid
    store.update_order_status(session_id, "paid")

    # Push to Clover POS in background
    background_tasks.add_task(push_order_to_clover, session_id, order)

    logger.info(f"Payment confirmed for session {session_id}. Pushing to Clover POS.")
    return {"received": True, "status": "processing"}


async def push_order_to_clover(session_id: str, order: dict):
    """Push a paid order to Clover POS (runs in background)."""
    try:
        result = await clover.create_pos_order(order)
        if result.get("success"):
            store.update_order_status(session_id, "sent_to_kitchen")
            store.update_order_clover_id(session_id, result["clover_order_id"])
            logger.info(f"Order {session_id} pushed to Clover. Clover ID: {result['clover_order_id']}")

            # Send confirmation SMS
            await sms.send_order_confirmed(
                phone=order["customer_phone"],
                customer_name=order["customer_name"],
                order_type=order["order_type"],
                language=order.get("language", "en")
            )

            # Notify manager that order is in kitchen
            kitchen_order = {**order, "clover_order_id": result["clover_order_id"]}
            send_order_to_kitchen_alert(kitchen_order)
        else:
            store.update_order_status(session_id, "clover_error")
            logger.error(f"Failed to push order {session_id} to Clover: {result.get('error')}")
    except Exception as e:
        store.update_order_status(session_id, "clover_error")
        logger.error(f"Exception pushing order {session_id}: {e}")

# ─── Payment Redirect Endpoints ─────────────────────────────

@app.get("/payment/success")
async def payment_success(checkoutSessionId: str = None, orderId: str = None):
    """
    Clover redirects here after successful payment.
    We also trigger the order push to kitchen.
    """
    session_id = checkoutSessionId or orderId
    if session_id:
        order = store.get_order_by_session(session_id)
        if order and order.get("status") == "pending_payment":
            store.update_order_status(session_id, "paid")
            import asyncio
            asyncio.create_task(push_order_to_clover(session_id, order))
            logger.info(f"Payment success redirect for session {session_id}")
    return {"status": "success", "message": "Payment received! Your order is being sent to the kitchen."}

@app.get("/payment/failure")
async def payment_failure(checkoutSessionId: str = None):
    """Clover redirects here after failed payment."""
    logger.warning(f"Payment failure redirect for session {checkoutSessionId}")
    return {"status": "failed", "message": "Payment was not completed. Please call us at 725-204-0379."}

# ─── Vapi Webhook ────────────────────────────────────────────

@app.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """
    Vapi sends call events here: call-started, call-ended, transcript, etc.
    Used for logging and monitoring.
    """
    try:
        body = await request.json()
        event_type = body.get("message", {}).get("type", "unknown")
        call_id = body.get("message", {}).get("call", {}).get("id", "")
        logger.info(f"Vapi webhook: {event_type} | call_id: {call_id}")

        if event_type == "end-of-call-report":
            call = body.get("message", {}).get("call", {})
            transcript = body.get("message", {}).get("transcript", "")
            duration = call.get("endedAt", "") 
            ended_reason = body.get("message", {}).get("endedReason", "")
            logger.info(f"Call ended: {call_id} | reason: {ended_reason} | duration: {duration}")
            if ended_reason in ("customer-ended-call", "assistant-ended-call"):
                logger.info(f"Normal call end: {ended_reason}")
            elif ended_reason in ("silence-timed-out", "max-duration-exceeded"):
                logger.warning(f"Call dropped: {ended_reason} for call {call_id}")
    except Exception as e:
        logger.error(f"Vapi webhook error: {e}")
    return {"received": True}

# ─── Dashboard API ───────────────────────────────────────────

@app.get("/api/orders")
async def get_orders(limit: int = 50, status: Optional[str] = None):
    orders = store.get_all_orders(limit=limit, status_filter=status)
    return {"orders": orders, "count": len(orders)}

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    order = store.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/stats")
async def get_stats():
    return store.get_stats()

# ─── Test Endpoints ─────────────────────────────────────────

@app.post("/test/kitchen-print")
async def test_kitchen_print():
    """Test endpoint: sends a test order to Clover POS to verify kitchen printing."""
    test_order = {
        "items": [
            {
                "item_id": "F9G6EBX5SCKK4",
                "item_name": "[KITCHEN TEST] Pepperoni Pizza",
                "quantity": 1,
                "unit_price_cents": 1299,
                "modifier_ids": [],
                "modifier_names": [],
                "special_instructions": "SYSTEM TEST - Please ignore"
            }
        ],
        "order_type": "pickup",
        "customer_name": "Kitchen Test",
        "customer_phone": "7025551234",
        "delivery_address": "",
        "total_cents": 1299
    }
    result = await clover.create_pos_order(test_order)
    return {
        "test": "kitchen_print",
        "clover_result": result,
        "message": "Check your kitchen printer!" if result.get("success") else "Failed to send to Clover POS"
    }

@app.get("/test/clover-connection")
async def test_clover_connection():
    """Test endpoint: verify Clover API connectivity."""
    import httpx
    merchant_id = os.getenv("CLOVER_MERCHANT_ID", "MRWSQWMCDSHQ1")
    api_token = os.getenv("CLOVER_API_TOKEN", "2148cad7-875f-f420-714a-1b29c5af924c")
    base_url = os.getenv("CLOVER_BASE_URL", "https://api.clover.com")
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json"
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base_url}/v3/merchants/{merchant_id}", headers=headers)
            return {
                "status_code": r.status_code,
                "success": r.status_code == 200,
                "merchant_id": merchant_id,
                "response_preview": r.text[:200] if r.status_code == 200 else r.text[:200]
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/test/sms")
async def test_sms(background_tasks: BackgroundTasks):
    """Test endpoint: send a test SMS to verify Twilio is working."""
    import os as _os
    twilio_sid = _os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_phone = _os.getenv("TWILIO_PHONE_NUMBER", "")
    # Check if credentials are loaded
    sid_loaded = bool(twilio_sid) and twilio_sid != "YOUR_TWILIO_ACCOUNT_SID"
    # Try to send a test SMS
    background_tasks.add_task(
        sms.send_payment_link,
        phone="7025448930",
        customer_name="Test",
        total_usd=19.99,
        payment_url="https://www.clover.com/pay-checkout/test-123?mode=checkout",
        language="es"
    )
    return {
        "test": "sms",
        "twilio_sid_loaded": sid_loaded,
        "twilio_sid_preview": twilio_sid[:8] + "..." if twilio_sid else "NOT SET",
        "twilio_phone": twilio_phone or "NOT SET",
        "message": "SMS queued - check your phone in 5 seconds"
    }

# ─── Static Frontend ─────────────────────────────────────────

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.exists(FRONTEND_PATH):
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="static")

# ─── Entry Point ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", 8000)),
        reload=True
    )
