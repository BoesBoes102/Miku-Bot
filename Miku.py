import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
DATA_FILE = 'data.json'

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# Load or create data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=4)

def get_user(user_id):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {"coins": 0, "last_claim": None}
    return user_data[uid]

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="daily", description="Claim your daily coins.")
async def daily(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    now = datetime.utcnow()

    if user["last_claim"]:
        last_claim = datetime.strptime(user["last_claim"], '%Y-%m-%d %H:%M:%S')
        if now - last_claim < timedelta(hours=24):
            next_claim = last_claim + timedelta(hours=24)
            remaining = next_claim - now
            hours, minutes = divmod(int(remaining.total_seconds()), 3600)
            minutes = minutes // 60
            await interaction.response.send_message(
                f"⏳ You've already claimed your daily reward. Try again in {hours}h {minutes}m.",
                ephemeral=True
            )
            return

    user["coins"] += 100
    user["last_claim"] = now.strftime('%Y-%m-%d %H:%M:%S')
    save_data()

    await interaction.response.send_message(
        f"💰 {interaction.user.mention}, you received **100 coins**! New balance: **{user['coins']}**"
    )

@tree.command(name="balance", description="Check your coin balance.")
async def balance(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    await interaction.response.send_message(
        f"💼 {interaction.user.mention}, your balance is **{user['coins']}** coins."
    )

@tree.command(name="pay", description="Send coins to another user.")
@app_commands.describe(user="The user to pay", amount="The amount to send")
async def pay(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.bot:
        await interaction.response.send_message("🤖 You can't pay coins to bots.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ You must send a positive amount.", ephemeral=True)
        return

    sender = get_user(interaction.user.id)
    recipient = get_user(user.id)

    if sender["coins"] < amount:
        await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
        return

    sender["coins"] -= amount
    recipient["coins"] += amount
    save_data()

    await interaction.response.send_message(
        f"✅ {interaction.user.mention} sent **{amount} coins** to {user.mention}!"
    )

@tree.command(name="addcoins", description="Add coins to a user (Admin only).")
@app_commands.describe(user="User to give coins to", amount="Amount of coins to add")
@app_commands.checks.has_permissions(administrator=True)
async def addcoins(interaction: discord.Interaction, user: discord.User, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return

    user_record = get_user(user.id)
    user_record["coins"] += amount
    save_data()

    await interaction.response.send_message(
        f"✅ {user.mention} received **{amount} coins**. New balance: **{user_record['coins']}**"
    )


# ✅ Remove Coins Command
@tree.command(name="removecoins", description="Remove coins from a user (Admin only).")
@app_commands.describe(user="User to remove coins from", amount="Amount of coins to remove")
@app_commands.checks.has_permissions(administrator=True)
async def removecoins(interaction: discord.Interaction, user: discord.User, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return

    user_record = get_user(user.id)
    user_record["coins"] = max(0, user_record["coins"] - amount)  # Prevent negative coins
    save_data()

    await interaction.response.send_message(
        f"❌ Removed **{amount} coins** from {user.mention}. New balance: **{user_record['coins']}**"
    )


@tree.command(name="leaderboard", description="Show top 10 richest users.")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    top = sorted(user_data.items(), key=lambda x: x[1].get("coins", 0), reverse=True)[:10]

    embed = discord.Embed(title="🏆 Coin Leaderboard", color=discord.Color.gold())
    for i, (user_id, data) in enumerate(top, start=1):
        try:
            member = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {member.name}", value=f"{data['coins']} coins", inline=False)
        except Exception:
            embed.add_field(name=f"{i}. Unknown User", value=f"{data['coins']} coins", inline=False)

    await interaction.followup.send(embed=embed)

@tree.command(name="coinflip", description="Bet coins on heads or tails.")
@app_commands.describe(choice="Your choice: heads or tails", amount="Amount of coins to bet")
async def coinflip(interaction: discord.Interaction, choice: str, amount: int):
    await interaction.response.defer()

    choice = choice.lower()
    if choice not in ['heads', 'tails']:
        await interaction.followup.send("❌ You must choose `heads` or `tails`.")
        return
    if amount <= 0:
        await interaction.followup.send("❌ Bet must be more than 0 coins.")
        return

    user = get_user(interaction.user.id)
    if user["coins"] < amount:
        await interaction.followup.send("❌ You don't have enough coins.")
        return

    result = random.choice(['heads', 'tails'])
    win = result == choice

    if win:
        user["coins"] += amount
        message = f"🪙 It was **{result}**! You won **{amount} coins**!"
    else:
        user["coins"] -= amount
        message = f"🪙 It was **{result}**! You lost **{amount} coins**."

    save_data()
    await interaction.followup.send(f"{interaction.user.mention} {message} New balance: **{user['coins']}**")

@tree.command(name="roulette", description="Bet on a number from 0 to 36.")
@app_commands.describe(number="Your number (0–36)", amount="Coins to bet")
async def roulette(interaction: discord.Interaction, number: int, amount: int):
    await interaction.response.defer()

    if not (0 <= number <= 36):
        await interaction.followup.send("❌ Choose a number between 0 and 36.")
        return
    if amount <= 0:
        await interaction.followup.send("❌ Bet must be more than 0 coins.")
        return

    user = get_user(interaction.user.id)
    if user["coins"] < amount:
        await interaction.followup.send("❌ You don't have enough coins.")
        return

    result = random.randint(0, 36)
    red = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    black = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
    color = "Green" if result == 0 else "Red" if result in red else "Black"

    if result == number:
        winnings = amount * 36
        user["coins"] += winnings
        outcome = f"🎉 You won! The ball landed on **{result} {color}**, and you won **{winnings} coins**!"
    else:
        user["coins"] -= amount
        outcome = f"💸 You lost! The ball landed on **{result} {color}**. You lost **{amount} coins**."

    save_data()
    await interaction.followup.send(f"{interaction.user.mention} {outcome} New balance: **{user['coins']}**")




active_rps_games = {}

@tree.command(name="rps", description="Challenge someone to Rock Paper Scissors with coin bet.")
@app_commands.describe(opponent="The user to challenge", bet="Coin amount to bet")
async def rps(interaction: discord.Interaction, opponent: discord.User, bet: int):
    challenger = interaction.user

    if challenger.id == opponent.id:
        await interaction.response.send_message("❌ You can't challenge yourself!", ephemeral=True)
        return

    if opponent.bot:
        await interaction.response.send_message("🤖 You can't challenge bots!", ephemeral=True)
        return

    if bet <= 0:
        await interaction.response.send_message("❌ Bet must be a positive number.", ephemeral=True)
        return

    challenger_data = get_user(challenger.id)
    opponent_data = get_user(opponent.id)

    if challenger_data["coins"] < bet:
        await interaction.response.send_message("❌ You don't have enough coins to place this bet.", ephemeral=True)
        return

    if opponent_data["coins"] < bet:
        await interaction.response.send_message(f"❌ {opponent.mention} doesn't have enough coins to accept this challenge.", ephemeral=True)
        return

    if challenger.id in active_rps_games or opponent.id in active_rps_games:
        await interaction.response.send_message("⏳ One of you is already in a game.", ephemeral=True)
        return

    view = RPSChallengeView(challenger, opponent, bet)
    embed = discord.Embed(
        title="🤜 Rock Paper Scissors Challenge",
        description=f"{opponent.mention}, you’ve been challenged by {challenger.mention}!\nBet: **{bet} coins**\n\nDo you accept?",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()

    active_rps_games[challenger.id] = view
    active_rps_games[opponent.id] = view

    async def timeout_handler():
        await asyncio.sleep(60)
        if not view.finished:
            view.disable_all()
            embed.color = discord.Color.red()
            embed.description += "\n\n⏰ Timed out. Game canceled."
            await msg.edit(embed=embed, view=view)
            active_rps_games.pop(challenger.id, None)
            active_rps_games.pop(opponent.id, None)

    view.timeout_task = asyncio.create_task(timeout_handler())

class RPSChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=None)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.choices = {}
        self.finished = False
        self.timeout_task = None

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    async def resolve_game(self, interaction):
        self.finished = True
        if self.timeout_task:
            self.timeout_task.cancel()

        choice1 = self.choices.get(self.challenger.id)
        choice2 = self.choices.get(self.opponent.id)

        beats = {
            "🪨": "✂️",
            "📄": "🪨",
            "✂️": "📄"
        }

        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Result",
            color=discord.Color.green()
        )
        embed.add_field(name=self.challenger.name, value=choice1 or "No choice")
        embed.add_field(name=self.opponent.name, value=choice2 or "No choice")

        winner = None
        if choice1 == choice2:
            embed.description = "🤝 It's a tie! No coins were exchanged."
        elif choice1 and choice2:
            if beats[choice1] == choice2:
                winner = self.challenger
            else:
                winner = self.opponent
        else:
            embed.description = "❌ Game incomplete. One or both players did not choose."

        if winner:
            loser = self.challenger if winner == self.opponent else self.opponent
            # Use get_user to avoid KeyError
            get_user(winner.id)["coins"] += self.bet
            get_user(loser.id)["coins"] -= self.bet
            embed.description = f"🏆 {winner.mention} wins and earns **{self.bet} coins**!"
            save_data()

        self.disable_all()
        await interaction.message.edit(embed=embed, view=self)
        active_rps_games.pop(self.challenger.id, None)
        active_rps_games.pop(self.opponent.id, None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in (self.challenger.id, self.opponent.id)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("❌ You can't accept this challenge.", ephemeral=True)
            return

        self.clear_items()
        for emoji in ["🪨", "📄", "✂️"]:
            self.add_item(RPSChoiceButton(self, emoji))

        await interaction.message.edit(embed=discord.Embed(
            title="🎮 Choose your move!",
            description=f"{self.challenger.mention} and {self.opponent.mention}, pick your move:",
            color=discord.Color.orange()
        ), view=self)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("❌ Only the challenged user can reject.", ephemeral=True)
            return

        self.finished = True
        if self.timeout_task:
            self.timeout_task.cancel()

        self.disable_all()
        embed = discord.Embed(
            title="❌ Challenge Rejected",
            description=f"{interaction.user.mention} rejected the challenge.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=self)
        active_rps_games.pop(self.challenger.id, None)
        active_rps_games.pop(self.opponent.id, None)

class RPSChoiceButton(discord.ui.Button):
    def __init__(self, view: RPSChallengeView, emoji: str):
        super().__init__(style=discord.ButtonStyle.primary, emoji=emoji)
        self.view_instance = view
        self.choice = emoji

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in (self.view_instance.challenger.id, self.view_instance.opponent.id):
            await interaction.response.send_message("❌ You're not part of this game.", ephemeral=True)
            return

        if interaction.user.id in self.view_instance.choices:
            await interaction.response.send_message("❌ You have already made your choice.", ephemeral=True)
            return

        self.view_instance.choices[interaction.user.id] = self.choice
        await interaction.response.send_message(f"You chose {self.choice}!", ephemeral=True)

        if len(self.view_instance.choices) == 2:
            await self.view_instance.resolve_game(interaction)

@addcoins.error
@removecoins.error
async def admin_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
    else:
        raise error


RARITIES = {
    "Common": 60,
    "Uncommon": 25,
    "Rare": 10,
    "Epic": 4,
    "Legendary": 1
}

FISH_TYPES = {
    "Common": ["Minnow", "Bluegill", "Carp"],
    "Uncommon": ["Trout", "Bass"],
    "Rare": ["Pike", "Catfish"],
    "Epic": ["Golden Koi", "Electric Eel"],
    "Legendary": ["Ancient Leviathan"]
}

# Load or initialize user data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        user_data = json.load(f)
else:
    user_data = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=4)

def get_user_data(user_id):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {}

    if "fishes" not in user_data[uid]:
        user_data[uid]["fishes"] = []

    return user_data[uid]

def pick_fish():
    roll = random.randint(1, 100)
    cumulative = 0
    for rarity, chance in RARITIES.items():
        cumulative += chance
        if roll <= cumulative:
            fish = random.choice(FISH_TYPES[rarity])
            return fish, rarity
    return random.choice(FISH_TYPES["Common"]), "Common"

class CatchButton(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=10)
        self.user = user
        self.clicked = False

    @discord.ui.button(label="🎣 Catch!", style=discord.ButtonStyle.green)
    async def catch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ This is not your fishing session!", ephemeral=True)
            return

        if self.clicked:
            await interaction.response.send_message("⏳ You've already caught something!", ephemeral=True)
            return

        self.clicked = True
        fish, rarity = pick_fish()
        user_info = get_user_data(interaction.user.id)
        user_info["fishes"].append({"name": fish, "rarity": rarity})
        save_data()

        embed = discord.Embed(
            title="🐟 You Caught Something!",
            description=f"**{fish}** ({rarity})",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

@tree.command(name="fish", description="Cast your line and try to catch something!")
async def fish(interaction: discord.Interaction):
    await interaction.response.send_message("🎣 Waiting for a bite...", ephemeral=False)
    await asyncio.sleep(random.randint(2, 4))

    view = CatchButton(interaction.user)
    await interaction.edit_original_response(content="🎯 A fish is biting! Press the button to catch it!", view=view)

@tree.command(name="fishlist", description="View your caught fish.")
async def fishlist(interaction: discord.Interaction):
    user_info = get_user_data(interaction.user.id)
    fish_by_rarity = {k: [] for k in RARITIES.keys()}

    for fish in user_info["fishes"]:
        fish_by_rarity[fish["rarity"]].append(fish["name"])

    embed = discord.Embed(title=f"🎣 {interaction.user.name}'s Fish List", color=discord.Color.blue())
    for rarity, fish_list in fish_by_rarity.items():
        if fish_list:
            embed.add_field(name=f"{rarity} ({len(fish_list)}):", value=", ".join(fish_list), inline=False)

    if not user_info["fishes"]:
        embed.description = "You haven't caught any fish yet. Try `/fish`!"
    await interaction.response.send_message(embed=embed)


bot.run(TOKEN)
