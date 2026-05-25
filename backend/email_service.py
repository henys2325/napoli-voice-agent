"""
Email notification service for Napoli Pizzeria Voice Agent.
Sends order alerts to the restaurant manager via SMTP.
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

# Email configuration from environment variables
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "info@napolipizzeria.net")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "noreply@napolipizzeria.net")


def _send_email(subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email via SMTP. Returns True if successful."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Skipping email notification.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = MANAGER_EMAIL

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, MANAGER_EMAIL, msg.as_string())

        logger.info(f"Email sent: {subject} → {MANAGER_EMAIL}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_new_order_alert(order: Dict) -> bool:
    """
    Send a new order alert to the manager when a payment link is sent to the customer.
    Called when the order is created (pending_payment status).
    """
    customer_name = order.get("customer_name", "Unknown")
    customer_phone = order.get("customer_phone", "N/A")
    order_type = order.get("order_type", "pickup").upper()
    total_usd = order.get("total_usd", 0.0)
    payment_url = order.get("payment_url", "")
    language = order.get("language", "en")
    delivery_address = order.get("delivery_address", "")
    items = order.get("items", [])
    order_id = order.get("order_id", "N/A")
    created_at = order.get("created_at", datetime.now().isoformat())

    # Build items HTML
    items_html = ""
    for item in items:
        qty = item.get("quantity", 1)
        name = item.get("item_name", "Item")
        price = item.get("unit_price_cents", 0) / 100
        mods = ", ".join(item.get("modifier_names", []))
        mod_str = f" ({mods})" if mods else ""
        items_html += f"<tr><td>{qty}x {name}{mod_str}</td><td>${price:.2f}</td></tr>"

    delivery_row = f"<tr><td><strong>Delivery Address:</strong></td><td>{delivery_address}</td></tr>" if delivery_address else ""

    subject = f"🍕 New Phone Order — {customer_name} — ${total_usd:.2f} ({order_type})"

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #d32f2f; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0;">🍕 New Phone Order — Napoli Pizzeria</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">Payment link sent — waiting for customer payment</p>
    </div>
    <div style="background: #f5f5f5; padding: 20px; border-radius: 0 0 8px 8px;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td><strong>Customer:</strong></td><td>{customer_name}</td></tr>
            <tr><td><strong>Phone:</strong></td><td>{customer_phone}</td></tr>
            <tr><td><strong>Order Type:</strong></td><td>{order_type}</td></tr>
            {delivery_row}
            <tr><td><strong>Language:</strong></td><td>{language.upper()}</td></tr>
            <tr><td><strong>Total:</strong></td><td><strong>${total_usd:.2f}</strong></td></tr>
        </table>
        
        <h3 style="margin-top: 20px;">Order Items:</h3>
        <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 4px;">
            <thead><tr style="background: #e0e0e0;">
                <th style="padding: 8px; text-align: left;">Item</th>
                <th style="padding: 8px; text-align: right;">Price</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
        </table>
        
        <div style="margin-top: 20px; padding: 15px; background: #fff3e0; border-radius: 4px; border-left: 4px solid #ff9800;">
            <p style="margin: 0;"><strong>⏳ Status:</strong> Waiting for customer payment</p>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Order ID: {order_id}</p>
        </div>
    </div>
    </body></html>
    """

    text_body = f"""
NEW PHONE ORDER - Napoli Pizzeria
Customer: {customer_name} | Phone: {customer_phone}
Order Type: {order_type} | Total: ${total_usd:.2f}
Status: Waiting for payment
Order ID: {order_id}
    """

    return _send_email(subject, html_body, text_body)


def send_order_to_kitchen_alert(order: Dict) -> bool:
    """
    Send a kitchen confirmation alert to the manager when an order is sent to Clover POS.
    Called after payment is confirmed and order is injected into kitchen.
    """
    customer_name = order.get("customer_name", "Unknown")
    customer_phone = order.get("customer_phone", "N/A")
    order_type = order.get("order_type", "pickup").upper()
    total_usd = order.get("total_usd", 0.0)
    clover_order_id = order.get("clover_order_id", "N/A")
    delivery_address = order.get("delivery_address", "")
    items = order.get("items", [])
    order_id = order.get("order_id", "N/A")

    # Build items HTML
    items_html = ""
    for item in items:
        qty = item.get("quantity", 1)
        name = item.get("item_name", "Item")
        price = item.get("unit_price_cents", 0) / 100
        mods = ", ".join(item.get("modifier_names", []))
        mod_str = f" ({mods})" if mods else ""
        items_html += f"<tr><td>{qty}x {name}{mod_str}</td><td>${price:.2f}</td></tr>"

    delivery_row = f"<tr><td><strong>Delivery Address:</strong></td><td>{delivery_address}</td></tr>" if delivery_address else ""

    subject = f"✅ Order PAID & In Kitchen — {customer_name} — ${total_usd:.2f} ({order_type})"

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #2e7d32; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0;">✅ Order PAID — Sent to Kitchen</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">Payment confirmed — order is now in Clover POS</p>
    </div>
    <div style="background: #f5f5f5; padding: 20px; border-radius: 0 0 8px 8px;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td><strong>Customer:</strong></td><td>{customer_name}</td></tr>
            <tr><td><strong>Phone:</strong></td><td>{customer_phone}</td></tr>
            <tr><td><strong>Order Type:</strong></td><td>{order_type}</td></tr>
            {delivery_row}
            <tr><td><strong>Total Paid:</strong></td><td><strong>${total_usd:.2f}</strong></td></tr>
            <tr><td><strong>Clover Order ID:</strong></td><td>{clover_order_id}</td></tr>
        </table>
        
        <h3 style="margin-top: 20px;">Order Items:</h3>
        <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 4px;">
            <thead><tr style="background: #e0e0e0;">
                <th style="padding: 8px; text-align: left;">Item</th>
                <th style="padding: 8px; text-align: right;">Price</th>
            </tr></thead>
            <tbody>{items_html}</tbody>
        </table>
        
        <div style="margin-top: 20px; padding: 15px; background: #e8f5e9; border-radius: 4px; border-left: 4px solid #4caf50;">
            <p style="margin: 0;"><strong>🖨️ Kitchen Status:</strong> Order sent to kitchen printer</p>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Order ID: {order_id} | Clover: {clover_order_id}</p>
        </div>
    </div>
    </body></html>
    """

    text_body = f"""
ORDER PAID & IN KITCHEN - Napoli Pizzeria
Customer: {customer_name} | Phone: {customer_phone}
Order Type: {order_type} | Total Paid: ${total_usd:.2f}
Clover Order ID: {clover_order_id}
Order ID: {order_id}
    """

    return _send_email(subject, html_body, text_body)
