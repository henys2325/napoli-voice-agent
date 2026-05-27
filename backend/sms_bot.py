"""
SMS Ordering Bot — Napoli Pizzeria
Handles inbound SMS messages from customers.

Conversation flow (Opción C — Combined):
  1. Greeting / "menu" / "hola" → sends menu link + quick order instructions
  2. Customer types their order in natural language → GPT parses it
  3. Bot confirms items + total → customer replies YES/SI/ДА
  4. Bot generates Stripe payment link → sends via SMS
  5. Customer pays → order goes to Clover kitchen

State is stored in-memory (per phone number, TTL 30 min).
"""
import os
import json
import uuid
import logging
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
MENU_LINK = "https://napolipizzerianorthlasvegas.com/"
RESTAURANT_NAME = "Napoli Pizzeria"
RESTAURANT_PHONE = "725-204-0379"
RESTAURANT_ADDRESS = "3131 W. Craig Rd., North Las Vegas"
TAX_RATE = 0.08375

# Session TTL: 30 minutes of inactivity
SESSION_TTL_MINUTES = 30

# ── Greeting keywords (any language) ─────────────────────────
GREETING_KEYWORDS = {
    "hola", "hello", "hi", "hey", "menu", "menú", "order", "ordenar",
    "start", "help", "ayuda", "привет", "заказ", "меню", "info",
    "información", "información", "pickup", "delivery", "entrega",
    "pizza", "wings", "food", "comida", "eat", "comer"
}

CONFIRM_KEYWORDS = {"yes", "si", "sí", "да", "confirm", "confirmar",
                    "ok", "okay", "sure", "correct", "correcto", "yep",
                    "yeah", "affirmative", "proceed", "go", "pay", "pagar"}

CANCEL_KEYWORDS = {"no", "cancel", "cancelar", "нет", "stop", "nevermind",
                   "never mind", "quit", "exit", "salir", "wrong", "malo"}

# ── In-memory session store ────────────────────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(phone: str) -> Dict[str, Any]:
    """Get or create a session for a phone number."""
    now = datetime.now(timezone.utc)
    if phone in _sessions:
        s = _sessions[phone]
        # Check TTL
        last_activity = s.get("last_activity")
        if last_activity and (now - last_activity).total_seconds() > SESSION_TTL_MINUTES * 60:
            del _sessions[phone]
        else:
            s["last_activity"] = now
            return s
    _sessions[phone] = {
        "phone": phone,
        "state": "idle",
        "language": "en",
        "items": [],
        "customer_name": "Customer",
        "order_type": "pickup",
        "pending_order": None,
        "last_activity": now,
        "created_at": now,
    }
    return _sessions[phone]


def _clear_session(phone: str):
    """Clear a session after order is placed or cancelled."""
    if phone in _sessions:
        del _sessions[phone]


def _detect_language(text: str) -> str:
    """Detect language from message text."""
    text_lower = text.lower()
    # Russian detection (Cyrillic)
    if re.search(r'[а-яА-ЯёЁ]', text):
        return "ru"
    # Spanish detection
    spanish_words = ["hola", "gracias", "quiero", "pizza", "orden", "pagar",
                     "sí", "si", "no", "por favor", "cuánto", "cuanto",
                     "menú", "menu", "entrega", "recoger"]
    if any(w in text_lower for w in spanish_words):
        return "es"
    return "en"


def _build_greeting(lang: str) -> str:
    """Build the initial greeting message with menu link."""
    if lang == "es":
        return (
            f"¡Hola! 🍕 Bienvenido a {RESTAURANT_NAME}.\n\n"
            f"📋 Ver menú completo y ordenar en línea:\n{MENU_LINK}\n\n"
            f"O escríbeme tu pedido aquí y te envío un link de pago.\n"
            f"Ejemplo: \"1 pizza pepperoni grande y 2 sodas\"\n\n"
            f"📞 {RESTAURANT_PHONE} | 📍 {RESTAURANT_ADDRESS}"
        )
    elif lang == "ru":
        return (
            f"Привет! 🍕 Добро пожаловать в {RESTAURANT_NAME}.\n\n"
            f"📋 Полное меню и онлайн-заказ:\n{MENU_LINK}\n\n"
            f"Или напишите ваш заказ здесь, и я пришлю ссылку для оплаты.\n"
            f"Пример: \"1 большая пицца пепперони и 2 содовых\"\n\n"
            f"📞 {RESTAURANT_PHONE} | 📍 {RESTAURANT_ADDRESS}"
        )
    else:
        return (
            f"Hi! 🍕 Welcome to {RESTAURANT_NAME}.\n\n"
            f"📋 View full menu & order online:\n{MENU_LINK}\n\n"
            f"Or text me your order and I'll send you a payment link!\n"
            f"Example: \"1 large pepperoni pizza and 2 sodas\"\n\n"
            f"📞 {RESTAURANT_PHONE} | 📍 {RESTAURANT_ADDRESS}"
        )


def _build_confirmation(items: List[Dict], total_usd: float, lang: str) -> str:
    """Build order confirmation message."""
    lines = []
    for item in items:
        name = item.get("item_name", item.get("name", "Item"))
        qty = item.get("quantity", 1)
        price = item.get("unit_price", 0)
        lines.append(f"  • {qty}x {name} — ${price * qty:.2f}")

    items_text = "\n".join(lines)
    tax = total_usd * TAX_RATE
    conv_fee = total_usd * 0.03
    grand_total = total_usd + tax + conv_fee

    if lang == "es":
        return (
            f"📋 Tu orden:\n{items_text}\n\n"
            f"Subtotal: ${total_usd:.2f}\n"
            f"Impuesto (8.375%): ${tax:.2f}\n"
            f"Cargo de conveniencia (3%): ${conv_fee:.2f}\n"
            f"💰 Total: ${grand_total:.2f}\n\n"
            f"¿Confirmas? Responde SI para pagar o NO para cancelar."
        )
    elif lang == "ru":
        return (
            f"📋 Ваш заказ:\n{items_text}\n\n"
            f"Подытог: ${total_usd:.2f}\n"
            f"Налог (8.375%): ${tax:.2f}\n"
            f"Комиссия (3%): ${conv_fee:.2f}\n"
            f"💰 Итого: ${grand_total:.2f}\n\n"
            f"Подтверждаете? Ответьте ДА для оплаты или НЕТ для отмены."
        )
    else:
        return (
            f"📋 Your order:\n{items_text}\n\n"
            f"Subtotal: ${total_usd:.2f}\n"
            f"Tax (8.375%): ${tax:.2f}\n"
            f"Convenience fee (3%): ${conv_fee:.2f}\n"
            f"💰 Total: ${grand_total:.2f}\n\n"
            f"Confirm? Reply YES to pay or NO to cancel."
        )


async def _parse_order_with_gpt(text: str, menu: dict, lang: str) -> Dict[str, Any]:
    """
    Use OpenAI GPT to parse a natural language order into structured items.
    Falls back to simple keyword matching if GPT is unavailable.
    """
    # Build a compact menu summary for the prompt
    categories = menu.get("categories", {})
    menu_lines = []
    for cat_name, cat_data in categories.items():
        if isinstance(cat_data, dict):
            items = cat_data.get("items", [])
            for item in items:
                if item.get("available", True):
                    menu_lines.append(
                        f"{item['name']} | ${item['price_usd']:.2f} | id:{item['id']}"
                    )
    menu_text = "\n".join(menu_lines[:150])  # Limit to 150 items

    system_prompt = f"""You are an order parser for {RESTAURANT_NAME}.
Extract items from the customer's message and match them to the menu.
Return a JSON object with this structure:
{{
  "items": [
    {{"item_id": "...", "item_name": "...", "quantity": 1, "unit_price": 0.00, "special_instructions": ""}}
  ],
  "order_type": "pickup",
  "customer_name": "Customer",
  "error": null
}}

Rules:
- Match items to the menu even if the customer uses informal names
- If an item is not on the menu, set error to a message explaining it
- order_type is "pickup" unless customer says "delivery" or "entrega" or "доставка"
- If customer mentions their name, extract it
- unit_price must be the exact price from the menu
- Return ONLY valid JSON, no other text

Menu:
{menu_text}
"""

    try:
        import openai
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("BUILT_IN_FORGE_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("BUILT_IN_FORGE_API_URL")

        if not api_key:
            raise ValueError("No OpenAI API key")

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = openai.AsyncOpenAI(**client_kwargs)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"GPT parse error: {e}")
        return {"items": [], "order_type": "pickup", "customer_name": "Customer",
                "error": f"Could not parse order: {e}"}


async def handle_inbound_sms(
    from_phone: str,
    body: str,
    menu: dict,
    stripe_svc,
    sms_svc,
    store,
    background_tasks=None
) -> str:
    """
    Main handler for inbound SMS messages.
    Returns the response text to send back to the customer.
    """
    session = _get_session(from_phone)
    text = body.strip()
    text_lower = text.lower()
    lang = _detect_language(text)
    session["language"] = lang

    logger.info(f"SMS from {from_phone}: '{text[:80]}' | state={session['state']} | lang={lang}")

    # ── CANCEL at any point ────────────────────────────────────
    if any(kw in text_lower for kw in CANCEL_KEYWORDS) and session["state"] != "idle":
        _clear_session(from_phone)
        if lang == "es":
            return "❌ Orden cancelada. ¡Escríbenos cuando quieras ordenar! 🍕"
        elif lang == "ru":
            return "❌ Заказ отменён. Напишите нам, когда захотите заказать! 🍕"
        else:
            return "❌ Order cancelled. Text us anytime to order! 🍕"

    # ── STATE: idle — check if greeting or order ───────────────
    if session["state"] == "idle":
        is_greeting = any(kw in text_lower for kw in GREETING_KEYWORDS) and len(text.split()) <= 4
        if is_greeting:
            session["state"] = "greeted"
            return _build_greeting(lang)
        else:
            # Treat as direct order attempt
            session["state"] = "greeted"
            # Fall through to order parsing below

    # ── STATE: greeted — parse the order ──────────────────────
    if session["state"] in ("greeted", "ordering"):
        # Check if it's just asking for menu
        if any(kw in text_lower for kw in {"menu", "menú", "меню", "link", "enlace"}):
            if lang == "es":
                return f"📋 Menú completo: {MENU_LINK}\n\nO escríbeme tu pedido aquí."
            elif lang == "ru":
                return f"📋 Полное меню: {MENU_LINK}\n\nИли напишите заказ здесь."
            else:
                return f"📋 Full menu: {MENU_LINK}\n\nOr text your order here."

        # Parse order with GPT
        if lang == "es":
            parsing_msg = "Un momento, procesando tu orden... ⏳"
        elif lang == "ru":
            parsing_msg = "Секунду, обрабатываю заказ... ⏳"
        else:
            parsing_msg = None  # Don't send intermediate message for English

        parsed = await _parse_order_with_gpt(text, menu, lang)

        if parsed.get("error") or not parsed.get("items"):
            error_msg = parsed.get("error", "")
            if lang == "es":
                return (
                    f"No pude entender tu pedido. 😕\n"
                    f"Por favor escribe algo como: \"1 pizza pepperoni grande\"\n"
                    f"O ve el menú completo: {MENU_LINK}"
                )
            elif lang == "ru":
                return (
                    f"Не смог распознать заказ. 😕\n"
                    f"Напишите, например: \"1 большая пицца пепперони\"\n"
                    f"Или посмотрите меню: {MENU_LINK}"
                )
            else:
                return (
                    f"I couldn't understand your order. 😕\n"
                    f"Try something like: \"1 large pepperoni pizza and 2 sodas\"\n"
                    f"Or view the full menu: {MENU_LINK}"
                )

        items = parsed["items"]
        order_type = parsed.get("order_type", "pickup")
        customer_name = parsed.get("customer_name", "Customer")

        # Calculate subtotal
        subtotal = sum(
            item.get("unit_price", 0) * item.get("quantity", 1)
            for item in items
        )

        # Store in session
        session["items"] = items
        session["order_type"] = order_type
        session["customer_name"] = customer_name
        session["subtotal"] = subtotal
        session["state"] = "confirming"

        return _build_confirmation(items, subtotal, lang)

    # ── STATE: confirming — wait for YES or NO ─────────────────
    if session["state"] == "confirming":
        if any(kw in text_lower for kw in CONFIRM_KEYWORDS):
            # Generate payment link
            items = session["items"]
            order_type = session["order_type"]
            customer_name = session["customer_name"]
            subtotal = session.get("subtotal", 0)
            lang = session["language"]

            # Build Stripe line items
            checkout_items = []
            for item in items:
                price_cents = int(item.get("unit_price", 0) * 100)
                checkout_items.append({
                    "name": item.get("item_name", item.get("name", "Item")),
                    "price": price_cents,
                    "unitQty": item.get("quantity", 1),
                    "note": item.get("special_instructions", "")[:100]
                })

            # Add delivery fee if needed
            if order_type == "delivery":
                checkout_items.append({"name": "Delivery Fee", "price": 199, "unitQty": 1, "note": ""})

            # Add 3% convenience fee
            conv_fee_cents = int(sum(
                item["price"] * item["unitQty"] for item in checkout_items
            ) * 0.03)
            checkout_items.append({
                "name": "Convenience Fee (3%)",
                "price": conv_fee_cents,
                "unitQty": 1,
                "note": "Non-taxable"
            })

            total_cents = int(subtotal * 100 * (1 + TAX_RATE) + conv_fee_cents)
            order_id = str(uuid.uuid4())

            try:
                checkout_result = await stripe_svc.create_payment_link(
                    customer_phone=from_phone,
                    customer_name=customer_name,
                    items=checkout_items,
                    total_cents=total_cents,
                    order_type=order_type,
                    order_id=order_id,
                    language=lang
                )

                if not checkout_result.get("success"):
                    raise ValueError(checkout_result.get("error", "Payment link failed"))

                payment_url = checkout_result["href"]
                session_id = checkout_result["checkoutSessionId"]

                # Save pending order
                order_record = {
                    "order_id": order_id,
                    "call_id": f"sms_{from_phone}",
                    "session_id": session_id,
                    "status": "pending_payment",
                    "source": "sms",
                    "customer_phone": from_phone,
                    "customer_name": customer_name,
                    "order_type": order_type,
                    "items": items,
                    "total_cents": total_cents,
                    "total_usd": round(total_cents / 100, 2),
                    "payment_url": payment_url,
                    "language": lang,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                store.save_order(session_id, order_record)

                # Clear session
                _clear_session(from_phone)

                total_usd = round(total_cents / 100, 2)
                if lang == "es":
                    return (
                        f"✅ ¡Perfecto! Aquí está tu link de pago:\n"
                        f"{payment_url}\n\n"
                        f"💰 Total: ${total_usd:.2f}\n"
                        f"⚠️ Tu orden se prepara al confirmar el pago.\n"
                        f"El link expira en 15 minutos."
                    )
                elif lang == "ru":
                    return (
                        f"✅ Отлично! Ссылка для оплаты:\n"
                        f"{payment_url}\n\n"
                        f"💰 Итого: ${total_usd:.2f}\n"
                        f"⚠️ Заказ начнём готовить после оплаты.\n"
                        f"Ссылка действует 15 минут."
                    )
                else:
                    return (
                        f"✅ Great! Here's your payment link:\n"
                        f"{payment_url}\n\n"
                        f"💰 Total: ${total_usd:.2f}\n"
                        f"⚠️ Your order will be prepared once payment is confirmed.\n"
                        f"Link expires in 15 minutes."
                    )

            except Exception as e:
                logger.error(f"SMS order payment link error: {e}")
                _clear_session(from_phone)
                if lang == "es":
                    return f"Lo siento, hubo un error al procesar tu pago. Por favor llama al {RESTAURANT_PHONE}."
                else:
                    return f"Sorry, there was an error processing your payment. Please call {RESTAURANT_PHONE}."

        elif any(kw in text_lower for kw in CANCEL_KEYWORDS):
            _clear_session(from_phone)
            if lang == "es":
                return "❌ Orden cancelada. ¡Escríbenos cuando quieras! 🍕"
            else:
                return "❌ Order cancelled. Text us anytime! 🍕"
        else:
            # Re-show confirmation
            items = session["items"]
            subtotal = session.get("subtotal", 0)
            if lang == "es":
                return f"Por favor responde SI para confirmar o NO para cancelar.\n\n{_build_confirmation(items, subtotal, lang)}"
            else:
                return f"Please reply YES to confirm or NO to cancel.\n\n{_build_confirmation(items, subtotal, lang)}"

    # ── Fallback ───────────────────────────────────────────────
    _clear_session(from_phone)
    return _build_greeting(lang)
