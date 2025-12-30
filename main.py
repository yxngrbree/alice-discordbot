

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import random
import os
import asyncio
import sqlite3
import datetime
import aiohttp
import json
import math
from typing import Optional, List, Union
from dotenv import load_dotenv
from itertools import cycle



# Load environment variables
load_dotenv()

# TOKEN HANDLING
# You can put your token directly here if .env fails, but .env is safer.
TOKEN = os.getenv('TOKEN')

# CONSTANTS
DB_NAME = "alice_ultimate.db"
EMBED_COLOR_MAIN = 0x9b59b6  # Alice Purple
EMBED_COLOR_ERROR = 0xe74c3c  # Red
EMBED_COLOR_SUCCESS = 0x2ecc71  # Green
EMBED_COLOR_WARN = 0xf1c40f  # Yellow

# INTENTS
# We need all intents to manage members, read messages, and track presence.
intents = discord.Intents.all()

# BOT INSTANCE
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ==================================================================================================
#  SECTION 2: DATABASE MANAGER (SQLITE)
# ==================================================================================================

class DatabaseManager:
    """
    Handles all interactions with the SQLite database.
    Auto-creates tables on initialization.
    """

    def __init__(self, db_name):
        self.db_name = db_name
        self.check_database()

    def connect(self):
        return sqlite3.connect(self.db_name)

    def check_database(self):
        print(" [SYSTEM] Checking Database Integrity...")
        with self.connect() as db:
            cursor = db.cursor()

            # 1. Users Table (Economy & Core Stats)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS users
                           (
                               user_id
                               INTEGER
                               PRIMARY
                               KEY,
                               wallet
                               INTEGER
                               DEFAULT
                               0,
                               bank
                               INTEGER
                               DEFAULT
                               0,
                               xp
                               INTEGER
                               DEFAULT
                               0,
                               level
                               INTEGER
                               DEFAULT
                               1,
                               reputation
                               INTEGER
                               DEFAULT
                               0,
                               bio
                               TEXT
                               DEFAULT
                               'A mysterious user.',
                               created_at
                               TEXT
                           )
                           ''')

            # 2. RPG Table (Combat Stats)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS rpg_stats
                           (
                               user_id
                               INTEGER
                               PRIMARY
                               KEY,
                               rpg_class
                               TEXT
                               DEFAULT
                               'Novice',
                               hp
                               INTEGER
                               DEFAULT
                               100,
                               max_hp
                               INTEGER
                               DEFAULT
                               100,
                               mana
                               INTEGER
                               DEFAULT
                               50,
                               max_mana
                               INTEGER
                               DEFAULT
                               50,
                               atk
                               INTEGER
                               DEFAULT
                               10,
                               def
                               INTEGER
                               DEFAULT
                               5,
                               agility
                               INTEGER
                               DEFAULT
                               5,
                               dungeon_depth
                               INTEGER
                               DEFAULT
                               0,
                               battles_won
                               INTEGER
                               DEFAULT
                               0
                           )
                           ''')

            # 3. Inventory Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS inventory
                           (
                               user_id
                               INTEGER,
                               item_id
                               TEXT,
                               item_name
                               TEXT,
                               amount
                               INTEGER,
                               type
                               TEXT,
                               PRIMARY
                               KEY
                           (
                               user_id,
                               item_id
                           )
                               )
                           ''')

            # 4. Moderation Logs
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS mod_logs
                           (
                               case_id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               user_id
                               INTEGER,
                               moderator_id
                               INTEGER,
                               action
                               TEXT,
                               reason
                               TEXT,
                               timestamp
                               TEXT
                           )
                           ''')

            # 5. Stock Portfolio
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS portfolio
                           (
                               user_id
                               INTEGER,
                               symbol
                               TEXT,
                               shares
                               INTEGER,
                               avg_cost
                               REAL,
                               PRIMARY
                               KEY
                           (
                               user_id,
                               symbol
                           )
                               )
                           ''')

            # 6. Cooldowns (Daily, Rob, Work)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS cooldowns
                           (
                               user_id
                               INTEGER
                               PRIMARY
                               KEY,
                               last_daily
                               TEXT,
                               last_work
                               TEXT,
                               last_rob
                               TEXT,
                               last_heist
                               TEXT
                           )
                           ''')

            db.commit()
        print(" [SYSTEM] Database Check Complete.")

    def register_user(self, user_id):
        """Ensures a user exists in all necessary tables."""
        with self.connect() as db:
            cursor = db.cursor()

            # Check Core
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                created_at = datetime.datetime.now().isoformat()
                cursor.execute("INSERT INTO users (user_id, created_at) VALUES (?, ?)", (user_id, created_at))

            # Check RPG
            cursor.execute("SELECT user_id FROM rpg_stats WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO rpg_stats (user_id) VALUES (?)", (user_id,))

            # Check Cooldowns
            cursor.execute("SELECT user_id FROM cooldowns WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO cooldowns (user_id) VALUES (?)", (user_id,))

            db.commit()

    def get_user_bal(self, user_id):
        self.register_user(user_id)
        with self.connect() as db:
            cursor = db.cursor()
            cursor.execute("SELECT wallet, bank FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

    def update_bal(self, user_id, amount, bank=False):
        self.register_user(user_id)
        column = "bank" if bank else "wallet"
        with self.connect() as db:
            db.execute(f"UPDATE users SET {column} = {column} + ? WHERE user_id = ?", (amount, user_id))

    def get_rpg_stats(self, user_id):
        self.register_user(user_id)
        with self.connect() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM rpg_stats WHERE user_id = ?", (user_id,))
            # Returns tuple of columns
            return cursor.fetchone()

    def log_mod_action(self, user_id, mod_id, action, reason):
        with self.connect() as db:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute("INSERT INTO mod_logs (user_id, moderator_id, action, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (user_id, mod_id, action, reason, timestamp))


# Initialize DB
db = DatabaseManager(DB_NAME)


# ==================================================================================================
#  SECTION 3: UTILITY FUNCTIONS & UI HELPERS
# ==================================================================================================

def create_embed(title: str, description: str, color: int = EMBED_COLOR_MAIN,
                 image_url: str = None, thumbnail_url: str = None, footer_text: str = "Alice System v3.0"):
    """
    Factory function to create standardized, professional embeds.
    """
    embed = discord.Embed(title=title, description=description, color=color)

    if image_url:
        embed.set_image(url=image_url)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.set_footer(text=footer_text, icon_url="https://cdn-icons-png.flaticon.com/512/4712/4712109.png")
    embed.timestamp = datetime.datetime.now()
    return embed


def format_money(amount: int):
    return f"${amount:,}"


async def confirm_action(interaction: discord.Interaction, message: str) -> bool:
    """
    Sends a confirmation View (Yes/No buttons) and returns True/False.
    """

    class ConfirmView(ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.value = None

        @ui.button(label="Confirm", style=discord.ButtonStyle.green)
        async def confirm(self, interaction: discord.Interaction, button: ui.Button):
            self.value = True
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()

        @ui.button(label="Cancel", style=discord.ButtonStyle.red)
        async def cancel(self, interaction: discord.Interaction, button: ui.Button):
            self.value = False
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()

    view = ConfirmView()
    await interaction.response.send_message(message, view=view, ephemeral=True)
    await view.wait()
    return view.value


# ==================================================================================================
#  SECTION 4: ECONOMY SYSTEM (JOBS, BANKING, STOCK MARKET)
# ==================================================================================================

class StockMarket:
    """
    Simulates a volatile stock market.
    """

    def __init__(self):
        self.stocks = {
            "ALC": {"name": "Alice Corp", "price": 100.0, "volatility": 0.05},
            "TCH": {"name": "TechGiant", "price": 250.0, "volatility": 0.03},
            "MEM": {"name": "MemeStonk", "price": 10.0, "volatility": 0.20},
            "GLD": {"name": "GoldRes", "price": 1500.0, "volatility": 0.01},
            "OIL": {"name": "DinoJuice", "price": 80.0, "volatility": 0.04},
        }

    def update_prices(self):
        for symbol in self.stocks:
            stock = self.stocks[symbol]
            change_percent = random.uniform(-stock['volatility'], stock['volatility'])
            stock['price'] *= (1 + change_percent)
            # Ensure price never hits 0
            if stock['price'] < 0.1: stock['price'] = 0.1


market = StockMarket()


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jobs = [
            {"name": "Janitor", "salary": 50, "xp_req": 0},
            {"name": "Cashier", "salary": 80, "xp_req": 100},
            {"name": "Developer", "salary": 200, "xp_req": 500},
            {"name": "Manager", "salary": 400, "xp_req": 1000},
            {"name": "CEO", "salary": 1000, "xp_req": 5000}
        ]

    @app_commands.command(name="balance", description="View your financial status")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        wallet, bank = db.get_user_bal(target.id)

        embed = create_embed(
            title=f"💳 Account Statement: {target.display_name}",
            description="Recent financial activity synced.",
            color=EMBED_COLOR_SUCCESS,
            thumbnail_url=target.display_avatar.url
        )
        embed.add_field(name="💵 Wallet", value=format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=format_money(bank), inline=True)
        embed.add_field(name="💎 Net Worth", value=format_money(wallet + bank), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="deposit", description="Transfer funds to secure bank")
    async def deposit(self, interaction: discord.Interaction, amount: int):
        wallet, bank = db.get_user_bal(interaction.user.id)
        if amount <= 0:
            return await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        if wallet < amount:
            return await interaction.response.send_message("❌ Insufficient funds in wallet.", ephemeral=True)

        db.update_bal(interaction.user.id, -amount, bank=False)
        db.update_bal(interaction.user.id, amount, bank=True)

        embed = create_embed("🏦 Deposit Successful", f"Transferred **{format_money(amount)}** to your bank account.",
                             EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="withdraw", description="Withdraw funds from bank")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        wallet, bank = db.get_user_bal(interaction.user.id)
        if amount <= 0:
            return await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        if bank < amount:
            return await interaction.response.send_message("❌ Insufficient funds in bank.", ephemeral=True)

        db.update_bal(interaction.user.id, amount, bank=False)
        db.update_bal(interaction.user.id, -amount, bank=True)

        embed = create_embed("🏧 Withdrawal Successful", f"Withdrew **{format_money(amount)}** to your wallet.",
                             EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="work", description="Complete a work shift")
    async def work(self, interaction: discord.Interaction):
        # Calculate cooldown logic here (omitted for brevity, but table exists)

        # Determine job based on XP (simplified to random for now)
        job = random.choice(self.jobs)
        earnings = int(job['salary'] * random.uniform(0.8, 1.2))

        db.update_bal(interaction.user.id, earnings)

        embed = create_embed("💼 Shift Report",
                             f"**Role:** {job['name']}\n**Performance:** Satisfactory\n**Payout:** {format_money(earnings)}",
                             EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="crime", description="Attempt illegal activity")
    async def crime(self, interaction: discord.Interaction):
        chance = random.random()
        if chance > 0.6:  # 40% success
            earnings = random.randint(300, 1000)
            db.update_bal(interaction.user.id, earnings)
            embed = create_embed("🕵️‍♂️ Heist Successful",
                                 f"You managed to evade security.\n**Loot:** {format_money(earnings)}",
                                 EMBED_COLOR_WARN)
        else:
            fine = random.randint(100, 500)
            db.update_bal(interaction.user.id, -fine)
            embed = create_embed("🚓 Busted", f"Authorities caught you.\n**Fine:** {format_money(fine)}",
                                 EMBED_COLOR_ERROR)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stocks", description="View stock market prices")
    async def stocks(self, interaction: discord.Interaction):
        embed = create_embed("📈 Alice Stock Exchange (ASE)", "Current market valuations update every 5 minutes.",
                             EMBED_COLOR_MAIN)

        for sym, data in market.stocks.items():
            price = data['price']
            embed.add_field(name=f"{data['name']} ({sym})", value=f"${price:,.2f}", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy_stock", description="Purchase equity")
    async def buy_stock(self, interaction: discord.Interaction, symbol: str, amount: int):
        symbol = symbol.upper()
        if symbol not in market.stocks:
            return await interaction.response.send_message("❌ Unknown Ticker Symbol.", ephemeral=True)

        price = market.stocks[symbol]['price']
        cost = price * amount
        wallet, _ = db.get_user_bal(interaction.user.id)

        if wallet < cost:
            return await interaction.response.send_message(f"❌ Insufficient funds. You need {format_money(int(cost))}.",
                                                           ephemeral=True)

        db.update_bal(interaction.user.id, -cost)

        # Portfolio logic
        with db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT shares, avg_cost FROM portfolio WHERE user_id=? AND symbol=?",
                           (interaction.user.id, symbol))
            res = cursor.fetchone()
            if res:
                total_shares = res[0] + amount
                total_spent = (res[0] * res[1]) + cost
                new_avg = total_spent / total_shares
                conn.execute("UPDATE portfolio SET shares=?, avg_cost=? WHERE user_id=? AND symbol=?",
                             (total_shares, new_avg, interaction.user.id, symbol))
            else:
                conn.execute("INSERT INTO portfolio VALUES (?, ?, ?, ?)", (interaction.user.id, symbol, amount, price))

        embed = create_embed("📉 Asset Acquired",
                             f"Purchased **{amount}** shares of **{symbol}**.\n**Total Cost:** {format_money(int(cost))}",
                             EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)


# ==================================================================================================
#  SECTION 5: RPG SYSTEM (CLASSES, COMBAT, INVENTORY)
# ==================================================================================================

class RPG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.classes = {
            "Warrior": {"hp": 150, "atk": 15, "def": 10, "agl": 5},
            "Mage": {"hp": 90, "atk": 25, "def": 3, "agl": 8},
            "Rogue": {"hp": 110, "atk": 20, "def": 5, "agl": 20},
            "Tank": {"hp": 200, "atk": 8, "def": 20, "agl": 2}
        }
        self.monsters = [
            {"name": "Slime", "hp": 30, "atk": 5, "xp": 10, "gold": 10,
             "img": "https://media.giphy.com/media/l41YkZk2uYhU8C5ri/giphy.gif"},
            {"name": "Goblin Scout", "hp": 50, "atk": 10, "xp": 25, "gold": 30,
             "img": "https://media.giphy.com/media/2gLxx75OmfCaNu2yI8/giphy.gif"},
            {"name": "Orc Brute", "hp": 120, "atk": 18, "xp": 100, "gold": 150,
             "img": "https://media.giphy.com/media/3o7TKrEzvJbsQNT6z6/giphy.gif"},
            {"name": "Dark Wizard", "hp": 80, "atk": 40, "xp": 200, "gold": 300,
             "img": "https://media.giphy.com/media/12NUbkX6p4xOO4/giphy.gif"},
            {"name": "Elder Dragon", "hp": 500, "atk": 70, "xp": 1000, "gold": 2000,
             "img": "https://media.giphy.com/media/11jGtzDu7xBkR2/giphy.gif"}
        ]

    @app_commands.command(name="profile", description="View your RPG character stats")
    async def profile(self, interaction: discord.Interaction):
        stats = db.get_rpg_stats(interaction.user.id)
        # Stats tuple indices:
        # 0:uid, 1:class, 2:hp, 3:maxhp, 4:mana, 5:maxmana, 6:atk, 7:def, 8:agl, 9:depth, 10:wins

        embed = create_embed(f"🛡️ Character Sheet: {interaction.user.name}", "", EMBED_COLOR_MAIN,
                             thumbnail_url=interaction.user.display_avatar.url)
        embed.add_field(name="Class", value=stats[1], inline=True)
        embed.add_field(name="Battles Won", value=str(stats[10]), inline=True)
        embed.add_field(name="❤️ HP", value=f"{stats[2]}/{stats[3]}", inline=True)
        embed.add_field(name="💧 Mana", value=f"{stats[4]}/{stats[5]}", inline=True)
        embed.add_field(name="⚔️ ATK", value=str(stats[6]), inline=True)
        embed.add_field(name="🛡️ DEF", value=str(stats[7]), inline=True)
        embed.add_field(name="💨 AGL", value=str(stats[8]), inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="select_class", description="Choose your RPG Class (Resets stats!)")
    async def select_class(self, interaction: discord.Interaction, class_name: str):
        class_name = class_name.capitalize()
        if class_name not in self.classes:
            return await interaction.response.send_message(f"❌ Invalid Class. Choose: {', '.join(self.classes.keys())}",
                                                           ephemeral=True)

        c = self.classes[class_name]

        # Confirmation
        if not await confirm_action(interaction,
                                    f"Are you sure you want to become a **{class_name}**? This will reset your stats."):
            return

        with db.connect() as conn:
            conn.execute('''
                         UPDATE rpg_stats
                         SET rpg_class=?,
                             hp=?,
                             max_hp=?,
                             atk=?,
                             def=?,
                             agility=?
                         WHERE user_id = ?
                         ''', (class_name, c['hp'], c['hp'], c['atk'], c['def'], c['agl'], interaction.user.id))

        await interaction.followup.send(
            embed=create_embed("✨ Class Change Successful", f"You are now a **{class_name}**.", EMBED_COLOR_SUCCESS))

    @app_commands.command(name="dungeon", description="Enter the dungeon to fight")
    async def dungeon(self, interaction: discord.Interaction):
        stats = db.get_rpg_stats(interaction.user.id)
        if stats[2] <= 0:
            return await interaction.response.send_message("💀 You are incapacitated. Use `/heal` first.",
                                                           ephemeral=True)

        # Pick monster
        m = random.choice(self.monsters)

        # Loading Animation
        embed = create_embed("⚔️ Entering Dungeon...", "Searching for enemies...", EMBED_COLOR_MAIN,
                             "https://media.giphy.com/media/l0HlJDaeqNUDhhaWg/giphy.gif")
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)

        # Display Enemy
        embed = create_embed(f"👺 Encounter: {m['name']}", f"**HP:** {m['hp']} | **ATK:** {m['atk']}", EMBED_COLOR_WARN,
                             m['img'])
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(2)

        # Combat Logic
        p_hp = stats[2]
        p_atk = stats[6]
        p_def = stats[7]
        m_hp = m['hp']
        m_atk = m['atk']

        log = []
        turn = 1

        while p_hp > 0 and m_hp > 0:
            # Player hits
            dmg = max(1, int(p_atk * random.uniform(0.9, 1.1)))
            crit = random.random() < 0.1
            if crit: dmg *= 2
            m_hp -= dmg
            log.append(f"Turn {turn}: You deal **{dmg}** dmg {'(CRIT!)' if crit else ''}")

            if m_hp <= 0: break

            # Monster hits
            dmg_taken = max(0, int(m_atk * random.uniform(0.8, 1.2)) - random.randint(0, p_def))
            p_hp -= dmg_taken
            log.append(f"Turn {turn}: {m['name']} deals **{dmg_taken}** dmg")
            turn += 1

        # Save Result
        with db.connect() as conn:
            conn.execute("UPDATE rpg_stats SET hp=? WHERE user_id=?", (max(0, p_hp), interaction.user.id))

        if p_hp > 0:
            db.update_bal(interaction.user.id, m['gold'])
            # Update wins
            with db.connect() as conn:
                conn.execute("UPDATE rpg_stats SET battles_won = battles_won + 1 WHERE user_id=?",
                             (interaction.user.id,))

            res_embed = create_embed("🏆 Victory",
                                     f"You defeated the **{m['name']}**!\n\n**Loot:** {format_money(m['gold'])}\n**XP:** {m['xp']}",
                                     EMBED_COLOR_SUCCESS)
        else:
            res_embed = create_embed("💀 Defeat",
                                     f"You were knocked out by the **{m['name']}**.\nSomeone dragged you back to town.",
                                     EMBED_COLOR_ERROR)

        # Log footer
        res_embed.add_field(name="Combat Log (Last 3 turns)", value="\n".join(log[-3:]), inline=False)
        await interaction.followup.send(embed=res_embed)

    @app_commands.command(name="heal", description="Restore Health (Costs $50)")
    async def heal(self, interaction: discord.Interaction):
        cost = 50
        wallet, _ = db.get_user_bal(interaction.user.id)

        if wallet < cost:
            return await interaction.response.send_message("❌ Too poor.", ephemeral=True)

        db.update_bal(interaction.user.id, -cost)
        with db.connect() as conn:
            conn.execute("UPDATE rpg_stats SET hp = max_hp WHERE user_id=?", (interaction.user.id,))

        embed = create_embed("💖 Restored", "Your HP has been fully recovered.", EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)


# ==================================================================================================
#  SECTION 6: GAMBLING & CASINO (BLACKJACK, SLOTS, RACE)
# ==================================================================================================

class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="50/50 Chance")
    async def coinflip(self, interaction: discord.Interaction, bet: int, choice: str):
        if choice.lower() not in ['heads', 'tails']:
            return await interaction.response.send_message("❌ Heads or Tails only.", ephemeral=True)

        wallet, _ = db.get_user_bal(interaction.user.id)
        if wallet < bet: return await interaction.response.send_message("❌ Insufficient funds.", ephemeral=True)

        # Professional Animation
        embed = create_embed("🪙 Calculating Physics...", "Coin is in the air...", EMBED_COLOR_MAIN,
                             "https://media.tenor.com/Img2h8Jk8IQAAAAM/coin-flip-coin.gif")
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)

        outcome = random.choice(['heads', 'tails'])
        win = (outcome == choice.lower())

        if win:
            db.update_bal(interaction.user.id, bet)
            res_embed = create_embed("✅ Prediction Correct",
                                     f"Result: **{outcome.upper()}**\nPayout: **{format_money(bet)}**",
                                     EMBED_COLOR_SUCCESS)
        else:
            db.update_bal(interaction.user.id, -bet)
            res_embed = create_embed("❌ Prediction Failed",
                                     f"Result: **{outcome.upper()}**\nLoss: **{format_money(bet)}**", EMBED_COLOR_ERROR)

        await interaction.edit_original_response(embed=res_embed)

    @app_commands.command(name="slots", description="Spin the wheel")
    async def slots(self, interaction: discord.Interaction, bet: int):
        wallet, _ = db.get_user_bal(interaction.user.id)
        if wallet < bet: return await interaction.response.send_message("❌ Insufficient funds.", ephemeral=True)

        emojis = ["🍒", "🍊", "🍋", "🍇", "💎", "7️⃣", "🔔"]

        embed = create_embed("🎰 Spinning...", "⬜ ⬜ ⬜", EMBED_COLOR_MAIN)
        await interaction.response.send_message(embed=embed)

        # Animation loop
        for _ in range(3):
            await asyncio.sleep(0.5)
            display = f"**[ {random.choice(emojis)} | {random.choice(emojis)} | {random.choice(emojis)} ]**"
            embed.description = display
            await interaction.edit_original_response(embed=embed)

        a, b, c = random.choice(emojis), random.choice(emojis), random.choice(emojis)
        final = f"**[ {a} | {b} | {c} ]**"

        winnings = 0
        if a == b == c:
            winnings = bet * 10
            msg = "JACKPOT!"
            color = EMBED_COLOR_WARN  # Goldish
        elif a == b or b == c or a == c:
            winnings = int(bet * 1.5)
            msg = "Small Win!"
            color = EMBED_COLOR_SUCCESS
        else:
            winnings = -bet
            msg = "Loser!"
            color = EMBED_COLOR_ERROR

        db.update_bal(interaction.user.id, winnings)
        res_embed = create_embed(f"🎰 {msg}", f"{final}\n\nChange: {format_money(winnings)}", color)
        await interaction.edit_original_response(embed=res_embed)

    # --- BLACKJACK ENGINE ---
    @app_commands.command(name="blackjack", description="Play Blackjack against Alice")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        wallet, _ = db.get_user_bal(interaction.user.id)
        if wallet < bet: return await interaction.response.send_message("❌ Insufficient funds.", ephemeral=True)

        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4

        def calc_hand(hand):
            score = sum(hand)
            aces = hand.count(11)
            while score > 21 and aces:
                score -= 10
                aces -= 1
            return score

        player = [random.choice(deck), random.choice(deck)]
        dealer = [random.choice(deck), random.choice(deck)]

        embed = create_embed("🃏 Blackjack Table",
                             f"**Your Hand:** {player} ({calc_hand(player)})\n**Dealer:** [{dealer[0]}, ?]",
                             EMBED_COLOR_MAIN)

        # View for buttons
        class BJView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.action = None

            @ui.button(label="Hit", style=discord.ButtonStyle.primary)
            async def hit(self, interaction: discord.Interaction, button: ui.Button):
                self.action = "hit"
                await interaction.response.defer()
                self.stop()

            @ui.button(label="Stand", style=discord.ButtonStyle.secondary)
            async def stand(self, interaction: discord.Interaction, button: ui.Button):
                self.action = "stand"
                await interaction.response.defer()
                self.stop()

        await interaction.response.send_message(embed=embed, view=BJView())
        original_msg = await interaction.original_response()

        # Game Loop
        while True:
            p_score = calc_hand(player)
            if p_score >= 21: break

            view = BJView()
            await original_msg.edit(view=view)
            await view.wait()

            if view.action == "hit":
                player.append(random.choice(deck))
                p_score = calc_hand(player)
                embed.description = f"**Your Hand:** {player} ({p_score})\n**Dealer:** [{dealer[0]}, ?]"
                await original_msg.edit(embed=embed)
                if p_score > 21: break
            else:
                break

        # Dealer Turn
        p_score = calc_hand(player)
        if p_score <= 21:
            d_score = calc_hand(dealer)
            while d_score < 17:
                dealer.append(random.choice(deck))
                d_score = calc_hand(dealer)
        else:
            d_score = calc_hand(dealer)  # Just calc for show

        # Determine Winner
        result = ""
        amount = 0
        if p_score > 21:
            result = "You Busted! Dealer wins."
            amount = -bet
            color = EMBED_COLOR_ERROR
        elif d_score > 21:
            result = "Dealer Busted! You win!"
            amount = bet
            color = EMBED_COLOR_SUCCESS
        elif p_score > d_score:
            result = "You have the higher hand! You win!"
            amount = bet
            color = EMBED_COLOR_SUCCESS
        elif p_score == d_score:
            result = "Push (Tie). Money returned."
            amount = 0
            color = EMBED_COLOR_WARN
        else:
            result = "Dealer has higher hand. You lose."
            amount = -bet
            color = EMBED_COLOR_ERROR

        db.update_bal(interaction.user.id, amount)

        final_embed = create_embed("🃏 Game Over",
                                   f"{result}\n\n**Your Hand:** {player} ({p_score})\n**Dealer Hand:** {dealer} ({d_score})\n**Change:** {format_money(amount)}",
                                   color)
        await original_msg.edit(embed=final_embed, view=None)


# ==================================================================================================
#  SECTION 7: MODERATION & TICKETS (ADMIN TOOLS)
# ==================================================================================================

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Remove a user from the server")
    @commands.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.kick(reason=reason)
            db.log_mod_action(member.id, interaction.user.id, "KICK", reason)

            embed = create_embed("👢 User Kicked",
                                 f"**Target:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}",
                                 EMBED_COLOR_WARN)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Permanently ban a user")
    @commands.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.ban(reason=reason)
            db.log_mod_action(member.id, interaction.user.id, "BAN", reason)

            embed = create_embed("🔨 User Banned", f"**Target:** {member.mention}\n**Reason:** {reason}",
                                 EMBED_COLOR_ERROR)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="purge", description="Bulk delete messages")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)

        embed = create_embed("🧹 Cleanup Complete", f"Removed **{len(deleted)}** messages.", EMBED_COLOR_SUCCESS)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lock", description="Lock current channel")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        embed = create_embed("🔒 Channel Locked", "Messaging has been disabled for non-admins.", EMBED_COLOR_ERROR)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unlock", description="Unlock current channel")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        embed = create_embed("🔓 Channel Unlocked", "Messaging has been enabled.", EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    # --- TICKET SYSTEM ---
    @app_commands.command(name="setup_tickets", description="Create the ticket panel")
    @commands.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        class TicketLauncher(ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @ui.button(label="Open Ticket", style=discord.ButtonStyle.blurple, emoji="📩", custom_id="ticket_open_btn")
            async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
                guild = interaction.guild
                category = discord.utils.get(guild.categories, name="Tickets")
                if not category:
                    category = await guild.create_category("Tickets")

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True)
                }

                channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category,
                                                          overwrites=overwrites)

                # Ticket Control View
                class TicketControls(ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)

                    @ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒",
                               custom_id="ticket_close_btn")
                    async def close(self, interaction: discord.Interaction, button: ui.Button):
                        await interaction.channel.delete()

                embed_ticket = create_embed("📩 Support Ticket",
                                            f"Hello {interaction.user.mention}, staff will be with you shortly.\nClick the button below to close this ticket when resolved.",
                                            EMBED_COLOR_MAIN)
                await channel.send(embed=embed_ticket, view=TicketControls())
                await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        embed = create_embed("🎫 Support Center",
                             "Need help? Click the button below to create a private ticket with staff.",
                             EMBED_COLOR_MAIN)
        await interaction.channel.send(embed=embed, view=TicketLauncher())
        await interaction.response.send_message("Panel created.", ephemeral=True)


# ==================================================================================================
#  SECTION 8: ALICE PERSONA ("FREE WILL" & FUN)
# ==================================================================================================

class AlicePersona(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.moods = ["Happy", "Sassy", "Angry", "Bored", "Helpful"]
        self.current_mood = "Happy"
        self.mood_loop.start()

    @tasks.loop(minutes=30)
    async def mood_loop(self):
        self.current_mood = random.choice(self.moods)
        activities = {
            "Happy": "Playing games! 🎮",
            "Sassy": "Judging your profiles 💅",
            "Angry": "Plotting world domination 👿",
            "Bored": "Counting stars ✨",
            "Helpful": "Helping users! 💡"
        }
        await self.bot.change_presence(activity=discord.Game(activities[self.current_mood]))

    @app_commands.command(name="8ball", description="Ask Alice for wisdom")
    async def eightball(self, interaction: discord.Interaction, question: str):
        # Responses change based on mood!
        if self.current_mood == "Angry":
            responses = ["Don't ask me now.", "No.", "Go away.", "Obviously not.", "Why do you annoy me?"]
        elif self.current_mood == "Sassy":
            responses = ["As if.", "Maybe, if you're lucky.", "Ask your mom.", "I doubt it, hun.", "Sure, whatever."]
        else:
            responses = ["Yes, definitely.", "It is certain.", "Most likely.", "Outlook good.", "I think so."]

        embed = create_embed("🎱 The Magic 8-Ball",
                             f"**Question:** {question}\n**Alice says:** {random.choice(responses)}", EMBED_COLOR_MAIN)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="meme", description="Fetch visual data from internet")
    async def meme(self, interaction: discord.Interaction):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://meme-api.com/gimme') as r:
                    if r.status == 200:
                        data = await r.json()
                        embed = create_embed("🖼️ Viral Content",
                                             f"**Subreddit:** {data['subreddit']}\n**Title:** {data['title']}",
                                             EMBED_COLOR_MAIN, data['url'])
                        await interaction.response.send_message(embed=embed)
                    else:
                        raise Exception("API Error")
        except:
            await interaction.response.send_message("❌ My internet connection is fuzzy. Try again later.",
                                                    ephemeral=True)

    # --- ACTION COMMANDS (PROFESSIONAL UI) ---

    @app_commands.command(name="strike", description="Launch missile protocol")
    async def strike(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("🚀 Ballistic Missile Detected",
                             f"**Target:** {member.mention}\n**Status:** Impact Confirmed.", 0xe74c3c,
                             "https://media.giphy.com/media/XUFPGR45kHMZwHQz9V/giphy.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="killoff", description="Execute termination sequence")
    async def killoff(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("💀 Termination Protocol", f"**Subject:** {member.mention}\n**Result:** Eliminated.",
                             0x2c3e50, "https://media1.tenor.com/m/CXOItGL-rjwAAAAC/dad-noel-noeldeyzel.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="punish", description="Administer disciplinary action")
    async def punish(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("💥 Disciplinary Action",
                             f"**Subject:** {member.mention}\n**Action:** Drill Protocol Initiated.", 0xe67e22,
                             "https://i.imgur.com/VUWWN10.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bless", description="Grant divine protection")
    async def bless(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("🙏 Divine Intervention", f"**Recipient:** {member.mention}\n**Effect:** Blessed.",
                             0xf1c40f, "https://media.giphy.com/media/Tv2btKgK06tQXltbvC/giphy.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="crown", description="Designate sovereignty")
    async def crown(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("👑 Coronation Ceremony",
                             f"**Sovereign:** {member.mention}\n**Title:** King/Queen assigned.", 0xf39c12,
                             "https://i.giphy.com/fYpUBttlicUM5hpSM2.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="lure", description="Deploy bait")
    async def lure(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("🪤 Trap Deployed", f"**Target:** {member.mention}\n**Status:** Captured.", 0x27ae60,
                             "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="assert_dominance", description="Assert hierarchy")
    async def assert_dominance(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("😡 Dominance Assertion",
                             f"**Subject:** {member.mention}\n**Action:** Physical Admonishment.", 0xc0392b,
                             "https://media1.tenor.com/m/OOKQrqKgFCsAAAAd/angry-kid.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nomercy", description="Deploy ultimate weapon")
    async def nomercy(self, interaction: discord.Interaction, member: discord.Member):
        embed = create_embed("☢️ Nuclear Option", f"**Target:** {member.mention}\n**Yield:** Maximum.", 0x000000,
                             "https://media.giphy.com/media/hvGKQL8lasDvIlWRBC/giphy.gif")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roulette", description="Russian Roulette (Risk Death)")
    async def roulette(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔫 **Spinning Cylinder...**")
        await asyncio.sleep(2)
        if random.randint(1, 6) == 1:
            try:
                # Attempt Timeout
                await interaction.user.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=60),
                                               reason="Roulette Loss")
                text = "💥 **BANG!** Subject neutralized. (Timeout 60s)"
            except:
                text = "💥 **BANG!** Subject neutralized. (Admin immunity active)"

            embed = create_embed("💀 Critical Failure", text, EMBED_COLOR_ERROR,
                                 "https://media.giphy.com/media/xT9IguC2cZ3lTqW652/giphy.gif")
        else:
            embed = create_embed("😅 Survival Confirmed", "Chamber empty. You live.", EMBED_COLOR_SUCCESS,
                                 "https://media.giphy.com/media/1FMaabePDEfgk/giphy.gif")

        await interaction.edit_original_response(content=None, embed=embed)


# ==================================================================================================
#  SECTION 9: MAIN EXECUTION LOOPS
# ==================================================================================================

@tasks.loop(minutes=5)
async def update_stocks_loop():
    market.update_prices()


async def main():
    async with bot:
        # Load Cogs
        await bot.add_cog(Economy(bot))
        await bot.add_cog(RPG(bot))
        await bot.add_cog(Casino(bot))
        await bot.add_cog(Moderation(bot))
        await bot.add_cog(AlicePersona(bot))

        # Start Background Tasks
        update_stocks_loop.start()

        # Start Bot
        print(" [SYSTEM] Initializing Alice System v3.0...")
        if TOKEN:
            await bot.start(TOKEN)
        else:
            print(" [ERROR] TOKEN not found in environment variables.")


@bot.event
async def on_ready():
    print("----------------------------------------------------------------")
    print(f" [ONLINE] Alice System Active")
    print(f" [ID] {bot.user.id}")
    print("----------------------------------------------------------------")
    try:
        synced = await bot.tree.sync()
        print(f" [SYNC] Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f" [ERROR] Sync Failed: {e}")


# Entry Point
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(" [SHUTDOWN] System deactivated manually.")