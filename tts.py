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
import re

def sanitize_speech_text(text: str) -> str:
    """
    Remove all metadata tags, stage directions, animation/emotion commands,
    asterisks, parentheses actions, markdown symbols, and emojis so TTS only speaks natural speech.
    """
    if not text:
        return ""
    
    clean = text
    # 1. Remove bracketed metadata e.g. [EMOTION: ...], [ANIMATION: ...], [ACTION: ...], [THOUGHT: ...]
    clean = re.sub(r'\[\s*(?:EMOTION|ANIMATION|ACTION|GESTURE|THOUGHT|MOOD|STAGE|POSE):?\s*[^\]]*\]', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\[[A-Za-z0-9_\-\s]+:\s*[^\]]+\]', '', clean)
    
    # 2. Remove loose line or prefix patterns e.g. "Emotion: happy", "Animation: wave"
    clean = re.sub(r'(?:^|\n|\.\s+)(?:Emotion|Emotions|Animation|Animations|Gesture|Mood):\s*[a-zA-Z0-9_\-\s]+(?:\.|$|\n)', ' ', clean, flags=re.IGNORECASE)
    
    # 3. Remove stage directions in asterisks e.g. *smiles warmly*, *sighs*, *giggles*, *laughs*
    clean = re.sub(r'\*[^*]+\*', '', clean)
    
    # 4. Remove stage directions in parentheses e.g. (smiles), (giggling softly), (sighs)
    clean = re.sub(r'\((?:smiles|smiling|giggles|giggling|laughs|laughing|sighs|sighing|pauses|whispers|winks|nodding|shaking head)[^)]*\)', '', clean, flags=re.IGNORECASE)
    
    # 5. Remove markdown syntax like **, __, #, >, `
    clean = re.sub(r'[*_#>`~]', '', clean)
    
    # 6. Remove URLs
    clean = re.sub(r'https?://\S+', '', clean)
    
    # 7. Remove emojis so TTS does not pronounce emoji descriptions
    clean = re.sub(r'[\U00010000-\U0010ffff]', '', clean)
    clean = re.sub(r'[\u2600-\u27BF\uE000-\uF8FF]', '', clean)
    
    # 8. Normalize multiple spaces/newlines
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

# Global Speech Mutex Lock to prevent overlapping/clashing voices
_speech_lock = threading.Lock()
_is_speaking = False

def _sapi_female_speak(text: str) -> None:
    """Offline Windows fallback strictly using female voices (e.g. Zira)."""
    clean_text = sanitize_speech_text(text)
    if not clean_text:
        return
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        for voice in speaker.GetVoices():
            desc = voice.GetDescription().lower()
            if any(name in desc for name in ["zira", "female", "eva", "hazel", "susan", "catherine", "heera"]):
                speaker.Voice = voice
                break
        speaker.Speak(clean_text)
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
        clean_text = sanitize_speech_text(text)
        if not clean_text:
            return
            
        with _speech_lock:
            _is_speaking = True
            self.stop() # Immediately cancel any lingering audio
            rate_val = rate or "+0%"
            pitch_val = pitch or "+0Hz"

        # Broadcast speaking state to live desktop orb and web avatar
        try:
            from orb_bridge import update_orb_state
            update_orb_state("speaking", energy=0.75, text=clean_text)
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
                        clean_text,
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
                    _sapi_female_speak(clean_text)
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
            _sapi_female_speak(clean_text)
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
    ElevenLabs High-Definition Neural TTS engine with automatic fallback.
    Uses ultra-fast, low-credit eleven_flash_v2_5.
    """
    def __init__(self, api_key: str = None, voice_id: str = None, model_id: str = "eleven_flash_v2_5"):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        # Default: Rachel (21m00Tcm4TlvDq8ikWAM) or Sarah (EXAVITQu4vr4xnSDxMaL)
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"
        self.model_id = model_id # Flash v2.5 consumes 50% fewer credits with ultra-low latency
        self._edge_fallback = EdgeTTS()
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
        clean_text = sanitize_speech_text(text)
        if not clean_text:
            return

        if not self.api_key or self.api_key.startswith("your_"):
            self._edge_fallback.speak(clean_text, rate=rate, pitch=pitch)
            return

        try:
            from elevenlabs.client import ElevenLabs
            import io

            client = ElevenLabs(api_key=self.api_key)
            audio = client.generate(
                text=clean_text,
                voice=self.voice_id,
                model=self.model_id
            )
            
            audio_bytes = b"".join(audio)
            audio_file = io.BytesIO(audio_bytes)
            
            with _speech_lock:
                self.stop()
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
        except Exception as e:
            # On any credit exhaustion or network error, fallback seamlessly to EdgeTTS
            self._edge_fallback.speak(clean_text, rate=rate, pitch=pitch)


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


def get_tts_engine(engine_type: str = "auto") -> BaseTTS:
    """Factory function to get configured TTS engine (auto detects ElevenLabs key)."""
    t = engine_type.lower().strip()
    if t == "auto":
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if api_key and not api_key.startswith("your_"):
            return ElevenLabsTTS(api_key=api_key)
        return EdgeTTS()
    elif t == "elevenlabs":
        return ElevenLabsTTS()
    elif t == "edge":
        return EdgeTTS()
    else:
        return EdgeTTS()

