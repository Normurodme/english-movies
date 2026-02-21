import os
import json
import asyncio
from datetime import datetime,timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, PreCheckoutQueryHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
CHANNEL = "@moviesbyone"
STORAGE = -1003793414081

DELETE_TIME = 900
REQUEST_DELAY = 8

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

# ================= FILES =================

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"

os.makedirs("/data",exist_ok=True)

if os.path.exists(DB_FILE):
    DB=json.load(open(DB_FILE))
else:
    DB={"movies":{}, "next":1, "stats":{}, "vip":{}}

if os.path.exists(USERS_FILE):
    USERS=json.load(open(USERS_FILE))
else:
    USERS=[]

LAST_REQ={}
SERIAL=False
SERIAL_CODE=None
SERIAL_PART=1

def save():
    json.dump(DB,open(DB_FILE,"w"))
    json.dump(USERS,open(USERS_FILE,"w"))

# ================= VIP =================

def is_vip(uid):
    exp=DB["vip"].get(str(uid))
    if not exp:
        return False
    if datetime.utcnow()>datetime.fromisoformat(exp):
        del DB["vip"][str(uid)]
        save()
        return False
    return True

# ================= SUB CHECK =================

async def check_sub(uid,context):
    try:
        m=await context.bot.get_chat_member(CHANNEL,uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga o'tish",url=f"https://t.me/{CHANNEL[1:]}")],
        [InlineKeyboardButton("✅ Tekshirish",callback_data="check")]
    ])
    await update.message.reply_text("Botdan foydalanish uchun kanalga a'zo bo‘ling.",reply_markup=kb)

# ================= START =================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(
        "🎬 *Kino botiga xush kelibsiz*\n\n"
        "📌 Kino kodini yuboring",
        parse_mode="Markdown"
    )

# ================= CALLBACK =================

async def cb(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Obuna tasdiqlandi. Kod yuboring.")
        else:
            await q.answer("❌ Avval kanalga kiring",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        await q.message.edit_text("📺 Qismlarni yuboring\nTugatish: /done")

    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]

        if is_vip(q.from_user.id):
            await q.message.reply_text("✅ Sizda allaqachon VIP mavjud")
            return

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

# ================= DOWNLOAD =================

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Kino",callback_data="movie"),
        InlineKeyboardButton("📺 Serial",callback_data="serial")
    ]])

    await update.message.reply_text("Yuklash turi:",reply_markup=kb)

# ================= DONE =================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL
    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL:
        await update.message.reply_text(f"✅ Serial saqlandi\nKod: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL=False

# ================= VIP MENU =================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])

    await update.message.reply_text(
        "👑 VIP tariflar\n\n"
        "Afzalliklar:\n"
        "• 24 soat o‘chmaydi\n"
        "• VIP kinolar\n"
        "• Reklama yo‘q\n\n"
        "Tanlang:",
        reply_markup=kb
    )

# ================= PAYMENT =================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    days=int(update.message.successful_payment.invoice_payload.split("_")[1])

    exp=datetime.utcnow()+timedelta(days=days)
    DB["vip"][str(uid)]=exp.isoformat()
    save()

    await update.message.reply_text(f"👑 VIP yoqildi\n⏳ {days} kun")

# ================= VIPS LIST =================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not DB["vip"]:
        await update.message.reply_text("VIP yo'q")
        return

    text="👑 VIP foydalanuvchilar:\n\n"

    for uid,exp in DB["vip"].items():
        text+=f"ID: {uid}\nTugaydi: {exp}\n\n"

    await update.message.reply_text(text)

# ================= DELETE =================

async def delete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["del"]=True
    await update.message.reply_text("Kod yuboring")

# ================= NDELETE =================

async def ndelete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["n"]=True
    await update.message.reply_text("Yangi next raqam")

# ================= ADS =================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ads"]=True
    await update.message.reply_text("Reklama yuboring")

# ================= STATS =================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=datetime.utcnow()
    users24=set()
    req24=0

    for u,times in DB["stats"].items():
        for t in times:
            if now-datetime.fromisoformat(t)<timedelta(hours=24):
                users24.add(u)
                req24+=1

    await update.message.reply_text(
        f"📊 Statistika\n\n"
        f"👥 Users: {len(USERS)}\n"
        f"🎬 Kinolar: {len(DB['movies'])}\n"
        f"🔢 Next: {DB['next']}\n\n"
        f"🕒 24h users: {len(users24)}\n"
        f"📥 24h request: {req24}"
    )

# ================= AUTO DELETE =================

async def autodel(context,chat,msg):
    await asyncio.sleep(DELETE_TIME)
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
        sent=0
        for u in USERS:
            try:
                if not is_vip(u):
                    await update.message.copy(u)
                    sent+=1
            except:
                pass
        await update.message.reply_text(f"Yuborildi: {sent}")
        return

    # NEXT
    if uid==ADMIN_ID and context.user_data.get("n"):
        context.user_data["n"]=False
        DB["next"]=int(text)
        save()
        await update.message.reply_text("Next o'zgardi")
        return

    # DELETE
    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("O'chirildi")
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

        sent=await context.bot.copy_message(STORAGE,update.effective_chat.id,update.message.message_id,caption=f"Kod: {code}")

        DB["movies"][code]=sent.message_id
        save()

        await update.message.reply_text(f"Saqlandi\nKod: {code}")
        return

    # CHECK SUB
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    # LIMIT
    now=datetime.utcnow().timestamp()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("⏳ Kuting...")
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)

    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    DB["stats"].setdefault(str(uid),[]).append(datetime.utcnow().isoformat())
    save()

    sent=await context.bot.copy_message(uid,STORAGE,msg_id)

    if not is_vip(uid):
        asyncio.create_task(autodel(context,uid,sent.message_id))

# ================= RUN =================

def main():
    app=ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete))
    app.add_handler(CommandHandler("ndelete",ndelete))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("vips",vips))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("BOT IS RUNNING")
    app.run_polling()

if __name__=="__main__":
    main()
