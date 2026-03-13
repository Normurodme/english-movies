import os
import json
import asyncio
import time
import re
from datetime import datetime, timedelta

from telegram import *
from telegram import ReplyKeyboardMarkup
from telegram.ext import *

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_ID = 6220077209
REQUIRED_CHANNEL = "@moviesbyone"
STORAGE_CHANNEL_ID = -1003793414081

REQUEST_DELAY = 5
MESSAGE_CHANNEL = "@xabarkino"

# =========================================
# QUEUE SYSTEM (25 req/sec)
# =========================================
SEND_QUEUE = asyncio.Queue()

async def queue_worker():
    while True:
        context, uid, msg_id, vip_flag, title = await SEND_QUEUE.get()
        try:
            sent = await context.bot.copy_message(
                uid,
                STORAGE_CHANNEL_ID,
                msg_id,
                caption=f"Name : {title}\n\n{WARNING}",
                parse_mode="HTML"
            )
            delete_sec = 21600 if vip_flag else 900
            asyncio.create_task(auto_delete(context, uid, sent.message_id, delete_sec))
        except:
            pass
        await asyncio.sleep(0.04)



# =========================================
# TEXT DESIGN
# =========================================

TXT_START = (
    "🎬 <b>English Movie Time</b>\n\n"
    "Send movie code\n"
    "Example: <code>12</code>\n\n"
    "🔎 /search  |  👑 /vip"
)
TXT_WAIT = "⏳ Processing your request... Please wait"
TXT_NOT_FOUND = "❌ Movie not found\n\n🔎 Try Search to find by name"
TXT_SUB = (
    "🍿 <b>Welcome Movie Lover</b>\n\n"
    "📢 Join channel to use the bot\n"
    "Then press ✅ Check"
)
TXT_VIP_ONLY = (
    "🔒 This movie for only VIP users \n"
    "🔑 Unlock with 👑 VIP"
)
TXT_DONE = "✅ Saved"
TXT_DELETED = "🗑 Deleted"
TXT_SETNEXT = "📌 Current code: <b>{}</b>\nSend new code"
TXT_UPDATED = "✅ Next code updated → {}"

WARNING = (
    "⚠️ <b>This video will be deleted automatically</b>\n"
    "📥 Download now"
)


# =========================================
# USER MENU KEYBOARD
# =========================================
USER_MENU = ReplyKeyboardMarkup(
    [
        ["Search 🔍", "Top 🔝"],
        ["Vip 🔐", "🎬 Request Movie"],
        ["Referral"]
    ],
    resize_keyboard=True
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

DB=load(DB_FILE,{"movies":{}, "next":1, "next_title":1, "vip_only":[], "catalog":{}, "ref_meta":{}})

# Ensure referral meta exists inside DB
if "ref_meta" not in DB:
    DB["ref_meta"] = {}


# FIX crash if vip_only missing
if "vip_only" not in DB:
    DB["vip_only"]=[]

if "next_title" not in DB:
    DB["next_title"]=1

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

# ================= OPTIMIZATION =================

DIRTY_STATS = False
SUB_CACHE = {}  # {uid: (is_member, expire_time)}

def mark_stats_dirty():
    global DIRTY_STATS
    DIRTY_STATS = True

async def autosave_stats_loop():
    global DIRTY_STATS
    while True:
        if DIRTY_STATS:
            limit = time.time() - 86400 * 31
            STATS["requests"] = [t for t in STATS["requests"] if t > limit]
            STATS["users"] = [(u, t) for u, t in STATS["users"] if t > limit]
            STATS["codes"] = [(c, t) for c, t in STATS["codes"] if t > limit]
            save()
            DIRTY_STATS = False
        await asyncio.sleep(30)


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

# SUB CHECK
# =========================================

async def check_sub(uid,context):
    now = time.time()

    if uid in SUB_CACHE:
        is_member, expire = SUB_CACHE[uid]
        if now < expire:
            return is_member

    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL, uid)
        is_member = m.status in ["member","administrator","creator"]
    except:
        is_member = False

    SUB_CACHE[uid] = (is_member, now + 420)
    return is_member

async def sub_msg(update):
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join channel",url="https://t.me/moviesbyone")],
        [InlineKeyboardButton("✅ Check",callback_data="check")]
    ])
    await update.message.reply_text(TXT_SUB,reply_markup=kb,parse_mode="HTML")


# =========================================
# REFERRAL SYSTEM
# =========================================

REF_FILE = "/data/referrals.json"
USED_REF_FILE = "/data/used_ref.json"

REFERRALS = load(REF_FILE, {})
USED_REF = load(USED_REF_FILE, {})

def save_ref():
    save_file(REF_FILE, REFERRALS)
    save_file(USED_REF_FILE, USED_REF)


def add_referral(referrer_id, new_user_id):
    referrer_id = str(referrer_id)
    new_user_id = str(new_user_id)

    # HARD protection: check DB ref_meta
    if new_user_id in DB.get("ref_meta", {}):
        return

    if referrer_id == new_user_id:
        return

    DB.setdefault("ref_meta", {})
    DB["ref_meta"][new_user_id] = referrer_id

    REFERRALS.setdefault(referrer_id, 0)
    REFERRALS[referrer_id] += 1

    count = REFERRALS[referrer_id]
    now = datetime.utcnow()

    reward_days = 0
    if count % 5 == 0:
        if count % 10 == 0:
            reward_days = 3
        else:
            reward_days = 1

    if reward_days > 0:
        current_exp = VIP.get(referrer_id)
        if current_exp:
            current_exp_dt = datetime.fromisoformat(current_exp)
            if current_exp_dt > now:
                expire = current_exp_dt + timedelta(days=reward_days)
            else:
                expire = now + timedelta(days=reward_days)
        else:
            expire = now + timedelta(days=reward_days)

        VIP[referrer_id] = expire.isoformat()

    save()
    save_ref()


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

    # store pending referral (do NOT count yet)
    if context.args:
        try:
            referrer = int(context.args[0])
            context.user_data["pending_ref"] = referrer
        except:
            pass

    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    await update.message.reply_text(TXT_START,parse_mode="HTML", reply_markup=USER_MENU)

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
        "👑 <b>Premium VIP Membership</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ Faster delivery\n"
        "🔓 VIP exclusive movies\n"
        "🚫 No advertisements\n"
        "🕒 Extended watch time\n"
        "🏆 Priority support\n\n"
        "Choose your plan below:"
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

    global SERIAL_MODE
    SERIAL_MODE = False
    context.user_data.clear()
    if update.effective_user.id!=ADMIN_ID: return

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino",callback_data="movie"),
         InlineKeyboardButton("📺 Serial",callback_data="serial")]
    ])
    await update.message.reply_text("📤 Choose upload type:",reply_markup=kb)

async def vipdownload(update:Update,context:ContextTypes.DEFAULT_TYPE):

    global SERIAL_MODE
    SERIAL_MODE = False
    context.user_data.clear()

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
        try:
            m = await context.bot.get_chat_member(REQUIRED_CHANNEL, q.from_user.id)
            is_member = m.status in ["member","administrator","creator"]
        except:
            is_member = False

        SUB_CACHE.pop(q.from_user.id, None)

        if is_member:

            # CONFIRM REFERRAL ONLY AFTER CHANNEL JOIN
            referrer = context.user_data.get("pending_ref")
            if referrer and str(q.from_user.id) not in USED_REF and referrer != q.from_user.id:
                add_referral(referrer, q.from_user.id)
                context.user_data.pop("pending_ref", None)

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
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data.clear()
    context.user_data["setnext"]=True

    await update.message.reply_text(
        f"📌 Current code: <b>{DB['next']}</b>\nSend new code",
        parse_mode="HTML"
    )

async def ntitle(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    context.user_data.clear()
    context.user_data["setnexttitle"]=True

    await update.message.reply_text(
        f"📌 Current title code: <b>{DB.get('next_title',1)}</b>\nSend new title code",
        parse_mode="HTML"
    )

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
        text = text.strip()

    if text and text.startswith("/"):
        context.user_data.pop("search_mode", None)
        context.user_data.pop("msg_mode", None)
        return

    # ================= EDITTITLE FLOW =================

    # STEP 1 — CODE
    if uid==ADMIN_ID and context.user_data.get("edit_step")=="code":

        code_val = str(update.message.text.strip())

        catalog = {str(k): v for k,v in DB.get("catalog", {}).items()}

        if code_val not in catalog:
            await update.message.reply_text("❌ Bunday kod topilmadi")
            return

        context.user_data["edit_code"] = code_val
        context.user_data["edit_step"] = "title"

        await update.message.reply_text(
            f"{code_val} uchun yangi title jo'nating"
        )
        return


    # STEP 2 — NEW TITLE
    if uid==ADMIN_ID and context.user_data.get("edit_step")=="title":

        new_title = update.message.text.strip()
        code_val = context.user_data.get("edit_code")

        if not code_val:
            context.user_data.clear()
            return

        DB.setdefault("catalog", {})
        DB["catalog"].setdefault(code_val, {})

        DB["catalog"][code_val]["title"] = new_title
        DB["catalog"][code_val].setdefault("msg_id", None)
        DB["catalog"][code_val].setdefault("date", time.time())

        save()
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ {code_val} new title - {new_title}"
        )
        return




    # ADDTITLE FLOW
    if uid==ADMIN_ID and context.user_data.get("addtitle"):
        if update.message.text=="/stop":
            context.user_data.clear()
            await update.message.reply_text("Stopped.")
            return

        title=update.message.text.strip()
        code=str(DB.get("next_title",1))

        _nt = str(DB.get("next_title",1))

        if "." in _nt:
            base,dec=_nt.split(".",1)
            DB["next_title"]=f"{base}.{int(dec)+1}"
        else:
            DB["next_title"]=int(_nt)+1

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
        await update.message.reply_text(f"✅ Next code updated → {text}")
        return

    # NEXT TITLE SET
    if uid==ADMIN_ID and context.user_data.get("setnexttitle"):
        context.user_data.clear()
        if not re.match(r'^\d+(\.\d+)?$', text):
            await update.message.reply_text("Send number like 88 or 88.1")
            return
        DB["next_title"]=text
        save()
        await update.message.reply_text(f"✅ Next title code updated → {text}")
        return


    
    # ================= UPLOAD FIXED =================
    if uid == ADMIN_ID and context.user_data.get("upload") and (
        update.message.video or update.message.document
    ):

        try:

            if context.user_data["upload"]=="movie":
                code=str(DB["next"])
                DB["next"]+=1
            else:
                code=f"{SERIAL_CODE}.{SERIAL_PART}"
                SERIAL_PART+=1

            caption = f"🔒Code: {code}" if context.user_data.get("vip") else f"Code: {code}"

            sent = await context.bot.copy_message(
                chat_id=STORAGE_CHANNEL_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )

            try:
                await context.bot.edit_message_caption(
                    chat_id=STORAGE_CHANNEL_ID,
                    message_id=sent.message_id,
                    caption=caption
                )
            except:
                pass

            DB["movies"][code]=sent.message_id

            if context.user_data.get("vip"):
                DB.setdefault("vip_only",[])
                if code not in DB["vip_only"]:
                    DB["vip_only"].append(code)

            if context.user_data["upload"]=="movie":
                context.user_data.clear()

            save()

            await update.message.reply_text(f"{TXT_DONE}: {code}")

        except Exception as e:
            await update.message.reply_text(f"❌ Upload error:\n{e}")

        return
    # =================================================


    # SUB CHECK
    if not await check_sub(uid,context):
        await sub_msg(update)
        return

    if not text: return

    # MENU BUTTONS (process these BEFORE message-mode)
    if text and text.startswith("Search"):
        context.user_data.pop("msg_mode", None)

        kb = ReplyKeyboardMarkup(
            [
                ["By Name", "By Code"],
                ["Back"]
            ],
            resize_keyboard=True
        )

        await update.message.reply_text(
            "Choose search method",
            reply_markup=kb
        )
        return

    if text == "By Name":
        context.user_data["search_mode"] = "name"
        await update.message.reply_text("Send movie name")
        return

    if text == "By Code":
        context.user_data["search_mode"] = "code"
        await update.message.reply_text("Send movie code")
        return

    if text == "Back":
        context.user_data.pop("search_mode", None)

        await update.message.reply_text(
            TXT_START,
            parse_mode="HTML",
            reply_markup=USER_MENU
        )
        return


    if text and text.startswith("Top"):
        context.user_data.pop("search_mode", None)
        await top_cmd(update, context)
        return

    if text and text.startswith("Vip"):
        context.user_data.pop("search_mode", None)
        await vip(update, context)
        return

    if text and text.startswith("Referral"):
        context.user_data.pop("search_mode", None)
        await referral(update, context)
        return

    if text and "Request Movie" in text:
        context.user_data.pop("search_mode", None)
        await message_cmd(update, context)
        return

    # ------------------------
    # MESSAGE FLOW — moved here so menu buttons override it
    # ------------------------
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
            # if user typed a menu command, ignore msg_mode and let menu handle (safety)
            # but since we moved this block after menu handling, this is mostly safe
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

    # ------------------------
    # SEARCH MODE (must run AFTER menu & msg_mode handling, BEFORE treating text as code)
    # ------------------------
    if context.user_data.get("search_mode"):

        mode = context.user_data.get("search_mode")
        context.user_data.pop("search_mode", None)

        catalog = DB.get("catalog", {})

        if mode == "code":

            item = catalog.get(text)

            if not item:
                await update.message.reply_text("❌ Movie not found")
                return

            title = item.get("title","")

            # Try to get stored message id for this code (media)
            msg_id = DB.get("movies", {}).get(text)
            if not msg_id:
                await update.message.reply_text("❌ Movie not found")
                return

            # VIP protection: block non-VIP users from VIP-only movies
            vip_list = set(str(x) for x in DB.get("vip_only", []))
            if text in vip_list and not is_vip(uid):
                await update.message.reply_text(TXT_VIP_ONLY)
                return

            # Log request statistics (keeps behaviour similar to code-request flow)
            now = time.time()
            STATS.setdefault("codes", []).append((text, now))
            STATS.setdefault("requests", []).append(now)
            STATS.setdefault("users", []).append((uid, now))
            mark_stats_dirty()

            # Enqueue media to be delivered (caption will include Name + WARNING)
            await SEND_QUEUE.put((context, uid, msg_id, is_vip(uid), title))
            await update.message.reply_text("⏳ Sending media...")
            return


        if mode == "name":

            keyword = text.lower()
            results = []

            for code_val,data in catalog.items():

                title = data.get("title","")

                if keyword in title.lower():
                    results.append((code_val,title))

            if not results:
                await update.message.reply_text("❌ No results found")
                return

            text_out="🔎 <b>Results :</b>\n\n"

            for i,(c,title) in enumerate(results,1):
                text_out+=f"{i}. {title} - <b>{c}</b>\n\n"

            await update.message.reply_text(text_out,parse_mode="HTML")
            return


    # LIMIT + COOLDOWN
    now=time.time()
    vip_user=is_vip(uid)

    delay = 5 if vip_user else 5
    daily_limit = 30 if vip_user else 30

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
    mark_stats_dirty()

    title = DB.get("catalog", {}).get(text, {}).get("title", "Unknown")
    await SEND_QUEUE.put((context, uid, msg_id, is_vip(uid), title))


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
    await update.message.reply_text("You can request movie 📽")



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

    context.user_data.clear()
    context.user_data["edit_step"] = "code"

    await update.message.reply_text(
        "Edit qilmoqchi bo'lgan kino raqamini jo'nating\n\n"
        "Masalan: 76 , 7 , 81.2 , 7.14"
    )
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
# SEARCH SYSTEM (TITLE ONLY)
# =========================================

async def search(update:Update, context:ContextTypes.DEFAULT_TYPE):
    context.user_data["search_mode"] = True
    await update.message.reply_text("Send a movie name")



# =========================================
# REFERRAL COMMAND
# =========================================

async def referral(update:Update, context:ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    link = f"https://t.me/englishmovietimebot?start={uid}"
    count = REFERRALS.get(str(uid), 0)

    text = (
        "You can get 1 day VIP by inviting 5 friends , 3 days VIP with 10 friends\n\n"
        f"{link}\n\n"
        f"👥 Your referrals: {count}"
    )

    await update.message.reply_text(text)


# =========================================
# ADMIN VIP USER MANAGEMENT
# =========================================

async def addvip_user(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /addvip user_id")
        return

    uid = str(context.args[0])
    expire = datetime.utcnow() + timedelta(days=30)
    VIP[uid] = expire.isoformat()
    save()

    await update.message.reply_text(f"👑 User {uid} added to VIP (30 days)")


async def removevip_user(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /removevip user_id")
        return

    uid = str(context.args[0])

    if uid in VIP:
        del VIP[uid]
        save()
        await update.message.reply_text(f"❌ User {uid} removed from VIP")
    else:
        await update.message.reply_text("User is not VIP")


# =========================================
# ADMIN USER VIP COMMANDS (SAFE)
# =========================================

async def addvips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /addvips user_id")
        return

    uid = str(context.args[0])
    expire = datetime.utcnow() + timedelta(days=30)
    VIP[uid] = expire.isoformat()
    save()

    await update.message.reply_text(f"👑 User {uid} added to VIP (30 days)")


async def removevips(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /removevips user_id")
        return

    uid = str(context.args[0])

    if uid in VIP:
        del VIP[uid]
        save()
        await update.message.reply_text(f"❌ User {uid} removed from VIP")
    else:
        await update.message.reply_text("User is not VIP")

# =========================================
# RUN
# =========================================

async def post_init(app):
    asyncio.create_task(queue_worker())
    asyncio.create_task(vip_checker(app))
    asyncio.create_task(autosave_stats_loop())


# =========================================
# TOP COMMAND
# =========================================
async def top_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📆Week", callback_data="top_week"),
            InlineKeyboardButton("🗓Month", callback_data="top_month")
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

        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "

        text += (
            f"{medal}{i}. <b>{title}</b>\n"
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
    app.add_handler(CommandHandler("ntitle",ntitle))
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
    app.add_handler(CommandHandler("search",search))
    app.add_handler(CommandHandler("referral",referral))
    app.add_handler(CommandHandler("addvips",addvips))
    app.add_handler(CommandHandler("removevips",removevips))
    app.add_handler(CommandHandler("edittitle",edittitle))
    app.add_handler(CommandHandler("titles", titles))
    app.add_handler(CommandHandler("getdb", getdb))
    app.add_handler(CommandHandler("loaddb", loaddb))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment))

    app.add_handler(CallbackQueryHandler(top_callback,pattern="^top_"))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL,channel_post))
    app.add_handler(MessageHandler(filters.ALL,msg))

    print("BOT RUNNING...")
    app.run_polling(close_loop=False)

if __name__=="__main__":
    main()


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ensure message exists
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # If user pressed the Search menu button, show two options (no Back button)
    if text.startswith("Search"):
        kb = ReplyKeyboardMarkup([["By Name", "By Code"]], resize_keyboard=True)
        await update.message.reply_text("Choose search method:", reply_markup=kb)
        return

    # If user chose By Name -> enter name search mode
    if text == "By Name":
        context.user_data["search_mode"] = "name"
        await update.message.reply_text("Send movie name")
        return

    # If user chose By Code -> enter code search mode
    if text == "By Code":
        context.user_data["search_mode"] = "code"
        await update.message.reply_text("Send movie code")
        return

    if text == "Back":
        context.user_data.pop("search_mode", None)

        await update.message.reply_text(
            TXT_START,
            parse_mode="HTML",
            reply_markup=USER_MENU
        )
        return

    # If we are in search mode, handle accordingly
    if context.user_data.get("search_mode"):
        mode = context.user_data.get("search_mode")
        # consume the mode
        context.user_data.pop("search_mode", None)

        catalog = DB.get("catalog", {})

        # search by code (exact match)
        if mode == "code":
            movie = catalog.get(text)
            if not movie:
                await update.message.reply_text("❌ Movie not found")
                return
            title = movie.get("title", "")
            await update.message.reply_text(f"🎬 {title}\\n\\nCode: {text}")
            return

        # search by name (partial match)
        if mode == "name":
            keyword = text.lower()
            results = []
            for code, data in catalog.items():
                title = data.get("title", "")
                if keyword in title.lower():
                    results.append((code, title))
            if not results:
                await update.message.reply_text("❌ No results found")
                return
            msg = "🔎 Results:\\n\\n"
            for i, (c, t) in enumerate(results, 1):
                msg += f"{i}. {t} - {c}\\n"
            await update.message.reply_text(msg)
            return

    # If user sent a plain numeric code (without entering search mode)
    if re.fullmatch(r"\\d+", text):
        catalog = DB.get("catalog", {})
        movie = catalog.get(text)
        if movie:
            title = movie.get("title", "")
            await update.message.reply_text(f"🎬 {title}\\n\\nCode: {text}")
            return

    # fallback
    try:
        await update.message.reply_text("I didn't understand that. Use the menu.", reply_markup=USER_MENU)
    except Exception:
        pass
