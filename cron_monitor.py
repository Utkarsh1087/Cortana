"""
Autonomous Cron & Web Monitoring Agent for Lisa AI.
Allows voice-commanded scheduled jobs, recurring web scrapers, price thresholds,
and automated dispatches to Telegram, Voice TTS, and 3D Avatar HUD.
"""

import time
import json
import sqlite3
import threading
import datetime
import re
import urllib.request
from typing import List, Dict, Any, Optional

class CronMonitorEngine:
    def __init__(self, db_path: str = "lisa_memory.db"):
        self.db_path = db_path
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cron_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    condition_rules TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    last_run TEXT,
                    notify_channel TEXT DEFAULT 'all',
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def create_job(self, task_name: str, task_type: str, target: str, 
                   condition_rules: str, interval_minutes: int = 30, 
                   notify_channel: str = "all") -> Dict[str, Any]:
        """
        Creates a new autonomous monitoring job.
        task_type: 'price_alert' | 'web_change' | 'recurring_digest' | 'reminder_poll'
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cron_jobs 
                (task_name, task_type, target, condition_rules, interval_minutes, last_run, notify_channel, status, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?, 'active', ?)
            """, (task_name, task_type, target, condition_rules, max(1, interval_minutes), notify_channel, now))
            job_id = cursor.lastrowid
            conn.commit()

        return {
            "status": "success",
            "job_id": job_id,
            "task_name": task_name,
            "task_type": task_type,
            "target": target,
            "interval_minutes": interval_minutes,
            "message": f"Autonomous monitoring job #{job_id} ('{task_name}') scheduled successfully."
        }

    def list_jobs(self, status: str = "active") -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status == "all":
                cursor.execute("SELECT id, task_name, task_type, target, condition_rules, interval_minutes, last_run, notify_channel, status FROM cron_jobs")
            else:
                cursor.execute("SELECT id, task_name, task_type, target, condition_rules, interval_minutes, last_run, notify_channel, status FROM cron_jobs WHERE status = ?", (status,))
            rows = cursor.fetchall()

        jobs = []
        for r in rows:
            jobs.append({
                "id": r[0],
                "task_name": r[1],
                "task_type": r[2],
                "target": r[3],
                "condition_rules": r[4],
                "interval_minutes": r[5],
                "last_run": r[6],
                "notify_channel": r[7],
                "status": r[8]
            })
        return jobs

    def cancel_job(self, job_id: int) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE cron_jobs SET status = 'cancelled' WHERE id = ?", (job_id,))
            affected = cursor.rowcount
            conn.commit()

        if affected > 0:
            return {"status": "success", "message": f"Monitoring job #{job_id} cancelled."}
        return {"status": "error", "message": f"Job #{job_id} not found."}

    def _execute_job(self, job: Dict[str, Any]):
        job_id = job["id"]
        task_type = job["task_type"]
        target = job["target"]
        conditions = job["condition_rules"]
        task_name = job["task_name"]
        channel = job["notify_channel"]

        triggered = False
        alert_message = ""

        try:
            if task_type == "price_alert":
                # Check crypto or stock price
                symbol = target.upper().strip()
                try:
                    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        data = json.loads(resp.read().decode())
                        if symbol.lower() in data:
                            curr_price = float(data[symbol.lower()]["usd"])
                            rule_match = re.search(r'([<>]=?)\s*([0-9.]+)', conditions)
                            if rule_match:
                                op, thresh_val = rule_match.group(1), float(rule_match.group(2))
                                if (op == '<' and curr_price < thresh_val) or \
                                   (op == '<=' and curr_price <= thresh_val) or \
                                   (op == '>' and curr_price > thresh_val) or \
                                   (op == '>=' and curr_price >= thresh_val):
                                    triggered = True
                                    alert_message = f"🔔 Price Alert Triggered for {symbol}! Current price is ${curr_price:,.2f} USD (Rule: {conditions})."
                except Exception:
                    pass

            elif task_type == "web_change":
                try:
                    req = urllib.request.Request(target, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        html = resp.read().decode('utf-8', errors='ignore')
                        if conditions.lower() in html.lower():
                            triggered = True
                            alert_message = f"🌐 Web Monitor Alert for {task_name}: Target condition '{conditions}' was detected on {target}!"
                except Exception:
                    pass

            elif task_type == "recurring_digest":
                triggered = True
                alert_message = f"📋 Scheduled Briefing for '{task_name}': Time to review {target}."

            if triggered and alert_message:
                self._dispatch_alert(alert_message, channel)

            # Update last_run
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE cron_jobs SET last_run = ? WHERE id = ?", (now_iso, job_id))
                conn.commit()

        except Exception as e:
            print(f"[CronEngine Error on Job #{job_id}]: {e}")

    def _dispatch_alert(self, message: str, channel: str = "all"):
        print(f"\n[Lisa Autonomous Cron Alert]: {message}\n")

        # 1. Dispatch to Telegram
        if channel in ("all", "telegram"):
            try:
                import os
                token = os.getenv("TELEGRAM_BOT_TOKEN")
                chat_id = os.getenv("TELEGRAM_CHAT_ID")
                if token and chat_id:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = json.dumps({"chat_id": chat_id, "text": f"🤖 *Lisa Monitor Alert*\n\n{message}", "parse_mode": "Markdown"}).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

        # 2. Dispatch to 3D Avatar HUD
        try:
            from reminder_daemon import reminder_daemon
            if reminder_daemon.alert_callback:
                reminder_daemon.alert_callback(message)
        except Exception:
            pass

        # 3. Speak via TTS
        if channel in ("all", "voice"):
            try:
                from tts import get_tts_engine
                tts = get_tts_engine("edge")
                tts.speak(message)
            except Exception:
                pass

    def check_and_run_due_jobs(self):
        active_jobs = self.list_jobs(status="active")
        now = datetime.datetime.now(datetime.timezone.utc)
        for job in active_jobs:
            last_run = job["last_run"]
            interval = job["interval_minutes"]
            should_run = False

            if not last_run:
                should_run = True
            else:
                try:
                    last_dt = datetime.datetime.fromisoformat(last_run)
                    if (now - last_dt).total_seconds() >= (interval * 60):
                        should_run = True
                except Exception:
                    should_run = True

            if should_run:
                self._execute_job(job)

    def start_background_daemon(self, poll_interval_seconds: int = 30):
        if self.is_running:
            return
        self.is_running = True

        def _loop():
            while self.is_running:
                self.check_and_run_due_jobs()
                time.sleep(poll_interval_seconds)

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()
        print("✓ [Lisa Cron]: Autonomous Monitoring Daemon started.")

    def stop_daemon(self):
        self.is_running = False

cron_engine = CronMonitorEngine()

if __name__ == "__main__":
    cron_engine.start_background_daemon(poll_interval_seconds=5)
    print("Testing Cron Engine. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cron_engine.stop_daemon()
