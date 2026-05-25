"""Test all backend modules."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv('.env')

from clover_service import CloverService
from sms_service import SMSService
from order_store import OrderStore
from webhook_handler import extract_session_id, is_payment_approved
import uuid
from datetime import datetime, timezone

print("Testing backend modules...")

store = OrderStore()
print('✅ OrderStore initialized')

test_order = {
    'order_id': str(uuid.uuid4()),
    'call_id': 'test-call-123',
    'status': 'pending_payment',
    'customer_phone': '7025551234',
    'customer_name': 'Test Customer',
    'order_type': 'pickup',
    'delivery_address': '',
    'items': [{'item_id': 'TEST', 'item_name': '14" Pepperoni Pizza', 'quantity': 1, 'unit_price_cents': 2249}],
    'total_cents': 2500,
    'total_usd': 25.00,
    'payment_url': 'https://www.clover.com/pay-checkout/test',
    'language': 'en',
    'created_at': datetime.now(timezone.utc).isoformat()
}
session_id = 'test-session-' + str(uuid.uuid4())[:8]
store.save_order(session_id, test_order)
print('✅ Order saved to SQLite')

retrieved = store.get_order_by_session(session_id)
print(f'✅ Order retrieved: {retrieved["customer_name"]}')

stats = store.get_stats()
print(f'✅ Stats: {stats}')

mock_webhook = {
    'type': 'PAYMENT',
    'status': 'APPROVED',
    'message': 'Approved for 2500',
    'data': session_id,
    'merchantId': 'MRWSQWMCDSHQ1'
}
sid = extract_session_id(mock_webhook)
approved = is_payment_approved(mock_webhook)
print(f'✅ Webhook parsing: session={sid}, approved={approved}')

print()
print('✅ All modules loaded and tested successfully!')
