"""
Telegram Anywhere Voice Sync for Lisa AI
Enables complete smartphone-to-PC assistant control via Telegram voice notes and text.
"""

import os
import io
import tempfile
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

from llm import get_llm_provider
from tools import registry
from memory import get_memory_manager
import self_expansion

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
memory = get_memory_manager("sqlite")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_msg = (
        "✨ *Lisa Voice Assistant Online* ✨\n\n"
        "I am synced to your main computer, Utkarsh!\n"
        "• Send me any *text message* or *voice note*.\n"
        "• I will execute PC tools, screen vision, coding, timers, and reply with my voice!"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages from Telegram."""
    user_text = update.message.text
    if not user_text:
        return

    # Typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    provider = get_llm_provider()
    history = memory.get_recent_context(limit=6)
    history.append({"role": "user", "content": user_text})

    response = provider.generate_response(history, tool_registry=registry)
    memory.add_interaction("user", user_text)
    memory.add_interaction("assistant", response)

    await update.message.reply_text(response)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice notes from Telegram: Transcribe with Whisper -> Process -> Reply with Voice."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

    # Download voice note (.ogg format)
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
        ogg_path = tf.name
    await voice_file.download_to_drive(ogg_path)

    try:
        # 1. Transcribe with local Faster-Whisper
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(ogg_path, beam_size=2)
        transcription = " ".join([s.text for s in segments]).strip()

        if not transcription:
            await update.message.reply_text("I couldn't clearly hear that voice note, Utkarsh. Could you try again?")
            return

        # 2. Process with LLM Brain + Tools
        provider = get_llm_provider()
        history = memory.get_recent_context(limit=6)
        history.append({"role": "user", "content": transcription})
        response = provider.generate_response(history, tool_registry=registry)
        memory.add_interaction("user", transcription)
        memory.add_interaction("assistant", response)

        # 3. Generate EdgeTTS voice response (.mp3)
        import edge_tts
        from tts import ACTIVE_VOICE
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as af:
            audio_response_path = af.name

        communicate = edge_tts.Communicate(response, ACTIVE_VOICE)
        await communicate.save(audio_response_path)

        # 4. Reply with Voice Note + Text
        with open(audio_response_path, "rb") as voice_data:
            await update.message.reply_voice(voice=voice_data, caption=f"🗣️ *You said:* \"{transcription}\"\n\n💬 {response}", parse_mode="Markdown")

        if os.path.exists(audio_response_path):
            os.remove(audio_response_path)

    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)


def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n⚠️ [Lisa Telegram Sync]: Set TELEGRAM_BOT_TOKEN in .env to activate smartphone sync.")
        return

    print("🤖 [Lisa Telegram Bot]: Connecting to Telegram...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    print("✓ [Lisa Telegram Bot]: Listening for smartphone voice notes and messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
