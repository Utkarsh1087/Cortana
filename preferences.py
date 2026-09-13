import sqlite3
import datetime
from typing import List, Dict, Any, Optional

DB_PATH = "lisa_memory.db"

def _init_preferences_table():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_text TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

_init_preferences_table()

class PreferenceManager:
    """
    Manages persistent user preferences, behavioral rules, and conflict resolution.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        _init_preferences_table()

    def get_all_active_rules(self) -> List[Dict[str, Any]]:
        """Retrieve all active user rules/preferences."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, rule_text, category FROM user_preferences WHERE status = 'active' ORDER BY id ASC")
            rows = cursor.fetchall()
            return [{"id": r[0], "rule_text": r[1], "category": r[2]} for r in rows]

    def get_rules_prompt_context(self) -> str:
        """Format active preferences into a system prompt injection string."""
        rules = self.get_all_active_rules()
        if not rules:
            return ""
        
        formatted = "User Preferences & Persistent Rules (Always adhere to these):\n"
        for i, r in enumerate(rules, 1):
            formatted += f"{i}. {r['rule_text']}\n"
        return formatted.strip()

    def check_conflict(self, new_rule: str) -> Optional[Dict[str, Any]]:
        """
        Detects potential direct contradictions between new rule and stored rules.
        """
        active_rules = self.get_all_active_rules()
        new_lower = new_rule.lower()

        # Common contradiction pairs / antonyms
        negations = ["don't", "do not", "never", "avoid", "stop"]
        affirmations = ["always", "only", "prefer", "ensure"]

        for rule in active_rules:
            existing_lower = rule["rule_text"].lower()

            # 1. Direct temperature conflicts (Celsius vs Fahrenheit)
            if ("celsius" in new_lower and "fahrenheit" in existing_lower) or \
               ("fahrenheit" in new_lower and "celsius" in existing_lower):
                return rule

            # 2. Direct format conflicts (e.g. metric vs imperial)
            if ("metric" in new_lower and "imperial" in existing_lower) or \
               ("imperial" in new_lower and "metric" in existing_lower):
                return rule

            # 3. Negation vs Affirmation on similar keywords
            has_neg_new = any(neg in new_lower for neg in negations)
            has_neg_exist = any(neg in existing_lower for neg in negations)

            if has_neg_new != has_neg_exist:
                # Extract common words
                words_new = set([w for w in new_lower.split() if len(w) > 3 and w not in negations and w not in affirmations])
                words_exist = set([w for w in existing_lower.split() if len(w) > 3 and w not in negations and w not in affirmations])
                common = words_new.intersection(words_exist)
                if len(common) >= 2:
                    return rule

        return None

    def store_rule(self, rule_text: str, category: str = "general", replace_rule_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Stores or replaces a preference rule.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if replace_rule_id:
                cursor.execute("UPDATE user_preferences SET status = 'replaced' WHERE id = ?", (replace_rule_id,))

            cursor.execute("""
                INSERT INTO user_preferences (rule_text, category, status, created_at)
                VALUES (?, ?, 'active', ?)
            """, (rule_text, category, now))
            conn.commit()
            new_id = cursor.lastrowid

        return {
            "status": "success",
            "rule_id": new_id,
            "rule_text": rule_text,
            "message": f"Preference stored and activated: '{rule_text}'"
        }

    def delete_rule(self, rule_id: int) -> bool:
        """Deactivate or remove a rule."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_preferences WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0


# Global singleton preference manager
preference_manager = PreferenceManager()
