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
    "⚠️ Kino 25 daqiqadan keyin o‘chadi\n"
    "📥 Yuklab oling"
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
VIP=load(VIP_FILE,{})

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
    dt=datetime.fromisoformat(exp)
    if datetime.utcnow()>dt:
        del VIP[str(uid)]
        save()
        return False
    return True

async def vip_checker(app):
    while True:
        now=datetime.utcnow()
        expired=[]
        for uid,exp in VIP.items():
            if now>datetime.fromisoformat(exp):
                expired.append(uid)

        for uid in expired:
            try:
                await app.bot.send_message(int(uid),"⏳ VIP obunangiz tugadi.\nYangilash: /vip")
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
        [InlineKeyboardButton("✅ Tekshirish",callback_data="check")]
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

# ================= INFO =================

async def info(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 VIP afzalliklari:\n\n"
        "• Kino 24 soat o‘chmaydi\n"
        "• VIP kinolar ochiladi\n"
        "• Reklama kelmaydi"
    )

# ================= VIP =================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])
    await update.message.reply_text("👑 VIP tarif tanlang:",reply_markup=kb)
    await info(update,context)

# ================= VIP LIST =================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=datetime.utcnow()
    text="👑 VIP foydalanuvchilar:\n\n"

    for uid,exp in list(VIP.items()):
        dt=datetime.fromisoformat(exp)
        if now>dt:
            del VIP[uid]
            continue
        text+=f"{uid} | {dt.strftime('%Y-%m-%d %H:%M')}\n"

    save()

    if text=="👑 VIP foydalanuvchilar:\n\n":
        text="VIP user yo‘q"

    await update.message.reply_text(text)

# ================= CALLBACK =================

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Tasdiqlandi. Kod yuboring.")
        else:
            await q.answer("Avval kanalga kiring",show_alert=True)

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

    if q.data=="vipmovie":
        context.user_data["upload"]="movie"
        context.user_data["vipup"]=True
        await q.message.edit_text("🔒 VIP kino yuboring")

    if q.data=="vipserial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vipup"]=True
        await q.message.edit_text("🔒 VIP serial yuboring")

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

# ================= DOWNLOAD =================

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Kino",callback_data="movie"),
        InlineKeyboardButton("📺 Serial",callback_data="serial")
    ]])

    await update.message.reply_text("⬇️ Nima yuklaysiz?",reply_markup=kb)

# ================= VIP DOWNLOAD =================

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([[
        InlineKeyboardButton("🔒 VIP Kino",callback_data="vipmovie"),
        InlineKeyboardButton("🔒 VIP Serial",callback_data="vipserial")
    ]])

    await update.message.reply_text("🔒 VIP yuklash paneli:",reply_markup=kb)

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

# ================= ADS =================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data["ads"]=True
    await update.message.reply_text("📢 Xabar yuboring")

# ================= DELETE =================

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["del"]=True
    await update.message.reply_text("🗑 Kod yuboring")

# ================= PAYMENT =================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    days=int(update.message.successful_payment.invoice_payload.split("_")[1])
    VIP[str(uid)]=(datetime.utcnow()+timedelta(days=days)).isoformat()
    save()
    await update.message.reply_text("👑 VIP aktivlashtirildi!")

# ================= MESSAGE =================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    if uid==ADMIN_ID and text and text.isdigit():
        return

    if uid==ADMIN_ID and context.user_data.get("ads"):
        context.user_data["ads"]=False
        s=0
        for u in USERS:
            if not is_vip(u):
                try:
                    await update.message.copy(u)
                    s+=1
                except:
                    pass
        await update.message.reply_text(f"✅ Yuborildi: {s}")
        return

    if uid==ADMIN_ID and context.user_data.get("del"):
        context.user_data["del"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("🗑 O‘chirildi")
        return

    # upload
    if uid==ADMIN_ID and context.user_data.get("upload") and (update.message.video or update.message.document):

        if context.user_data["upload"]=="movie":
            code=str(DB["next"])
            DB["next"]+=1
        else:
            code=f"{SERIAL_CODE}.{SERIAL_PART}"
            SERIAL_PART+=1

        sent=await context.bot.copy_message(STORAGE_CHANNEL_ID,update.effective_chat.id,update.message.message_id)
        DB["movies"][code]=sent.message_id

        if context.user_data.get("vipup") and code not in DB["vip_only"]:
            DB["vip_only"].append(code)

        save()
        await update.message.reply_text(f"✅ Saqlandi\nKod: {code}")
        return

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        sec=int(REQUEST_DELAY-(now-LAST_REQ[uid]))
        await update.message.reply_text(f"⏳ {sec} soniya kuting")
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    if text in DB.get("vip_only",[]) and not is_vip(uid):
        await update.message.reply_text("🔒 Bu kino VIP uchun\n👉 /vip yuboring")
        return

    STATS["requests"].append(now)
    STATS["users"].append((uid,now))
    save()

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
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("info",info))
    app.add_handler(CommandHandler("vips",vips))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
