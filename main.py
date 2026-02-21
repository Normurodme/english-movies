import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

DB_FILE = "db.json"
USERS_FILE = "users.json"

# ================= LOAD =================

if os.path.exists(DB_FILE):
    DB = json.load(open(DB_FILE))
else:
    DB = {"movies":{}, "next":1}

if os.path.exists(USERS_FILE):
    USERS = json.load(open(USERS_FILE))
else:
    USERS = []

SERIAL_MODE = False
SERIAL_CODE = None
SERIAL_PART = 1

def save():
    json.dump(DB, open(DB_FILE,"w"))
    json.dump(USERS, open(USERS_FILE,"w"))

# ================= SUB CHECK =================

async def check_sub(user_id, context):
    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies in English", url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="check")]
    ])
    await update.message.reply_text(
        "💡 Botdan foydalanish uchun kanalga a’zo bo‘ling.",
        reply_markup=kb
    )

# ================= START =================

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "🎬 Movies in English botiga xush kelibsiz.\n\n"
        "📌 Kino kodini yuboring."
    )

# ================= CALLBACK =================

async def callbacks(update:Update, context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q = update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ A’zolik tasdiqlandi!\n📌 Kod yuboring.")
        else:
            await q.answer("❌ Kanalga a’zo bo‘ling",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        await q.message.edit_text("📺 Serial yuboring\nTugatish: /done")

# ================= DOWNLOAD =================

async def download(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Kino",callback_data="movie"),
        InlineKeyboardButton("📺 Serial",callback_data="serial")
    ]])

    await update.message.reply_text("Nimani yuklaysiz?",reply_markup=kb)

# ================= DONE =================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE

    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Serial saqlandi\nKod: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False

# ================= STATS =================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    await update.message.reply_text(
        f"📊 Statistika\n\n"
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Movies: {len(DB['movies'])}\n"
        f"🔢 Next: {DB['next']}"
    )

# ================= DELETE =================

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data["del"]=True
    await update.message.reply_text("🗑 Kod yuboring")

# ================= ADS =================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data["ads"]=True
    await update.message.reply_text("📢 Reklama yuboring")

# ================= AUTO DELETE =================

async def autodel(context,chat,msg):
    await asyncio.sleep(1500)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ================= MESSAGE =================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    # ADS
    if uid==ADMIN_ID and context.user_data.get("ads"):
        context.user_data["ads"]=False
        s=0
        for u in USERS:
            try:
                await update.message.copy(u)
                s+=1
            except:
                pass
        await update.message.reply_text(f"✅ Yuborildi: {s}")
        return

    # DELETE
    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("🗑 O‘chirildi")
        else:
            await update.message.reply_text("Topilmadi")
        return

    # UPLOAD
    if uid==ADMIN_ID and context.user_data.get("upload") and (update.message.video or update.message.document):

        if context.user_data["upload"]=="movie":
            code=str(DB["next"])
            DB["next"]+=1
        else:
            code=f"{SERIAL_CODE}.{SERIAL_PART}"
            SERIAL_PART+=1

        sent=await context.bot.copy_message(
            STORAGE_CHANNEL_ID,
            update.effective_chat.id,
            update.message.message_id,
            caption=f"Code: {code}"
        )

        DB["movies"][code]=sent.message_id
        save()

        await update.message.reply_text(f"✅ Saqlandi\nKod: {code}")
        return

    # USER
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    msg_id=DB["movies"].get(text)

    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    sent=await context.bot.forward_message(
        uid,
        STORAGE_CHANNEL_ID,
        msg_id
    )

    asyncio.create_task(autodel(context,uid,sent.message_id))

# ================= RUN =================

def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
