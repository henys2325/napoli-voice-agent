"""
Order Store — SQLite-based persistent storage for voice AI orders.
Tracks all orders from creation through payment and kitchen dispatch.
"""
import os
import json
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'orders.db')


class OrderStore:

    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE,
                    call_id TEXT,
                    status TEXT DEFAULT 'pending_payment',
                    customer_phone TEXT,
                    customer_name TEXT,
                    order_type TEXT DEFAULT 'pickup',
                    delivery_address TEXT,
                    items_json TEXT,
                    total_cents INTEGER DEFAULT 0,
                    total_usd REAL DEFAULT 0.0,
                    payment_url TEXT,
                    clover_order_id TEXT,
                    language TEXT DEFAULT 'en',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON orders(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON orders(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON orders(created_at)")
            conn.commit()
        logger.info(f"OrderStore initialized at {DB_PATH}")

    def save_order(self, session_id: str, order: Dict) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO orders
                    (order_id, session_id, call_id, status, customer_phone, customer_name,
                     order_type, delivery_address, items_json, total_cents, total_usd,
                     payment_url, language, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    order["order_id"],
                    session_id,
                    order.get("call_id", ""),
                    order.get("status", "pending_payment"),
                    order.get("customer_phone", ""),
                    order.get("customer_name", ""),
                    order.get("order_type", "pickup"),
                    order.get("delivery_address", ""),
                    json.dumps(order.get("items", [])),
                    order.get("total_cents", 0),
                    order.get("total_usd", 0.0),
                    order.get("payment_url", ""),
                    order.get("language", "en"),
                    order.get("created_at", now),
                    now
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Save order error: {e}")
            return False

    def get_order_by_session(self, session_id: str) -> Optional[Dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM orders WHERE session_id = ?", (session_id,)
                ).fetchone()
                return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"Get order error: {e}")
            return None

    def get_order(self, order_id: str) -> Optional[Dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM orders WHERE order_id = ?", (order_id,)
                ).fetchone()
                return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"Get order error: {e}")
            return None

    def update_order_status(self, session_id: str, status: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE orders SET status = ?, updated_at = ? WHERE session_id = ?",
                    (status, now, session_id)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Update status error: {e}")
            return False

    def update_order_clover_id(self, session_id: str, clover_order_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE orders SET clover_order_id = ?, updated_at = ? WHERE session_id = ?",
                    (clover_order_id, now, session_id)
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Update clover ID error: {e}")
            return False

    def get_all_orders(self, limit: int = 50, status_filter: Optional[str] = None) -> List[Dict]:
        try:
            with self._get_conn() as conn:
                if status_filter:
                    rows = conn.execute(
                        "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                        (status_filter, limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
                return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get all orders error: {e}")
            return []

    def get_stats(self) -> Dict:
        try:
            with self._get_conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
                paid = conn.execute("SELECT COUNT(*) FROM orders WHERE status IN ('paid','sent_to_kitchen')").fetchone()[0]
                pending = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending_payment'").fetchone()[0]
                revenue = conn.execute(
                    "SELECT SUM(total_usd) FROM orders WHERE status IN ('paid','sent_to_kitchen')"
                ).fetchone()[0] or 0.0
                today_revenue = conn.execute(
                    "SELECT SUM(total_usd) FROM orders WHERE status IN ('paid','sent_to_kitchen') AND date(created_at) = date('now')"
                ).fetchone()[0] or 0.0
                return {
                    "total_orders": total,
                    "paid_orders": paid,
                    "pending_orders": pending,
                    "total_revenue_usd": round(revenue, 2),
                    "today_revenue_usd": round(today_revenue, 2)
                }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {}

    def _row_to_dict(self, row) -> Dict:
        d = dict(row)
        if d.get("items_json"):
            try:
                d["items"] = json.loads(d["items_json"])
            except Exception:
                d["items"] = []
            del d["items_json"]
        return d
