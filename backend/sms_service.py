"""
SMS Service using Twilio
Sends payment links and order confirmations in English, Spanish, and Russian.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER", "")

# SMS Templates — English, Spanish, Russian
PAYMENT_LINK_TEMPLATES = {
    "en": (
        "Hi {name}! 🍕 Napoli Pizzeria here.\n"
        "Your order total is ${total:.2f}.\n"
        "Please pay here to send your order to the kitchen:\n"
        "{url}\n\n"
        "⚠️ Your order will NOT be prepared until payment is received.\n"
        "Link expires in 15 minutes. Thank you!"
    ),
    "es": (
        "¡Hola {name}! 🍕 Te habla Napoli Pizzeria.\n"
        "El total de tu orden es ${total:.2f}.\n"
        "Por favor realiza el pago aquí para enviar tu orden a la cocina:\n"
        "{url}\n\n"
        "⚠️ Tu orden NO será preparada hasta recibir el pago.\n"
        "El enlace expira en 15 minutos. ¡Gracias!"
    ),
    "ru": (
        "Привет, {name}! 🍕 Это Napoli Pizzeria.\n"
        "Сумма вашего заказа: ${total:.2f}.\n"
        "Пожалуйста, оплатите здесь, чтобы отправить заказ на кухню:\n"
        "{url}\n\n"
        "⚠️ Заказ не будет приготовлен до получения оплаты.\n"
        "Ссылка действует 15 минут. Спасибо!"
    )
}

ORDER_CONFIRMED_TEMPLATES = {
    "en": (
        "✅ Payment received! Your order is now being prepared at Napoli Pizzeria.\n"
        "📍 3131 W. Craig Rd., North Las Vegas\n"
        "📞 725-204-0379\n"
        "Thank you for your order! 🍕"
    ),
    "es": (
        "✅ ¡Pago recibido! Tu orden ya está siendo preparada en Napoli Pizzeria.\n"
        "📍 3131 W. Craig Rd., North Las Vegas\n"
        "📞 725-204-0379\n"
        "¡Gracias por tu orden! 🍕"
    ),
    "ru": (
        "✅ Оплата получена! Ваш заказ уже готовится в Napoli Pizzeria.\n"
        "📍 3131 W. Craig Rd., North Las Vegas\n"
        "📞 725-204-0379\n"
        "Спасибо за заказ! 🍕"
    )
}

ORDER_CONFIRMED_DELIVERY_TEMPLATES = {
    "en": "✅ Payment received! Your order is on its way to you. 🚗 Estimated delivery: 30-45 min. Napoli Pizzeria 📞 725-204-0379",
    "es": "✅ ¡Pago recibido! Tu orden está en camino. 🚗 Entrega estimada: 30-45 min. Napoli Pizzeria 📞 725-204-0379",
    "ru": "✅ Оплата получена! Ваш заказ уже едет к вам. 🚗 Доставка: 30-45 мин. Napoli Pizzeria 📞 725-204-0379"
}


class SMSService:

    def _get_client(self):
        """Get Twilio client (lazy init)."""
        if not TWILIO_ACCOUNT_SID or TWILIO_ACCOUNT_SID == "YOUR_TWILIO_ACCOUNT_SID":
            logger.warning("Twilio credentials not configured. SMS will be logged only.")
            return None
        try:
            from twilio.rest import Client
            return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        except Exception as e:
            logger.error(f"Twilio client error: {e}")
            return None

    def _format_phone(self, phone: str) -> str:
        """Ensure phone number has +1 prefix for US numbers."""
        phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not phone.startswith("+"):
            if len(phone) == 10:
                phone = f"+1{phone}"
            elif len(phone) == 11 and phone.startswith("1"):
                phone = f"+{phone}"
            else:
                phone = f"+{phone}"
        return phone

    async def send_payment_link(
        self,
        phone: str,
        customer_name: str,
        total_usd: float,
        payment_url: str,
        language: str = "en"
    ) -> bool:
        """Send payment link SMS to customer."""
        lang = language if language in PAYMENT_LINK_TEMPLATES else "en"
        template = PAYMENT_LINK_TEMPLATES[lang]
        name = customer_name.split()[0] if customer_name else "there"
        body = template.format(name=name, total=total_usd, url=payment_url)

        return await self._send(phone, body)

    async def send_order_confirmed(
        self,
        phone: str,
        customer_name: str,
        order_type: str = "pickup",
        language: str = "en"
    ) -> bool:
        """Send order confirmation SMS after payment."""
        lang = language if language in ORDER_CONFIRMED_TEMPLATES else "en"
        if order_type == "delivery":
            body = ORDER_CONFIRMED_DELIVERY_TEMPLATES[lang]
        else:
            body = ORDER_CONFIRMED_TEMPLATES[lang]
        return await self._send(phone, body)

    async def _send(self, phone: str, body: str) -> bool:
        """Send an SMS message."""
        formatted_phone = self._format_phone(phone)
        logger.info(f"SMS to {formatted_phone}: {body[:100]}...")

        client = self._get_client()
        if not client:
            # Log only — Twilio not configured
            logger.info(f"[SMS MOCK] To: {formatted_phone}\n{body}")
            return True

        try:
            message = client.messages.create(
                body=body,
                from_=TWILIO_PHONE,
                to=formatted_phone
            )
            logger.info(f"SMS sent. SID: {message.sid} | Status: {message.status}")
            return True
        except Exception as e:
            logger.error(f"SMS send error to {formatted_phone}: {e}")
            return False
