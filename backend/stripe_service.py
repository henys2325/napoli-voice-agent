"""
Stripe Payment Service for Napoli Pizzeria Voice AI
Generates Stripe Payment Links for SMS delivery to customers.
"""
import os
import logging
import stripe
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Configure Stripe
stripe.api_key = STRIPE_SECRET_KEY


class StripeService:
    """Handles Stripe payment link generation for order checkout."""

    async def create_payment_link(
        self,
        customer_phone: str,
        customer_name: str,
        items: List[Dict[str, Any]],
        total_cents: int,
        order_type: str = "pickup",
        order_id: str = None,
        language: str = "es"
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Link for the order.
        Returns the payment URL to send via SMS.
        """
        try:
            # Build line items for Stripe
            line_items = []
            for item in items:
                item_name = item.get("name", "Item")
                item_price = item.get("price", 0)  # price in cents
                quantity = item.get("unitQty", 1)
                note = item.get("note", "")

                if item_price <= 0:
                    continue  # Skip $0 items

                display_name = item_name
                if note:
                    display_name = f"{item_name} ({note[:50]})"

                line_items.append({
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": display_name,
                        },
                        "unit_amount": item_price,
                    },
                    "quantity": quantity,
                })

            if not line_items:
                return {"success": False, "error": "No valid items for payment"}

            # Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="payment",
                success_url=f"https://napoli-voice-agent.onrender.com/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"https://napoli-voice-agent.onrender.com/payment/failure?session_id={{CHECKOUT_SESSION_ID}}",
                customer_email=None,
                phone_number_collection={"enabled": False},
                metadata={
                    "customer_phone": customer_phone,
                    "customer_name": customer_name,
                    "order_type": order_type,
                    "order_id": order_id or "",
                    "language": language,
                },
                expires_at=int(__import__("time").time()) + 1800,  # 30 minutes (Stripe minimum)
            )

            logger.info(f"Stripe session created: {session.id} | URL: {session.url}")
            return {
                "success": True,
                "href": session.url,
                "checkoutSessionId": session.id,
                "provider": "stripe"
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Stripe payment link error: {e}")
            return {"success": False, "error": str(e)}

    async def verify_payment(self, session_id: str) -> Dict[str, Any]:
        """Verify if a Stripe payment was completed."""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                "paid": session.payment_status == "paid",
                "status": session.payment_status,
                "customer_email": session.customer_details.email if session.customer_details else None,
                "amount_total": session.amount_total,
                "metadata": dict(session.metadata) if session.metadata else {}
            }
        except Exception as e:
            logger.error(f"Stripe verify error: {e}")
            return {"paid": False, "status": "error", "error": str(e)}
