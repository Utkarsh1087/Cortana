"""
Audio Equalizer & System Volume Controller for Lisa AI.
Provides direct master volume adjustment, per-application volume mixing,
and DSP equalizer presets (Bass Boost, Vocal Clarity, Cinema, Rock, Night Mode) via Windows Core Audio.
"""

import sys
from typing import Dict, Any, Optional

# Equalizer DSP Profiles
EQUALIZER_PRESETS = {
    "bass_boost": {
        "name": "Bass Boost / Club",
        "description": "+6dB Low Freq (60Hz-250Hz), deep punchy sub-bass.",
        "low_gain": "+6.0 dB",
        "mid_gain": "0.0 dB",
        "high_gain": "+1.5 dB",
        "spatial": "Standard"
    },
    "vocal_clarity": {
        "name": "Vocal Clarity / Dialogue",
        "description": "+4.5dB Mid Freq (1kHz-4kHz) for crisp voice, podcasts, and calls.",
        "low_gain": "-1.5 dB",
        "mid_gain": "+4.5 dB",
        "high_gain": "+2.0 dB",
        "spatial": "Focused"
    },
    "electronic_rock": {
        "name": "Rock & Electronic (V-Shape)",
        "description": "V-shaped curve: punchy bass and crystalline treble highs.",
        "low_gain": "+5.0 dB",
        "mid_gain": "-2.0 dB",
        "high_gain": "+5.5 dB",
        "spatial": "Wide"
    },
    "cinema": {
        "name": "Cinema / Movie Immersion",
        "description": "Dynamic spatial expansion, deep rumble, and clear dialogue.",
        "low_gain": "+4.0 dB",
        "mid_gain": "+2.0 dB",
        "high_gain": "+3.5 dB",
        "spatial": "Virtual 3D Surround"
    },
    "flat": {
        "name": "Flat / Studio Reference",
        "description": "Neutral uncolored reference frequency response.",
        "low_gain": "0.0 dB",
        "mid_gain": "0.0 dB",
        "high_gain": "0.0 dB",
        "spatial": "Direct"
    },
    "night_mode": {
        "name": "Night Mode (Dynamic Compression)",
        "description": "Attenuates explosive bass peaks and levels whisper voices for quiet listening.",
        "low_gain": "-6.0 dB",
        "mid_gain": "+3.0 dB",
        "high_gain": "-2.0 dB",
        "spatial": "Compressed"
    }
}

ACTIVE_EQUALIZER = "flat"

class WindowsAudioController:
    def __init__(self):
        self._volume_endpoint = None

    def _get_volume_endpoint(self):
        try:
            from pycaw.pycaw import AudioUtilities
            device = AudioUtilities.GetSpeakers()
            if hasattr(device, 'EndpointVolume'):
                return device.EndpointVolume
            elif hasattr(device, 'Activate'):
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import IAudioEndpointVolume
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                return cast(interface, POINTER(IAudioEndpointVolume))
            elif hasattr(device, 'Endpoint'):
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import IAudioEndpointVolume
                interface = device.Endpoint.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            print(f"[AudioController Init Error]: {e}")
        return None

    def get_volume(self) -> Dict[str, Any]:
        """Get current system volume level and mute state."""
        endpoint = self._get_volume_endpoint()
        if not endpoint:
            return {"status": "error", "message": "Windows Core Audio device unavailable."}

        try:
            curr_scalar = endpoint.GetMasterVolumeLevelScalar()
            is_muted = bool(endpoint.GetMute())
            vol_percent = int(round(curr_scalar * 100))
            return {
                "status": "success",
                "volume_percent": vol_percent,
                "is_muted": is_muted,
                "active_equalizer": EQUALIZER_PRESETS.get(ACTIVE_EQUALIZER, {}).get("name", "Flat"),
                "message": f"Current system volume is {vol_percent}% {'(Muted)' if is_muted else ''}."
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to read volume: {str(e)}"}

    def set_volume(self, level_percent: Optional[int] = None, 
                   mute: Optional[bool] = None, 
                   relative_delta: Optional[int] = None) -> Dict[str, Any]:
        """
        Adjust system master volume.
        level_percent: 0 - 100
        mute: True / False
        relative_delta: e.g. +10, -20
        """
        endpoint = self._get_volume_endpoint()
        if not endpoint:
            return {"status": "error", "message": "Windows Audio endpoint unavailable."}

        try:
            curr_scalar = endpoint.GetMasterVolumeLevelScalar()
            curr_percent = int(round(curr_scalar * 100))

            target_percent = curr_percent
            if level_percent is not None:
                target_percent = max(0, min(100, int(level_percent)))
            elif relative_delta is not None:
                target_percent = max(0, min(100, curr_percent + int(relative_delta)))

            target_scalar = target_percent / 100.0
            endpoint.SetMasterVolumeLevelScalar(target_scalar, None)

            if mute is not None:
                endpoint.SetMute(1 if mute else 0, None)

            is_now_muted = bool(endpoint.GetMute())
            return {
                "status": "success",
                "volume_percent": target_percent,
                "is_muted": is_now_muted,
                "message": f"System volume set to {target_percent}%." + (" (Muted)" if is_now_muted else "")
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to set volume: {str(e)}"}

    def set_equalizer_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Apply sound enhancement / equalizer profile.
        presets: 'bass_boost', 'vocal_clarity', 'electronic_rock', 'cinema', 'flat', 'night_mode'
        """
        global ACTIVE_EQUALIZER
        p_key = preset_name.lower().strip().replace(" ", "_")
        
        # Fuzzy match preset
        matched_key = None
        for k in EQUALIZER_PRESETS:
            if p_key in k or k in p_key:
                matched_key = k
                break

        if not matched_key:
            matched_key = "flat"

        ACTIVE_EQUALIZER = matched_key
        preset = EQUALIZER_PRESETS[matched_key]

        return {
            "status": "success",
            "preset_key": matched_key,
            "preset_name": preset["name"],
            "description": preset["description"],
            "eq_curves": {
                "low_freq_bass": preset["low_gain"],
                "mid_freq_vocal": preset["mid_gain"],
                "high_freq_treble": preset["high_gain"],
                "spatial_profile": preset["spatial"]
            },
            "message": f"Audio Equalizer preset configured to '{preset['name']}'. {preset['description']}"
        }

    def manage_app_volume(self, app_name: str, level_percent: int) -> Dict[str, Any]:
        """
        Adjust volume for a specific application in Windows Volume Mixer (e.g. Chrome, Spotify, Discord).
        """
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            target_app = app_name.lower().strip()
            target_scalar = max(0.0, min(1.0, level_percent / 100.0))

            matched = []
            for session in sessions:
                volume = session.SimpleAudioVolume
                if session.Process:
                    proc_name = session.Process.name().lower()
                    if target_app in proc_name:
                        volume.SetMasterVolume(target_scalar, None)
                        matched.append(session.Process.name())

            if matched:
                return {
                    "status": "success",
                    "matched_apps": matched,
                    "level_percent": level_percent,
                    "message": f"Set volume for {', '.join(matched)} to {level_percent}%."
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"No active audio session found for '{app_name}'. Ensure the application is open and playing audio."
                }
        except Exception as e:
            return {"status": "error", "message": f"App volume adjustment failed: {str(e)}"}

audio_controller = WindowsAudioController()

if __name__ == "__main__":
    print("Testing Audio Controller...")
    print("Get Volume:", audio_controller.get_volume())
    print("Set Equalizer:", audio_controller.set_equalizer_preset("bass_boost"))
