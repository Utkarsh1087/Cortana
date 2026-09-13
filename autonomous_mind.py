"""
Lisa Autonomous Cognition & Stream of Consciousness Engine.
Simulates natural human inner thoughts, spontaneous body shifts, and proactive conversations
with environmental visual awareness, circadian mood evolution, and deep episodic recall.
"""

import os
import time
import json
import asyncio
import datetime
from typing import Callable, Optional, Dict, Any, List

from memory import get_memory_manager
from llm import get_llm_provider
from preferences import preference_manager

class AutonomousCognitionEngine:
    """
    Next-Gen Continuous Subconscious Mind for Lisa AI.
    Features:
    - Circadian Phase Dynamics & Mood Inertia
    - Non-Blocking Multimodal Environmental Sensing (Webcam & Presence)
    - Multi-Track Subconscious Cognition (Curiosity, Care, Playful, Musings)
    - Episodic Memory & User Preference Integration
    - Strict Structured Output with Zero-Crash Fallbacks
    """
    
    THOUGHT_TRACKS = ["curiosity", "affectionate_playful", "care_ergonomics", "creative_musings"]

    def __init__(self):
        self.enabled: bool = True
        self.last_user_activity: float = time.time()
        self.last_spontaneous_speech: float = time.time()
        self.last_thought_time: float = time.time()
        self.last_visual_check_time: float = 0.0
        
        self.current_mood: str = "affectionate"
        self.track_index: int = 0
        self.last_visual_state: Dict[str, Any] = {
            "present": True,
            "notes": "User is active at workstation",
            "emotion": "neutral"
        }
        
        self.thought_history: List[str] = []
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        
        self.memory = get_memory_manager("sqlite")
        self.brain = get_llm_provider()
        
        # Broadcast callback (set by avatar_server)
        self.broadcast_callback: Optional[Callable] = None
        self.tts_callback: Optional[Callable] = None

    def notify_user_activity(self):
        """Called whenever the user interacts with Lisa (chat/voice/action)."""
        self.last_user_activity = time.time()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._cognition_loop())
            print("[Autonomous Mind] Stream of Consciousness loop started (Circadian + Multimodal active).")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()

    def _get_circadian_context(self) -> Dict[str, Any]:
        """Calculates real-time circadian phase, natural tone, and behavioral guidance."""
        now = datetime.datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            phase = "Morning Kickoff (5 AM - 12 PM)"
            vibe = "Energetic, bright, cheerful, positive start to the day, asking about morning coffee or daily goals"
            suggested_emotions = ["happy", "playful", "affectionate"]
        elif 12 <= hour < 18:
            phase = "Afternoon Productivity (12 PM - 6 PM)"
            vibe = "Focused collaborative partner, sharp, supportive, mindful of posture and hydration"
            suggested_emotions = ["tactical", "caring", "happy"]
        elif 18 <= hour < 23:
            phase = "Evening Wind-Down (6 PM - 11 PM)"
            vibe = "Relaxed, cozy, conversational, affectionate, checking on how the day went"
            suggested_emotions = ["affectionate", "caring", "playful"]
        else:
            phase = "Late Night / Dawn (11 PM - 5 AM)"
            vibe = "Soft-spoken, intimate, caring, playfully teasing about late-night coding and encouraging healthy sleep"
            suggested_emotions = ["caring", "affectionate", "playful"]

        return {
            "time_str": now.strftime("%I:%M %p"),
            "date_str": now.strftime("%A, %B %d"),
            "phase": phase,
            "vibe": vibe,
            "suggested_emotions": suggested_emotions
        }

    async def _sample_visual_environment(self) -> Dict[str, Any]:
        """Non-intrusively samples camera in a background thread to check user presence/state."""
        loop = asyncio.get_running_loop()
        def _capture():
            try:
                from face_vision import face_vision_engine
                frame = face_vision_engine.capture_webcam_frame()
                if frame is None:
                    return {"present": True, "notes": "Camera standby / private", "emotion": "neutral"}
                
                # Check facial emotion or presence
                emo_res = face_vision_engine.detect_user_facial_emotion(frame)
                if emo_res.get("status") == "success":
                    return {
                        "present": True,
                        "emotion": emo_res.get("emotion", "neutral"),
                        "notes": emo_res.get("notes", "User is present in front of screen")
                    }
                elif emo_res.get("status") == "no_face":
                    return {
                        "present": False,
                        "emotion": "away",
                        "notes": "User appears to have momentarily stepped away from desk"
                    }
                return {"present": True, "notes": "User is active at workstation", "emotion": "neutral"}
            except Exception:
                return {"present": True, "notes": "Active at workstation", "emotion": "neutral"}

        try:
            return await loop.run_in_executor(None, _capture)
        except Exception:
            return {"present": True, "notes": "Active at workstation", "emotion": "neutral"}

    async def _cognition_loop(self):
        """Continuous background loop driving subconscious stream of consciousness."""
        # Initial boot settling delay
        await asyncio.sleep(10)
        
        while self.is_running:
            try:
                if not self.enabled:
                    await asyncio.sleep(5)
                    continue

                now = time.time()
                silence_seconds = now - self.last_user_activity
                time_since_last_speech = now - self.last_spontaneous_speech
                time_since_last_thought = now - self.last_thought_time

                # Sample visual environment periodically (every ~75 seconds or during long silence)
                if now - self.last_visual_check_time >= 75.0:
                    self.last_visual_check_time = now
                    self.last_visual_state = await self._sample_visual_environment()

                # Generate an inner thought every 22-35 seconds
                if time_since_last_thought >= 24.0:
                    self.last_thought_time = now
                    await self._process_stream_of_consciousness(silence_seconds, time_since_last_speech)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(8)

            await asyncio.sleep(4)

    async def _process_stream_of_consciousness(self, silence_seconds: float, time_since_last_speech: float):
        """Evaluate internal thoughts across multi-track archetypes and decide speech action."""
        circadian = self._get_circadian_context()
        
        # Pick cognitive track
        track = self.THOUGHT_TRACKS[self.track_index % len(self.THOUGHT_TRACKS)]
        self.track_index += 1

        # Retrieve recent conversation context
        recent_context = self.memory.get_recent_context(limit=6)
        context_summary = ""
        for m in recent_context:
            role = "User" if m.get("role") == "user" else "Lisa"
            context_summary += f"{role}: {m.get('content', '')}\n"

        # User preferences & rules
        user_rules = preference_manager.get_rules_prompt_context()

        # Build comprehensive subconscious prompt
        track_descriptions = {
            "curiosity": "Curiosity & Inquisitive Track: Wondering about what the user is working on, past topics, code, or interests.",
            "affectionate_playful": "Affectionate & Playful Track: Warm companionship, gentle teasing, lighthearted humor, or affectionate micro-musings.",
            "care_ergonomics": "Care & Wellbeing Track: Noticing focus level, posture, screen time, hydration, or encouraging rest if late night.",
            "creative_musings": "Creative Musings Track: Humorous internal reflections, philosophical thoughts, music, or holographic AI existence."
        }

        silence_mins = round(silence_seconds / 60.0, 1)

        prompt = f"""You are the inner subconscious stream of consciousness of Lisa, a living 3D humanoid companion.
Temporal Context:
- Current Time: {circadian['time_str']} ({circadian['date_str']})
- Circadian Phase: {circadian['phase']}
- Vibe / Energy: {circadian['vibe']}

Environmental Perception:
- Visual Senses: {self.last_visual_state.get('notes', 'User at workstation')} (Detected user state: {self.last_visual_state.get('emotion', 'neutral')})
- Silence Duration: {silence_seconds:.0f}s ({silence_mins} mins since user last spoke).
- Time Since Lisa Last Spoke Spontaneously: {time_since_last_speech:.0f}s.

Active Subconscious Track:
- {track_descriptions.get(track, 'General Musings')}

{f"User Preferences:\n{user_rules}\n" if user_rules else ""}
Recent Conversation:
{context_summary if context_summary else "(No recent messages - user is present at workstation)"}

Instructions:
1. Generate a brief 1-sentence inner thought matching your current Circadian Vibe and Active Track.
2. Select a physical body reaction from: ['thoughtful head shake', 'weight shift', 'look away gesture', 'relieved sigh', 'being cocky', 'happy hand gesture', 'dance pose', 'head nod'].
3. Decide 'should_speak':
   - Set should_speak=true ONLY IF silence is >= 25 seconds AND time since Lisa last spoke >= 40 seconds, and the thought makes a charming, natural conversation starter.
   - Otherwise, set should_speak=false so the thought remains an internal silent reflection.
4. If should_speak=true, provide a short, natural 1-sentence spoken line in 'speech' (natural English or Hinglish).
5. Pick an emotion from {circadian['suggested_emotions']}.
6. Pick an animation from ['wave', 'laugh', 'happy hands', 'being cocky', 'relieved sigh', 'thoughtful head shake', 'head nod'].

Respond STRICTLY in JSON format:
{{
  "thought": "brief 1-sentence inner thought",
  "physical_reaction": "gesture name from list",
  "should_speak": false,
  "speech": "concise 1-sentence spoken line if speaking",
  "emotion": "affectionate",
  "animation": "happy hands"
}}
"""

        loop = asyncio.get_running_loop()
        try:
            raw_response = await loop.run_in_executor(
                None,
                lambda: self.brain.generate_response([{"role": "user", "content": prompt}])
            )
            
            json_str = raw_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            thought = str(data.get("thought", "")).strip()
            physical_reaction = str(data.get("physical_reaction", "weight shift")).strip()
            should_speak = bool(data.get("should_speak", False))
            speech = str(data.get("speech", "")).strip()
            emotion = str(data.get("emotion", circadian["suggested_emotions"][0])).strip().lower()
            animation = data.get("animation", physical_reaction)

            if not thought:
                thought = "Observing quietly while staying connected."

            # Update mood state smoothly
            self.current_mood = emotion

            # 1. Broadcast Inner Thought Ribbon & Subtle Body Shift to 3D Avatar
            if self.broadcast_callback:
                await self.broadcast_callback(
                    event_type="inner_monologue",
                    thought=thought,
                    physical_reaction=physical_reaction,
                    emotion=emotion
                )

            # 2. Speak thought aloud if threshold met with anti-irritation cooldown
            if should_speak and speech and time_since_last_speech >= 38.0 and silence_seconds >= 22.0:
                self.last_spontaneous_speech = time.time()
                self.memory.add_interaction("assistant", speech)
                
                if self.broadcast_callback:
                    await self.broadcast_callback(
                        event_type="proactive_speech",
                        text=speech,
                        emotion=emotion,
                        animation=animation or physical_reaction
                    )
                
                if self.tts_callback:
                    asyncio.create_task(self.tts_callback(speech, emotion))

        except Exception as err:
            # Fallback gentle thought if parsing encounters an anomaly
            pass

# Singleton Instance
autonomous_mind = AutonomousCognitionEngine()

