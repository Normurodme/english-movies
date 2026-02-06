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

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209   # ✅ ANIQ ADMIN ID

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

# Kino bazasi (RAM)
MOVIES = {}
NEXT_CODE = 1

# ================== A'ZOLIK ==================
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

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

# ================== /download (ADMIN) ==================
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["awaiting_movie"] = True
    await update.message.reply_text(
        "🎬 Kino yuboring.\n\n"
        "📌 Video ostiga avtomatik kod beriladi."
    )

# ================== 25 DAQIQA O‘CHIRISH ==================
async def delete_later(context, chat_id, message_id):
    await asyncio.sleep(25 * 60)
    try:
        await context.bot.delete_message(chat_id, message_id)
    except:
        pass

# ================== MESSAGE ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global NEXT_CODE

    # ===== ADMIN KINO QO‘SHISH =====
    if (
        update.effective_user.id == ADMIN_ID
        and context.user_data.get("awaiting_movie")
        and (update.message.video or update.message.document)
    ):
        file = update.message.video or update.message.document
        file_id = file.file_id

        code = str(NEXT_CODE)
        MOVIES[code] = file_id
        NEXT_CODE += 1

        await update.message.reply_text(
            f"✅ Kino saqlandi!\n\n📌 Kod: {code}"
        )

        context.user_data["awaiting_movie"] = False
        return

    # ===== FOYDALANUVCHI =====
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

    sent = await context.bot.send_video(
        chat_id=update.effective_chat.id,
        video=MOVIES[code]
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=WARNING_TEXT
    )

    asyncio.create_task(
        delete_later(context, update.effective_chat.id, sent.message_id)
    )

# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("🎬 Movies in English bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
