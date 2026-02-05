import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================== SOZLAMALAR ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"     # majburiy a'zolik kanali
PRIVATE_CHANNEL_ID = -1003793414081   # yopiq kanal ID

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

# ================== A'ZOLIK TEKSHIRISH ==================
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================== A'ZOLIK XABARI ==================
async def send_subscribe_message(update: Update):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies in English", url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub")]
    ])

    await update.message.reply_text(
        "💡 Botdan foydalanish uchun kanalga a’zo bo‘lishingiz kerak.\n\n"
        "👉 A’zo bo‘lib, Tasdiqlash tugmasini bosing.",
        reply_markup=keyboard
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

# ================== CALLBACK ==================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_sub":
        if await check_subscription(query.from_user.id, context):
            await query.message.edit_text(
                "✅ A’zolik tasdiqlandi!\n\n📌 Kino kodini yuboring."
            )
        else:
            await query.answer("❌ Kanalga a’zo emassiz!", show_alert=True)

# ================== KINO QIDIRISH ==================
async def find_movie_by_code(code, context):
    async for msg in context.bot.get_chat_history(PRIVATE_CHANNEL_ID, limit=300):
        if msg.caption and f"Kod - {code}" in msg.caption:
            return msg.message_id
        if msg.text and f"Kod - {code}" in msg.text:
            return msg.message_id
    return None

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

    if not code.isdigit():
        await update.message.reply_text(
            "❌ Noto‘g‘ri format.\n👉 Faqat kino kodini yuboring (masalan: 1)."
        )
        return

    movie_message_id = await find_movie_by_code(code, context)

    if not movie_message_id:
        await update.message.reply_text(
            "❌ Bunday kod topilmadi.\n"
            "👉 Kino kodini ochiq kanaldan tekshirib ko‘ring."
        )
        return

    # Forward EMAS, COPY — kanal nomi ko‘rinmaydi
    sent = await context.bot.copy_message(
        chat_id=update.effective_chat.id,
        from_chat_id=PRIVATE_CHANNEL_ID,
        message_id=movie_message_id
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=WARNING_TEXT
    )

    # 25 daqiqadan keyin avtomatik o‘chirish
    asyncio.create_task(
        delete_later(context, update.effective_chat.id, sent.message_id)
    )

# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🎬 Movies in English bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
