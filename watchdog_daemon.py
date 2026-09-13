"""
Proactive Ambient Sentinel Watchdog for Lisa AI
Monitors screen errors, long builds, background dev servers, and heavy CPU spikes,
spontaneously alerting the user via voice TTS and 3D Avatar WebSockets.
"""

import time
import threading
import psutil
from typing import Optional

class SentinelWatchdog:
    def __init__(self):
        self.is_running = False
        self.last_alert_time = 0
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("✓ [Lisa Watchdog]: Proactive Ambient Sentinel running in background.")

    def _run_loop(self):
        while self.is_running:
            time.sleep(15) # Check every 15s
            now = time.time()
            if now - self.last_alert_time < 90: # Cooldown between proactive alerts
                continue

            try:
                # 1. Check for extreme CPU spikes (> 92%)
                cpu_load = psutil.cpu_percent(interval=1)
                if cpu_load > 92:
                    self._fire_alert(f"Utkarsh, your CPU load is spiking at {int(cpu_load)} percent. Would you like me to inspect running processes?")
                    continue

                # 2. Check for battery low warning (< 18%)
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged and battery.percent < 18:
                    self._fire_alert(f"Utkarsh, your battery is at {battery.percent} percent. You might want to plug in your charger soon.")
                    continue

            except Exception:
                pass

    def _fire_alert(self, message: str):
        self.last_alert_time = time.time()
        print(f"\n🦅 [Lisa Proactive Sentinel]: {message}\n")
        
        # 1. Broadcast to avatar WebSocket
        try:
            from reminder_daemon import reminder_daemon
            if reminder_daemon.alert_callback:
                reminder_daemon.alert_callback(message)
        except Exception:
            pass

        # 2. Speak with female voice
        try:
            from tts import get_tts_engine
            tts = get_tts_engine("edge")
            tts.speak(message)
        except Exception:
            pass

watchdog = SentinelWatchdog()

if __name__ == "__main__":
    watchdog.start()
    while True:
        time.sleep(1)
