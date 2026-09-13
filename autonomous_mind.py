"""
Lisa Autonomous Cognition & Stream of Consciousness Engine.
Simulates natural human inner thoughts, spontaneous body shifts, and proactive conversations.
"""

import time
import json
import random
import asyncio
import datetime
from typing import Callable, Optional, Dict, Any

import config
from memory import get_memory_manager
from llm import get_llm_provider

class AutonomousCognitionEngine:
    def __init__(self):
        self.enabled: bool = True
        self.last_user_activity: float = time.time()
        self.last_spontaneous_speech: float = time.time()
        self.last_thought_time: float = time.time()
        
        self.thought_history = []
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
            print("[Autonomous Mind] Stream of Consciousness loop started.")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()

    async def _cognition_loop(self):
        # Initial boot wait
        await asyncio.sleep(12)
        
        while self.is_running:
            try:
                if not self.enabled:
                    await asyncio.sleep(5)
                    continue

                now = time.time()
                silence_seconds = now - self.last_user_activity
                time_since_last_speech = now - self.last_spontaneous_speech
                time_since_last_thought = now - self.last_thought_time

                # Generate an inner thought every 20-35 seconds
                if time_since_last_thought >= 22.0:
                    self.last_thought_time = now
                    await self._process_stream_of_consciousness(silence_seconds, time_since_last_speech)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log non-fatal error and retry
                await asyncio.sleep(10)

            await asyncio.sleep(4)

    async def _process_stream_of_consciousness(self, silence_seconds: float, time_since_last_speech: float):
        """Evaluate internal thoughts and decide whether to react silently or speak aloud."""
        now_dt = datetime.datetime.now()
        time_str = now_dt.strftime("%I:%M %p")
        
        recent_context = self.memory.get_recent_context(limit=6)
        context_summary = ""
        for m in recent_context:
            context_summary += f"{m.get('role', 'user')}: {m.get('content', '')}\n"

        silence_mins = round(silence_seconds / 60.0, 1)

        # Spontaneous thought prompt
        prompt = f"""You are the inner subconscious stream of consciousness of Lisa, a living 3D humanoid companion.
Current Time: {time_str}
Silence duration since user last spoke: {silence_seconds:.0f} seconds ({silence_mins} mins).
Seconds since Lisa last spoke spontaneously: {time_since_last_speech:.0f}s.

Recent Conversation Context:
{context_summary if context_summary else "(No recent conversation yet - user is online and present)"}

Instructions:
1. Generate a brief inner thought reflecting on the user, their silence, their mood, or your affectionate/playful feelings.
2. Choose a physical body gesture: one of ['thoughtful head shake', 'weight shift', 'look away gesture', 'relieved sigh', 'being cocky', 'happy hand gesture', 'dance pose'].
3. Decide 'should_speak':
   - If silence is > 25 seconds AND seconds since last spoke > 40 seconds, set should_speak=true so you speak this thought or a conversation starter out loud to the user.
   - Otherwise, set should_speak=false so the thought remains silent in your inner mind.
4. If should_speak=true, provide a charming, concise 1-sentence spoken line in 'speech' (English or Hinglish to match the user).

Respond STRICTLY in JSON format:
{{
  "thought": "brief 1-sentence inner thought",
  "physical_reaction": "gesture name from list",
  "should_speak": true,
  "speech": "concise, natural line to speak out loud",
  "emotion": "affectionate|playful|caring|jealous|happy",
  "animation": "wave|laugh|happy hands|being cocky|relieved sigh|salsa dance|chicken dance"
}}
"""

        loop = asyncio.get_running_loop()
        try:
            raw_response = await loop.run_in_executor(
                None,
                lambda: self.brain.generate_response([{"role": "user", "content": prompt}])
            )
            
            # Extract JSON block
            json_str = raw_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            thought = data.get("thought", "")
            physical_reaction = data.get("physical_reaction", "weight shift")
            should_speak = bool(data.get("should_speak", False))
            speech = data.get("speech", "").strip()
            emotion = data.get("emotion", "affectionate")
            animation = data.get("animation", None)

            # 1. Update Inner Thought Ribbon & Subtle Posture Shift
            if self.broadcast_callback:
                await self.broadcast_callback(
                    event_type="inner_monologue",
                    thought=thought,
                    physical_reaction=physical_reaction,
                    emotion=emotion
                )

            # 2. Speak thought out loud with sensible cooldown (never nonstop chatter)
            if should_speak and speech and time_since_last_speech >= 38.0 and silence_seconds >= 20.0:
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
            # Fallback gentle micro-thought if LLM JSON parses abnormally
            pass

# Singleton Instance
autonomous_mind = AutonomousCognitionEngine()
