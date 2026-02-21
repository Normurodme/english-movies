import os
import json
import asyncio
import time
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, PreCheckoutQueryHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 8

WARNING_TEXT = (
    "⚠️ <b>Video 15 daqiqadan keyin o‘chadi!</b>\n"
    "📥 Yuklab oling."
)

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

# ---------- FILES ----------

os.makedirs("/data",exist_ok=True)

def load(path,default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_file(path,data):
    with open(path,"w") as f:
        json.dump(data,f)

DB_FILE="/data/db.json"
USERS_FILE="/data/users.json"
STATS_FILE="/data/stats.json"
VIP_FILE="/data/vip.json"

DB=load(DB_FILE,{"movies":{}, "next":1, "vip_only":[]})
USERS=load(USERS_FILE,[])
STATS=load(STATS_FILE,{"requests":[], "users":[]})
VIP=load(VIP_FILE,{})

def save():
    save_file(DB_FILE,DB)
    save_file(USERS_FILE,USERS)
    save_file(STATS_FILE,STATS)
    save_file(VIP_FILE,VIP)

# ---------- STATES ----------

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

# ---------- VIP ----------

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
        for uid,exp in VIP.items():
            if now>datetime.fromisoformat(exp):
                expired.append(uid)

        for uid in expired:
            try:
                await app.bot.send_message(int(uid),"⏳ VIP tugadi. /vip orqali yangilang")
            except:
                pass
            del VIP[uid]

        if expired:
            save()

        await asyncio.sleep(3600)

# ---------- SUB ----------

async def check_sub(user_id,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,user_id)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanal",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tekshirish",callback_data="check")]
    ])
    await update.message.reply_text("📢 <b>Kanalga a’zo bo‘ling</b>",reply_markup=kb,parse_mode="HTML")

# ---------- START ----------

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(
        "🎬 <b>Kino kodini yuboring</b>\n\nMasalan: <code>12</code>",
        parse_mode="HTML"
    )

# ---------- VIP ----------

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])
    await update.message.reply_text("👑 <b>VIP tarifni tanlang</b>",reply_markup=kb,parse_mode="HTML")

# ---------- VIP LIST ----------

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("VIP yo‘q")
        return

    text="👑 <b>VIP LIST</b>\n\n"

    for uid,exp in VIP.items():
        user=await context.bot.get_chat(uid)
        name=user.username if user.username else user.full_name
        end=datetime.fromisoformat(exp)
        text+=f"<code>{uid}</code> | {name}\n⏳ {end}\n\n"

    await update.message.reply_text(text,parse_mode="HTML")

# ---------- DOWNLOAD PANEL ----------

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])

    await update.message.reply_text("📤 <b>Yuklash turini tanlang</b>",reply_markup=kb,parse_mode="HTML")

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 VIP Kino",callback_data="vipmovie"),
         InlineKeyboardButton("🔒 VIP Serial",callback_data="vipserial")]
    ])

    await update.message.reply_text("🔐 <b>VIP yuklash paneli</b>",reply_markup=kb,parse_mode="HTML")

# ---------- CALLBACK ----------

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Tasdiqlandi")
        else:
            await q.answer("Kanalga kiring",show_alert=True)

    if q.data=="movie":
        SERIAL_MODE=False
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
        SERIAL_MODE=False
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

# ---------- DONE SERIAL ----------

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE
    if update.effective_user.id!=ADMIN_ID:
        return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Saqlandi kod: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False

# ---------- DELETE ----------

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["delete"]=True
    await update.message.reply_text("🗑 Kod yuboring")

async def ndelete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["setnext"]=True
    await update.message.reply_text(f"Hozirgi keyingi kod: {DB['next']}\nYangi kodni yuboring:")

# ---------- ADS ----------

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ads"]=True
    await update.message.reply_text("📢 Reklama yuboring")

# ---------- STATS ----------

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    now=time.time()
    day=86400

    users_24=set([u for u,t in STATS["users"] if now-t<day])
    req_24=len([1 for t in STATS["requests"] if now-t<day])

    await update.message.reply_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Users: <b>{len(USERS)}</b>\n"
        f"🎬 Movies: <b>{len(DB['movies'])}</b>\n"
        f"🔢 Next: <b>{DB['next']}</b>\n\n"
        f"🕒 24h users: <b>{len(users_24)}</b>\n"
        f"📥 24h requests: <b>{req_24}</b>",
        parse_mode="HTML"
    )

# ---------- MESSAGE ----------

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

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

        await update.message.reply_text(f"✅ Reklama {sent} ta userga yuborildi")
        return

    # set next code
    if uid==ADMIN_ID and context.user_data.get("setnext"):
        context.user_data["setnext"]=False

        if not text.isdigit():
            await update.message.reply_text("Faqat raqam yuboring")
            return

        DB["next"]=int(text)
        save()
        await update.message.reply_text(f"✅ Next kod yangilandi → {text}")
        return

    # delete
    if uid==ADMIN_ID and context.user_data.get("delete"):
        context.user_data["delete"]=False
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

        if context.user_data.get("vipup"):
            if code not in DB["vip_only"]:
                DB["vip_only"].append(code)

        save()
        await update.message.reply_text(f"✅ Saqlandi: {code}")
        return

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text:
        return

    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text("⏳ Biroz kuting...")
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text("❌ Kod topilmadi")
        return

    if text in DB.get("vip_only",[]) and not is_vip(uid):
        await update.message.reply_text(
            "🔒 <b>Bu kino faqat VIP foydalanuvchilar uchun</b>\n\nVIP olish uchun 👉 /vip",
            parse_mode="HTML"
        )
        return

    STATS["requests"].append(now)
    STATS["users"].append((uid,now))
    save()

    sent=await context.bot.copy_message(uid,STORAGE_CHANNEL_ID,msg_id,caption=WARNING_TEXT,parse_mode="HTML")

    delete_sec=86400 if is_vip(uid) else 900
    asyncio.create_task(auto_delete(context,uid,sent.message_id,delete_sec))

# ---------- AUTO DELETE ----------

async def auto_delete(context,chat,msg,sec):
    await asyncio.sleep(sec)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ---------- RUN ----------

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
    app.add_handler(CommandHandler("ndelete",ndelete))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("done",done))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    app.run_polling()

if __name__=="__main__":
    main()
