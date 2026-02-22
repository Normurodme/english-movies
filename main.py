import os
import json
import asyncio
import time
from datetime import datetime, timedelta

from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
CHANNEL = "@moviesbyone"
STORAGE = -1003793414081

DELAY = 8

# =========================================
# TEXT DESIGN
# =========================================

TXT_START = "🎬 <b>Kino kodini yuboring</b>\n\nMisol: <code>15</code>"
TXT_WAIT = "⏳ Kuting..."
TXT_NOT = "❌ Kod topilmadi"
TXT_SUB = "📢 <b>Botdan foydalanish uchun kanalga a'zo bo‘ling</b>"
TXT_VIP = "🔒 Bu VIP kino\n👑 /vip orqali ochiladi"
TXT_DONE = "✅ Saqlandi"
TXT_DEL = "🗑 O‘chirildi"
TXT_NEXT = "📌 Hozirgi kod: <b>{}</b>\nYangi kod yuboring"
TXT_SET = "✅ Next yangilandi → {}"

WARNING = "⚠️ <b>Video 15 daqiqadan keyin o‘chadi!</b>"

# =========================================
# VIP PLANS
# =========================================

PLANS = {
    "week": (35,7),
    "month": (125,30),
    "3month": (300,90)
}

# =========================================
# STORAGE
# =========================================

os.makedirs("data",exist_ok=True)

def load(p,d):
    return json.load(open(p)) if os.path.exists(p) else d

def savef(p,d):
    json.dump(d,open(p,"w"))

DB=load("data/db.json",{"movies":{},"next":1,"vip_only":[]})
USERS=load("data/users.json",[])
VIP=load("data/vip.json",{})
STATS=load("data/stats.json",{"req":[],"users":[]})

def save():
    savef("data/db.json",DB)
    savef("data/users.json",USERS)
    savef("data/vip.json",VIP)
    savef("data/stats.json",STATS)

# =========================================
# STATES
# =========================================

SERIAL=False
SCODE=None
SPART=1
LAST={}

# =========================================
# VIP SYSTEM
# =========================================

def is_vip(uid:int):
    exp=VIP.get(str(uid))
    if not exp: return False
    if datetime.utcnow()>datetime.fromisoformat(exp):
        del VIP[str(uid)]
        save()
        return False
    return True

async def vip_loop(app):
    while True:
        now=datetime.utcnow()
        expired=[]
        for uid,exp in list(VIP.items()):
            if now>datetime.fromisoformat(exp):
                expired.append(uid)
        for uid in expired:
            del VIP[uid]
            try:
                await app.bot.send_message(uid,"⌛ VIP tugadi\n/vip orqali yangilang")
            except: pass
        if expired: save()
        await asyncio.sleep(3600)

# =========================================
# SUB CHECK
# =========================================

async def sub(uid,ctx):
    try:
        m=await ctx.bot.get_chat_member(CHANNEL,uid)
        return m.status in ["member","administrator","creator"]
    except:
        return False

async def submsg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanal",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Tekshirish",callback_data="check")]
    ])
    await update.message.reply_text(TXT_SUB,reply_markup=kb,parse_mode="HTML")

# =========================================
# START
# =========================================

async def start(update,ctx):
    uid=update.effective_user.id

    if uid not in USERS:
        USERS.append(uid)
        save()

    if not await sub(uid,ctx):
        await submsg(update)
        return

    await update.message.reply_text(TXT_START,parse_mode="HTML")

# =========================================
# VIP PANEL
# =========================================

async def vip(update,ctx):

    text="👑 <b>VIP tariflar</b>\n\nVIP foyda:\n• Reklamasiz\n• VIP kino\n• Video o‘chmaydi"

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ 1 hafta — 35",callback_data="pay_week")],
        [InlineKeyboardButton("⭐ 1 oy — 125",callback_data="pay_month")],
        [InlineKeyboardButton("⭐ 3 oy — 300",callback_data="pay_3month")]
    ])

    await update.message.reply_text(text,reply_markup=kb,parse_mode="HTML")

# =========================================
# PAYMENT
# =========================================

async def precheckout(update,ctx):
    await update.pre_checkout_query.answer(ok=True)

async def success(update,ctx):
    uid=update.effective_user.id
    plan=update.message.successful_payment.invoice_payload
    price,days=PLANS[plan]

    exp=datetime.utcnow()+timedelta(days=days)
    VIP[str(uid)]=exp.isoformat()
    save()

    await update.message.reply_text("✅ VIP aktiv!")

# =========================================
# VIP LIST
# =========================================

async def vips(update,ctx):
    if update.effective_user.id!=ADMIN_ID: return
    if not VIP:
        await update.message.reply_text("VIP yo‘q")
        return

    t="👑 VIP USERS\n\n"
    for uid,exp in VIP.items():
        t+=f"{uid}\n{exp}\n\n"
    await update.message.reply_text(t)

# =========================================
# DOWNLOAD PANEL
# =========================================

async def download(update,ctx):
    if update.effective_user.id!=ADMIN_ID: return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])
    await update.message.reply_text("Tur tanlang:",reply_markup=kb)

async def vipdownload(update,ctx):
    if update.effective_user.id!=ADMIN_ID: return
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 VIP Kino",callback_data="vmovie"),
         InlineKeyboardButton("🔒 VIP Serial",callback_data="vserial")]
    ])
    await update.message.reply_text("VIP yuklash:",reply_markup=kb)

# =========================================
# CALLBACK
# =========================================

async def cb(update,ctx):

    global SERIAL,SCODE,SPART

    q=update.callback_query
    await q.answer()

    if q.data=="check":
        if await sub(q.from_user.id,ctx):
            await q.message.edit_text("✅ Tasdiqlandi")

    if q.data=="movie":
        ctx.user_data["up"]="movie"
        ctx.user_data["vip"]=False
        await q.message.edit_text("Kino yubor")

    if q.data=="serial":
        SERIAL=True
        SCODE=str(DB["next"])
        SPART=1
        ctx.user_data["up"]="serial"
        ctx.user_data["vip"]=False
        await q.message.edit_text("Serial yubor")

    if q.data=="vmovie":
        ctx.user_data["up"]="movie"
        ctx.user_data["vip"]=True
        await q.message.edit_text("VIP kino yubor")

    if q.data=="vserial":
        SERIAL=True
        SCODE=str(DB["next"])
        SPART=1
        ctx.user_data["up"]="serial"
        ctx.user_data["vip"]=True
        await q.message.edit_text("VIP serial yubor")

    # payment
    if q.data.startswith("pay_"):
        plan=q.data.split("_")[1]
        price,_=PLANS[plan]

        await ctx.bot.send_invoice(
            q.from_user.id,
            title="VIP",
            description="VIP obuna",
            payload=plan,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("VIP",price)]
        )

# =========================================
# DELETE
# =========================================

async def delete(update,ctx):
    if update.effective_user.id!=ADMIN_ID: return
    if not ctx.args:
        await update.message.reply_text("Kod yoz: /delete 15")
        return
    code=ctx.args[0]

    if code not in DB["movies"]:
        await update.message.reply_text("Topilmadi")
        return

    del DB["movies"][code]
    if code in DB["vip_only"]:
        DB["vip_only"].remove(code)

    save()
    await update.message.reply_text(TXT_DEL)

# =========================================
# NEXT
# =========================================

async def ndelete(update,ctx):
    if update.effective_user.id!=ADMIN_ID:return
    ctx.user_data["next"]=True
    await update.message.reply_text(TXT_NEXT.format(DB["next"]),parse_mode="HTML")

# =========================================
# MSG HANDLER
# =========================================

async def msg(update,ctx):

    global SPART

    if not update.message: return

    uid=update.effective_user.id
    text=update.message.text.strip() if update.message.text else None

    if text and text.startswith("/"): return

    # next set
    if uid==ADMIN_ID and ctx.user_data.get("next"):
        ctx.user_data.clear()
        if text.isdigit():
            DB["next"]=int(text)
            save()
            await update.message.reply_text(TXT_SET.format(text))
        return

    # upload
    if uid==ADMIN_ID and ctx.user_data.get("up") and (update.message.video or update.message.document):

        if ctx.user_data["up"]=="movie":
            code=str(DB["next"])
            DB["next"]+=1
        else:
            code=f"{SCODE}.{SPART}"
            SPART+=1

        cap=f"🔒Code: {code}" if ctx.user_data["vip"] else f"Code: {code}"

        sent=await ctx.bot.copy_message(
            STORAGE,
            update.effective_chat.id,
            update.message.message_id,
            caption=cap
        )

        DB["movies"][code]=sent.message_id

        if ctx.user_data["vip"]:
            DB["vip_only"].append(code)

        ctx.user_data.clear()
        save()

        await update.message.reply_text(f"{TXT_DONE}: {code}")
        return

    # sub
    if not await sub(uid,ctx):
        await submsg(update)
        return

    if not text: return

    # cooldown
    now=time.time()
    if uid in LAST and now-LAST[uid]<DELAY:
        await update.message.reply_text(TXT_WAIT)
        return
    LAST[uid]=now

    mid=DB["movies"].get(text)
    if not mid:
        await update.message.reply_text(TXT_NOT)
        return

    # vip protect
    if text in DB["vip_only"] and not is_vip(uid):
        await update.message.reply_text(TXT_VIP)
        return

    STATS["req"].append(now)
    STATS["users"].append((uid,now))
    save()

    sent=await ctx.bot.copy_message(uid,STORAGE,mid,caption=WARNING,parse_mode="HTML")

    sec=86400 if is_vip(uid) else 900
    asyncio.create_task(auto_del(ctx,uid,sent.message_id,sec))

# =========================================
# AUTO DELETE
# =========================================

async def auto_del(ctx,chat,msg,sec):
    await asyncio.sleep(sec)
    try:
        await ctx.bot.delete_message(chat,msg)
    except: pass

# =========================================
# RUN
# =========================================

async def post(app):
    asyncio.create_task(vip_loop(app))

def main():

    app=ApplicationBuilder().token(TOKEN).post_init(post).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("vip",vip))
    app.add_handler(CommandHandler("vips",vips))
    app.add_handler(CommandHandler("download",download))
    app.add_handler(CommandHandler("vipdownload",vipdownload))
    app.add_handler(CommandHandler("delete",delete))
    app.add_handler(CommandHandler("ndelete",ndelete))

    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL,msg))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,success))

    print("BOT RUNNING")
    app.run_polling()

if __name__=="__main__":
    main()
