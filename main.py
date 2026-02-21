import os
import json
import asyncio
import re
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

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

MOVIES_FILE = "movies.json"
CODE_FILE = "next_code.txt"
USERS_FILE = "users.json"

# ================= LOAD =================

if os.path.exists(MOVIES_FILE):
    with open(MOVIES_FILE) as f:
        MOVIES=json.load(f)
else:
    MOVIES={}

if os.path.exists(CODE_FILE):
    with open(CODE_FILE) as f:
        NEXT_CODE=int(f.read())
else:
    NEXT_CODE=1

if os.path.exists(USERS_FILE):
    with open(USERS_FILE) as f:
        USERS=json.load(f)
else:
    USERS=[]

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1

def save_db():
    with open(MOVIES_FILE,"w") as f:
        json.dump(MOVIES,f)
    with open(CODE_FILE,"w") as f:
        f.write(str(NEXT_CODE))
    with open(USERS_FILE,"w") as f:
        json.dump(USERS,f)

# ================= FIND IN CHANNEL =================

async def find_movie(code,context):
    try:
        async for msg in context.bot.get_chat_history(STORAGE_CHANNEL_ID,limit=2000):
            if msg.caption and f"Code: {code}" in msg.caption:
                return msg.message_id
    except:
        pass
    return None

# ================= SUB CHECK =================

async def check_subscription(uid,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def send_subscribe(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Channel",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("Check",callback_data="check_sub")]
    ])
    await update.message.reply_text("Join channel first",reply_markup=kb)

# ================= START =================

async def start(update,context):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save_db()

    if not await check_subscription(uid,context):
        await send_subscribe(update)
        return

    await update.message.reply_text("Send movie code")

# ================= CALLBACK =================

async def callbacks(update,context):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check_sub":
        if await check_subscription(q.from_user.id,context):
            await q.message.edit_text("Confirmed")
        else:
            await q.answer("Not subscribed",show_alert=True)

    if q.data=="dl_movie":
        context.user_data["awaiting_movie"]=True
        context.user_data["mode"]="movie"
        await q.message.edit_text("Send movie file")

    if q.data=="dl_serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(NEXT_CODE)
        SERIAL_PART=1
        context.user_data["awaiting_movie"]=True
        context.user_data["mode"]="serial"
        await q.message.edit_text("Send episodes then /done")

# ================= DOWNLOAD =================

async def download(update,context):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("Movie",callback_data="dl_movie"),
        InlineKeyboardButton("Serial",callback_data="dl_serial")
    ]])

    await update.message.reply_text("Choose type",reply_markup=kb)

# ================= DONE =================

async def done(update,context):
    global SERIAL_MODE,NEXT_CODE

    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"Serial saved code={SERIAL_CODE}")
        NEXT_CODE+=1
        save_db()

    SERIAL_MODE=False

# ================= STATS =================

async def stats(update,context):
    if update.effective_user.id!=ADMIN_ID:
        return

    await update.message.reply_text(
        f"Users={len(USERS)}\nMovies={len(MOVIES)}\nNext={NEXT_CODE}"
    )

# ================= ADS =================

async def ads(update,context):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["awaiting_ads"]=True
    await update.message.reply_text("Send ad")

# ================= DELETE TIMER =================

async def delete_later(context,chat,msg):
    await asyncio.sleep(1500)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ================= MESSAGE =================

async def handle_message(update,context):
    global NEXT_CODE,SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    # ADS
    if uid==ADMIN_ID and context.user_data.get("awaiting_ads"):
        context.user_data["awaiting_ads"]=False
        for u in USERS:
            try: await update.message.copy(u)
            except: pass
        await update.message.reply_text("Sent")
        return

    # DELETE
    if uid==ADMIN_ID and context.user_data.get("awaiting_delete"):
        if text in MOVIES:
            del MOVIES[text]
            save_db()
            await update.message.reply_text("Deleted")
        else:
            await update.message.reply_text("Not found")
        context.user_data["awaiting_delete"]=False
        return

    # ADD MOVIE
    if uid==ADMIN_ID and context.user_data.get("awaiting_movie") and (update.message.video or update.message.document):

        if context.user_data["mode"]=="movie":
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
        save_db()

        await update.message.reply_text(f"Saved code={code}")
        return

    # USER REQUEST
    if not await check_subscription(uid,context):
        await send_subscribe(update)
        return

    if not text:
        return

    code=re.sub(r"\D","",text)

    msg_id=MOVIES.get(code)

    if not msg_id:
        msg_id=await find_movie(code,context)
        if msg_id:
            MOVIES[code]=msg_id
            save_db()

    if not msg_id:
        await update.message.reply_text("Code not found")
        return

    sent=await context.bot.forward_message(
        chat_id=update.effective_chat.id,
        from_chat_id=STORAGE_CHANNEL_ID,
        message_id=msg_id
    )

    asyncio.create_task(delete_later(context,update.effective_chat.id,sent.message_id))

# ================= RUN =================

def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,handle_message))

    print("BOT RUNNING")
    app.run_polling()

if __name__=="__main__":
    main()
