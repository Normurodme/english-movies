import os
import json
import asyncio
from datetime import datetime,timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, PreCheckoutQueryHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 15 minutes.\n"
    "📥 Please download or save it."
)

REQUEST_DELAY = 8

VIP_PLANS = {
    "week": (50,7),
    "month": (125,30),
    "3month": (300,90)
}

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"

# LOAD
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
    json.dump(DB,open(DB_FILE,"w"))
    json.dump(USERS,open(USERS_FILE,"w"))

# VIP CHECK
def is_vip(uid):
    exp=DB["vip_users"].get(str(uid))
    if not exp:
        return False
    try:
        if datetime.utcnow()>datetime.fromisoformat(exp):
            del DB["vip_users"][str(uid)]
            save()
            return False
    except:
        return False
    return True

# SUB CHECK
async def check_sub(user_id,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,user_id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies in English",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Confirm",callback_data="check")]
    ])
    await update.message.reply_text("💡 Join channel to use bot.",reply_markup=kb)

# START
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text("👋 Hello!\n\n🎬 Welcome.\n📌 Send movie code.")

# CALLBACK
async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Subscription confirmed!\n📌 Send code.")
        else:
            await q.answer("❌ Join channel",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        await q.message.edit_text("🎬 Send movie")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        await q.message.edit_text("📺 Send episodes\nFinish: /done")

    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]
        price,days=VIP_PLANS[plan]

        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title="VIP Subscription",
            description=f"{days} days VIP access",
            payload=f"vip_{days}",
            provider_token=None,
            currency="XTR",
            prices=[LabeledPrice("VIP",price)]
        )

# DOWNLOAD
async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Movie",callback_data="movie"),
        InlineKeyboardButton("📺 Serial",callback_data="serial")
    ]])

    await update.message.reply_text("Upload type?",reply_markup=kb)

# DONE
async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE
    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Serial saved\nCode: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False
    context.user_data.pop("upload",None)

# STATS
async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=datetime.utcnow()
    users24=set()
    req24=0

    for uid,data in DB["stats"].items():
        for t in data:
            try:
                dt=datetime.fromisoformat(t)
                if now-dt<timedelta(hours=24):
                    users24.add(uid)
                    req24+=1
            except:
                pass

    await update.message.reply_text(
        f"📊 Statistics\n\n"
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Movies: {len(DB['movies'])}\n"
        f"🔢 Next: {DB['next']}\n\n"
        f"🕒 24h Users: {len(users24)}\n"
        f"📥 24h Requests: {req24}"
    )

# VIP MENU
async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 Week — 50",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 Month — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 Months — 300",callback_data="buy_3month")]
    ])

    await update.message.reply_text("👑 VIP Plans\nChoose subscription:",reply_markup=kb)

# PAYMENT
async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    payload=update.message.successful_payment.invoice_payload
    days=int(payload.split("_")[1])

    exp=datetime.utcnow()+timedelta(days=days)
    DB["vip_users"][str(uid)]=exp.isoformat()
    save()

    await update.message.reply_text(f"👑 VIP Activated!\n⏳ Valid {days} days")

# DELETE
async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["del"]=True
    await update.message.reply_text("🗑 Send code")

# RESET NEXT
async def ndelete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["nreset"]=True
    await update.message.reply_text("🔢 Send new next number")

# ADS
async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ads"]=True
    await update.message.reply_text("📢 Send broadcast")

# AUTO DELETE
async def autodel(context,chat,msg,seconds):
    await asyncio.sleep(seconds)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# MESSAGE
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
                if not is_vip(u):
                    await update.message.copy(u)
                    s+=1
            except:
                pass
        await update.message.reply_text(f"✅ Sent: {s}")
        return

    # RESET NEXT
    if uid==ADMIN_ID and context.user_data.get("nreset"):
        context.user_data["nreset"]=False
        try:
            DB["next"]=int(text)
            save()
            await update.message.reply_text(f"✅ Next updated → {text}")
        except:
            await update.message.reply_text("❌ Send number")
        return

    # DELETE
    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("🗑 Deleted")
        else:
            await update.message.reply_text("Not found")
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
            caption=f"Code: {code}\n\n{WARNING_TEXT}"
        )

        DB["movies"][code]=sent.message_id
        save()

        await update.message.reply_text(f"✅ Saved\nCode: {code}")
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
        wait=int(REQUEST_DELAY-(now-LAST_REQ[uid]))
        await update.message.reply_text(f"⏱ Wait {wait}s")
        return

    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)

    if not msg_id:
        await update.message.reply_text("❌ Code not found")
        return

    DB["stats"].setdefault(str(uid),[]).append(datetime.utcnow().isoformat())
    save()

    sent=await context.bot.copy_message(uid,STORAGE_CHANNEL_ID,msg_id)

    if not is_vip(uid):
        asyncio.create_task(autodel(context,uid,sent.message_id,900))

# RUN
def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ndelete",ndelete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT | filters.VIDEO | filters.Document.ALL,msg))

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
