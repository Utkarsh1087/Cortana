"""
Twilio Cellular Voice Calling & Phone Alarm Service for Lisa AI.
Allows Lisa to place automated outbound phone calls, deliver voice briefings,
and trigger cellular wake-up alarms with synthesized speech.
"""

import os
import time
import sqlite3
import datetime
from typing import Dict, Any, Optional

class PhoneCallingService:
    def __init__(self, db_path: str = "lisa_memory.db"):
        self.db_path = db_path
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER", "")
        self.default_user_phone = os.getenv("USER_PHONE_NUMBER", "")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheduled_time TEXT NOT NULL,
                    to_phone TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def make_voice_call(self, message: str, to_phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Places an automated outbound voice call and speaks the message via TwiML.
        """
        target_number = to_phone or self.default_user_phone
        if not target_number:
            return {
                "status": "error",
                "message": "No destination phone number provided. Set USER_PHONE_NUMBER in .env or provide a phone number."
            }

        # Check if live Twilio is configured
        if self.account_sid and self.auth_token and self.from_phone:
            try:
                from twilio.rest import Client
                client = Client(self.account_sid, self.auth_token)
                twiml_voice = f"<Response><Say voice='Polly.Joanna-Neural'>{message}</Say></Response>"
                call = client.calls.create(
                    twiml=twiml_voice,
                    to=target_number,
                    from_=self.from_phone
                )
                return {
                    "status": "success",
                    "call_sid": call.sid,
                    "to": target_number,
                    "message": f"📞 Outbound cellular phone call placed to {target_number} (SID: {call.sid})."
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Twilio API call failed: {str(e)}"
                }
        else:
            # Fallback Simulation mode
            print(f"\n[Lisa Simulated Cellular Call to {target_number}]:")
            print(f"   Speech: \"{message}\"\n")
            return {
                "status": "simulated_success",
                "to": target_number,
                "speech_script": message,
                "message": f"[Simulated Mode]: Call placed to {target_number}. Speech: \"{message[:60]}...\" (Configure TWILIO_* keys in .env for live carrier routing)."
            }

    def schedule_phone_alarm(self, scheduled_time_iso: str, message: str, to_phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Schedules a phone wake-up call at a specific datetime.
        """
        target_number = to_phone or self.default_user_phone or "+1234567890"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scheduled_calls (scheduled_time, to_phone, message, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
            """, (scheduled_time_iso, target_number, message, now))
            call_id = cursor.lastrowid
            conn.commit()

        return {
            "status": "success",
            "call_id": call_id,
            "scheduled_time": scheduled_time_iso,
            "to": target_number,
            "message": f"⏰ Scheduled phone wake-up call #{call_id} for {scheduled_time_iso} to {target_number}."
        }

phone_service = PhoneCallingService()

if __name__ == "__main__":
    print("Testing Phone Calling Service...")
    res = phone_service.make_voice_call("Good morning Utkarsh, this is Lisa calling with your wake up briefing.")
    print("Result:", res)
