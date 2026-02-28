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
BANNED_FILE="/data/banned.json"

DB=load(DB_FILE,{"movies":{}, "next":1, "vip_only":[]})
USERS=load(USERS_FILE,[])
VIP=load(VIP_FILE,{})
STATS=load(STATS_FILE,{"requests":[], "users":[]})
BANNED=load(BANNED_FILE,[])

if "vip_only" not in DB:
    DB["vip_only"]=[]

# =========================================
# 🔥 PRELOAD ALL OLD MOVIES TO DB["titles"]
# =========================================

PRELOAD_MOVIES = {

"8":"The Godfather",
"9":"The Godfather 2",
"10":"Shawshank Redemption",
"11":"Fight Club",
"12":"One Flew Over the Cuckoo's Nest",
"13":"Forrest Gump",
"14":"Schindler's List",
"15":"Inception",
"16":"Titanic",
"17":"Interstellar",
"18":"Pulp Fiction",

"7.1":"Sherlock","7.2":"Sherlock","7.3":"Sherlock","7.4":"Sherlock",
"7.5":"Sherlock","7.6":"Sherlock","7.7":"Sherlock","7.8":"Sherlock",
"7.9":"Sherlock","7.10":"Sherlock","7.11":"Sherlock","7.12":"Sherlock",

"19.1":"Kung Fu Panda","19.2":"Kung Fu Panda","19.3":"Kung Fu Panda","19.4":"Kung Fu Panda",

"20":"The Truman Show",
"21":"12 Angry Men",
"22":"The Green Mile",
"23":"La La Land",
"24":"Warcraft",
"25":"Shutter Island",

"1":"The Lord Of The Rings: Fellowship of the Rings",
"2":"The Lord Of The Rings: The Two Towers",
"3":"The Lord Of The Rings: Return of the King",

"4":"The Hobbit: The Unexpected Journey",
"5":"The Hobbit: The Desolation of Smaug",
"6":"The Hobbit: The Battle of the Five Armies",

"7":"Se7en",
"26":"Whiplash",
"27":"The Fault in Our Stars",

"28.1":"Transformers","28.2":"Transformers","28.3":"Transformers",
"28.4":"Transformers","28.5":"Transformers","28.6":"Transformers",

"29":"Harry Potter and the Philosopher's Stone",
"30":"Harry Potter and the Chamber of Secrets",
"31":"Harry Potter and the Prisoner of Azkaban",
"32":"Harry Potter and the Goblet of Fire",
"33":"Harry Potter and the Order of the Phoenix",
"34":"Harry Potter and the Half-Blood Prince",
"35":"Harry Potter and the Deathly Hallows 1",
"36":"Harry Potter and the Deathly Hallows 2",

"37":"Pirates of the Caribbean: The Curse of the Black Pearl",
"38":"Pirates of the Caribbean: Dead Man's Chest",
"39":"Pirates of the Caribbean: At World's End",
"40":"Pirates of the Caribbean: On Stranger Tides",
"41":"Pirates of the Caribbean: Dead Men Tell No Tales",

"42":"Joker",
"43":"Oppenheimer",
"44":"The Avengers",
"45":"Avengers: Age of Ultron",
"46":"Avengers: Infinity War",
"47":"Avengers: Endgame",

"48":"The Silence of the Lambs",
"49":"Legend",
"50":"Troy",
"51":"Gladiator",
"52":"Mad Max: Fury Road",
"53":"American Psycho",
"54":"Inglourious Basterds",
"55":"The Social Network",
"56":"The Wolf of Wall Street",
"57":"Scarface",
"58":"Django Unchained",
"59":"The Departed",
"60":"Avatar",
"61":"Avatar: The Way of Water",
"62":"No Country for Old Men",
"63":"Memento",
"64":"The Prestige",
"65":"Batman Begins",
"66":"The Dark Knight",
"67":"The Dark Knight Rises",
"68":"The Revenant",

"69.1":"Now You See Me","69.2":"Now You See Me","69.3":"Now You See Me",

"70.1":"Spider-Man","70.2":"Spider-Man","70.3":"Spider-Man",
"71.1":"The Amazing Spider-Man","71.2":"The Amazing Spider-Man",

"72":"Spider-Man: Homecoming",
"73":"Spider-Man: Far From Home",
"74":"Spider-Man: No Way Home"
}

if "titles" not in DB:
    DB["titles"]={}

for code,title in PRELOAD_MOVIES.items():
    DB["titles"][code]=title

def save():
    save_file(DB_FILE,DB)
    save_file(USERS_FILE,USERS)
    save_file(VIP_FILE,VIP)
    save_file(STATS_FILE,STATS)
    save_file(BANNED_FILE,BANNED)

save()

print("OLD MOVIES PRELOADED ✔")

# =========================================
# (QOLGAN KODING O'ZGARMAGAN)
# =========================================

def main():
    app=ApplicationBuilder().token(TOKEN).build()
    print("BOT RUNNING...")
    app.run_polling()

if __name__=="__main__":
    main()
