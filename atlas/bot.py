"""
bot.py — Telegram entrypoint.

Deliberately thin: this file only knows about Telegram's API. It hands every
text message straight to ai_engine.handle_turn() and lets the model decide
what happens next. No slash commands are registered on purpose.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

import ai_engine
import memory

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    memory.get_or_create_user(user.id, user.first_name or "")

    # --- Onboarding stub -------------------------------------------------
    # TODO: on a brand-new user (facts_json == '{}' and onboarded == 0),
    # branch into a short conversational onboarding instead of going
    # straight to ai_engine.handle_turn(). Ask 1-2 light questions
    # (e.g. what they're using Atlas for, a couple tickers they follow),
    # save them with memory.save_fact(), then memory.mark_onboarded(user.id).
    # -----------------------------------------------------------------------

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = ai_engine.handle_turn(user.id, update.message.text)
    await update.message.reply_text(reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: wire up tools.transcribe_voice.
    # file = await update.message.voice.get_file()
    # audio_bytes = await file.download_as_bytearray()
    # text = tools.transcribe_voice(bytes(audio_bytes), ai_engine.client)
    # reply = ai_engine.handle_turn(update.effective_user.id, text)
    # await update.message.reply_text(reply)
    await update.message.reply_text(
        "Voice notes aren't wired up yet — type it out for now and I'll get to it."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # TODO: wire up tools.extract_pdf_text for PDFs, then feed the extracted
    # text into ai_engine.handle_turn() as context so the user can ask
    # questions about the document.
    await update.message.reply_text(
        "I can't read documents yet — that's next on the list. Hang tight."
    )


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    memory.init_db()

    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("Atlas is running.")

    port = int(os.environ.get("PORT", 8443))
    external_url = os.environ["RENDER_EXTERNAL_URL"]
    webhook_path = token

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=webhook_path,
        webhook_url=f"{external_url}/{webhook_path}",
    )


if __name__ == "__main__":
    main()
