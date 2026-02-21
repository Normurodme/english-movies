import os
import json
import asyncio
from datetime import datetime,timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, PreCheckoutQueryHandler

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL="@moviesbyone"
ADMIN_ID=6220077209
STORAGE_CHANNEL_ID=-1003793414081

PROVIDER_TOKEN="PAYMENT_PROVIDER_TOKEN"

WARNING_TEXT="⚠️ Movie will be deleted automatically in 15 minutes.\n📥 Please download or save it."

REQUEST_DELAY=8

VIP_PLANS={
"week":(35,7),
"month":(125,30),
"3month":(300,90)
}

os.makedirs("/data",exist_ok=True)

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"

if os.path.exists(DB_FILE):
    DB=json.load(open(DB_FILE))
else:
    DB={"movies":{},"next":1,"stats":{},"vip_users":{}}

if os.path.exists(USERS_FILE):
    USERS=json.load(open(USERS_FILE))
else:
    USERS=[]

LAST_REQ={}
SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1

def save():
    with open(DB_FILE,"w") as f:
        json.dump(DB,f)
    with open(USERS_FILE,"w") as f:
        json.dump(USERS,f)

# ================= VIP CHECK =================

def is_vip(uid):
    exp=DB["vip_users"].get(str(uid))
    if not exp:
        return False
    if datetime.utcnow()>datetime.fromisoformat(exp):
        del DB["vip_users"][str(uid)]
        save()
        return False
    return True

# ================= SUB CHECK =================

async def check_sub(user_id,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,user_id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Channel",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("Confirm",callback_data="check")]
    ])
    await update.message.reply_text("Join channel to use bot.",reply_markup=kb)

# ================= START =================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text("Send movie code.")

# ================= CALLBACK =================

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("Subscription confirmed.")
        else:
            await q.answer("Join channel",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        await q.message.edit_text("Send movie file")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        await q.message.edit_text("Send episodes. Finish: /done")

    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]
        price,days=VIP_PLANS[plan]

        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title="VIP Access",
            description=f"{days} days VIP",
            payload=f"vip_{days}",
            provider_token=PROVIDER_TOKEN,
            currency="XTR",
            prices=[LabeledPrice("VIP",price)]
        )

# ================= DOWNLOAD =================

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("Movie",callback_data="movie"),
        InlineKeyboardButton("Serial",callback_data="serial")
    ]])
    await update.message.reply_text("Upload type?",reply_markup=kb)

# ================= VIP DOWNLOAD =================

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data["vipupload"]=True
    await update.message.reply_text("Send VIP file")

# ================= DONE =================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE
    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"Serial saved code: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False

# ================= STATS =================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=datetime.utcnow()
    users24=set()
    req24=0

    for uid,data in DB["stats"].items():
        for t in data:
            if now-datetime.fromisoformat(t)<timedelta(hours=24):
                users24.add(uid)
                req24+=1

    await update.message.reply_text(
f"""📊 Stats

Users: {len(USERS)}
Movies: {len(DB["movies"])}
Next: {DB["next"]}

24h Users: {len(users24)}
24h Requests: {req24}"""
)

# ================= VIP MENU =================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    kb=InlineKeyboardMarkup([
    [InlineKeyboardButton("1 Week — 35⭐",callback_data="buy_week")],
    [InlineKeyboardButton("1 Month — 125⭐",callback_data="buy_month")],
    [InlineKeyboardButton("3 Month — 300⭐",callback_data="buy_3month")]
    ])

    await update.message.reply_text(
"""VIP Benefits:
/info

Choose plan:""",
reply_markup=kb)

# ================= INFO =================

async def info(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""VIP Privileges:

• Movies not deleted for 24h
• Access VIP movies & series
• No ads"""
)

# ================= PAYMENT =================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    payload=update.message.successful_payment.invoice_payload
    days=int(payload.split("_")[1])

    exp=datetime.utcnow()+timedelta(days=days)
    DB["vip_users"][str(uid)]=exp.isoformat()
    save()

    await update.message.reply_text("VIP Activated")

# ================= DELETE =================

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["del"]=True
    await update.message.reply_text("Send code to delete")

async def ndelete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["nreset"]=True
    await update.message.reply_text("Send new next code")

# ================= ADS =================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ads"]=True
    await update.message.reply_text("Send broadcast")

# ================= AUTO DELETE =================

async def autodel(context,chat,msg,sec):
    await asyncio.sleep(sec)
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
            if not is_vip(u):
                try:
                    await update.message.copy(u)
                    s+=1
                except: pass
        await update.message.reply_text(f"Sent {s}")
        return

    # RESET NEXT
    if uid==ADMIN_ID and context.user_data.get("nreset"):
        context.user_data["nreset"]=False
        DB["next"]=int(text)
        save()
        await update.message.reply_text("Next updated")
        return

    # DELETE
    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("Deleted")
        else:
            await update.message.reply_text("Not found")
        return

    # UPLOAD NORMAL
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
            caption=f"Code: {code}\n\n{WARNING_TEXT}"
        )

        DB["movies"][code]={"id":sent.message_id,"vip":False}
        save()
        await update.message.reply_text(f"Saved {code}")
        return

    # UPLOAD VIP
    if uid==ADMIN_ID and context.user_data.get("vipupload") and (update.message.video or update.message.document):
        context.user_data["vipupload"]=False
        code=str(DB["next"])
        DB["next"]+=1

        sent=await context.bot.copy_message(
            STORAGE_CHANNEL_ID,
            update.effective_chat.id,
            update.message.message_id,
            caption=f"VIP Code: {code}"
        )

        DB["movies"][code]={"id":sent.message_id,"vip":True}
        save()
        await update.message.reply_text(f"VIP Saved {code}")
        return

    # SUB CHECK
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    # RATE LIMIT
    now=datetime.utcnow().timestamp()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("Wait few seconds")
        return

    LAST_REQ[uid]=now

    data=DB["movies"].get(text)
    if not data:
        await update.message.reply_text("Code not found")
        return

    # VIP CHECK
    if data["vip"] and not is_vip(uid):
        await update.message.reply_text("VIP only. Use /vip")
        return

    DB["stats"].setdefault(str(uid),[]).append(datetime.utcnow().isoformat())
    save()

    sent=await context.bot.copy_message(uid,STORAGE_CHANNEL_ID,data["id"])

    if not is_vip(uid):
        asyncio.create_task(autodel(context,uid,sent.message_id,900))

# ================= VIP EXPIRY CHECK =================

async def vip_checker(app):
    while True:
        now=datetime.utcnow()
        expired=[]

        for uid,exp in DB["vip_users"].items():
            if now>datetime.fromisoformat(exp):
                expired.append(uid)

        for u in expired:
            del DB["vip_users"][u]
            try:
                await app.bot.send_message(int(u),"Your VIP expired. Renew with /vip")
            except:
                pass

        if expired:
            save()

        await asyncio.sleep(3600)

# ================= RUN =================

def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ndelete",ndelete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("info",info))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    app.job_queue.run_once(lambda c: asyncio.create_task(vip_checker(app)),1)

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
