import os
import asyncio
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PUBLIC_CHANNEL = "@moviesbyone"
PRIVATE_CHANNEL_ID = -1003793414081

CODE_REGEX = re.compile(r"(kod|code)\s*[:\-]?\s*(\d+)", re.IGNORECASE)

WARNING_TEXT = (
    "⚠️ Diqqat!\n\n"
    "⏱ Bu kino 25 daqiqadan so‘ng avtomatik o‘chiriladi.\n"
    "📥 Iltimos, saqlab oling yoki yuklab oling."
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom!\n\n"
        "🎬 Movies in English botiga xush kelibsiz.\n\n"
        "📌 Kino kodini yuboring (masalan: 1).\n\n"
        "⚠️ Kino 25 daqiqadan so‘ng avtomatik o‘chiriladi."
    )

# ================= DELETE TIMER =================
async def delete_later(context, chat_id, message_id):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.delete_message(chat_id, message_id)
    except:
        pass

# ================= HANDLE CODE =================
async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()

    if not code.isdigit():
        return

    found_message_id = None

    async for msg in context.bot.get_chat_history(PRIVATE_CHANNEL_ID, limit=100):
        if msg.text:
            m = CODE_REGEX.search(msg.text)
            if m and m.group(2) == code:
                found_message_id = msg.message_id
                break

    if not found_message_id:
        await update.message.reply_text(
            "❌ Bunday kod topilmadi.\n"
            "👉 Kino kodini ochiq kanaldan tekshirib ko‘ring."
        )
        return

    sent = await context.bot.copy_message(
        chat_id=update.effective_chat.id,
        from_chat_id=PRIVATE_CHANNEL_ID,
        message_id=found_message_id
    )

    await update.message.reply_text(WARNING_TEXT)

    asyncio.create_task(
        delete_later(context, update.effective_chat.id, sent.message_id)
    )

# ================= RUN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    print("🎬 Movies in English bot ishga tushdi")
    app.run_polling()

if __name__ == "__main__":
    main()
