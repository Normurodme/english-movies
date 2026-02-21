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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

REQUIRED_CHANNEL = "@moviesbyone"
ADMIN_ID = 6220077209
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 8

WARNING_TEXT = (
    "⚠️ <b>Video 15 daqiqadan keyin o‘chadi!</b>\n"
    "📥 Iltimos yuklab oling."
)

VIP_PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

# ---------------- FILES ----------------

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

# ---------------- STATES ----------------

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}

# ---------------- VIP SYSTEM ----------------

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
                await app.bot.send_message(
                    int(uid),
                    "⏳ <b>VIP obunangiz tugadi!</b>\nYangilash uchun: /vip",
                    parse_mode="HTML"
                )
            except:
                pass
            del VIP[uid]

        if expired:
            save()

        await asyncio.sleep(3600)

# ---------------- SUB CHECK ----------------

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
    await update.message.reply_text(
        "❗ <b>Botdan foydalanish uchun kanalga a’zo bo‘ling</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ---------------- START ----------------

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(
        "🎬 <b>Kino kodini yuboring</b>",
        parse_mode="HTML"
    )

# ---------------- INFO ----------------

async def info(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 <b>VIP imkoniyatlari</b>\n\n"
        "• 24 soat o‘chmaydi\n"
        "• VIP kinolar ochiladi\n"
        "• Reklama kelmaydi",
        parse_mode="HTML"
    )

# ---------------- VIP ----------------

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="buy_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="buy_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="buy_3month")]
    ])
    await update.message.reply_text(
        "👑 <b>VIP tarifni tanlang:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await info(update,context)

# ---------------- VIP LIST ADMIN ----------------

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("VIP foydalanuvchi yo‘q")
        return

    txt="👑 <b>VIP foydalanuvchilar:</b>\n\n"
    for uid,exp in VIP.items():
        txt+=f"🆔 <code>{uid}</code>\n⏳ {exp}\n\n"

    await update.message.reply_text(txt,parse_mode="HTML")

# ---------------- CALLBACK ----------------

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

# ---------------- DELETE ----------------

async def delete_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["delete"]=True
    await update.message.reply_text("🗑 O‘chirish uchun kod yuboring")

async def ndelete(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["ndelete"]=True
    await update.message.reply_text("🧹 O‘chiriladigan kodni yuboring")

# ---------------- PAYMENT ----------------

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    days=int(update.message.successful_payment.invoice_payload.split("_")[1])
    VIP[str(uid)]=(datetime.utcnow()+timedelta(days=days)).isoformat()
    save()
    await update.message.reply_text("👑 VIP muvaffaqiyatli aktivlashtirildi!")

# ---------------- MESSAGE ----------------

async def msg(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_PART

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    # ndelete fix
    if uid==ADMIN_ID and context.user_data.get("ndelete"):
        context.user_data["ndelete"]=False

        code=str(text).strip()

        if code in DB["movies"]:
            del DB["movies"][code]

            if code in DB.get("vip_only",[]):
                DB["vip_only"].remove(code)

            save()
            await update.message.reply_text(f"✅ Kod o‘chirildi: {code}")
        else:
            await update.message.reply_text("❌ Bunday kod topilmadi")

        return

    # sub check
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
        await update.message.reply_text("🔒 Bu kino VIP uchun\n👉 /vip yuboring")
        return

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

# ---------------- AUTO DELETE ----------------

async def auto_delete(context,chat,msg,sec):
    await asyncio.sleep(sec)
    try:
        await context.bot.delete_message(chat,msg)
    except:
        pass

# ---------------- RUN ----------------

async def post_init(app):
    asyncio.create_task(vip_checker(app))

def main():
    app=ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("delete",delete_cmd))
    app.add_handler(CommandHandler("ndelete",ndelete))
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
