import discord
from discord.ext import commands, tasks
import datetime
import json
import os

import os
TOKEN = os.getenv('TOKEN')


intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = 'times.json'

# --- Load and save user times ---
def load_times():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_times(times):
    with open(DATA_FILE, 'w') as f:
        json.dump(times, f)

user_times = load_times()

# --- Command to set time ---
@bot.command()
async def settime(ctx, time: str):
    """Set your kick time in HH:MM format"""
    try:
        datetime.datetime.strptime(time, "%H:%M")
    except ValueError:
        await ctx.send("❌ Invalid time format! Use HH:MM (24-hour).")
        return

    user_id = str(ctx.author.id)
    user_times[user_id] = time
    save_times(user_times)
    await ctx.send(f"✅ Your kick time has been set to {time}.")

# --- Task that runs every minute ---
@tasks.loop(minutes=1)
async def check_kick_times():
    now = datetime.datetime.now().strftime("%H:%M")
    for guild in bot.guilds:
        for user_id, target_time in user_times.items():
            if now == target_time:
                member = guild.get_member(int(user_id))
                if member and member.voice and member.voice.channel:
                    try:
                        await member.move_to(None)
                        print(f"Kicked {member.display_name} from voice channel in {guild.name}.")
                    except Exception as e:
                        print(f"Error kicking {member.display_name}: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    check_kick_times.start()

bot.run(TOKEN)
