import os
import sys
import asyncio
from typing import List, Set
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
tts = get_tts_engine("edge")

# Proactive reminder alert callback
def on_proactive_alert(msg: str):
    asyncio.run(broadcast_state("speaking", msg))
    tts.speak(msg)

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
    """Extract [EMOTION: ...] and [ANIMATION: ...] tags from LLM output, returning clean text & metadata."""
    emotion = "affectionate"
    animation = None
    
    emotion_match = re.search(r'\[EMOTION:\s*([a-zA-Z_\-]+)\]', raw_text, re.IGNORECASE)
    if emotion_match:
        emotion = emotion_match.group(1).lower().strip()
    
    anim_match = re.search(r'\[ANIMATION:\s*([^\]]+)\]', raw_text, re.IGNORECASE)
    if anim_match:
        animation = anim_match.group(1).lower().strip()
        
    clean_text = re.sub(r'\[(EMOTION|ANIMATION):\s*[^\]]+\]', '', raw_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
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
    await websocket.send_json({
        "type": "state_change",
        "state": "idle",
        "text": "Hey there! I'm online and ready. How can I help you today?"
    })
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
    raw_response_text = await loop.run_in_executor(
        None, 
        lambda: brain.generate_response(context_messages, tool_registry=registry)
    )

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
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: tts.speak(text))
    # Return to idle after speech completes
    await broadcast_state("idle", text, emotion=emotion)

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
