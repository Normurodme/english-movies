import os
import json
import asyncio
import time
from datetime import datetime,timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, PreCheckoutQueryHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 8

WARNING_TEXT = (
    "⚠️ Movie will be deleted automatically in 25 minutes.\n"
    "📥 Please download or save it."
)

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"
STATS_FILE="/data/stats.json"
VIP_FILE="/data/vip.json"

os.makedirs("/data",exist_ok=True)

def load(path,default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

DB=load(DB_FILE,{"movies":{}, "next":1, "vip_only":[]})
USERS=load(USERS_FILE,[])
STATS=load(STATS_FILE,{"requests":[], "users":[]})
VIP=load(VIP_FILE,{})   # {uid:{expire:"iso"}}

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

def save():
    json.dump(DB,open(DB_FILE,"w"))
    json.dump(USERS,open(USERS_FILE,"w"))
    json.dump(STATS,open(STATS_FILE,"w"))
    json.dump(VIP,open(VIP_FILE,"w"))

# ================= VIP CHECK =================

def is_vip(uid):
    user=VIP.get(str(uid))
    if not user:
        return False
    exp=datetime.fromisoformat(user["expire"])
    if datetime.utcnow()>exp:
        del VIP[str(uid)]
        save()
        return False
    return True

# ================= VIP CLEANER =================

async def vip_checker(app):
    while True:
        now=datetime.utcnow()
        expired=[]
        for uid,data in VIP.items():
            if now>datetime.fromisoformat(data["expire"]):
                expired.append(uid)

        for uid in expired:
            try:
                await app.bot.send_message(int(uid),"⏳ VIP muddati tugadi\nYangilash → /vip")
            except:
                pass
            del VIP[uid]

        if expired:
            save()

        await asyncio.sleep(3600)

# ================= SUB =================

async def check_sub(user_id,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,user_id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tasdiqlash",callback_data="check")]
    ])
    await update.message.reply_text("❗ Kanalga a’zo bo‘ling",reply_markup=kb)

# ================= START =================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text("🎬 Kino kodini yuboring")

# ================= VIP =================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])
    await update.message.reply_text("👑 VIP tarif:",reply_markup=kb)

# ================= VIP LIST =================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("VIP yo‘q")
        return

    text="👑 ACTIVE VIP:\n\n"
    for uid,data in VIP.items():
        exp=datetime.fromisoformat(data["expire"])
        text+=f"{uid} — {exp.strftime('%d %b %H:%M')}\n"

    await update.message.reply_text(text)

# ================= CALLBACK =================

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART
    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Tasdiqlandi\nKod yuboring")
        else:
            await q.answer("Kanalga kiring",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        context.user_data["vipup"]=False
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vipup"]=False
        await q.message.edit_text("📺 Serial yuboring\n/done tugatadi")

    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]
        price,days=VIP_PLANS[plan]

        await context.bot.send_invoice(
            q.from_user.id,
            title="VIP",
            description=f"{days} kun VIP",
            payload=f"vip_{days}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("VIP",price)]
        )

# ================= PAYMENT =================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    pay=update.message.successful_payment
    uid=update.effective_user.id
    days=int(pay.invoice_payload.split("_")[1])

    VIP[str(uid)]={"expire":(datetime.utcnow()+timedelta(days=days)).isoformat()}
    save()

    await update.message.reply_text("👑 VIP aktiv!")

# ================= STATS =================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=time.time()
    day=86400

    users_24=set([u for u,t in STATS["users"] if now-t<day])
    req_24=len([1 for t in STATS["requests"] if now-t<day])

    await update.message.reply_text(
        f"📊 STATISTIKA\n\n"
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Movies: {len(DB['movies'])}\n"
        f"➡ Next: {DB['next']}\n\n"
        f"🕐 24h users: {len(users_24)}\n"
        f"📥 24h requests: {req_24}"
    )

# ================= MESSAGE =================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):

    uid=update.effective_user.id
    text=update.message.text

    if not text:
        return

    if text.startswith("/"):
        return   # <<< ENG MUHIM FIX

    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("⏳ Kuting...")
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    if text in DB["vip_only"] and not is_vip(uid):
        await update.message.reply_text("🔒 VIP kerak → /vip")
        return

    sent=await context.bot.copy_message(uid,STORAGE_CHANNEL_ID,msg_id,caption=WARNING_TEXT)

    delete_sec=86400 if is_vip(uid) else 1500
    asyncio.create_task(autodel(context,uid,sent.message_id,delete_sec))

# ================= AUTO DELETE =================

async def autodel(context,chat,msg,seconds):
    await asyncio.sleep(seconds)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ================= RUN =================

async def post_init(app):
    asyncio.create_task(vip_checker(app))

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("vips",vips))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))
    app.add_handler(CallbackQueryHandler(callbacks))

    app.add_handler(MessageHandler(filters.TEXT,msg))  # <<< FIX

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
