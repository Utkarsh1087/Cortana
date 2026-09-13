import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import sys
import time
from llm import get_llm_provider
from stt import get_stt_engine, MicrophoneRecorder
from tts import get_tts_engine
from wake_word import get_wake_word_detector
from memory import get_memory_manager
from tools import registry
import self_expansion

def main():
    print("=" * 65)
    print("✨ Lisa - Personal AI Voice Assistant [Stage 4: Voice + Tools] ✨")
    print("=" * 65)
    
    # 1. Initialize LLM Brain & Memory
    print("🧠 Initializing Lisa's LLM brain & memory...", end="", flush=True)
    try:
        brain = get_llm_provider()
        memory = get_memory_manager("sqlite")
        print(" Ready.")
        print(f"🔧 Loaded {len(registry.tools)} tools into Lisa's registry: {list(registry.tools.keys())}")
    except Exception as e:
        print(f"\n❌ Error initializing LLM/Memory: {e}")
        sys.exit(1)

    # 2. Initialize Text-to-Speech
    print("🔊 Initializing Text-to-Speech engine...", end="", flush=True)
    try:
        tts = get_tts_engine(engine_type="edge")
        print(" Ready.")
    except Exception as e:
        print(f"\n❌ Error initializing TTS: {e}")
        sys.exit(1)

    # 3. Initialize Speech-to-Text (Whisper)
    print("🎙️ Initializing Whisper STT engine...", end="", flush=True)
    try:
        stt = get_stt_engine(model_size="base")
        recorder = MicrophoneRecorder(sample_rate=16000, silence_duration=1.2)
        print(" Ready.")
    except Exception as e:
        print(f"\n❌ Error initializing STT: {e}")
        sys.exit(1)

    # 4. Initialize Wake Word Detector
    print("🔔 Initializing Wake Word detector...", end="", flush=True)
    try:
        wake_detector = get_wake_word_detector("adaptive")
        print(" Ready.")
    except Exception as e:
        print(f"\n❌ Error initializing Wake Word: {e}")
        wake_detector = None

    print("\n" + "=" * 65)
    print("✨ Lisa is online in Natural Conversational Mode!")
    print("✨ Speak naturally anytime (no wake word needed). Press Ctrl+C to stop.")
    print("=" * 65 + "\n")

    greeting = "Hello! I'm online and listening. How can I help you today?"
    print(f"Lisa: {greeting}\n")
    from orb_bridge import update_orb_state
    update_orb_state("speaking", energy=0.75, text=greeting)
    tts.speak(greeting)
    update_orb_state("idle", text="Lisa is listening...")

    while True:
        try:
            # Step A: Direct Natural Voice Listening with VAD
            from orb_bridge import update_orb_state
            update_orb_state("listening", energy=0.2, text="Listening...")
            audio_data = recorder.record_utterance(max_duration=14.0)
            
            if len(audio_data) == 0:
                update_orb_state("idle", text="Lisa is listening...")
                continue

            # Step B: Transcribe via Faster-Whisper
            print("⏳ Transcribing speech...", end="\r", flush=True)
            update_orb_state("thinking", energy=0.4, text="Transcribing speech...")
            transcription = stt.transcribe(audio_data)

            if not transcription or len(transcription.strip()) < 2:
                update_orb_state("idle", text="Lisa is listening...")
                continue

            print(f"You (Voice): \"{transcription}\"")
            update_orb_state("thinking", energy=0.5, text=f"Processing: \"{transcription}\"")

            # Check for exit command
            if transcription.lower().strip().rstrip(".") in ["exit", "quit", "goodbye", "bye lisa", "stop"]:
                farewell = "Goodbye! Call me whenever you need me."
                print(f"\nLisa: {farewell}\n")
                tts.speak(farewell)
                update_orb_state("idle")
                break

            # Step D: Process with LLM Brain + Memory Context + Tools
            memory.add_interaction("user", transcription)
            context = memory.get_recent_context(limit=10)
            
            print("🤔 Lisa is thinking & executing tools if needed...", end="\r", flush=True)
            raw_response = brain.generate_response(context, tool_registry=registry)
            from tts import sanitize_speech_text
            clean_response = sanitize_speech_text(raw_response)
            
            print(f"Lisa: {clean_response}\n")
            memory.add_interaction("assistant", clean_response)

            # Step E: Speak the response via TTS
            print("🔊 Speaking...", end="\r", flush=True)
            tts.speak(clean_response)
            time.sleep(0.35) # Echo-suppression: prevent mic from capturing trailing speaker audio

        except KeyboardInterrupt:
            print("\n\nLisa: Voice session closed. Have a great day!")
            from orb_bridge import update_orb_state
            update_orb_state("idle")
            break
        except Exception as e:
            print(f"\n❌ Error in voice loop: {e}\n")
            time.sleep(1)

if __name__ == "__main__":
    main()
