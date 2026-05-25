"""
Email notification service for Napoli Pizzeria Voice AI
Sends order alerts to the manager when orders are placed or sent to kitchen.
Uses smtplib (built-in Python) via Gmail SMTP or any SMTP provider.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "info@napolipizzeria.net")
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_NAME     = "Napoli Voice AI"
FROM_EMAIL    = os.getenv("SMTP_USER", "noreply@napolipizzeria.net")


def _send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email via SMTP. Returns True on success."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — email not sent.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"]      = to
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_new_order_alert(order: dict) -> bool:
    """
    Notify manager when a new order is created and payment link is sent.
    """
    items_html = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #2a2a2a;color:#e4e4e7'>"
        f"{item.get('quantity', 1)}x {item.get('item_name', 'Item')}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #2a2a2a;color:#a1a1aa;text-align:right'>"
        f"${(item.get('unit_price_cents', 0) * item.get('quantity', 1) / 100):.2f}</td></tr>"
        for item in (order.get("items") or [])
    )

    lang_flags = {"en": "🇺🇸", "es": "🇲🇽", "ru": "🇷🇺"}
    lang = order.get("language", "en")
    flag = lang_flags.get(lang, "")

    payment_url = order.get("payment_url", "")
    payment_btn = (
        f"<a href='{payment_url}' style='display:inline-block;margin-top:16px;padding:10px 24px;"
        f"background:#dc2626;color:#fff;text-decoration:none;border-radius:6px;font-family:monospace;font-size:13px'>"
        f"View Payment Link →</a>"
    ) if payment_url else ""

    html = f"""
    <div style="background:#0a0a0f;font-family:Arial,sans-serif;padding:32px;max-width:560px;margin:0 auto">
      <div style="border-bottom:2px solid #dc2626;padding-bottom:16px;margin-bottom:24px">
        <span style="color:#dc2626;font-size:20px;font-weight:bold">🍕 Napoli Voice AI</span>
        <span style="color:#52525b;font-size:13px;margin-left:12px">New Order Alert</span>
      </div>

      <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden">
        <tr><td style="padding:10px 12px;color:#71717a;font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2a2a2a" colspan="2">Order Details</td></tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Customer</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px">{order.get('customer_name', 'Unknown')} {flag}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Phone</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px;font-family:monospace">{order.get('customer_phone', 'N/A')}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Type</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px;text-transform:capitalize">{order.get('order_type', 'pickup')}</td>
        </tr>
        {"<tr><td style='padding:8px 12px;color:#a1a1aa;font-size:13px'>Address</td><td style='padding:8px 12px;color:#e4e4e7;font-size:13px'>" + order.get('delivery_address', '') + "</td></tr>" if order.get('delivery_address') else ""}
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Time</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px;font-family:monospace">{datetime.now().strftime('%I:%M %p')}</td>
        </tr>
      </table>

      <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden;margin-top:16px">
        <tr><td style="padding:10px 12px;color:#71717a;font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2a2a2a" colspan="2">Items Ordered</td></tr>
        {items_html}
        <tr>
          <td style="padding:10px 12px;color:#e4e4e7;font-weight:bold;font-size:14px">Total</td>
          <td style="padding:10px 12px;color:#4ade80;font-weight:bold;font-size:14px;text-align:right">${order.get('total_usd', 0):.2f}</td>
        </tr>
      </table>

      <div style="margin-top:16px;padding:12px;background:#1c1917;border:1px solid #fbbf24;border-radius:6px">
        <span style="color:#fbbf24;font-size:12px;font-family:monospace">⏳ AWAITING PAYMENT — Order will not go to kitchen until customer pays.</span>
      </div>

      {payment_btn}

      <p style="color:#3f3f46;font-size:11px;margin-top:32px;font-family:monospace">
        Napoli Pizzeria Voice AI · Order ID: {order.get('order_id', 'N/A')[:8]}...
      </p>
    </div>
    """
    subject = f"🍕 New Order — {order.get('customer_name', 'Customer')} · ${order.get('total_usd', 0):.2f}"
    return _send_email(MANAGER_EMAIL, subject, html)


def send_order_to_kitchen_alert(order: dict) -> bool:
    """
    Notify manager when payment is confirmed and order is sent to kitchen.
    """
    items_html = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #2a2a2a;color:#e4e4e7'>"
        f"{item.get('quantity', 1)}x {item.get('item_name', 'Item')}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #2a2a2a;color:#a1a1aa;text-align:right'>"
        f"${(item.get('unit_price_cents', 0) * item.get('quantity', 1) / 100):.2f}</td></tr>"
        for item in (order.get("items") or [])
    )

    html = f"""
    <div style="background:#0a0a0f;font-family:Arial,sans-serif;padding:32px;max-width:560px;margin:0 auto">
      <div style="border-bottom:2px solid #22c55e;padding-bottom:16px;margin-bottom:24px">
        <span style="color:#22c55e;font-size:20px;font-weight:bold">✅ Napoli Voice AI</span>
        <span style="color:#52525b;font-size:13px;margin-left:12px">Order Sent to Kitchen</span>
      </div>

      <div style="padding:16px;background:#052e16;border:1px solid #22c55e;border-radius:8px;margin-bottom:20px">
        <span style="color:#4ade80;font-size:14px;font-weight:bold">💳 Payment Confirmed — Order is now in the kitchen queue.</span>
      </div>

      <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden">
        <tr><td style="padding:10px 12px;color:#71717a;font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2a2a2a" colspan="2">Order Summary</td></tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Customer</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px">{order.get('customer_name', 'Unknown')}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Phone</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px;font-family:monospace">{order.get('customer_phone', 'N/A')}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#a1a1aa;font-size:13px">Type</td>
          <td style="padding:8px 12px;color:#e4e4e7;font-size:13px;text-transform:capitalize">{order.get('order_type', 'pickup')}</td>
        </tr>
        {"<tr><td style='padding:8px 12px;color:#a1a1aa;font-size:13px'>Address</td><td style='padding:8px 12px;color:#e4e4e7;font-size:13px'>" + order.get('delivery_address', '') + "</td></tr>" if order.get('delivery_address') else ""}
      </table>

      <table style="width:100%;border-collapse:collapse;background:#18181b;border-radius:8px;overflow:hidden;margin-top:16px">
        <tr><td style="padding:10px 12px;color:#71717a;font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2a2a2a" colspan="2">Items</td></tr>
        {items_html}
        <tr>
          <td style="padding:10px 12px;color:#e4e4e7;font-weight:bold;font-size:14px">Total Paid</td>
          <td style="padding:10px 12px;color:#4ade80;font-weight:bold;font-size:14px;text-align:right">${order.get('total_usd', 0):.2f}</td>
        </tr>
      </table>

      <p style="color:#3f3f46;font-size:11px;margin-top:32px;font-family:monospace">
        Napoli Pizzeria Voice AI · Order ID: {order.get('order_id', 'N/A')[:8]}... · Clover Order: {order.get('clover_order_id', 'N/A')}
      </p>
    </div>
    """
    subject = f"✅ Order to Kitchen — {order.get('customer_name', 'Customer')} · ${order.get('total_usd', 0):.2f}"
    return _send_email(MANAGER_EMAIL, subject, html)
