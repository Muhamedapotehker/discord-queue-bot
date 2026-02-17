import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import sqlite3
import asyncio
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
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER PRIMARY KEY,
                minecraft_name TEXT,
                server TEXT,
                gamemode TEXT,
                region TEXT,
                verified_at TEXT
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

    def is_verified(self, user_id):
        self.cursor.execute('SELECT * FROM verified_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None

    def get_verified_data(self, user_id):
        self.cursor.execute('SELECT * FROM verified_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()

    def remove_verified(self, user_id):
        self.cursor.execute('DELETE FROM verified_users WHERE user_id = ?', (user_id,))
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

# Gamemode Config mit Rollen und Channel IDs
GAMEMODES = {
    "nethpot": {"role_id": 1473104076840370350, "category_id": 1473104195274932395, "channel_id": 1473104526968881308, "waitlist_id": 1473103962428412025, "emoji": "🔪"},
    "pot": {"role_id": 0, "category_id": 0, "channel_id": 0, "waitlist_id": 0, "emoji": "⚗️"},
    "smp": {"role_id": 1473104080779088067, "category_id": 1473104226799321160, "channel_id": 1473104544161599710, "waitlist_id": 1473103965649506556, "emoji": "👑"},
    "uhc": {"role_id": 1473104083211649159, "category_id": 1473104190485299260, "channel_id": 1473104554743697418, "waitlist_id": 1473103964831481928, "emoji": "❤️"},
    "sword": {"role_id": 1473104077977026641, "category_id": 1473104187339571412, "channel_id": 1473104534141272064, "waitlist_id": 1473103960431661076, "emoji": "🗡️"},
    "axe": {"role_id": 1473104082225987786, "category_id": 1473104229500715010, "channel_id": 1473104552084639744, "waitlist_id": 1473103966589157498, "emoji": "🪓"},
    "crystal": {"role_id": 1473104079759605770, "category_id": 1473104193051955455, "channel_id": 1473104541074325626, "waitlist_id": 1473103961581162538, "emoji": "💣"},
    "mace": {"role_id": 1473104078379679901, "category_id": 1473104232805564508, "channel_id": 1473104538012745912, "waitlist_id": 1473103967125897217, "emoji": "🔨"},
    "diapot": {"role_id": 1473104089218023474, "category_id": 1473104234982539315, "channel_id": 1473104530509008926, "waitlist_id": 1473103963401486522, "emoji": "💎"}
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
        placeholder="nethpot, pot, smp, uhc, sword, axe, crystal, mace, diapot, cpvp",
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

        embed = discord.Embed(
            title="✅ Verification Complete!",
            description=f"**MC:** `{temp_data['mc_name']}`\n**Server:** {self.server}\n**Gamemode:** {gamemode}\n**Region:** {self.region}\n\nWait for a tester to start!",
            color=SUCCESS_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Verification View mit Buttons
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Account", style=discord.ButtonStyle.primary, emoji="📝")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db.is_verified(interaction.user.id):
            return await interaction.response.send_message(
                "❌ You are already verified!", 
                ephemeral=True
            )
        await interaction.response.send_modal(VerifyModal())

    @discord.ui.button(label="Enter Waitlist", style=discord.ButtonStyle.primary, emoji="📋")
    async def waitlist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db.is_verified(interaction.user.id):
            return await interaction.response.send_message(
                "✅ You are already verified! Wait for a tester to start.", 
                ephemeral=True
            )
        await interaction.response.send_modal(WaitlistModal())

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
        value="• Region should be the region of the server you wish to test on\n• Username should be the name of the account you will be testing on",
        inline=False
    )

    embed.add_field(
        name="⚠️ Warning",
        value="Failure to provide authentic information will result in a denied test.",
        inline=False
    )

    await interaction.response.send_message("✅ Panel created!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VerificationView())

# "No Testers" Embed
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
        title=f"{emoji} [1.21+] Minecraft {display_name} VM Community",
        description=f"**No Testers Online**\n\nNo testers for your region are available at this time.\nYou will be pinged when a tester is available.\nCheck back later!{last_session_text}",
        color=INFO_COLOR
    )
    return embed

# Aktive Queue Embed
def create_queue_embed(gamemode):
    config = GAMEMODES.get(gamemode, {})

    testers = db.get_testers(gamemode)

    # Tester-Liste mit Mentions
    tester_mentions = []
    for tester_id in testers:
        tester = bot.get_user(tester_id)
        if tester:
            tester_mentions.append(tester.mention)

    # Queue-Liste
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
        if not db.is_verified(interaction.user.id):
            return await interaction.response.send_message("❌ Verify first!", ephemeral=True)

        user_data = db.get_verified_data(interaction.user.id)
        if not user_data:
            return await interaction.response.send_message("❌ Not verified!", ephemeral=True)

        user_gamemode = user_data[3] if len(user_data) > 3 else None
        if user_gamemode != self.gamemode:
            return await interaction.response.send_message(
                f"❌ You are verified for {user_gamemode or 'none'}! Use that queue instead.",
                ephemeral=True
            )

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

    # Lösche alte "No Testers" Nachricht
    if gamemode in queue_sys.closed_messages:
        try:
            await queue_sys.closed_messages[gamemode].delete()
        except:
            pass
        del queue_sys.closed_messages[gamemode]

    # Lösche alte Queue-Nachricht
    if queue_sys.messages.get(gamemode):
        try:
            await queue_sys.messages[gamemode].delete()
        except:
            pass

    # Sende neue Queue-Nachricht mit @here
    view = QueueView(gamemode)
    embed = create_queue_embed(gamemode)
    queue_sys.messages[gamemode] = await interaction.channel.send("@here", embed=embed, view=view)

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

    # Lösche aktive Queue-Nachricht
    if queue_sys.messages.get(gamemode):
        try:
            await queue_sys.messages[gamemode].delete()
        except:
            pass
        queue_sys.messages[gamemode] = None

    # Wenn keine Tester mehr, sende "No Testers" Embed
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

# TICKET - Automatisch in richtige Kategorie basierend auf Gamemode
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

    if not db.is_verified(user.id):
        return await interaction.response.send_message(f"❌ User not verified!", ephemeral=True)

    data = db.get_verified_data(user.id)
    mc_name, region, server = data[1], data[4], data[2]

    # HIER: Finde die richtige Kategorie basierend auf Gamemode
    gamemode_config = GAMEMODES.get(gamemode, {})
    category_id = gamemode_config.get("category_id", 0)

    # Versuche zuerst die Gamemode-spezifische Kategorie zu finden
    category = None
    if category_id != 0:
        category = discord.utils.get(interaction.guild.categories, id=category_id)

    # Fallback auf die allgemeine Ticket-Kategorie wenn keine gefunden
    if not category:
        category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)

    # Wenn immer noch keine Kategorie, error
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

    # Erstelle Ticket in der gefundenen Kategorie
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

@bot.tree.command(name="next", description="Skip to next player in queue")
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

    next_player = queue_sys.next_player(gamemode)
    if not next_player:
        return await interaction.response.send_message("❌ No one in queue!", ephemeral=True)

    msg_obj = queue_sys.messages.get(gamemode)
    if msg_obj:
        view = QueueView(gamemode)
        await msg_obj.edit(embed=create_queue_embed(gamemode), view=view)

    await interaction.response.send_message(
        f"⏭️ Skipped to next: {next_player['user'].mention}\n🎮 They are now ready to test!"
    )

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

        data = db.get_verified_data(tested_user_id)
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

        gamemode_config = GAMEMODES.get(gamemode, {})
        verified_role = interaction.guild.get_role(gamemode_config.get("role_id", 0))
        if verified_role:
            await tested_user.remove_roles(verified_role)
        db.remove_verified(tested_user_id)

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
            "✅ Result entered! Closing ticket...", 
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

            # Füge Reaktionen hinzu
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

# Start
keep_alive()
bot.run("MTQ3Mjc2Mjc0MzMxOTk1Nzc5OA.GsndhM.MDhhheXK2aCdp-fv0pnn4N0_d_uc7lEHjo-4Xg")
