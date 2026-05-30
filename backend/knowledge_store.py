"""
Knowledge Store — SQLite-based persistent storage for Eva's learning knowledge base.
Allows restaurant staff to add custom knowledge entries that Eva uses to answer questions.
"""
import os
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')

CATEGORIES = [
    "Menu & Pricing",
    "Hours & Location",
    "Policies",
    "Specials & Promotions",
    "FAQs",
    "Ordering Rules",
    "Other"
]


class KnowledgeStore:

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
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'Other',
                    active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_active ON knowledge(active)")
            conn.commit()
        logger.info(f"KnowledgeStore initialized at {DB_PATH}")
        # Seed with default entries if empty
        self._seed_defaults()

    def _seed_defaults(self):
        """Seed with useful default knowledge entries if the table is empty."""
        with self._get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            if count > 0:
                return
            now = datetime.now(timezone.utc).isoformat()
            defaults = [
                ("Pickup Special", "We have a pickup special: 16\" pizza with 1 topping for only $12.99! Mention this to customers who want pickup.", "Specials & Promotions"),
                ("Delivery Fee", "Delivery fee is $1.99. We deliver to the North Las Vegas area.", "Policies"),
                ("Convenience Fee", "There is a 3% convenience fee applied to all orders for payment processing.", "Policies"),
                ("Hours", "We are open Sunday–Thursday 10AM–10PM and Friday–Saturday 10AM–11PM. Lunch specials are Monday–Friday 9AM–3PM.", "Hours & Location"),
                ("Gluten Free Options", "We offer gluten-free pizza crust (14\" only, $12.75) and gluten-free bread for subs, burgers, wraps, and triple deckers.", "Menu & Pricing"),
                ("Half & Half Wings", "For orders of 10 or more wings, customers can split the flavor — half one flavor, half another.", "Ordering Rules"),
                ("Free Soda with Lunch", "Every lunch special (Mon–Fri 9AM–3PM) includes a FREE can of soda!", "Specials & Promotions"),
                ("Wine & Beer", "Wine and beer are available for dine-in only. We do not include alcohol in delivery or pickup orders.", "Policies"),
            ]
            for title, content, category in defaults:
                conn.execute(
                    "INSERT INTO knowledge (title, content, category, active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                    (title, content, category, now, now)
                )
            conn.commit()
            logger.info(f"KnowledgeStore seeded with {len(defaults)} default entries")

    def add_entry(self, title: str, content: str, category: str = "Other") -> Dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge (title, content, category, active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                (title, content, category, now, now)
            )
            conn.commit()
            entry_id = cursor.lastrowid
        return self.get_entry(entry_id)

    def update_entry(self, entry_id: int, title: str = None, content: str = None, category: str = None, active: bool = None) -> Optional[Dict]:
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        if title is not None:
            fields.append("title = ?")
            values.append(title)
        if content is not None:
            fields.append("content = ?")
            values.append(content)
        if category is not None:
            fields.append("category = ?")
            values.append(category)
        if active is not None:
            fields.append("active = ?")
            values.append(1 if active else 0)
        if not fields:
            return self.get_entry(entry_id)
        fields.append("updated_at = ?")
        values.append(now)
        values.append(entry_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE knowledge SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM knowledge WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_entry(self, entry_id: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM knowledge WHERE id = ?", (entry_id,)).fetchone()
            return dict(row) if row else None

    def get_all_entries(self, category: str = None, active_only: bool = False) -> List[Dict]:
        query = "SELECT * FROM knowledge"
        conditions = []
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if active_only:
            conditions.append("active = 1")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY category, created_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_active_knowledge_text(self) -> str:
        """Returns all active knowledge entries as a formatted text block for Eva's prompt."""
        entries = self.get_all_entries(active_only=True)
        if not entries:
            return ""
        lines = ["## ADDITIONAL KNOWLEDGE (from staff-added learning entries):"]
        current_cat = None
        for e in entries:
            if e["category"] != current_cat:
                current_cat = e["category"]
                lines.append(f"\n### {current_cat}")
            lines.append(f"- **{e['title']}**: {e['content']}")
        return "\n".join(lines)

    def get_stats(self) -> Dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM knowledge WHERE active = 1").fetchone()[0]
            by_cat = conn.execute(
                "SELECT category, COUNT(*) as count FROM knowledge GROUP BY category"
            ).fetchall()
            return {
                "total": total,
                "active": active,
                "inactive": total - active,
                "by_category": {r["category"]: r["count"] for r in by_cat}
            }
