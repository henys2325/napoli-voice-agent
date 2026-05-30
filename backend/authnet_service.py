"""
Authorize.net Payment Service for Napoli Pizzeria Voice AI
Handles card-not-present (phone/DTMF) transactions via Authorize.net AIM API.

Flow:
1. Eva collects card number via DTMF keypad input (digits pressed by customer)
2. Eva collects expiration date (MMYY) via DTMF
3. Eva collects CVV via DTMF
4. Eva calls submit_order_and_send_payment with card data
5. This service charges the card via Authorize.net createTransactionRequest
6. On success, order is pushed to Clover kitchen
"""
import os
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# Authorize.net Production endpoint
AUTHNET_ENDPOINT = "https://api.authorize.net/xml/v1/request.api"
# Authorize.net Sandbox endpoint (for testing)
AUTHNET_SANDBOX_ENDPOINT = "https://apitest.authorize.net/xml/v1/request.api"


class AuthNetService:
    def __init__(self):
        self.api_login_id = os.getenv("AUTHNET_API_LOGIN_ID", "")
        self.transaction_key = os.getenv("AUTHNET_TRANSACTION_KEY", "")
        self.sandbox = os.getenv("AUTHNET_SANDBOX", "false").lower() == "true"
        self.endpoint = AUTHNET_SANDBOX_ENDPOINT if self.sandbox else AUTHNET_ENDPOINT

        if not self.api_login_id or not self.transaction_key:
            logger.warning("Authorize.net credentials not configured (AUTHNET_API_LOGIN_ID / AUTHNET_TRANSACTION_KEY)")

    def is_configured(self) -> bool:
        return bool(self.api_login_id and self.transaction_key)

    async def charge_card(
        self,
        amount_usd: float,
        card_number: str,
        expiry_month: str,   # MM (e.g. "06")
        expiry_year: str,    # YY or YYYY (e.g. "27" or "2027")
        cvv: str,
        customer_name: str = "Customer",
        customer_phone: str = "",
        order_description: str = "Napoli Pizzeria Order",
        invoice_number: str = "",
    ) -> dict:
        """
        Charge a credit/debit card via Authorize.net createTransactionRequest.
        Returns dict with keys: success (bool), transaction_id, auth_code, error_message.
        """
        if not self.is_configured():
            return {"success": False, "error": "Authorize.net not configured"}

        # Normalize card number — strip spaces and dashes
        card_number = card_number.replace(" ", "").replace("-", "").strip()

        # Normalize expiry — support MMYY, MM/YY, MM/YYYY
        expiry_month = expiry_month.strip().zfill(2)
        expiry_year = expiry_year.strip()
        if len(expiry_year) == 2:
            expiry_year = "20" + expiry_year  # "27" → "2027"
        expiry = f"{expiry_month}{expiry_year}"  # "062027"

        # Build the Authorize.net JSON payload
        payload = {
            "createTransactionRequest": {
                "merchantAuthentication": {
                    "name": self.api_login_id,
                    "transactionKey": self.transaction_key
                },
                "refId": invoice_number or "NAPOLI-VOICE",
                "transactionRequest": {
                    "transactionType": "authCaptureTransaction",
                    "amount": f"{amount_usd:.2f}",
                    "payment": {
                        "creditCard": {
                            "cardNumber": card_number,
                            "expirationDate": expiry,
                            "cardCode": cvv.strip()
                        }
                    },
                    "order": {
                        "invoiceNumber": invoice_number or "NAPOLI-VOICE",
                        "description": order_description[:255]
                    },
                    "customer": {
                        "type": "individual",
                        "email": ""
                    },
                    "billTo": {
                        "firstName": customer_name.split()[0] if customer_name else "Customer",
                        "lastName": " ".join(customer_name.split()[1:]) if len(customer_name.split()) > 1 else ".",
                        "phoneNumber": customer_phone
                    },
                    # Card-not-present (phone order) — marketType 0
                    "transactionSettings": {
                        "setting": [
                            {"settingName": "marketType", "settingValue": "0"},
                            {"settingName": "deviceType", "settingValue": "1"}
                        ]
                    }
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                resp.raise_for_status()

            # Authorize.net sometimes prepends a BOM character — strip it
            text = resp.text.lstrip("\ufeff")
            data = json.loads(text)

            logger.info(f"Authorize.net response: {json.dumps(data)[:400]}")

            # Parse response
            result = data.get("transactionResponse", {})
            messages = data.get("messages", {})
            result_code = messages.get("resultCode", "Error")

            if result_code == "Ok":
                response_code = str(result.get("responseCode", ""))
                if response_code == "1":
                    # Approved
                    return {
                        "success": True,
                        "transaction_id": result.get("transId", ""),
                        "auth_code": result.get("authCode", ""),
                        "amount_usd": amount_usd,
                        "message": "Payment approved"
                    }
                else:
                    # Declined or error
                    errors = result.get("errors", [{}])
                    err_text = errors[0].get("errorText", "Card declined") if errors else "Card declined"
                    return {
                        "success": False,
                        "error": err_text,
                        "response_code": response_code
                    }
            else:
                # API-level error
                api_messages = messages.get("message", [{}])
                err_text = api_messages[0].get("text", "Payment failed") if api_messages else "Payment failed"
                return {"success": False, "error": err_text}

        except httpx.TimeoutException:
            logger.error("Authorize.net request timed out")
            return {"success": False, "error": "Payment gateway timeout. Please try again."}
        except Exception as e:
            logger.error(f"Authorize.net error: {e}")
            return {"success": False, "error": f"Payment error: {str(e)}"}

    async def verify_credentials(self) -> dict:
        """Test Authorize.net credentials by calling authenticateTestRequest."""
        if not self.is_configured():
            return {"success": False, "error": "Credentials not configured"}
        payload = {
            "authenticateTestRequest": {
                "merchantAuthentication": {
                    "name": self.api_login_id,
                    "transactionKey": self.transaction_key
                }
            }
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
            text = resp.text.lstrip("\ufeff")
            data = json.loads(text)
            result_code = data.get("messages", {}).get("resultCode", "Error")
            return {
                "success": result_code == "Ok",
                "sandbox": self.sandbox,
                "endpoint": self.endpoint,
                "result_code": result_code
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
