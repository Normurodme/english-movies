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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

USERS_FILE = "users.json"

SERIAL_MODE = False
SERIAL_PREFIX = None
SERIAL_COUNT = 1


# ================= USERS LOAD =================
if os.path.exists(USERS_FILE):
    with open(USERS_FILE) as f:
        USERS = json.load(f)
else:
    USERS = []


def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(USERS, f)


# ================= SUB CHECK =================
async def check_subscription(user_id, context):
    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False


async def send_subscribe(update):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Join Channel", url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Check", callback_data="check")]
    ])
    await update.message.reply_text("Join channel first", reply_markup=kb)


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save_users()

    if not await check_subscription(uid, context):
        await send_subscribe(update)
        return

    await update.message.reply_text("🎬 Send movie code.")


# ================= CALLBACK =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE, SERIAL_PREFIX, SERIAL_COUNT

    q = update.callback_query
    await q.answer()

    if q.data == "check":
        if await check_subscription(q.from_user.id, context):
            await q.message.edit_text("✅ Verified\nSend code")
        else:
            await q.answer("Join channel first", show_alert=True)

    if q.data == "movie":
        context.user_data["upload"] = "movie"
        await q.message.edit_text("Send movie file")

    if q.data == "serial":
        SERIAL_MODE = True
        SERIAL_PREFIX = None
        SERIAL_COUNT = 1
        context.user_data["upload"] = "serial"
        await q.message.edit_text("Send episodes\n/done to finish")


# ================= DOWNLOAD MENU =================
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Movie", callback_data="movie"),
        InlineKeyboardButton("📺 Serial", callback_data="serial")
    ]])

    await update.message.reply_text("Choose type", reply_markup=kb)


# ================= DONE SERIAL =================
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE
    if update.effective_user.id != ADMIN_ID:
        return

    SERIAL_MODE = False
    await update.message.reply_text("✅ Serial finished")


# ================= DELETE POST =================
async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["delete"] = True
    await update.message.reply_text("Send message_id to delete")


# ================= ADS =================
async def ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    context.user_data["ads"] = True
    await update.message.reply_text("Send broadcast message")


# ================= STATS =================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"Users: {len(USERS)}"
    )


# ================= AUTO DELETE =================
async def autodel(context, chat_id, msg_id):
    await asyncio.sleep(1500)
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass


# ================= MAIN HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SERIAL_PREFIX, SERIAL_COUNT

    uid = update.effective_user.id
    text = update.message.text

    # ADS SEND
    if uid == ADMIN_ID and context.user_data.get("ads"):
        context.user_data["ads"] = False
        sent = 0
        for u in USERS:
            try:
                await update.message.copy(u)
                sent += 1
            except:
                pass
        await update.message.reply_text(f"Sent: {sent}")
        return

    # DELETE POST
    if uid == ADMIN_ID and context.user_data.get("delete"):
        context.user_data["delete"] = False
        try:
            await context.bot.delete_message(STORAGE_CHANNEL_ID, int(text))
            await update.message.reply_text("Deleted")
        except:
            await update.message.reply_text("Error")
        return

    # UPLOAD
    if uid == ADMIN_ID and context.user_data.get("upload"):
        if update.message.video or update.message.document:

            sent = await context.bot.copy_message(
                STORAGE_CHANNEL_ID,
                update.effective_chat.id,
                update.message.message_id
            )

            if context.user_data["upload"] == "serial":
                if not SERIAL_PREFIX:
                    SERIAL_PREFIX = sent.message_id
                code = f"{SERIAL_PREFIX}.{SERIAL_COUNT}"
                SERIAL_COUNT += 1
            else:
                code = str(sent.message_id)

            await context.bot.edit_message_caption(
                STORAGE_CHANNEL_ID,
                sent.message_id,
                caption=f"Code: {code}"
            )

            await update.message.reply_text(f"Saved\nCode: {code}")
        return

    # USER REQUEST
    if not await check_subscription(uid, context):
        await send_subscribe(update)
        return

    if not text:
        return

    # parse code
    try:
        msg_id = int(text.split(".")[0])
    except:
        await update.message.reply_text("Invalid code")
        return

    try:
        sent = await context.bot.forward_message(
            uid,
            STORAGE_CHANNEL_ID,
            msg_id
        )

        asyncio.create_task(autodel(context, uid, sent.message_id))

    except:
        await update.message.reply_text("Code not found")


# ================= RUN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("ads", ads))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL, handle))

    print("BOT RUNNING")
    app.run_polling()


if __name__ == "__main__":
    main()
