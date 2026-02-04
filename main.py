import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== SOZLAMALAR ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PUBLIC_CHANNEL = "@moviesbyone"          # ochiq kanal
PRIVATE_CHANNEL_ID = -1003793414081       # ⚠️ YOPIQ KANAL ID (ALMASHTIR!)

DELETE_AFTER = 25 * 60  # 25 daqiqa

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies in English", url="https://t.me/moviesbyone")]
    ])

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "🎥 **Movies in English** botiga xush kelibsiz.\n\n"
        "📌 Kino kodini yuboring (masalan: 1024).\n\n"
        "⚠️ Kino 25 daqiqadan so‘ng avtomatik o‘chiriladi.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ================== KINO KOD QABUL QILISH ==================
async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        await update.message.reply_text("❌ Iltimos, faqat kino kodini yuboring.")
        return

    code = update.message.text

    try:
        msg = await context.bot.forward_message(
            chat_id=update.message.chat_id,
            from_chat_id=PRIVATE_CHANNEL_ID,
            message_id=int(code)
        )

        await update.message.reply_text(
            "⚠️ Diqqat!\n\n"
            "🕒 Bu kino **25 daqiqadan so‘ng avtomatik o‘chiriladi**.\n"
            "📥 Iltimos, saqlab oling yoki yuklab oling."
        )

        # ===== AUTO DELETE =====
        async def auto_delete():
            await asyncio.sleep(DELETE_AFTER)
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=msg.message_id
                )
            except:
                pass

        asyncio.create_task(auto_delete())

    except:
        await update.message.reply_text(
            "❌ Bunday kod topilmadi.\n"
            "👉 Kino kodini ochiq kanaldan tekshirib ko‘ring."
        )

# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))

    print("🎬 Movies in English bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
