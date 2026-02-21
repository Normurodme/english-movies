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

# ===== FILES =====

DB_FILE = "/data/db.json"
USERS_FILE = "/data/users.json"
STATS_FILE = "/data/stats.json"
VIP_FILE="/data/vip.json"

os.makedirs("/data",exist_ok=True)

# ================= LOAD =================

DB=json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {"movies":{}, "next":1}
USERS=json.load(open(USERS_FILE)) if os.path.exists(USERS_FILE) else []
STATS=json.load(open(STATS_FILE)) if os.path.exists(STATS_FILE) else {"requests":[], "users":[]}
VIP=json.load(open(VIP_FILE)) if os.path.exists(VIP_FILE) else {}

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

def save():
    json.dump(DB,open(DB_FILE,"w"))
    json.dump(USERS,open(USERS_FILE,"w"))
    json.dump(STATS,open(STATS_FILE,"w"))
    json.dump(VIP,open(VIP_FILE,"w"))

# ================= VIP =================

def is_vip(uid):
    exp=VIP.get(str(uid))
    if not exp:
        return False
    if datetime.utcnow()>datetime.fromisoformat(exp):
        del VIP[str(uid)]
        save()
        return False
    return True

async def vip_checker(app):
    while True:
        now=datetime.utcnow()
        remove=[]
        for uid,exp in VIP.items():
            if now>datetime.fromisoformat(exp):
                try:
                    await app.bot.send_message(int(uid),"⏳ VIP obuna tugadi. Yangilash uchun /vip")
                except:
                    pass
                remove.append(uid)
        for u in remove:
            del VIP[u]
        if remove:
            save()
        await asyncio.sleep(3600)

# ================= SUB =================

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
    await update.message.reply_text("💡 Botdan foydalanish uchun kanalga a’zo bo‘ling.",reply_markup=kb)

# ================= START =================

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text("👋 Salom!\n\n📌 Kino kodini yuboring.")

# ================= INFO =================

async def info(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "VIP advantages:\n\n"
        "• Movie not deleted for 24h\n"
        "• Access to VIP movies\n"
        "• No ads"
    )

# ================= VIP MENU =================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])

    await update.message.reply_text("VIP tarif tanlang:",reply_markup=kb)
    await info(update,context)

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
        context.user_data["vipup"]=False
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vipup"]=False
        await q.message.edit_text("📺 Serial yuboring\nTugatish: /done")

    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]
        price,days=VIP_PLANS[plan]

        await context.bot.send_invoice(
            q.from_user.id,
            title="VIP obuna",
            description=f"{days} kun VIP",
            payload=f"vip_{days}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("VIP",price)]
        )

# ================= VIP DOWNLOAD =================

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Kino",callback_data="vipmovie"),
        InlineKeyboardButton("📺 Serial",callback_data="vipserial")
    ]])

    await update.message.reply_text("VIP yuklash:",reply_markup=kb)

# ================= PAYMENT =================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    days=int(update.message.successful_payment.invoice_payload.split("_")[1])
    VIP[str(uid)]=(datetime.utcnow()+timedelta(days=days)).isoformat()
    save()
    await update.message.reply_text("✅ VIP yoqildi!")

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

    now=time.time()
    day=86400

    users_24=set([u for u,t in STATS["users"] if now-t<day])
    req_24=len([1 for t in STATS["requests"] if now-t<day])

    await update.message.reply_text(
        f"📊 Statistika\n\n"
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Movies: {len(DB['movies'])}\n"
        f"🔢 Next: {DB['next']}\n\n"
        f"🕒 24h Users: {len(users_24)}\n"
        f"📥 24h Requests: {req_24}"
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

async def autodel(context,chat,msg,seconds):
    await asyncio.sleep(seconds)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ================= MESSAGE =================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    # ===== ADMIN TEXT IGNORE =====
    if uid==ADMIN_ID and text and text.isdigit():
        return

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

        sent=await context.bot.copy_message(STORAGE_CHANNEL_ID,update.effective_chat.id,update.message.message_id,caption=f"Code: {code}")
        DB["movies"][code]=sent.message_id
        save()

        await update.message.reply_text(f"✅ Saqlandi\nKod: {code}")
        return

    # USER REQUEST
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    # RATE LIMIT
    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("⏳ Kuting...")
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)

    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    STATS["requests"].append(now)
    STATS["users"].append((uid,now))
    save()

    sent=await context.bot.copy_message(uid,STORAGE_CHANNEL_ID,msg_id,caption=WARNING_TEXT)

    delete_sec=86400 if is_vip(uid) else 1500
    asyncio.create_task(autodel(context,uid,sent.message_id,delete_sec))

# ================= RUN =================

def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("info",info))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    app.create_task(vip_checker(app))

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
