import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

WARNING_TEXT = "⚠️ Movie will be deleted automatically in 25 minutes.\n📥 Please download or save it."

MOVIES_FILE = "movies.json"
USERS_FILE = "users.json"
CODE_FILE = "code.txt"

# ================= LOAD =================
if os.path.exists(MOVIES_FILE):
    MOVIES = json.load(open(MOVIES_FILE))
else:
    MOVIES = {}

if os.path.exists(USERS_FILE):
    USERS = json.load(open(USERS_FILE))
else:
    USERS = []

if os.path.exists(CODE_FILE):
    NEXT_CODE = int(open(CODE_FILE).read())
else:
    NEXT_CODE = 1

SERIAL_MODE = False
SERIAL_CODE = None
SERIAL_PART = 1


def save():
    json.dump(MOVIES, open(MOVIES_FILE,"w"))
    json.dump(USERS, open(USERS_FILE,"w"))
    open(CODE_FILE,"w").write(str(NEXT_CODE))


# ================= SUB =================
async def check_subscription(uid,context):
    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL,uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False


async def send_sub(update):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies in English", url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub")]
    ])
    await update.message.reply_text(
        "💡 Botdan foydalanish uchun kanalga a’zo bo‘ling.",
        reply_markup=kb
    )


# ================= START =================
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_subscription(uid,context):
        await send_sub(update)
        return

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "📌 Kino kodini yuboring."
    )


# ================= CALLBACK =================
async def cb(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q = update.callback_query
    await q.answer()

    if q.data=="check_sub":
        if await check_subscription(q.from_user.id,context):
            await q.message.edit_text("✅ A’zolik tasdiqlandi!\n📌 Kod yuboring")
        else:
            await q.answer("A’zo emassiz",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(NEXT_CODE)
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        await q.message.edit_text("📺 Serial yuboring\n/done tugatadi")


# ================= DOWNLOAD =================
async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])
    await update.message.reply_text("Nima yuklaysiz?",reply_markup=kb)


# ================= DONE =================
async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,NEXT_CODE
    if update.effective_user.id!=ADMIN_ID:return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Serial saqlandi\nKod: {SERIAL_CODE}")
        NEXT_CODE+=1
        save()

    SERIAL_MODE=False


# ================= DELETE =================
async def delete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:return
    context.user_data["del"]=True
    await update.message.reply_text("Kod yuboring")


# ================= ADS =================
async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:return
    context.user_data["ads"]=True
    await update.message.reply_text("Reklama yuboring")


# ================= STATS =================
async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:return
    await update.message.reply_text(
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Files: {len(MOVIES)}\n"
        f"🔢 Next: {NEXT_CODE}"
    )


# ================= AUTO DELETE =================
async def autodel(context,chat,msg):
    await asyncio.sleep(1500)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass


# ================= MESSAGE =================
async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global NEXT_CODE,SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text

    # ads
    if uid==ADMIN_ID and context.user_data.get("ads"):
        context.user_data["ads"]=False
        c=0
        for u in USERS:
            try:
                await update.message.copy(u)
                c+=1
            except:pass
        await update.message.reply_text(f"Yuborildi {c}")
        return

    # delete
    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in MOVIES:
            del MOVIES[text]
            save()
            await update.message.reply_text("O‘chirildi")
        else:
            await update.message.reply_text("Topilmadi")
        return

    # upload
    if uid==ADMIN_ID and context.user_data.get("upload") and (update.message.video or update.message.document):

        if context.user_data["upload"]=="movie":
            code=str(NEXT_CODE)
            NEXT_CODE+=1
        else:
            code=f"{SERIAL_CODE}.{SERIAL_PART}"
            SERIAL_PART+=1

        sent=await context.bot.copy_message(
            chat_id=STORAGE_CHANNEL_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            caption=f"Code: {code}"
        )

        MOVIES[code]=sent.message_id
        save()

        await update.message.reply_text(f"Saqlangan\nKod: {code}")
        return


    # user request
    if not await check_subscription(uid,context):
        await send_sub(update)
        return

    if text not in MOVIES:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    sent=await context.bot.forward_message(
        chat_id=update.effective_chat.id,
        from_chat_id=STORAGE_CHANNEL_ID,
        message_id=MOVIES[text]
    )

    asyncio.create_task(autodel(context,update.effective_chat.id,sent.message_id))


# ================= RUN =================
def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL,msg))

    app.run_polling()

if __name__=="__main__":
    main()
