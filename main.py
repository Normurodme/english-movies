import os
import json
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
ADMIN_ID = 6220077209

STORAGE_CHANNEL_ID = -1003793414081

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

MOVIES_FILE = "movies.json"
CODE_FILE = "next_code.txt"
USERS_FILE = "users.json"

# ================== BAZANI YUKLASH ==================
if os.path.exists(MOVIES_FILE):
    with open(MOVIES_FILE, "r") as f:
        MOVIES = json.load(f)
else:
    MOVIES = {}

if os.path.exists(CODE_FILE):
    with open(CODE_FILE, "r") as f:
        NEXT_CODE = int(f.read())
else:
    NEXT_CODE = 1

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        USERS = json.load(f)
else:
    USERS = []

def save_db():
    with open(MOVIES_FILE, "w") as f:
        json.dump(MOVIES, f)
    with open(CODE_FILE, "w") as f:
        f.write(str(NEXT_CODE))
    with open(USERS_FILE, "w") as f:
        json.dump(USERS, f)

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
    user_id = update.effective_user.id

    if user_id not in USERS:
        USERS.append(user_id)
        save_db()

    if not await check_subscription(user_id, context):
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

# ================== /download ==================
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["awaiting_movie"] = True
    await update.message.reply_text(
        "🎬 Kino yuboring.\n\n"
        "📌 Video ostiga avtomatik kod beriladi."
    )

# ================== /delete ==================
async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["awaiting_delete"] = True
    await update.message.reply_text(
        "🗑 Qaysi kino o‘chiriladi?\n\n📌 Kino kodini yuboring."
    )

# ================== /ads ==================
async def ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["awaiting_ads"] = True
    await update.message.reply_text("📢 Reklama xabarini yuboring.")

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

    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else None

    # ===== ADS SEND =====
    if user_id == ADMIN_ID and context.user_data.get("awaiting_ads"):
        context.user_data["awaiting_ads"] = False

        sent_count = 0
        for uid in USERS:
            try:
                await update.message.copy(uid)
                sent_count += 1
            except:
                pass

        await update.message.reply_text(f"✅ Reklama yuborildi: {sent_count} ta foydalanuvchi.")
        return

    # ===== DELETE =====
    if user_id == ADMIN_ID and context.user_data.get("awaiting_delete"):
        if text in MOVIES:
            del MOVIES[text]
            save_db()
            await update.message.reply_text(f"🗑 Kino {text} o‘chirildi.")
        else:
            await update.message.reply_text("❌ Bunday kod topilmadi.")
        context.user_data["awaiting_delete"] = False
        return

    # ===== ADD MOVIE =====
    if (
        user_id == ADMIN_ID
        and context.user_data.get("awaiting_movie")
        and (update.message.video or update.message.document)
    ):
        file = update.message.video or update.message.document

        sent_channel = await context.bot.copy_message(
            chat_id=STORAGE_CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )

        code = str(NEXT_CODE)
        MOVIES[code] = sent_channel.message_id
        NEXT_CODE += 1
        save_db()

        await update.message.reply_text(
            f"✅ Kino saqlandi!\n\n📌 Kod: {code}"
        )

        context.user_data["awaiting_movie"] = False
        return

    # ===== USER =====
    if not await check_subscription(user_id, context):
        await send_subscribe_message(update)
        return

    if not text or text not in MOVIES:
        await update.message.reply_text(
            "❌ Bunday kod topilmadi.\n"
            "👉 Kino kodini ochiq kanaldan tekshirib ko‘ring."
        )
        return

    sent = await context.bot.copy_message(
        chat_id=update.effective_chat.id,
        from_chat_id=STORAGE_CHANNEL_ID,
        message_id=MOVIES[text]
    )

    await context.bot.edit_message_caption(
        chat_id=update.effective_chat.id,
        message_id=sent.message_id,
        caption=WARNING_TEXT
    )

    asyncio.create_task(
        delete_later(context, update.effective_chat.id, sent.message_id)
    )

# ================== RUN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("ads", ads))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("🎬 Movies in English bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
