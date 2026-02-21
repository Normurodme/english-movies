import os
import json
import asyncio
import time
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PreCheckoutQueryHandler
)

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
REQUIRED_CHANNEL = "@moviesbyone"
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 8

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

WARNING_TEXT = (
    "⚠️ <b>Video 15 daqiqadan keyin o‘chadi!</b>\n"
    "📥 Yuklab oling."
)

# =========================
# STORAGE
# =========================

os.makedirs("/data", exist_ok=True)

def load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_file(path,data):
    with open(path,"w") as f:
        json.dump(data,f)

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"
VIP_FILE="/data/vip.json"
STATS_FILE="/data/stats.json"

DB=load(DB_FILE,{"movies":{}, "next":1, "vip_only":[]})
USERS=load(USERS_FILE,[])
VIP=load(VIP_FILE,{})
STATS=load(STATS_FILE,{"requests":[], "users":[]})

def save():
    save_file(DB_FILE,DB)
    save_file(USERS_FILE,USERS)
    save_file(VIP_FILE,VIP)
    save_file(STATS_FILE,STATS)

# =========================
# STATES
# =========================

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

# =========================
# VIP SYSTEM
# =========================

def is_vip(uid:int):
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
        expired=[]
        for uid,exp in list(VIP.items()):
            if now>datetime.fromisoformat(exp):
                expired.append(uid)

        for uid in expired:
            try:
                await app.bot.send_message(int(uid),"⏳ VIP muddati tugadi.\nYangilash: /vip")
            except:
                pass
            del VIP[uid]

        if expired:
            save()

        await asyncio.sleep(3600)

# =========================
# SUB CHECK
# =========================

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
    await update.message.reply_text("Botdan foydalanish uchun kanalga a'zo bo'ling",reply_markup=kb)

# =========================
# START
# =========================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(
        "🎬 <b>Kino kodini yuboring</b>\n\nMisol: <code>12</code>",
        parse_mode="HTML"
    )

# =========================
# VIP BUY
# =========================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])
    await update.message.reply_text("👑 VIP tarifni tanlang:",reply_markup=kb)

# =========================
# VIP LIST
# =========================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("VIP yo'q")
        return

    text="👑 VIP USERS\n\n"

    for uid,exp in VIP.items():
        try:
            user=await context.bot.get_chat(uid)
            name=user.username if user.username else user.full_name
        except:
            name="unknown"

        text+=f"{uid} | {name}\nTugaydi: {exp}\n\n"

    await update.message.reply_text(text)

# =========================
# DOWNLOAD PANEL
# =========================

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])

    await update.message.reply_text("Yuklash turini tanlang:",reply_markup=kb)

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 VIP Kino",callback_data="vipmovie"),
         InlineKeyboardButton("🔒 VIP Serial",callback_data="vipserial")]
    ])

    await update.message.reply_text("VIP yuklash paneli:",reply_markup=kb)

# =========================
# CALLBACK
# =========================

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Tasdiqlandi")
        else:
            await q.answer("Avval kanalga kiring",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        context.user_data["vip"]=False
        await q.message.edit_text("Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=False
        await q.message.edit_text("Serial yuboring\n/done tugatadi")

    if q.data=="vipmovie":
        context.user_data["upload"]="movie"
        context.user_data["vip"]=True
        await q.message.edit_text("VIP kino yuboring")

    if q.data=="vipserial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=True
        await q.message.edit_text("VIP serial yuboring")

# =========================
# DONE SERIAL
# =========================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE

    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"Saqlandi. Kod: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False

# =========================
# DELETE
# =========================

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["delete"]=True
    await update.message.reply_text("O'chiriladigan kodni yuboring")

# =========================
# ADS
# =========================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ads"]=True
    await update.message.reply_text("Reklama matnini yuboring")

# =========================
# STATS
# =========================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=time.time()
    day=86400

    users_24=set([u for u,t in STATS["users"] if now-t<day])
    req_24=len([1 for t in STATS["requests"] if now-t<day])

    await update.message.reply_text(
        f"Users: {len(USERS)}\nMovies: {len(DB['movies'])}\nNext: {DB['next']}\n\n24h users: {len(users_24)}\n24h requests: {req_24}"
    )

# =========================
# MESSAGE HANDLER
# =========================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global SERIAL_PART

    if update.message is None:
        return

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    # command skip
    if text and text.startswith("/"):
        return

    # broadcast
    if uid==ADMIN_ID and context.user_data.get("ads"):
        context.user_data["ads"]=False
        sent=0
        for u in USERS:
            if u==ADMIN_ID:
                continue
            if is_vip(u):
                continue
            try:
                await update.message.copy(u)
                sent+=1
            except:
                pass

        await update.message.reply_text(f"Yuborildi: {sent}")
        return

    # delete
    if uid==ADMIN_ID and context.user_data.get("delete"):
        context.user_data["delete"]=False
        if text in DB["movies"]:
            del DB["movies"][text]
            save()
            await update.message.reply_text("O'chirildi")
        else:
            await update.message.reply_text("Kod topilmadi")
        return

    # upload
    if uid==ADMIN_ID and context.user_data.get("upload") and (update.message.video or update.message.document):

        if context.user_data["upload"]=="movie":
            code=str(DB["next"])
            DB["next"]+=1
        else:
            code=f"{SERIAL_CODE}.{SERIAL_PART}"
            SERIAL_PART+=1

        caption = f"🔒Code: {code}" if context.user_data.get("vip") else f"Code: {code}"

        sent=await context.bot.copy_message(
            STORAGE_CHANNEL_ID,
            update.effective_chat.id,
            update.message.message_id,
            caption=caption
        )

        DB["movies"][code]=sent.message_id

        if context.user_data.get("vip"):
            DB["vip_only"].append(code)

        context.user_data.pop("upload",None)
        context.user_data.pop("vip",None)

        save()

        await update.message.reply_text(f"Saqlandi: {code}")
        return

    # sub check
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    # cooldown
    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("Kutib turing")
        return
    LAST_REQ[uid]=now

    # movie request
    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text("Kod topilmadi")
        return

    # VIP check
    if text in DB.get("vip_only",[]) and not is_vip(uid):
        await update.message.reply_text("🔒 Bu VIP kino\nVIP olish: /vip")
        return

    # stats
    STATS["requests"].append(now)
    STATS["users"].append((uid,now))
    save()

    sent=await context.bot.copy_message(
        uid,
        STORAGE_CHANNEL_ID,
        msg_id,
        caption=WARNING_TEXT,
        parse_mode="HTML"
    )

    delete_sec=86400 if is_vip(uid) else 900
    asyncio.create_task(auto_delete(context,uid,sent.message_id,delete_sec))

# =========================
# AUTO DELETE
# =========================

async def auto_delete(context,chat,msg,sec):
    await asyncio.sleep(sec)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# =========================
# RUN
# =========================

async def post_init(app):
    asyncio.create_task(vip_checker(app))

def main():

    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("vips",vips))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("done",done))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("BOT IS RUNNING...")
    app.run_polling()

if __name__=="__main__":
    main()
