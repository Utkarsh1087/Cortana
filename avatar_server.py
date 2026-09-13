import os
import sys
import random
import asyncio
from typing import List, Set, Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from llm import get_llm_provider
from memory import get_memory_manager
from tools import registry
from tts import get_tts_engine
import self_expansion
from reminder_daemon import reminder_daemon
from autonomous_mind import autonomous_mind

app = FastAPI(title="Lisa AI Avatar Server")

# Mount avatar static assets
static_dir = os.path.join(os.path.dirname(__file__), "avatar")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Connected WebSocket Clients
connected_websockets: Set[WebSocket] = set()

# Initialize Core Services
brain = get_llm_provider()
memory = get_memory_manager("sqlite")
tts = get_tts_engine("auto")

main_loop: Optional[asyncio.AbstractEventLoop] = None

# Proactive reminder alert callback
def on_proactive_alert(msg: str):
    global main_loop
    try:
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_state("speaking", msg), main_loop)
    except Exception:
        pass
    try:
        tts.speak(msg)
    except Exception:
        pass

reminder_daemon.alert_callback = on_proactive_alert
reminder_daemon.start()

# Autonomous Mind callbacks
async def on_autonomous_mind_event(event_type: str, **kwargs):
    """Broadcast inner thoughts and proactive speech to avatar clients."""
    if not connected_websockets:
        return
    
    if event_type == "inner_monologue":
        msg = {
            "type": "inner_monologue",
            "thought": kwargs.get("thought", ""),
            "gesture": kwargs.get("physical_reaction", "weight shift"),
            "emotion": kwargs.get("emotion", "affectionate")
        }
    elif event_type == "proactive_speech":
        msg = {
            "type": "state_change",
            "state": "speaking",
            "text": kwargs.get("text", ""),
            "emotion": kwargs.get("emotion", "affectionate"),
            "animation": kwargs.get("animation", "talking"),
            "energy": 0.7
        }
    else:
        msg = kwargs

    dead_sockets = []
    for ws in connected_websockets:
        try:
            await ws.send_json(msg)
        except Exception:
            dead_sockets.append(ws)
    for dead in dead_sockets:
        connected_websockets.discard(dead)

autonomous_mind.broadcast_callback = on_autonomous_mind_event

import re

def parse_llm_response_tags(raw_text: str):
    """Extract [EMOTION: ...] and [ANIMATION: ...] tags from LLM output, returning clean spoken text & metadata."""
    if not raw_text:
        return "", "affectionate", None

    emotion = "affectionate"
    animation = None
    
    # Check for [EMOTION: ...] or Emotion: ...
    emotion_match = re.search(r'\[\s*EMOTION:\s*([a-zA-Z_\-]+)\s*\]', raw_text, re.IGNORECASE)
    if not emotion_match:
        emotion_match = re.search(r'(?:^|\n|\.\s+)Emotion:\s*([a-zA-Z_\-]+)', raw_text, re.IGNORECASE)
    if emotion_match:
        emotion = emotion_match.group(1).lower().strip()
    
    # Check for [ANIMATION: ...] or Animation: ...
    anim_match = re.search(r'\[\s*ANIMATION:\s*([^\]]+)\]', raw_text, re.IGNORECASE)
    if not anim_match:
        anim_match = re.search(r'(?:^|\n|\.\s+)Animation:\s*([a-zA-Z0-9_\-\s]+?)(?:\.|$|\n)', raw_text, re.IGNORECASE)
    if anim_match:
        animation = anim_match.group(1).lower().strip()
        
    # Strip all metadata tags, actions, asterisks, and prefixes
    clean_text = re.sub(r'\[\s*(?:EMOTION|ANIMATION|ACTION|GESTURE|THOUGHT|MOOD|STAGE|POSE):?\s*[^\]]*\]', '', raw_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\[[A-Za-z0-9_\-\s]+:\s*[^\]]+\]', '', clean_text)
    clean_text = re.sub(r'(?:^|\n|\.\s+)(?:Emotion|Emotions|Animation|Animations|Gesture|Mood):\s*[a-zA-Z0-9_\-\s]+(?:\.|$|\n)', ' ', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\*[^*]+\*', '', clean_text)
    clean_text = re.sub(r'\((?:smiles|smiling|giggles|giggling|laughs|laughing|sighs|sighing|pauses|whispers|winks|nodding|shaking head)[^)]*\)', '', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Dynamic Contextual Animation Inference if LLM omitted [ANIMATION: ...]
    if not animation:
        lower = clean_text.lower()
        if any(w in lower for w in ['joke', 'haha', 'funny', 'laugh', 'giggle', 'chuckle', 'rofl', 'lmao', 'pun', 'hilarious', 'mazak', 'haso']):
            animation = "laugh"
        elif any(w in lower for w in ['hello', 'hi ', 'hey ', 'good morning', 'good evening', 'good afternoon', 'bye', 'see you', 'namaste']):
            animation = "wave"
        elif any(w in lower for w in ['thank', 'grateful', 'welcome', 'shukriya', 'dhanyawad']):
            animation = "bow"
        elif any(w in lower for w in ['yes', 'agree', 'definitely', 'sure', 'of course', 'bilkul', 'sahi']):
            animation = "head nod"
        elif any(w in lower for w in ['no ', 'never', 'disagree', 'not really', 'nahi', 'nahin']):
            animation = "shake head no"
        elif emotion in ['playful', 'happy']:
            animation = random.choice(['laugh', 'excited', 'happy hands', 'being cocky', 'talking'])
        elif emotion in ['affectionate', 'caring']:
            animation = random.choice(['happy hands', 'relieved sigh', 'talking', 'acknowledging'])
        elif emotion in ['jealous', 'angry']:
            animation = random.choice(['angry gesture', 'angry point', 'dismissing gesture'])
        else:
            animation = random.choice(['talking', 'talking 1', 'talking 2', 'talking 3', 'weight shift'])
    
    return clean_text, emotion, animation

class ChatRequest(BaseModel):
    message: str

async def broadcast_state(state: str, text: str = None, energy: float = 0.0, emotion: str = None, animation: str = None):
    """Broadcast state updates to all connected browser avatar clients."""
    if not connected_websockets:
        return
    message = {
        "type": "state_change",
        "state": state,
        "text": text,
        "energy": energy,
        "emotion": emotion,
        "animation": animation
    }
    dead_sockets = []
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            dead_sockets.append(ws)
    for dead in dead_sockets:
        connected_websockets.discard(dead)

async def bridge_sync_loop():
    """Background task continuously syncing state between terminal voice sessions & Web GUI."""
    from orb_bridge import get_orb_state
    last_timestamp = 0.0
    last_state = "idle"
    last_text = ""
    while True:
        try:
            state_data = get_orb_state()
            ts = state_data.get("timestamp", 0.0)
            state = state_data.get("state", "idle")
            emotion = state_data.get("emotion", "caring")
            energy = state_data.get("energy", 0.0)
            text = state_data.get("text", "")
            
            if ts != last_timestamp or state != last_state or text != last_text:
                last_timestamp = ts
                last_state = state
                last_text = text
                await broadcast_state(state, text=text if text else None, energy=energy, emotion=emotion)
        except Exception:
            pass
        await asyncio.sleep(0.08)

@app.on_event("startup")
async def on_startup():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(bridge_sync_loop())
    autonomous_mind.tts_callback = speak_async
    autonomous_mind.start()

@app.get("/")
async def serve_index():
    """Serve the 3D Holographic Avatar interface."""
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    # Send initial idle state
    try:
        await websocket.send_json({
            "type": "state_change",
            "state": "idle",
            "text": "Hey there! I'm online and ready. How can I help you today?"
        })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            # Reset user activity on any incoming interaction
            autonomous_mind.notify_user_activity()
    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
    except Exception:
        connected_websockets.discard(websocket)

@app.get("/api/animations")
async def get_available_animations():
    """Return all available FBX mocap animation filenames."""
    anim_dir = os.path.join(static_dir, "models", "animations")
    if not os.path.exists(anim_dir):
        return {"animations": []}
    files = [f for f in os.listdir(anim_dir) if f.lower().endswith(".fbx")]
    return {"animations": files}

@app.post("/api/autonomous_mind/toggle")
async def toggle_autonomous_mind():
    """Toggle Lisa's spontaneous inner thoughts and proactive speech."""
    autonomous_mind.set_enabled(not autonomous_mind.enabled)
    return {"enabled": autonomous_mind.enabled}

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    user_text = request.message.strip()
    if not user_text:
        return {"response": ""}

    # Reset autonomous mind silence timer
    autonomous_mind.notify_user_activity()

    # 1. State: Thinking
    await broadcast_state("thinking", f"Processing: \"{user_text}\"")

    # 2. Save User Input to Memory
    memory.add_interaction("user", user_text)
    context_messages = memory.get_recent_context(limit=10)

    # 3. Generate response via LLM + Tools
    loop = asyncio.get_running_loop()
    try:
        raw_response_text = await loop.run_in_executor(
            None, 
            lambda: brain.generate_response(context_messages, tool_registry=registry)
        )
    except Exception as e:
        print(f"[Chat Generation Warning: {e}]")
        raw_response_text = "I'm right here with you! There was a brief network hiccup, but I'm listening."

    # 4. Parse [EMOTION: ...] and [ANIMATION: ...] metadata
    clean_text, emotion, animation = parse_llm_response_tags(raw_response_text)

    # 5. Save clean Assistant response to Memory
    memory.add_interaction("assistant", clean_text)

    # 6. State: Speaking with parsed Emotion & Animation
    await broadcast_state("speaking", clean_text, energy=0.7, emotion=emotion, animation=animation)

    # 7. Trigger TTS voice speech in background
    asyncio.create_task(speak_async(clean_text, emotion=emotion))

    return {
        "response": clean_text,
        "emotion": emotion,
        "animation": animation
    }

async def speak_async(text: str, emotion: str = "affectionate"):
    """Play speech in background thread while avatar animates."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: tts.speak(text))
    except Exception:
        pass
    finally:
        # Return to idle after speech completes
        try:
            await broadcast_state("idle", text, emotion=emotion)
        except Exception:
            pass

def start_avatar_server(port: int = 8000):
    print("=" * 65)
    print("Lisa - Holographic 3D Avatar Server [Stage 6]")
    print("=" * 65)
    print(f"Holographic Web Interface running at: http://localhost:{port}")
    print(f"Features: 3D Quantum Core, Real-time Palette Switcher, Pepper's Ghost mode.")
    print("=" * 65)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    start_avatar_server()
