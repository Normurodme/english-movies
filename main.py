import os
import json

DB_FILE = "/data/db.json"

# LOAD
def load():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {}

# SAVE
def save(data):
    with open(DB_FILE,"w") as f:
        json.dump(data,f,indent=2)

DB = load()

if "titles" not in DB:
    DB["titles"] = {}

MOVIES = {

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

"1":"LOTR Fellowship",
"2":"LOTR Two Towers",
"3":"LOTR Return King",

"4":"Hobbit Unexpected Journey",
"5":"Hobbit Smaug",
"6":"Hobbit Five Armies",

"7":"Se7en",
"26":"Whiplash",
"27":"The Fault in Our Stars",

"28.1":"Transformers","28.2":"Transformers","28.3":"Transformers",
"28.4":"Transformers","28.5":"Transformers","28.6":"Transformers",

"29":"Harry Potter 1",
"30":"Harry Potter 2",
"31":"Harry Potter 3",
"32":"Harry Potter 4",
"33":"Harry Potter 5",
"34":"Harry Potter 6",
"35":"Harry Potter 7.1",
"36":"Harry Potter 7.2",

"37":"Pirates 1",
"38":"Pirates 2",
"39":"Pirates 3",
"40":"Pirates 4",
"41":"Pirates 5",

"42":"Joker",
"43":"Oppenheimer",
"44":"Avengers",
"45":"Avengers Ultron",
"46":"Infinity War",
"47":"Endgame",

"48":"Silence of the Lambs",
"49":"Legend",
"50":"Troy",
"51":"Gladiator",
"52":"Mad Max Fury Road",
"53":"American Psycho",
"54":"Inglourious Basterds",
"55":"Social Network",
"56":"Wolf of Wall Street",
"57":"Scarface",
"58":"Django",
"59":"Departed",
"60":"Avatar",
"61":"Avatar 2",
"62":"No Country for Old Men",
"63":"Memento",
"64":"Prestige",
"65":"Batman Begins",
"66":"Dark Knight",
"67":"Dark Knight Rises",
"68":"Revenant",

"69.1":"Now You See Me","69.2":"Now You See Me","69.3":"Now You See Me",

"70.1":"Spider-Man","70.2":"Spider-Man","70.3":"Spider-Man",

"71.1":"Amazing Spider-Man","71.2":"Amazing Spider-Man",

"72":"Spider-Man Homecoming",
"73":"Spider-Man Far From Home",
"74":"Spider-Man No Way Home"
}

for code,title in MOVIES.items():
    DB["titles"][code] = title

save(DB)

print("✅ DB SUCCESSFULLY FILLED WITH MOVIES")
