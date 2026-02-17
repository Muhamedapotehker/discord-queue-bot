import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import sqlite3
import asyncio
import re
from flask import Flask
from threading import Thread

# Web Server für 24/7
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Datenbank
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('queue_bot.db')
        self.cursor = self.conn.cursor()
        self.create_tables()
        
    def create_tables(self):
        # Verifizierte User - jetzt mit mehreren Gamemodes
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER,
                minecraft_name TEXT,
                server TEXT,
                gamemode TEXT,
                region TEXT,
                verified_at TEXT,
                PRIMARY KEY (user_id, gamemode)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                region TEXT,
                gamemode TEXT,
                server TEXT,
                previous_rank TEXT,
                earned_rank TEXT,
                tester_id INTEGER,
                tester_name TEXT,
                timestamp TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_tickets (
                channel_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                tester_id INTEGER,
                gamemode TEXT,
                created_at TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_testers (
                user_id INTEGER,
                gamemode TEXT,
                started_at TEXT,
                PRIMARY KEY (user_id, gamemode)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue_status (
                gamemode TEXT PRIMARY KEY,
                last_session TEXT,
                message_id INTEGER
            )
        ''')
        self.conn.commit()
        
    def add_verified(self, user_id, mc_name, server, gamemode, region):
        self.cursor.execute('''
            INSERT OR REPLACE INTO verified_users 
            (user_id, minecraft_name, server, gamemode, region, verified_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, mc_name, server, gamemode.lower(), region, datetime.now().isoformat()))
        self.conn.commit()
        
    def is_verified_for_gamemode(self, user_id, gamemode):
        self.cursor.execute('SELECT * FROM verified_users WHERE user_id = ? AND gamemode = ?', (user_id, gamemode.lower()))
        return self.cursor.fetchone() is not None
        
    def get_verified_data(self, user_id, gamemode):
        self.cursor.execute('SELECT * FROM verified_users WHERE user_id = ? AND gamemode = ?', (user_id, gamemode.lower()))
        return self.cursor.fetchone()
        
    def get_all_verified_gamemodes(self, user_id):
        self.cursor.execute('SELECT gamemode FROM verified_users WHERE user_id = ?', (user_id,))
        return [row[0] for row in self.cursor.fetchall()]
        
    def count_verified_gamemodes(self, user_id):
        self.cursor.execute('SELECT COUNT(*) FROM verified_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()[0]
        
    def remove_verified(self, user_id, gamemode):
        self.cursor.execute('DELETE FROM verified_users WHERE user_id = ? AND gamemode = ?', (user_id, gamemode))
        self.conn.commit()
        
    def add_result(self, user_id, username, region, gamemode, server, prev_rank, earned_rank, tester_id, tester_name):
        self.cursor.execute('''
            INSERT INTO test_results 
            (user_id, username, region, gamemode, server, previous_rank, earned_rank, tester_id, tester_name, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, region, gamemode, server, prev_rank, earned_rank, tester_id, tester_name, datetime.now().isoformat()))
        self.conn.commit()
        
    def add_ticket(self, channel_id, user_id, tester_id, gamemode):
        self.cursor.execute('''
            INSERT INTO active_tickets (channel_id, user_id, tester_id, gamemode, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (channel_id, user_id, tester_id, gamemode, datetime.now().isoformat()))
        self.conn.commit()
        
    def get_ticket(self, channel_id):
        self.cursor.execute('SELECT * FROM active_tickets WHERE channel_id = ?', (channel_id,))
        return self.cursor.fetchone()
        
    def remove_ticket(self, channel_id):
        self.cursor.execute('DELETE FROM active_tickets WHERE channel_id = ?', (channel_id,))
        self.conn.commit()
        
    def add_tester(self, user_id, gamemode):
        self.cursor.execute('''
            INSERT OR REPLACE INTO active_testers (user_id, gamemode, started_at)
            VALUES (?, ?, ?)
        ''', (user_id, gamemode, datetime.now().isoformat()))
        self.conn.commit()
        
    def remove_tester(self, user_id, gamemode):
        self.cursor.execute('DELETE FROM active_testers WHERE user_id = ? AND gamemode = ?', (user_id, gamemode))
        self.conn.commit()
        
    def get_testers(self, gamemode):
        self.cursor.execute('SELECT user_id FROM active_testers WHERE gamemode = ?', (gamemode,))
        return [row[0] for row in self.cursor.fetchall()]
        
    def is_tester_active(self, user_id, gamemode):
        self.cursor.execute('SELECT * FROM active_testers WHERE user_id = ? AND gamemode = ?', (user_id, gamemode))
        return self.cursor.fetchone() is not None
        
    def save_last_session(self, gamemode, message_id=None):
        self.cursor.execute('''
            INSERT OR REPLACE INTO queue_status (gamemode, last_session, message_id)
            VALUES (?, ?, ?)
        ''', (gamemode, datetime.now().isoformat(), message_id))
        self.conn.commit()
        
    def get_last_session(self, gamemode):
        self.cursor.execute('SELECT last_session, message_id FROM queue_status WHERE gamemode = ?', (gamemode,))
        result = self.cursor.fetchone()
        return result if result else (None, None)

db = Database()

# Config
EMBED_COLOR = 0x5865F2
SUCCESS_COLOR = 0x57F287
ERROR_COLOR = 0xED4245
INFO_COLOR = 0xFEE75C
# IDS ANPASSEN!
TICKET_CATEGORY_ID = 1473104146046517451
LOG_CHANNEL_ID = 1473104377114791946
VERIFICATION_CHANNEL_ID = 1473104464134148229
ADMIN_ROLE_ID = 1473103952923987989
MAX_VERIFICATIONS = 8  # Max 8 Gamemodes gleichzeitig

# RANK ROLE IDS - PRO GAMEMODE UND RANK!
RANK_ROLES = {
    # SWORD
    "sword_lt5": 1473104066191294475, "sword_lt4": 1473104040618361077, "sword_lt3": 1473104017050701824, "sword_lt2": 1473103998218141791, "sword_lt1": 1473103983793934531,
    "sword_ht5": 1473104052308017325, "sword_ht4": 1473104026525765633, "sword_ht3": 1473104008079216690, "sword_ht2": 1473103990509277194, "sword_ht1": 1473103975162052619,
    
    # CPVP
    "cpvp_lt5": 1473104067864690923, "cpvp_lt4": 1473104041654620336, "cpvp_lt3": 1473104017986162930, "cpvp_lt2": 1473103999786815722, "cpvp_lt1": 1473103984817606746,
    "cpvp_ht5": 1473104053134295241, "cpvp_ht4": 1473104029797191762, "cpvp_ht3": 1473104008901169336, "cpvp_ht2": 1473103991364911289, "cpvp_ht1": 1473103976541982770,
    
    # AXE
    "axe_lt5": 1473104068628189376, "axe_lt4": 1473104042480898139, "axe_lt3": 1473104021752516732, "axe_lt2": 1473104003943501875, "axe_lt1": 1473103986918690816,
    "axe_ht5": 1473104059295596634, "axe_ht4": 1473104027775402104, "axe_ht3": 1473104014764675213, "axe_ht2": 1473103993294295266, "axe_ht1": 1473103977347420260,
    
    # SMP
    "smp_lt5": 1473104071782174752, "smp_lt4": 1473104044951076947, "smp_lt3": 1473104026001215643, "smp_lt2": 1473104006426398801, "smp_lt1": 1473103988877426688,
    "smp_ht5": 1473104062516953158, "smp_ht4": 1473104038814814351, "smp_ht3": 1473104010595799214, "smp_ht2": 1473103995055767734, "smp_ht1": 1473103978064777351,
    
    # DIAPOT
    "diapot_lt5": 1473104069676498984, "diapot_lt4": 1473104043453972633, "diapot_lt3": 1473104019894309068, "diapot_lt2": 1473104004816048158, "diapot_lt1": 1473103985845080247,
    "diapot_ht5": 1473104060264480861, "diapot_ht4": 1473104028710994001, "diapot_ht3": 1473104012684300432, "diapot_ht2": 1473103992375480503, "diapot_ht1": 1473103979192913951,
    
    # MACE
    "mace_lt5": 1473104072855916736, "mace_lt4": 1473104048679948364, "mace_lt3": 1473104023048556677, "mace_lt2": 1473104005587796069, "mace_lt1": 1473103987896221748,
    "mace_ht5": 1473104064400330903, "mace_ht4": 1473104031743344650, "mace_ht3": 1473104011463753903, "mace_ht2": 1473103994195939531, "mace_ht1": 1473103980283560230,
    
    # UHC
    "uhc_lt5": 1473104070788120667, "uhc_lt4": 1473104044363874487, "uhc_lt3": 1473104019013505075, "uhc_lt2": 1473104001569394939, "uhc_lt1": 1473103982959267961,
    "uhc_ht5": 1473104061103341810, "uhc_ht4": 1473104030669607117, "uhc_ht3": 1473104009727574331, "uhc_ht2": 1473103996930621723, "uhc_ht1": 1473103981134876855,
    
    # NETHPOT
    "nethpot_lt5": 1473104073736851456, "nethpot_lt4": 1473104046347915425, "nethpot_lt3": 1473104024428478595, "nethpot_lt2": 1473104007273775248, "nethpot_lt1": 1473103989712097433,
    "nethpot_ht5": 1473104065050312747, "nethpot_ht4": 1473104039712395429, "nethpot_ht3": 1473104016136208394, "nethpot_ht2": 1473103995957411942, "nethpot_ht1": 1473103981923270849,
    
    # CRYSTAL
    "crystal_lt5": 0, "crystal_lt4": 0, "crystal_lt3": 0, "crystal_lt2": 0, "crystal_lt1": 0,
    "crystal_ht5": 0, "crystal_ht4": 0, "crystal_ht3": 0, "crystal_ht2": 0, "crystal_ht1": 0,
}

# Gamemode Config mit Rollen und Channel IDs
GAMEMODES = {
    "nethpot": {"role_id": 1473104076840370350, "category_id": 1473104195274932395, "channel_id": 1473104526968881308, "waitlist_id": 1473104076840370350, "emoji": "🔪"},
    "smp": {"role_id": 1473104080779088067, "category_id": 1473104226799321160, "channel_id": 1473104544161599710, "waitlist_id": 1473104080779088067, "emoji": "👑"},
    "uhc": {"role_id": 1473104083211649159, "category_id": 1473104190485299260, "channel_id": 1473104554743697418, "waitlist_id": 1473104083211649159, "emoji": "❤️"},
    "sword": {"role_id": 1473104077977026641, "category_id": 1473104187339571412, "channel_id": 1473104534141272064, "waitlist_id": 1473104077977026641, "emoji": "🗡️"},
    "axe": {"role_id": 1473104082225987786, "category_id": 1473104229500715010, "channel_id": 1473104552084639744, "waitlist_id": 1473104082225987786, "emoji": "🪓"},
    "crystal": {"role_id": 1473104079759605770, "category_id": 1473104193051955455, "channel_id": 1473104541074325626, "waitlist_id": 1473104079759605770, "emoji": "💣"},
    "mace": {"role_id": 1473104078379679901, "category_id": 1473104232805564508, "channel_id": 1473104538012745912, "waitlist_id": 1473104078379679901, "emoji": "🔨"},
    "diapot": {"role_id": 1473104089218023474, "category_id": 1473104234982539315, "channel_id": 1473104530509008926, "waitlist_id": 1473104089218023474, "emoji": "💎"}
}

temp_verify = {}

# Queue System
class QueueSystem:
    def __init__(self):
        self.queues = {}
        self.messages = {}
        self.closed_messages = {}
        
    def get_queue(self, gamemode):
        if gamemode not in self.queues:
            self.queues[gamemode] = []
        return self.queues[gamemode]
        
    def add(self, user, gamemode, region):
        testers = db.get_testers(gamemode)
        if not testers:
            return False, "❌ No tester available! Wait for a tester to start."
            
        queue = self.get_queue(gamemode)
        if any(u["id"] == user.id for u in queue):
            return False, "Already in queue!"
        queue.append({
            "id": user.id,
            "user": user,
            "time": datetime.now(),
            "region": region
        })
        return True, "✅ Joined queue!"
        
    def remove(self, user, gamemode):
        queue = self.get_queue(gamemode)
        for i, u in enumerate(queue):
            if u["id"] == user.id:
                queue.pop(i)
                return True, "✅ Left queue!"
        return False, "Not in queue!"
        
    def next_player(self, gamemode):
        queue = self.get_queue(gamemode)
        if not queue:
            return None
        return queue.pop(0)

queue_sys = QueueSystem()

# Bot
class QueueBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Test Queues 👀"
            )
        )
        
    async def setup_hook(self):
        print("✅ Bot ready!")
        try:
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} Commands synced")
        except Exception as e:
            print(f"❌ {e}")
            
    async def on_ready(self):
        print(f"🤖 {self.user} is online!")
        for guild in bot.guilds:
            try:
                await guild.me.edit(nick="VM TierTest")
            except:
                pass

bot = QueueBot()

# Verification Modal - Schritt 1: Minecraft Name
class VerifyModal(discord.ui.Modal, title="📝 Verify Account"):
    minecraft_name = discord.ui.TextInput(
        label="Minecraft Username",
        placeholder="Enter your Minecraft username",
        required=True,
        max_length=16
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        temp_verify[interaction.user.id] = {"mc_name": str(self.minecraft_name)}
        await interaction.response.send_message(
            f"✅ Minecraft name saved: `{self.minecraft_name}`\n\nNow click **Enter Waitlist** to continue!",
            ephemeral=True
        )

# Verification Modal - Schritt 2: Waitlist Details
class WaitlistModal(discord.ui.Modal, title="📝 Enter Waitlist"):
    region = discord.ui.TextInput(
        label="Region", 
        placeholder="EU, NA, ASIA, SA, OCE", 
        required=True
    )
    server = discord.ui.TextInput(
        label="Server", 
        placeholder="BerryPvP, CatPvP, Turtled...", 
        required=True
    )
    gamemode = discord.ui.TextInput(
        label="Gamemode", 
        placeholder="nethpot, smp, uhc, sword, axe, crystal, mace, diapot, cpvp",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id not in temp_verify:
            return await interaction.response.send_message(
                "❌ Please click **Verify Account** first!", 
                ephemeral=True
            )
            
        gamemode = str(self.gamemode).lower().strip()
        if gamemode not in GAMEMODES:
            gamelist = ", ".join(GAMEMODES.keys())
            return await interaction.response.send_message(
                f"❌ Invalid gamemode! Choose from: {gamelist}",
                ephemeral=True
            )
        
        # Prüfe ob User schon für diesen Gamemode verifiziert ist
        if db.is_verified_for_gamemode(interaction.user.id, gamemode):
            return await interaction.response.send_message(
                f"❌ You are already verified for {gamemode.upper()}!",
                ephemeral=True
            )
        
        # Prüfe ob User schon 8 Gamemodes hat
        current_count = db.count_verified_gamemodes(interaction.user.id)
        if current_count >= MAX_VERIFICATIONS:
            return await interaction.response.send_message(
                f"❌ You can only verify for up to {MAX_VERIFICATIONS} gamemodes!\nRemove one first with `/unverify gamemode`",
                ephemeral=True
            )
            
        temp_data = temp_verify[interaction.user.id]
        db.add_verified(
            interaction.user.id, 
            temp_data["mc_name"], 
            str(self.server), 
            gamemode, 
            str(self.region).upper()
        )
        
        # Gebe Gamemode Rolle
        gamemode_config = GAMEMODES[gamemode]
        gamemode_role = interaction.guild.get_role(gamemode_config["role_id"])
        if gamemode_role:
            await interaction.user.add_roles(gamemode_role)
            
        del temp_verify[interaction.user.id]
        
        # Zeige alle aktuellen Verifikationen
        all_gamemodes = db.get_all_verified_gamemodes(interaction.user.id)
        gamemodes_list = ", ".join([g.upper() for g in all_gamemodes])
        
        embed = discord.Embed(
            title="✅ Verification Complete!",
            description=f"**MC:** `{temp_data['mc_name']}`\n**Server:** {self.server}\n**Gamemode:** {gamemode}\n**Region:** {self.region}\n\n**Your verifications ({len(all_gamemodes)}/{MAX_VERIFICATIONS}):** {gamemodes_list}",
            color=SUCCESS_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Verification View mit ROTEN Buttons
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Verify Account", style=discord.ButtonStyle.danger, emoji="📝")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prüfe ob User schon 8 Gamemodes hat
        current_count = db.count_verified_gamemodes(interaction.user.id)
        if current_count >= MAX_VERIFICATIONS:
            return await interaction.response.send_message(
                f"❌ You already have {MAX_VERIFICATIONS} verifications! Remove one first.",
                ephemeral=True
            )
        await interaction.response.send_modal(VerifyModal())
        
    @discord.ui.button(label="Enter Waitlist", style=discord.ButtonStyle.danger, emoji="📋")
    async def waitlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Zeige aktuelle Verifikationen
        all_gamemodes = db.get_all_verified_gamemodes(interaction.user.id)
        if len(all_gamemodes) >= MAX_VERIFICATIONS:
            return await interaction.response.send_message(
                f"❌ You already have {MAX_VERIFICATIONS} verifications!\nYour gamemodes: {', '.join([g.upper() for g in all_gamemodes])}",
                ephemeral=True
            )
        await interaction.response.send_modal(WaitlistModal())

# NEU: Unverify Command
@bot.tree.command(name="unverify", description="Remove verification for a specific gamemode")
@app_commands.describe(gamemode="Which gamemode to unverify from")
async def unverify_cmd(interaction: discord.Interaction, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(f"❌ Invalid gamemode!", ephemeral=True)
    
    if not db.is_verified_for_gamemode(interaction.user.id, gamemode):
        return await interaction.response.send_message(
            f"❌ You are not verified for {gamemode.upper()}!",
            ephemeral=True
        )
    
    # Entferne Rolle
    gamemode_config = GAMEMODES[gamemode]
    gamemode_role = interaction.guild.get_role(gamemode_config["role_id"])
    if gamemode_role:
        await interaction.user.remove_roles(gamemode_role)
    
    # Entferne aus DB
    db.remove_verified(interaction.user.id, gamemode)
    
    all_gamemodes = db.get_all_verified_gamemodes(interaction.user.id)
    await interaction.response.send_message(
        f"✅ Removed verification for {gamemode.upper()}!\n"
        f"Remaining verifications: {len(all_gamemodes)}/{MAX_VERIFICATIONS}",
        ephemeral=True
    )

@bot.tree.command(name="verifypanel", description="Post verification panel (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def verify_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📝 Evaluation Testing Waitlist",
        description="Upon applying, you will be added to a waitlist channel.\nHere you will be pinged when a tester of your region is available.\nIf you are HT3 or higher, a high ticket will be created.",
        color=EMBED_COLOR
    )
    
    embed.add_field(
        name="Instructions",
        value="• Region should be the region of the server you wish to test on\n• Username should be the name of the account you will be testing on\n• You can verify for up to 8 gamemodes simultaneously",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Warning",
        value="Failure to provide authentic information will result in a denied test.",
        inline=False
    )
    
    await interaction.response.send_message("✅ Panel created!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VerificationView())

# "No Testers" Embed - MIT ROTEM RAND
def create_closed_embed(gamemode):
    config = GAMEMODES.get(gamemode, {})
    emoji = config.get("emoji", "🎮")
    display_name = config.get("display_name", gamemode.upper())
    
    last_session, _ = db.get_last_session(gamemode)
    last_session_text = ""
    if last_session:
        last_time = datetime.fromisoformat(last_session)
        last_session_text = f"\n\nLast testing session: <t:{int(last_time.timestamp())}:f>"
    
    embed = discord.Embed(
        title=f"{emoji} [1.21+] Minecraft {display_name} PvP Community",
        description=f"**No Testers Online**\n\nNo testers for your region are available at this time.\nYou will be pinged when a tester is available.\nCheck back later!{last_session_text}",
        color=ERROR_COLOR  # Roter Rand durch ERROR_COLOR
    )
    return embed

# Aktive Queue Embed
def create_queue_embed(gamemode):
    config = GAMEMODES.get(gamemode, {})
    
    testers = db.get_testers(gamemode)
    
    tester_mentions = []
    for tester_id in testers:
        tester = bot.get_user(tester_id)
        if tester:
            tester_mentions.append(tester.mention)
    
    queue = queue_sys.get_queue(gamemode)
    queue_text = ""
    if not queue:
        queue_text = "*Empty*"
    else:
        for i, u in enumerate(queue[:15], 1):
            queue_text += f"{i}. {u['user'].mention}\n"
    
    embed = discord.Embed(
        title="Tester(s) Available!",
        description=f"⏱️ The queue updates every 1 minute.\nUse `/leave` if you wish to be removed from the waitlist or queue.",
        color=SUCCESS_COLOR
    )
    
    embed.add_field(name="Queue:", value=queue_text or "*Empty*", inline=False)
    
    if tester_mentions:
        embed.add_field(
            name="Active Testers:", 
            value="\n".join([f"{i+1}. {t}" for i, t in enumerate(tester_mentions)]), 
            inline=False
        )
    
    return embed

class QueueView(discord.ui.View):
    def __init__(self, gamemode):
        super().__init__(timeout=None)
        self.gamemode = gamemode
        
    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.blurple)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not db.is_verified_for_gamemode(interaction.user.id, self.gamemode):
            return await interaction.response.send_message(
                f"❌ Verify first for {self.gamemode.upper()}!", 
                ephemeral=True
            )
            
        user_data = db.get_verified_data(interaction.user.id, self.gamemode)
        if not user_data:
            return await interaction.response.send_message("❌ Not verified!", ephemeral=True)
            
        region = user_data[4] if len(user_data) > 4 else "?"
        
        ok, msg = queue_sys.add(interaction.user, self.gamemode, region)
        await interaction.response.send_message(msg, ephemeral=True)
        if ok:
            msg_obj = queue_sys.messages.get(self.gamemode)
            if msg_obj:
                await msg_obj.edit(embed=create_queue_embed(self.gamemode), view=self)
            
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, msg = queue_sys.remove(interaction.user, self.gamemode)
        await interaction.response.send_message(msg, ephemeral=True)
        if ok:
            msg_obj = queue_sys.messages.get(self.gamemode)
            if msg_obj:
                view = QueueView(self.gamemode)
                await msg_obj.edit(embed=create_queue_embed(self.gamemode), view=view)

@bot.tree.command(name="start", description="Start testing and open queue")
@app_commands.describe(gamemode="Which gamemode to test")
async def start_cmd(interaction: discord.Interaction, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(
            f"❌ Invalid gamemode! Use: {', '.join(GAMEMODES.keys())}", 
            ephemeral=True
        )
    
    gamemode_config = GAMEMODES[gamemode]
    tester_role = interaction.guild.get_role(gamemode_config["role_id"])
    
    if tester_role and tester_role not in interaction.user.roles:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                f"❌ You need the {gamemode.upper()} Tester role!", 
                ephemeral=True
            )
    
    db.add_tester(interaction.user.id, gamemode)
    
    if gamemode in queue_sys.closed_messages:
        try:
            await queue_sys.closed_messages[gamemode].delete()
        except:
            pass
        del queue_sys.closed_messages[gamemode]
    
    if queue_sys.messages.get(gamemode):
        try:
            await queue_sys.messages[gamemode].delete()
        except:
            pass
    
    # NEU: Pinge die Gamemode-Rolle statt @here
    view = QueueView(gamemode)
    embed = create_queue_embed(gamemode)
    
    gamemode_role = interaction.guild.get_role(gamemode_config.get("role_id", 0))
    if gamemode_role:
        ping_text = gamemode_role.mention
    else:
        ping_text = "@here"  # Fallback
    
    queue_sys.messages[gamemode] = await interaction.channel.send(ping_text, embed=embed, view=view)
    
    db.save_last_session(gamemode, queue_sys.messages[gamemode].id)
    
    await interaction.response.send_message(
        f"✅ {gamemode.upper()} queue opened! You are now testing.", 
        ephemeral=True
    )

@bot.tree.command(name="stop", description="Stop testing and close queue")
@app_commands.describe(gamemode="Which gamemode to stop")
async def stop_cmd(interaction: discord.Interaction, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(f"❌ Invalid gamemode!", ephemeral=True)
    
    db.remove_tester(interaction.user.id, gamemode)
    
    remaining_testers = db.get_testers(gamemode)
    
    if queue_sys.messages.get(gamemode):
        try:
            await queue_sys.messages[gamemode].delete()
        except:
            pass
        queue_sys.messages[gamemode] = None
    
    if not remaining_testers:
        closed_embed = create_closed_embed(gamemode)
        queue_sys.closed_messages[gamemode] = await interaction.channel.send(embed=closed_embed)
        db.save_last_session(gamemode, None)
    
    await interaction.response.send_message(f"🔴 {gamemode.upper()} queue closed!", ephemeral=True)

@bot.tree.command(name="addtester", description="Add another tester to the gamemode")
@app_commands.describe(user="User to add as tester", gamemode="Which gamemode")
@app_commands.checks.has_permissions(administrator=True)
async def addtester_cmd(interaction: discord.Interaction, user: discord.Member, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(f"❌ Invalid gamemode!", ephemeral=True)
    
    gamemode_config = GAMEMODES[gamemode]
    tester_role = interaction.guild.get_role(gamemode_config["role_id"])
    
    if tester_role and tester_role not in user.roles:
        return await interaction.response.send_message(
            f"❌ {user.mention} doesn't have the {gamemode.upper()} Tester role!", 
            ephemeral=True
        )
    
    db.add_tester(user.id, gamemode)
    
    if queue_sys.messages.get(gamemode):
        view = QueueView(gamemode)
        await queue_sys.messages[gamemode].edit(embed=create_queue_embed(gamemode), view=view)
    
    await interaction.response.send_message(
        f"✅ Added {user.mention} as tester for {gamemode.upper()}!", 
        ephemeral=True
    )

@bot.tree.command(name="removetester", description="Remove a tester from the gamemode")
@app_commands.describe(user="User to remove", gamemode="Which gamemode")
@app_commands.checks.has_permissions(administrator=True)
async def removetester_cmd(interaction: discord.Interaction, user: discord.Member, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(f"❌ Invalid gamemode!", ephemeral=True)
    
    db.remove_tester(user.id, gamemode)
    
    testers = db.get_testers(gamemode)
    
    if queue_sys.messages.get(gamemode):
        if testers:
            view = QueueView(gamemode)
            await queue_sys.messages[gamemode].edit(embed=create_queue_embed(gamemode), view=view)
        else:
            try:
                await queue_sys.messages[gamemode].delete()
            except:
                pass
            queue_sys.messages[gamemode] = None
            closed_embed = create_closed_embed(gamemode)
            queue_sys.closed_messages[gamemode] = await interaction.channel.send(embed=closed_embed)
    
    if not testers:
        await interaction.response.send_message(
            f"🗑️ Removed {user.mention}. No testers left, queue closed!", 
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"🗑️ Removed {user.mention} from {gamemode.upper()} testers!", 
            ephemeral=True
        )

@bot.tree.command(name="ticket", description="Create ticket for user (removes from queue)")
@app_commands.describe(user="User from queue to test", gamemode="Which gamemode")
async def ticket_cmd(interaction: discord.Interaction, user: discord.Member, gamemode: str):
    gamemode = gamemode.lower().strip()
    if gamemode not in GAMEMODES:
        return await interaction.response.send_message(f"❌ Invalid gamemode!", ephemeral=True)
    
    if not db.is_tester_active(interaction.user.id, gamemode):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                f"❌ You are not an active tester for {gamemode.upper()}!", 
                ephemeral=True
            )
    
    queue_sys.remove(user, gamemode)
    msg_obj = queue_sys.messages.get(gamemode)
    if msg_obj:
        view = QueueView(gamemode)
        await msg_obj.edit(embed=create_queue_embed(gamemode), view=view)
    
    if not db.is_verified_for_gamemode(user.id, gamemode):
        return await interaction.response.send_message(f"❌ User not verified for {gamemode.upper()}!", ephemeral=True)
        
    data = db.get_verified_data(user.id, gamemode)
    mc_name, region, server = data[1], data[4], data[2]
    
    gamemode_config = GAMEMODES.get(gamemode, {})
    category_id = gamemode_config.get("category_id", 0)
    
    category = None
    if category_id != 0:
        category = discord.utils.get(interaction.guild.categories, id=category_id)
    
    if not category:
        category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)
    
    if not category:
        return await interaction.response.send_message(
            "❌ No category found! Please set up category IDs in the config.", 
            ephemeral=True
        )
        
    ticket_name = f"{gamemode}-test-{user.name.lower()}"
    existing = discord.utils.get(interaction.guild.channels, name=ticket_name)
    if existing:
        return await interaction.response.send_message(f"❌ Ticket already exists!", ephemeral=True)
        
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    testers = db.get_testers(gamemode)
    for tester_id in testers:
        tester = interaction.guild.get_member(tester_id)
        if tester:
            overwrites[tester] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
    channel = await interaction.guild.create_text_channel(
        name=ticket_name, 
        category=category, 
        overwrites=overwrites
    )
    db.add_ticket(channel.id, user.id, interaction.user.id, gamemode)
    
    tester_mentions = []
    for tester_id in testers:
        tester = interaction.guild.get_member(tester_id)
        if tester:
            tester_mentions.append(tester.mention)
    
    embed = discord.Embed(title=f"📝 {gamemode.upper()} Test Ticket", color=ERROR_COLOR)
    embed.add_field(name="Discord", value=user.mention, inline=False)
    embed.add_field(name="MC", value=f"`{mc_name}`", inline=False)
    embed.add_field(name="Region", value=region, inline=False)
    embed.add_field(name="Server", value=server, inline=False)
    embed.add_field(name="Gamemode", value=gamemode, inline=False)
    embed.add_field(
        name="🎮 Testing by", 
        value=", ".join(tester_mentions) if tester_mentions else interaction.user.mention, 
        inline=False
    )
    embed.add_field(
        name="Commands", 
        value="`/add @user` - Add player\n`/remove @user` - Remove player\n`/next` - Skip to next\n`/result` - Finish test", 
        inline=False
    )
    
    await channel.send(f"{user.mention} {' '.join(tester_mentions)}", embed=embed)
    await interaction.response.send_message(
        f"✅ Ticket created in **{category.name}**: {channel.mention}\n🗑️ User removed from queue!", 
        ephemeral=True
    )

@bot.tree.command(name="add", description="Add player to ticket")
@app_commands.describe(user="User to add")
async def add_cmd(interaction: discord.Interaction, user: discord.Member):
    if not any(interaction.channel.name.startswith(f"{gm}-test-") for gm in GAMEMODES.keys()):
        return await interaction.response.send_message("❌ Only in test tickets!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to ticket!")

@bot.tree.command(name="remove", description="Remove player from ticket")
@app_commands.describe(user="User to remove")
async def remove_cmd(interaction: discord.Interaction, user: discord.Member):
    if not any(interaction.channel.name.startswith(f"{gm}-test-") for gm in GAMEMODES.keys()):
        return await interaction.response.send_message("❌ Only in test tickets!", ephemeral=True)
    
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"🗑️ Removed {user.mention} from ticket!")

@bot.tree.command(name="next", description="Skip to next player in queue and close ticket")
async def next_cmd(interaction: discord.Interaction):
    if not any(interaction.channel.name.startswith(f"{gm}-test-") for gm in GAMEMODES.keys()):
        return await interaction.response.send_message("❌ Only in test tickets!", ephemeral=True)
    
    gamemode = None
    for gm in GAMEMODES.keys():
        if interaction.channel.name.startswith(f"{gm}-test-"):
            gamemode = gm
            break
    
    if not gamemode:
        return await interaction.response.send_message("❌ Could not determine gamemode!", ephemeral=True)
    
    ticket_data = db.get_ticket(interaction.channel.id)
    if not ticket_data:
        return await interaction.response.send_message("❌ No active ticket found!", ephemeral=True)
    
    current_user_id = ticket_data[1]
    current_user = interaction.guild.get_member(current_user_id)
    
    next_player = queue_sys.next_player(gamemode)
    
    msg_obj = queue_sys.messages.get(gamemode)
    if msg_obj:
        view = QueueView(gamemode)
        await msg_obj.edit(embed=create_queue_embed(gamemode), view=view)
    
    await interaction.response.send_message(
        f"⏭️ Skipped to next: {next_player['user'].mention if next_player else 'No one in queue'}\n"
        f"🗑️ Closing ticket in 3 seconds and removing role...", 
        ephemeral=True
    )
    
    await asyncio.sleep(3)
    
    # Entferne nur die Waitlist-Rolle (Gamemode Rolle)
    if current_user:
        gamemode_config = GAMEMODES.get(gamemode, {})
        waitlist_role = interaction.guild.get_role(gamemode_config.get("role_id", 0))
        if waitlist_role and waitlist_role in current_user.roles:
            await current_user.remove_roles(waitlist_role)
            await interaction.channel.send(f"✅ Removed {gamemode.upper()} waitlist role from {current_user.mention}")
    
    db.remove_ticket(interaction.channel.id)
    await interaction.channel.delete()

def parse_rank(rank_str):
    """Extrahiert Rank aus String wie 'HT3', 'ht3', 'LT1', etc."""
    rank_str = rank_str.lower().strip()
    match = re.match(r'(lt|ht)(\d+)', rank_str)
    if match:
        return match.group(1) + match.group(2)
    return None

def get_rank_role_id(gamemode, rank):
    """Gibt die Role ID für einen bestimmten Gamemode und Rank zurück"""
    if not rank:
        return None
    
    rank = rank.lower().strip()
    key = f"{gamemode}_{rank}"
    role_id = RANK_ROLES.get(key, 0)
    
    if role_id != 0:
        return role_id
    return None

class ResultModal(discord.ui.Modal, title="🏆 Test Result"):
    previous_rank = discord.ui.TextInput(
        label="Previous Rank", 
        placeholder="Unranked, LT5, HT3", 
        required=True
    )
    earned_rank = discord.ui.TextInput(
        label="Earned Rank", 
        placeholder="LT1-LT5 / HT1-HT10", 
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        ticket_data = db.get_ticket(interaction.channel.id)
        if not ticket_data:
            return await interaction.response.send_message(
                "❌ No active ticket!", 
                ephemeral=True
            )
            
        tested_user_id = ticket_data[1]
        gamemode = ticket_data[3]
        tested_user = interaction.guild.get_member(tested_user_id)
        if not tested_user:
            return await interaction.response.send_message(
                "❌ User not found!", 
                ephemeral=True
            )
            
        data = db.get_verified_data(tested_user_id, gamemode)
        if not data:
            return await interaction.response.send_message(
                "❌ Not verified!", 
                ephemeral=True
            )
            
        mc_name, server, gm, region = data[1], data[2], data[3], data[4]
        
        db.add_result(
            tested_user_id, 
            mc_name, 
            region, 
            gamemode, 
            server, 
            str(self.previous_rank), 
            str(self.earned_rank), 
            interaction.user.id, 
            interaction.user.name
        )
        
        # NEU: Entferne NUR die Waitlist-Rolle (nicht die Rank-Rolle)
        gamemode_config = GAMEMODES.get(gamemode, {})
        waitlist_role = interaction.guild.get_role(gamemode_config.get("role_id", 0))
        if waitlist_role and waitlist_role in tested_user.roles:
            await tested_user.remove_roles(waitlist_role)
        
        # Vergib Rank Rolle
        earned_rank_parsed = parse_rank(str(self.earned_rank))
        rank_role_msg = ""
        
        if earned_rank_parsed:
            rank_role_id = get_rank_role_id(gamemode, earned_rank_parsed)
            if rank_role_id:
                rank_role = interaction.guild.get_role(rank_role_id)
                if rank_role:
                    await tested_user.add_roles(rank_role)
                    rank_role_msg = f"\n✅ Assigned **{gamemode.upper()} {earned_rank_parsed.upper()}** role: {rank_role.mention}"
                else:
                    rank_role_msg = f"\n⚠️ Rank role not found in server"
            else:
                rank_role_msg = f"\n⚠️ No role configured for {gamemode.upper()} {earned_rank_parsed.upper()}"
        else:
            rank_role_msg = "\n⚠️ Could not parse rank"
        
        # Entferne aus verified_users für diesen Gamemode
        db.remove_verified(tested_user_id, gamemode)
        
        embed = discord.Embed(
            title=f"🏆 {mc_name}'s Test Results",
            color=ERROR_COLOR,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=f"https://mc-heads.net/body/{mc_name}/100.png")
        embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
        embed.add_field(name="Region", value=region, inline=False)
        embed.add_field(name="Username", value=f"`{mc_name}`", inline=False)
        embed.add_field(name="Gamemode", value=gamemode, inline=False)
        embed.add_field(name="Previous Rank", value=str(self.previous_rank), inline=False)
        embed.add_field(name="Rank Earned", value=f"**{str(self.earned_rank)}**", inline=False)
        
        await interaction.response.send_message(
            f"✅ Result entered!{rank_role_msg}\nClosing ticket...", 
            ephemeral=True
        )
        await interaction.channel.send(embed=embed)
        
        # Sende in Log-Channel mit Reaktionen
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_message = await log_channel.send(
                content=tested_user.mention, 
                embed=embed
            )
            
            reactions = ["👑", "🥳", "😱", "😭", "😂", "💀"]
            for reaction in reactions:
                await log_message.add_reaction(reaction)
        
        await asyncio.sleep(3)
        db.remove_ticket(interaction.channel.id)
        await interaction.channel.delete()

@bot.tree.command(name="result", description="Enter test result (in ticket)")
async def result_cmd(interaction: discord.Interaction):
    if not any(interaction.channel.name.startswith(f"{gm}-test-") for gm in GAMEMODES.keys()):
        return await interaction.response.send_message(
            "❌ Only in test tickets!", 
            ephemeral=True
        )
        
    ticket_data = db.get_ticket(interaction.channel.id)
    if not ticket_data:
        return await interaction.response.send_message(
            "❌ No ticket found!", 
            ephemeral=True
        )
    
    gamemode = ticket_data[3]
    if not db.is_tester_active(interaction.user.id, gamemode):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only active testers!", 
                ephemeral=True
            )
    
    await interaction.response.send_modal(ResultModal())
    
