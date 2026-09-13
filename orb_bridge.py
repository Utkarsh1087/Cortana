"""
Universal Real-Time State Sync Bridge for Lisa AI Desktop Orb & Avatar.
Ensures the floating live icon instantly reflects chat states (thinking, speaking, idle, emotions)
across main.py, voice_main.py, avatar_server.py, and tools.
"""

import os
import json
import time
from typing import Dict, Any, Optional

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".orb_state.json")

def update_orb_state(state: str, emotion: Optional[str] = None, energy: float = 0.0, text: Optional[str] = None):
    """
    Broadcasts real-time state to the floating desktop orb and web avatar.
    state: 'idle' | 'listening' | 'thinking' | 'speaking'
    emotion: 'caring' | 'affectionate' | 'playful' | 'tactical'
    """
    try:
        current = get_orb_state()
        data = {
            "state": state.lower().strip(),
            "emotion": emotion.lower().strip() if emotion else current.get("emotion", "caring"),
            "energy": float(energy),
            "text": text if text is not None else current.get("text", ""),
            "timestamp": time.time()
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def get_orb_state() -> Dict[str, Any]:
    """Reads the current active state for the floating desktop orb and avatar."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"state": "idle", "emotion": "caring", "energy": 0.0, "text": "", "timestamp": time.time()}

# Initialize state on module load
if not os.path.exists(STATE_FILE):
    update_orb_state("idle", "caring")
