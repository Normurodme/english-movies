import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== SOZLAMALAR ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

# ================== KINOLAR BAZASI ==================
# ⚠️ BU YERGA KINOLARNI BOTGA YUBORIB OLGAN file_id NI QO‘YASAN
MOVIES = {
    "1": "BQACAgQAAxkBAAIBG2WhiplashFILEID",   # Whiplash (2014)
    "2": "BQACAgQAAxkBAAIBH2Movie2FILEID",
    "3": "BQACAgQAAxkBAAIBI2Movie3FILEID",
}

# ================== A'ZOLIK TEKSHIRISH ==================
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================== A'ZOLIK XABARI ==================
async def send_subscribe_message(update: Update):
    await update.message.reply_text(
        "💡 Botdan foydalanish uchun kanalga a’zo bo‘lishingiz kerak.\n\n"
        "👉 @moviesbyone kanaliga a’zo bo‘ling va qayta urinib ko‘ring."
    )

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update.effective_user.id, context):
        await send_subscribe_message(update)
        return

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "🎬 Movies in English botiga xush kelibsiz.\n\n"
        "📌 Kino kodini yuboring (masalan: 1).\n\n"
        "⚠️ Kino 25 daqiqadan so‘ng avtomatik o‘chiriladi."
    )

# ================== 25 DAQIQADAN KEYIN O‘CHIRISH ==================
async def delete_later(context, chat_id, message_id):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.delete_message(chat_id, message_id)
    except:
        pass

# ================== MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update.effective_user.id, context):
        await send_subscribe_message(update)
        return

    code = update.message.text.strip()

    if code not in MOVIES:
        await update.message.reply_text(
            "❌ Bunday kod topilmadi.\n"
            "👉 Kino kodini ochiq kanaldan tekshirib ko‘ring."
        )
        return

    # 🎬 Kinoni yuborish (FORWARD EMAS)
    sent = await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=MOVIES[code]
    )

    # ⚠️ Ogohlantirish
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=WARNING_TEXT
    )

    # ⏱ 25 daqiqadan keyin o‘chirish
    asyncio.create_task(
        delete_later(context, update.effective_chat.id, sent.message_id)
    )

# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🎬 Movies in English bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
