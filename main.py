
import os
import json
import asyncio
import time
from datetime import datetime, timedelta

from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
REQUIRED_CHANNEL = "@moviesbyone"
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 8

# =========================================
# TEXT DESIGN
# =========================================

TXT_START = "🎬 <b>Kino kodini yuboring</b>\n\nMasalan: <code>12</code>"
TXT_WAIT = "⏳ Biroz kuting..."
TXT_NOT_FOUND = "❌ Bunday kod topilmadi"
TXT_SUB = "📢 <b>Botdan foydalanish uchun kanalga a’zo bo‘ling</b>"
TXT_VIP_ONLY = "🔒 Bu kino faqat VIP obunachilar uchun\n👑 /vip orqali ochiladi"
TXT_DONE = "✅ Saqlandi"
TXT_DELETED = "🗑 O‘chirildi"
TXT_SETNEXT = "📌 Hozirgi kod: <b>{}</b>\nYangi kodni yuboring"
TXT_UPDATED = "✅ Next kod yangilandi → {}"

WARNING = (
    "⚠️ <b>Video 15 daqiqadan keyin o‘chadi!</b>\n"
    "📥 Yuklab oling."
)

# =========================================
# VIP PLANS
# =========================================

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

# =========================================
# STORAGE
# =========================================

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

# FIX crash if vip_only missing
if "vip_only" not in DB:
    DB["vip_only"]=[]
USERS=load(USERS_FILE,[])
VIP=load(VIP_FILE,{})
STATS=load(STATS_FILE,{"requests":[], "users":[]})

def save():
    save_file(DB_FILE,DB)
    save_file(USERS_FILE,USERS)
    save_file(VIP_FILE,VIP)
    save_file(STATS_FILE,STATS)

# =========================================
# STATES
# =========================================

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

# =========================================
# VIP SYSTEM
# =========================================

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
                await app.bot.send_message(int(uid),"⌛ VIP muddati tugadi\nYangilash: /vip")
            except:
                pass
            del VIP[uid]

        if expired:
            save()

        await asyncio.sleep(3600)

# =========================================
# SUB CHECK
# =========================================

async def check_sub(uid,context):
    try:
        m=await context.bot.get_chat_member(REQUIRED_CHANNEL,uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga kirish",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tekshirish",callback_data="check")]
    ])
    await update.message.reply_text(TXT_SUB,reply_markup=kb,parse_mode="HTML")

# =========================================
# START
# =========================================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(TXT_START,parse_mode="HTML")

# =========================================
# DELETE COMMAND (NEW)
# =========================================

async def delete_movie(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Kod kiriting: /delete 12")
        return

    code = context.args[0]

    if code not in DB["movies"]:
        await update.message.reply_text("❌ Bu kino mavjud emas")
        return

    msg_id = DB["movies"][code]

    try:
        await context.bot.delete_message(STORAGE_CHANNEL_ID,msg_id)
    except:
        pass

    del DB["movies"][code]

    if code in DB.get("vip_only",[]):
        DB["vip_only"].remove(code)

    save()

    await update.message.reply_text(TXT_DELETED)

# =========================================
# VIP BUY PANEL
# =========================================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    text=(
        "👑 <b>VIP imkoniyatlari</b>\n\n"
        "• 24 soat o‘chmaydi\n"
        "• VIP kinolar ochiladi\n"
        "• Reklama kelmaydi"
    )

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])

    await update.message.reply_text(text,reply_markup=kb,parse_mode="HTML")

# =========================================
# VIP LIST
# =========================================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("VIP user yo‘q")
        return

    text="👑 <b>VIP FOYDALANUVCHILAR</b>\n\n"

    for uid,exp in VIP.items():
        try:
            user=await context.bot.get_chat(uid)
            name=user.username if user.username else user.full_name
        except:
            name="unknown"

        text+=f"🆔 <code>{uid}</code>\n👤 {name}\n⏳ {exp}\n\n"

    await update.message.reply_text(text,parse_mode="HTML")

# =========================================
# DOWNLOAD PANEL
# =========================================

async def download(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])
    await update.message.reply_text("📤 Yuklash turini tanlang:",reply_markup=kb)

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    if not is_vip(uid) and uid != ADMIN_ID:
        await update.message.reply_text("❌ Bu bo‘lim faqat VIP foydalanuvchilar uchun\n\n👑 VIP olish: /vip")
        return

    if update.effective_user.id!=ADMIN_ID: return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 VIP Kino",callback_data="vipmovie"),
         InlineKeyboardButton("🔒 VIP Serial",callback_data="vipserial")]
    ])
    await update.message.reply_text("🔐 VIP yuklash paneli:",reply_markup=kb)

# =========================================
# CALLBACK
# =========================================

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
        context.user_data["upload"]="movie"
        context.user_data["vip"]=False
        await q.message.edit_text("🎬 Kino yuboring")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=False
        await q.message.edit_text("📺 Serial yuboring\n/done tugatadi")

    if q.data=="vipmovie":
        context.user_data["upload"]="movie"
        context.user_data["vip"]=True
        await q.message.edit_text("🔒 VIP kino yuboring")


    # VIP PURCHASE BUTTONS
    if q.data.startswith("buy_"):
        plan=q.data.split("_")[1]
        if plan not in VIP_PLANS:
            await q.answer("Xatolik",show_alert=True)
            return

        stars,days = VIP_PLANS[plan]
        uid=str(q.from_user.id)

        expire = datetime.utcnow()+timedelta(days=days)
        VIP[uid]=expire.isoformat()
        save()

        await q.message.edit_text(
            f"✅ VIP aktivlashtirildi!\n\n⏳ Tugash: {expire.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        return

    if q.data=="vipserial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=True
        await q.message.edit_text("🔒 VIP serial yuboring")

# =========================================
# DONE SERIAL
# =========================================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE

    if update.effective_user.id!=ADMIN_ID: return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Saqlandi. Kod: {SERIAL_CODE}")
        DB["next"]+=1
        save()

    SERIAL_MODE=False

# =========================================
# NEXT CODE SETTER
# =========================================

async def ndelete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    context.user_data["setnext"]=True
    await update.message.reply_text(TXT_SETNEXT.format(DB["next"]),parse_mode="HTML")

# =========================================
# ADS
# =========================================

async def ads(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    context.user_data["ads"]=True
    await update.message.reply_text("📢 Reklama yuboring")

# =========================================
# STATS
# =========================================

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID: return

    now=time.time()
    day=86400

    users_24=set([u for u,t in STATS["users"] if now-t<day])
    req_24=len([1 for t in STATS["requests"] if now-t<day])

    txt=(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Users: <b>{len(USERS)}</b>\n"
        f"🎬 Movies: <b>{len(DB['movies'])}</b>\n"
        f"🔢 Next: <b>{DB['next']}</b>\n\n"
        f"🕒 24h users: <b>{len(users_24)}</b>\n"
        f"📥 24h requests: <b>{req_24}</b>"
    )

    await update.message.reply_text(txt,parse_mode="HTML")

# =========================================
# MESSAGE HANDLER
# =========================================

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global SERIAL_PART

    if update.message is None:
        return

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    if text and text.startswith("/"): return

    # ADS SEND
    if uid==ADMIN_ID and context.user_data.get("ads"):
        context.user_data.clear()
        sent=0
        for u in USERS:
            if u==ADMIN_ID: continue
            if is_vip(u): continue
            try:
                await update.message.copy(u)
                sent+=1
            except:
                pass
        await update.message.reply_text(f"✅ Yuborildi: {sent}")
        return

    # NEXT SET
    if uid==ADMIN_ID and context.user_data.get("setnext"):
        context.user_data.clear()
        if not text.isdigit():
            await update.message.reply_text("Faqat raqam yubor")
            return
        DB["next"]=int(text)
        save()
        await update.message.reply_text(TXT_UPDATED.format(text))
        return

    # UPLOAD
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
            DB.setdefault("vip_only",[])
        if code not in DB["vip_only"]:
            DB["vip_only"].append(code)

        context.user_data.clear()
        save()

        await update.message.reply_text(f"{TXT_DONE}: {code}")
        return

    # SUB CHECK
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text: return

    # COOLDOWN
    now=time.time()
    if uid in LAST_REQ and now-LAST_REQ[uid]<REQUEST_DELAY:
        await update.message.reply_text(TXT_WAIT)
        return
    LAST_REQ[uid]=now

    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text(TXT_NOT_FOUND)
        return

    # VIP PROTECTION
    if text in DB.setdefault("vip_only",[]) and not is_vip(uid):
        await update.message.reply_text(TXT_VIP_ONLY)
        return

    STATS["requests"].append(now)
    STATS["users"].append((uid,now))
    save()

    sent=await context.bot.copy_message(
        uid,
        STORAGE_CHANNEL_ID,
        msg_id,
        caption=WARNING,
        parse_mode="HTML"
    )

    delete_sec=86400 if is_vip(uid) else 900
    asyncio.create_task(auto_delete(context,uid,sent.message_id,delete_sec))

# =========================================
# AUTO DELETE
# =========================================

async def auto_delete(context,chat,msg,sec):
    await asyncio.sleep(sec)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# =========================================
# RUN
# =========================================

async def post_init(app):
    asyncio.create_task(vip_checker(app))

def main():

    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("vips",vips))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("ndelete",ndelete))
    app.add_handler(CommandHandler("ads",ads))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CommandHandler("done",done))
    app.add_handler(CommandHandler("delete",delete_movie))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("BOT RUNNING...")
    app.run_polling()

if __name__=="__main__":
    main()
