import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import asyncio
import tempfile
import pygame
from abc import ABC, abstractmethod
from typing import Dict, Optional

FEMALE_VOICES: Dict[str, str] = {
    "jenny": "en-US-JennyNeural",     # US Warm Natural Companion (Default)
    "aria": "en-US-AriaNeural",       # US Energetic & Expressive
    "sonia": "en-GB-SoniaNeural",     # British Sleek Modern
    "natasha": "en-AU-NatashaNeural", # Australian Crisp
    "neerja": "en-IN-NeerjaNeural",   # Indian English Expressive
}

# Current global active voice
ACTIVE_VOICE = "en-US-JennyNeural"

# Emotion vocal modulation presets
EMOTION_PROFILES = {
    "calm": {"rate": "-8%", "pitch": "-2Hz"},
    "soothing": {"rate": "-12%", "pitch": "-4Hz"},
    "energetic": {"rate": "+15%", "pitch": "+4Hz"},
    "cheerful": {"rate": "+8%", "pitch": "+6Hz"},
    "focused": {"rate": "+5%", "pitch": "+0Hz"},
    "neutral": {"rate": "+0%", "pitch": "+0Hz"}
}

import threading

# Global Speech Mutex Lock to prevent overlapping/clashing voices
_speech_lock = threading.Lock()
_is_speaking = False

def _sapi_female_speak(text: str) -> None:
    """Offline Windows fallback strictly using female voices (e.g. Zira)."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        for voice in speaker.GetVoices():
            desc = voice.GetDescription().lower()
            if any(name in desc for name in ["zira", "female", "eva", "hazel", "susan", "catherine", "heera"]):
                speaker.Voice = voice
                break
        speaker.Speak(text)
    except Exception:
        pass


class BaseTTS(ABC):
    """Abstract base class for Text-to-Speech engines."""
    
    @abstractmethod
    def speak(self, text: str, rate: Optional[str] = None, pitch: Optional[str] = None) -> None:
        """Convert text to speech and play audio through speakers."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Immediately stop currently playing speech."""
        pass


class EdgeTTS(BaseTTS):
    """
    High-quality Neural Text-to-Speech using Edge TTS with strictly female neural voices
    and dynamic emotion/sentiment pitch and rate modulation.
    """
    def __init__(self, voice: str = None):
        global ACTIVE_VOICE
        self.voice = voice or ACTIVE_VOICE
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            pass

    def speak(self, text: str, rate: Optional[str] = None, pitch: Optional[str] = None) -> None:
        global ACTIVE_VOICE, _is_speaking
        if not text.strip():
            return
            
        with _speech_lock:
            _is_speaking = True
            self.stop() # Immediately cancel any lingering audio
            rate_val = rate or "+0%"
            pitch_val = pitch or "+0Hz"

        # Broadcast speaking state to live desktop orb and web avatar
        try:
            from orb_bridge import update_orb_state
            update_orb_state("speaking", energy=0.75, text=text)
        except Exception:
            pass

        async def _generate_and_play():
            import edge_tts
            temp_filename = None

            for attempt in range(2):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        temp_filename = f.name

                    voice_to_use = ACTIVE_VOICE
                    communicate = edge_tts.Communicate(
                        text,
                        voice_to_use,
                        rate=rate_val,
                        pitch=pitch_val
                    )
                    await communicate.save(temp_filename)
                    
                    # Play audio using pygame
                    pygame.mixer.music.load(temp_filename)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        await asyncio.sleep(0.05)
                    return # Successfully played
                except Exception:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    # On repeated network timeout, use offline female Windows SAPI fallback
                    _sapi_female_speak(text)
                    return
                finally:
                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                    if temp_filename and os.path.exists(temp_filename):
                        try:
                            os.remove(temp_filename)
                        except Exception:
                            pass

        try:
            asyncio.run(_generate_and_play())
        except Exception:
            _sapi_female_speak(text)
        finally:
            _is_speaking = False
            try:
                from orb_bridge import update_orb_state
                update_orb_state("idle")
            except Exception:
                pass

    def stop(self) -> None:
        """Immediately stop playback."""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass

    def speak_with_emotion(self, text: str, emotion: str = "neutral") -> None:
        """Modulate vocal rate and pitch based on detected emotion."""
        profile = EMOTION_PROFILES.get(emotion.lower(), EMOTION_PROFILES["neutral"])
        self.speak(text, rate=profile["rate"], pitch=profile["pitch"])


class ElevenLabsTTS(BaseTTS):
    """
    ElevenLabs TTS engine implementation (swappable).
    """
    def __init__(self, api_key: str = None, voice_id: str = "21m00Tcm4TlvDq8ikWAM"): # Rachel / Female
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            pass

    def stop(self) -> None:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass

    def speak(self, text: str, rate: Optional[str] = None, pitch: Optional[str] = None) -> None:
        if not self.api_key or self.api_key == "your_elevenlabs_api_key_here":
            # Fallback to EdgeTTS
            EdgeTTS().speak(text, rate=rate, pitch=pitch)
            return

        from elevenlabs.client import ElevenLabs
        import io

        client = ElevenLabs(api_key=self.api_key)
        audio = client.generate(
            text=text,
            voice=self.voice_id,
            model="eleven_monolingual_v1"
        )
        
        audio_bytes = b"".join(audio)
        audio_file = io.BytesIO(audio_bytes)
        
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)


def set_active_female_voice(preset_name: str) -> str:
    """Set the active female voice preset."""
    global ACTIVE_VOICE
    name = preset_name.lower().strip()
    if name in FEMALE_VOICES:
        ACTIVE_VOICE = FEMALE_VOICES[name]
        return ACTIVE_VOICE
    for k, v in FEMALE_VOICES.items():
        if name in k or name in v.lower():
            ACTIVE_VOICE = v
            return ACTIVE_VOICE
    return ACTIVE_VOICE


def get_tts_engine(engine_type: str = "edge") -> BaseTTS:
    """Factory function to get configured TTS engine."""
    if engine_type.lower() == "edge":
        return EdgeTTS()
    elif engine_type.lower() == "elevenlabs":
        return ElevenLabsTTS()
    else:
        raise ValueError(f"Unsupported TTS engine_type: {engine_type}")
