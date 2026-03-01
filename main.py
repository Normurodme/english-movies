import os
import json
import asyncio
import time
import re
from datetime import datetime, timedelta

from telegram import *
from telegram.ext import *

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
REQUIRED_CHANNEL = "@moviesbyone"
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 5
MESSAGE_CHANNEL = "@xabarkino"


# =========================================
# TEXT DESIGN
# =========================================

TXT_START = "🎬 <b>Send movie code</b>\n\nExample: <code>12</code>"
TXT_WAIT = "⏳ Please wait a bit..."
TXT_NOT_FOUND = "❌ Such code was not found"
TXT_SUB = "📢 <b>Join the channel to use the bot</b>"
TXT_VIP_ONLY = "🔒 This movie is only for VIP subscribers\n👑 Unlock via /vip"
TXT_DONE = "✅ Saved"
TXT_DELETED = "🗑 Deleted"
TXT_SETNEXT = "📌 Current code: <b>{}</b>\nSend new code"
TXT_UPDATED = "✅ Next code updated → {}"

WARNING = (
    "⚠️ <b>Video will be deleted after 15 minutes!</b>\n"
    "📥 Download it."
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

DB=load(DB_FILE,{"movies":{}, "next":1, "vip_only":[], "catalog":{}})

# FIX crash if vip_only missing
if "vip_only" not in DB:
    DB["vip_only"]=[]

# NORMALIZE VIP_ONLY TYPES
if "vip_only" in DB:
    DB["vip_only"] = [str(x) for x in DB["vip_only"]]

USERS=load(USERS_FILE,[])
VIP=load(VIP_FILE,{})
STATS=load(STATS_FILE,{"requests":[], "users":[], "codes":[]})
BANNED_FILE="/data/banned.json"
BANNED=load(BANNED_FILE,[])


def save():
    save_file(DB_FILE,DB)
    save_file(USERS_FILE,USERS)
    save_file(VIP_FILE,VIP)
    save_file(STATS_FILE,STATS)
    save_file(BANNED_FILE,BANNED)

# =========================================
# STATES
# =========================================

SERIAL_MODE=False
SERIAL_CODE=None
SERIAL_PART=1
LAST_REQ={}
USER_REQS={}

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
                await app.bot.send_message(int(uid),"⌛ VIP expired\nRenew: /vip")
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
        [InlineKeyboardButton("📢 Join channel",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Check",callback_data="check")]
    ])
    await update.message.reply_text(TXT_SUB,reply_markup=kb,parse_mode="HTML")

# =========================================
# START
# =========================================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    if str(uid) in BANNED:
        await update.message.reply_text("You are banned 🚫")
        return

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
        await update.message.reply_text("Enter code: /delete 12")
        return

    code = context.args[0]

    if code not in DB["movies"]:
        await update.message.reply_text("❌ This movie does not exist")
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
# ADD VIP MOVIE
# =========================================
async def addvip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /addvip code")
        return

    code=str(context.args[0])

    if code not in DB["movies"]:
        await update.message.reply_text("❌ Code not found")
        return

    DB.setdefault("vip_only",[])

    if code in DB["vip_only"]:
        await update.message.reply_text("⚠️ Already VIP")
        return

    DB["vip_only"].append(code)
    save()

    await update.message.reply_text(f"✅ {code} added to VIP list")


# =========================================
# REMOVE VIP MOVIE
# =========================================
async def delvip(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /delvip code")
        return

    code=str(context.args[0])

    if code not in DB.get("vip_only",[]):
        await update.message.reply_text("❌ This code is not VIP")
        return

    DB["vip_only"].remove(code)
    save()

    await update.message.reply_text(f"✅ {code} removed from VIP list")


# =========================================
# VIP BUY PANEL
# =========================================

async def vip(update:Update,context:ContextTypes.DEFAULT_TYPE):

    text=(
        "👑 <b>VIP privileges</b>\n\n"
        "• 6 soat will not be deleted\n"
        "• VIP movies unlock\n"
        "• No ads"
    )

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("1 week — 35 ⭐️",callback_data="buy_week")],
        [InlineKeyboardButton("1 month — 125 ⭐️",callback_data="buy_month")],
        [InlineKeyboardButton("3 months — 300 ⭐️",callback_data="buy_3month")]
    ])

    await update.message.reply_text(text,reply_markup=kb,parse_mode="HTML")

# =========================================
# VIP LIST
# =========================================

async def vips(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    if not VIP:
        await update.message.reply_text("No VIP users")
        return

    text="👑 <b>VIP USERS</b>\n\n"

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
    await update.message.reply_text("📤 Choose upload type:",reply_markup=kb)

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    if not is_vip(uid) and uid != ADMIN_ID:
        await update.message.reply_text("❌ This section is only for VIP users\n\n👑 Get VIP: /vip")
        return

    if update.effective_user.id!=ADMIN_ID: return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 VIP Kino",callback_data="vipmovie"),
         InlineKeyboardButton("🔒 VIP Serial",callback_data="vipserial")]
    ])
    await update.message.reply_text("🔐 VIP upload panel:",reply_markup=kb)

# =========================================
# CALLBACK
# =========================================

async def callbacks(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global SERIAL_MODE,SERIAL_CODE,SERIAL_PART

    q=update.callback_query
    await q.answer()

    # BUY VIP
    if q.data.startswith("buy_"):

        plan=q.data.split("_")[1]
        stars,days=VIP_PLANS[plan]

        prices=[LabeledPrice(label="VIP", amount=stars)]

        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title="VIP Subscription",
            description=f"{days} days VIP subscription",
            payload=f"vip_{plan}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return


    if q.data=="check":
        if await check_sub(q.from_user.id,context):
            await q.message.edit_text("✅ Confirmed")
        else:
            await q.answer("Join channel",show_alert=True)

    if q.data=="movie":
        context.user_data["upload"]="movie"
        context.user_data["vip"]=False
        await q.message.edit_text("🎬 Send movie")

    if q.data=="serial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=False
        await q.message.edit_text("📺 Send series\n/done finishes")

    if q.data=="vipmovie":
        context.user_data["upload"]="movie"
        context.user_data["vip"]=True
        await q.message.edit_text("🔒 Send VIP movie")

    if q.data=="vipserial":
        SERIAL_MODE=True
        SERIAL_CODE=str(DB["next"])
        SERIAL_PART=1
        context.user_data["upload"]="serial"
        context.user_data["vip"]=True
        await q.message.edit_text("🔒 Send VIP series")

# =========================================
# DONE SERIAL
# =========================================

async def done(update:Update,context:ContextTypes.DEFAULT_TYPE):
    global SERIAL_MODE

    if update.effective_user.id!=ADMIN_ID: return

    if SERIAL_MODE:
        await update.message.reply_text(f"✅ Saved. Kod: {SERIAL_CODE}")
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
    await update.message.reply_text("📢 Send advertisement")

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
        "📊 <b>STATISTICS</b>\n\n"
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

    if str(uid) in BANNED:
        await update.message.reply_text("You are banned 🚫")
        return

    text = update.message.text if update.message.text else None
    if text:
        text = text.strip().replace(" ", "").replace("\n","").replace("\r","")

    if text and text.startswith("/"): return

    
    # EDITTITLE FLOW STEP1
    if uid==ADMIN_ID and context.user_data.get("edit_step")=="code":
        code_val=update.message.text.strip()
        context.user_data["edit_code"]=code_val
        context.user_data["edit_step"]="title"
        await update.message.reply_text("Send new title")
        return

    # EDITTITLE FLOW STEP2
    if uid==ADMIN_ID and context.user_data.get("edit_step")=="title":
        title=update.message.text.strip()
        code_val=context.user_data["edit_code"]

        DB.setdefault("catalog",{})
        DB["catalog"].setdefault(code_val,{})
        DB["catalog"][code_val]["title"]=title
        DB["catalog"][code_val].setdefault("msg_id",None)
        DB["catalog"][code_val].setdefault("date",time.time())

        save()
        context.user_data.clear()
        await update.message.reply_text(f"✅ {code_val} → {title}")
        return


    # ADDTITLE FLOW
    if uid==ADMIN_ID and context.user_data.get("addtitle"):
        if update.message.text=="/stop":
            context.user_data.clear()
            await update.message.reply_text("Stopped.")
            return

        title=update.message.text.strip()
        code=str(len(DB.get("catalog",{}))+1)

        DB.setdefault("catalog",{})
        DB["catalog"][code]={
            "title":title,
            "msg_id":None,
            "date":time.time()
        }
        save()

        await update.message.reply_text(f"✅ {code} → {title}")
        return

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
        await update.message.reply_text(f"✅ Sent: {sent}")
        return

    # NEXT SET
    if uid==ADMIN_ID and context.user_data.get("setnext"):
        context.user_data.clear()
        if not text.isdigit():
            await update.message.reply_text("Send numbers only")
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

        # ===== FIX: SERIAL MODE CLEAR BO'LMAYDI =====
        if context.user_data["upload"]=="movie":
            context.user_data.clear()

        save()

        await update.message.reply_text(f"{TXT_DONE}: {code}")
        return

    
    # MESSAGE FLOW
    if context.user_data.get("msg_mode"):
        mode=context.user_data.get("msg_mode")

        # ADMIN REPLY TO USER
        if mode=="admin":
            target=context.user_data.get("msg_target")
            try:
                await update.message.copy(target)
                await update.message.reply_text("✅ Sent")
            except:
                await update.message.reply_text("❌ Failed to send")
            context.user_data.clear()
            return

        # USER SEND TO CHANNEL
        if mode=="user":
            try:
                txt=update.message.text or ""
                await context.bot.send_message(
                    MESSAGE_CHANNEL,
                    f"📩 Message from {uid}:\n{txt}"
                )
                await update.message.reply_text("✅ Sent to admin")
            except:
                await update.message.reply_text("❌ Failed")
            context.user_data.clear()
            return

    # SUB CHECK
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text: return

    
    # LIMIT + COOLDOWN
    now=time.time()
    vip_user=is_vip(uid)

    delay = 5 if vip_user else 10
    daily_limit = 30 if vip_user else 15

    # cooldown
    if uid in LAST_REQ and now-LAST_REQ[uid]<delay:
        await update.message.reply_text(TXT_WAIT)
        return

    LAST_REQ[uid]=now

    # daily limit
    logs=USER_REQS.get(uid,[])
    logs=[t for t in logs if now-t<86400]
    if len(logs)>=daily_limit:
        await update.message.reply_text("❌ Daily request limit reached")
        return

    logs.append(now)
    USER_REQS[uid]=logs


    msg_id=DB["movies"].get(text)
    if not msg_id:
        await update.message.reply_text(TXT_NOT_FOUND)
        return

    # VIP PROTECTION
    vip_list = set(str(x) for x in DB.get("vip_only",[]))
    if text in vip_list and not is_vip(uid):
        await update.message.reply_text(TXT_VIP_ONLY)
        return

    STATS["requests"].append(now)
    STATS.setdefault("codes",[]).append((text,now))
    STATS["users"].append((uid,now))
    save()

    sent=await context.bot.copy_message(
        uid,
        STORAGE_CHANNEL_ID,
        msg_id,
        caption=WARNING,
        parse_mode="HTML"
    )

    delete_sec=21600 if is_vip(uid) else 900
    asyncio.create_task(auto_delete(context,uid,sent.message_id,delete_sec))


# =========================================
# CHANNEL POST CAPTURE (SAVE MOVIE NAME)
# =========================================
async def channel_post(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if not update.channel_post:
        return

    msg = update.channel_post

    if not msg.chat.username:
        return

    if msg.chat.username.lower() != REQUIRED_CHANNEL.replace("@","").lower():
        return

    text = msg.text or msg.caption or ""
    if not text:
        return

    title = text.split("\n")[0].strip()

    m=re.search(r'(?:Code|CODE|code)\s*[:\-]\s*(\S+)', text)
    if not m:
        return

    code_val=m.group(1)

    DB.setdefault("catalog",{})
    DB["catalog"][code_val]={
        "title":title,
        "msg_id":msg.message_id,
        "date":time.time()
    }

    save()
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
# PAYMENT HANDLERS
# =========================================

async def precheckout(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update:Update,context:ContextTypes.DEFAULT_TYPE):

    payment=update.message.successful_payment
    payload=payment.invoice_payload

    if not payload.startswith("vip_"):
        return

    plan=payload.split("_")[1]
    stars,days=VIP_PLANS[plan]

    uid=str(update.effective_user.id)
    expire=datetime.utcnow()+timedelta(days=days)

    VIP[uid]=expire.isoformat()
    save()

    await update.message.reply_text(
        f"👑 VIP aktivlashtirildi!\n⏳ Tugash: {expire.date()}"
    )


# =========================================
# BAN SYSTEM
# =========================================

async def ban_user(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /ban id")
        return

    uid=context.args[0]

    if uid not in BANNED:
        BANNED.append(uid)
        save()

    await update.message.reply_text(f"🚫 Banned: {uid}")

async def unban_user(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban id")
        return

    uid=context.args[0]

    if uid in BANNED:
        BANNED.remove(uid)
        save()
        await update.message.reply_text(f"✅ Unbanned: {uid}")
    else:
        await update.message.reply_text("❌ User is not banned")



# =========================================
# MESSAGE SYSTEM
# =========================================

async def message_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    # ADMIN MODE
    if uid==ADMIN_ID and context.args:
        try:
            target=int(context.args[0])
        except:
            await update.message.reply_text("Invalid ID")
            return

        context.user_data["msg_mode"]="admin"
        context.user_data["msg_target"]=target
        await update.message.reply_text("Do you have message to user ?")
        return

    # USER MODE
    context.user_data["msg_mode"]="user"
    await update.message.reply_text("Do you have message to administator ?")



# =========================================
# GET DB FILE (ADMIN)
# =========================================
async def getdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        await update.message.reply_document(open(DB_FILE,"rb"))
    except:
        await update.message.reply_text("DB file not found")



# =========================================
# LOAD DB FROM FILE (ADMIN)
# =========================================

# =========================================
# LOAD DB FROM FILE (ADMIN) — FIXED
# =========================================
async def loaddb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.document:
        await update.message.reply_text("❌ Send JSON file as document")
        return

    try:
        file = await update.message.document.get_file()
        await file.download_to_drive(DB_FILE)

        with open(DB_FILE) as f:
            data = json.load(f)

        if "movies" not in data:
            raise Exception("Invalid DB structure")

        global DB
        DB = data
        save()

        await update.message.reply_text("✅ DB loaded successfully")

    except Exception as e:
        await update.message.reply_text(f"❌ Load failed: {e}")



# =========================================
# ADDTITLE SYSTEM
# =========================================
async def addtitle(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    context.user_data["addtitle"]=True
    await update.message.reply_text("Send titles one by one. Send /stop to finish")

async def edittitle(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

# =========================================
# TITLES LIST (ADMIN)
# =========================================
async def titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    catalog = DB.get("catalog", {})

    if not catalog:
        await update.message.reply_text("❌ No titles found")
        return

    text = "🎬 <b>All Movie Titles</b>"

    for code, data in sorted(catalog.items(), key=lambda x: x[0]):
        title = data.get("title", "No title")
        text += f"🔢 <b>{code}</b> — {title}"

    await update.message.reply_text(text, parse_mode="HTML")

    context.user_data["edit_step"]="code"
    await update.message.reply_text("Send movie code to edit")


# =========================================
# RUN
# =========================================

async def post_init(app):
    asyncio.create_task(vip_checker(app))


# =========================================
# TOP COMMAND
# =========================================
async def top_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Week", callback_data="top_week"),
            InlineKeyboardButton("Month", callback_data="top_month")
        ]
    ])
    await update.message.reply_text("Choose period",reply_markup=kb)


async def top_callback(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()

    period = 7 if "week" in q.data else 30
    period_name = "WEEK" if period==7 else "MONTH"

    now=time.time()
    limit=now-(period*86400)

    stats={}
    for code_val,t in STATS.get("codes",[]):
        if t>=limit:
            stats[code_val]=stats.get(code_val,0)+1

    if not stats:
        await q.message.edit_text("No statistics yet")
        return

    top=sorted(stats.items(), key=lambda x:x[1], reverse=True)[:10]

    text = f"<b>TOP {period_name}</b>\n"
    text += "──────────────────\n\n"

    for i,(c,count) in enumerate(top,1):
        title = DB.get("catalog",{}).get(c,{}).get("title","Unknown")

        text += (
            f"{i}. <b>{title}</b>\n"
            f"   Code: <code>{c}</code>\n"
            f"   Requests: {count}\n\n"
        )

    text += "──────────────────"

    await q.message.edit_text(text,parse_mode="HTML")

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
    app.add_handler(CommandHandler("addvip",addvip))
    app.add_handler(CommandHandler("delvip",delvip))
    app.add_handler(CommandHandler("ban",ban_user))
    app.add_handler(CommandHandler("unban",unban_user))
    app.add_handler(CommandHandler("message",message_cmd))
    app.add_handler(CommandHandler("top",top_cmd))
    app.add_handler(CommandHandler("addtitle",addtitle))
    app.add_handler(CommandHandler("edittitle",edittitle))
    app.add_handler(CommandHandler("titles", titles))
    app.add_handler(CommandHandler("getdb", getdb))
    app.add_handler(CommandHandler("loaddb", loaddb))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment))

    app.add_handler(CallbackQueryHandler(top_callback,pattern="^top_"))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL,msg))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL,channel_post))

    print("BOT RUNNING...")
    app.run_polling()

if __name__=="__main__":
    main()
    
