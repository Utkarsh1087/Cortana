import time
import sqlite3
import datetime
import threading
from typing import Callable, Optional

DB_PATH = "lisa_memory.db"

class ReminderDaemon:
    """
    Background worker that checks for due reminders and fires proactive audio/visual alerts.
    """
    def __init__(self, alert_callback: Optional[Callable[[str], None]] = None, check_interval: int = 30):
        self.alert_callback = alert_callback
        self.check_interval = check_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            try:
                self._check_and_notify_due_items()
            except Exception as e:
                pass
            time.sleep(self.check_interval)

    def _check_and_notify_due_items(self):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Check for due reminders
            cursor.execute("""
                SELECT id, task, due_time FROM reminders
                WHERE status = 'pending' AND due_time != 'Unspecified'
            """)
            rows = cursor.fetchall()

            for r in rows:
                r_id, task, due_time = r
                # If due_time matches or is contained in current time
                if due_time in now_str or now_str in due_time:
                    # Mark reminder as alerted/completed
                    cursor.execute("UPDATE reminders SET status = 'alerted' WHERE id = ?", (r_id,))
                    conn.commit()
                    
                    alert_msg = f"Reminder Alert: It's time to {task}!"
                    if self.alert_callback:
                        self.alert_callback(alert_msg)
                    else:
                        print(f"\n🔔 [Lisa Alert]: {alert_msg}\n")


# Global reminder daemon instance
reminder_daemon = ReminderDaemon()
