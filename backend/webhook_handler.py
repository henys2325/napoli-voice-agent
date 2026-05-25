"""
Clover Hosted Checkout Webhook Handler
Processes payment notifications from Clover and triggers order dispatch to POS.

Webhook payload format from Clover HCO:
{
  "type": "PAYMENT",
  "id": "<payment_uuid>",
  "merchantId": "<merchant_id>",
  "data": "<checkout_session_uuid>",
  "message": "Approved for 4800",
  "status": "APPROVED",
  "createdTime": 1642599079
}
"""
import os
import hmac
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("CLOVER_WEBHOOK_SECRET", "")


def validate_clover_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Validate the Clover-Signature header using HMAC-SHA256.
    Format: t=<timestamp>,v1=<signature>
    """
    if not WEBHOOK_SECRET:
        logger.warning("CLOVER_WEBHOOK_SECRET not set — skipping signature validation")
        return True  # Allow in development; enforce in production

    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")

        # Reconstruct the signed payload: timestamp.raw_body
        signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}".encode()
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, v1_sig)
    except Exception as e:
        logger.error(f"Signature validation error: {e}")
        return False


def extract_session_id(body: dict) -> Optional[str]:
    """
    Extract the checkout session ID from a Clover HCO webhook payload.
    Clover sends the session ID in the 'data' field.
    """
    # Primary location: 'data' field contains the checkout session UUID
    session_id = body.get("data", "")

    # Fallback locations
    if not session_id:
        session_id = (
            body.get("checkoutSessionId") or
            body.get("object", {}).get("checkoutSessionId") or
            body.get("object", {}).get("metadata", {}).get("checkoutSessionId") or
            ""
        )

    return session_id if session_id else None


def is_payment_approved(body: dict) -> bool:
    """Check if the webhook indicates an approved payment."""
    event_type = body.get("type", "").upper()
    status = body.get("status", "").upper()
    message = body.get("message", "").upper()

    # Clover HCO sends type=PAYMENT, status=APPROVED on success
    if event_type == "PAYMENT" and status == "APPROVED":
        return True

    # Also check message field (e.g., "Approved for 4800")
    if "APPROVED" in message:
        return True

    return False


def get_payment_amount(body: dict) -> Optional[int]:
    """Extract payment amount in cents from webhook payload."""
    message = body.get("message", "")
    # Format: "Approved for 4800" (amount in cents)
    if "for" in message.lower():
        try:
            amount_str = message.lower().split("for")[-1].strip()
            return int(amount_str)
        except (ValueError, IndexError):
            pass
    return None
