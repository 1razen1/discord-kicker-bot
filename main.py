import discord
from discord.ext import commands, tasks
import asyncio
import os
from datetime import datetime, time as dtime
import json

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

# In-memory user settings
user_settings = {}
DATA_FILE = "user_settings.json"

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_settings, f)

def load_data():
    global user_settings
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE) as f:
            user_settings = json.load(f)

load_data()

@bot.event
async def on_ready():
    print(f'✨ Logged in as {bot.user}')
    kicker_loop.start()

# Helper to convert offset
def apply_offset(t, offset):
    result = (t.hour + offset) % 24
    return dtime(result, t.minute)

@bot.command()
async def kicktime(ctx, time: str):
    """
    User sets their personal daily kick time
    Usage: /kicktime HH:MM
    """
    try:
        author_id = str(ctx.author.id)
        parts = [int(x) for x in time.split(':')]
        user_time = dtime(hour=parts[0], minute=parts[1])

        if author_id not in user_settings:
            await ctx.send(f"🌍 I don't know your timezone yet! Please reply with your current local time (HH:MM).")
            def check(m): return m.author == ctx.author and ':' in m.content
            reply = await bot.wait_for('message', check=check, timeout=60)
            now_utc = datetime.utcnow().time()
            reply_parts = [int(x) for x in reply.content.split(':')]
            local_time = dtime(hour=reply_parts[0], minute=reply_parts[1])
            offset = (local_time.hour - now_utc.hour) % 24
            user_settings[author_id] = {"offset": offset}
        else:
            offset = user_settings[author_id].get("offset", 0)

        user_settings[author_id]["kick_time"] = time
        save_data()

        await ctx.send(f"✨ ✅ **Your daily kick time has been saved!** ⏰\n> **Time (your clock):** {time}\n> **UTC Offset:** {offset}")
    except Exception as e:
        print(e)
        await ctx.send("❗ **Error:** Please use format `/kicktime HH:MM` (example: `/kicktime 01:30`).")

@bot.command()
async def setrange(ctx, start: str, end: str):
    """
    User sets their restricted kick range
    Usage: /setrange HH:MM HH:MM
    """
    try:
        author_id = str(ctx.author.id)
        start_parts = [int(x) for x in start.split(':')]
        end_parts = [int(x) for x in end.split(':')]
        start_time = dtime(hour=start_parts[0], minute=start_parts[1])
        end_time = dtime(hour=end_parts[0], minute=end_parts[1])

        if author_id not in user_settings:
            await ctx.send(f"🌍 I don't know your timezone yet! Please reply with your current local time (HH:MM).")
            def check(m): return m.author == ctx.author and ':' in m.content
            reply = await bot.wait_for('message', check=check, timeout=60)
            now_utc = datetime.utcnow().time()
            reply_parts = [int(x) for x in reply.content.split(':')]
            local_time = dtime(hour=reply_parts[0], minute=reply_parts[1])
            offset = (local_time.hour - now_utc.hour) % 24
            user_settings[author_id] = {"offset": offset}
        else:
            offset = user_settings[author_id].get("offset", 0)

        user_settings[author_id]["range"] = [start, end]
        save_data()

        await ctx.send(f"✨ ✅ **Your kick range has been saved!** 🔄\n> **From:** {start}\n> **To:** {end}\n> **UTC Offset:** {offset}")
    except Exception as e:
        print(e)
        await ctx.send("❗ **Error:** Please use format `/setrange HH:MM HH:MM` (example: `/setrange 23:00 08:00`).")

@bot.command()
async def removetime(ctx):
    author_id = str(ctx.author.id)
    if author_id in user_settings and "kick_time" in user_settings[author_id]:
        del user_settings[author_id]["kick_time"]
        save_data()
        await ctx.send(f"✅ **Your daily kick time has been removed!** ❌")
    else:
        await ctx.send("ℹ️ You don't have a kick time set.")

@bot.command()
async def removerange(ctx):
    author_id = str(ctx.author.id)
    if author_id in user_settings and "range" in user_settings[author_id]:
        del user_settings[author_id]["range"]
        save_data()
        await ctx.send(f"✅ **Your kick range has been removed!** ❌")
    else:
        await ctx.send("ℹ️ You don't have a kick range set.")

@bot.command()
async def status(ctx):
    author_id = str(ctx.author.id)
    settings = user_settings.get(author_id)
    if not settings:
        await ctx.send("ℹ️ You don't have any settings yet.")
        return

    offset = settings.get("offset", 0)
    kick_time = settings.get("kick_time", "None")
    kick_range = settings.get("range", "None")

    await ctx.send(f"📋 **Your Settings:**\n> **Kick Time:** {kick_time}\n> **Range:** {kick_range}\n> **UTC Offset:** {offset}")

@bot.command()
async def help(ctx):
    await ctx.send(
        "**🤖 Available Commands:**\n"
        "• `/kicktime HH:MM` – Set your daily kick time.\n"
        "• `/setrange START END` – Set your restricted time range.\n"
        "• `/removetime` – Remove your kick time.\n"
        "• `/removerange` – Remove your kick range.\n"
        "• `/status` – View your current settings.\n"
        "• `/help` – Show this help message."
    )

@tasks.loop(seconds=2)
async def kicker_loop():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue
                settings = user_settings.get(str(member.id))
                if not settings:
                    continue

                now = datetime.utcnow().time()
                offset = settings.get("offset", 0)
                local_now = apply_offset(now, offset)

                # Check single kick time
                if "kick_time" in settings:
                    parts = [int(x) for x in settings["kick_time"].split(':')]
                    kick_time = dtime(hour=parts[0], minute=parts[1])
                    if local_now.hour == kick_time.hour and local_now.minute == kick_time.minute:
                        try:
                            await member.move_to(None)
                            print(f"Kicked {member} at set time.")
                        except Exception as e:
                            print(f"Error kicking {member}: {e}")

                # Check range
                if "range" in settings:
                    start_parts = [int(x) for x in settings["range"][0].split(':')]
                    end_parts = [int(x) for x in settings["range"][1].split(':')]
                    start_time = dtime(hour=start_parts[0], minute=start_parts[1])
                    end_time = dtime(hour=end_parts[0], minute=end_parts[1])

                    if start_time < end_time:
                        in_range = start_time <= local_now <= end_time
                    else:
                        in_range = local_now >= start_time or local_now <= end_time

                    if in_range:
                        try:
                            await member.move_to(None)
                            print(f"Kicked {member} for being in restricted range.")
                        except Exception as e:
                            print(f"Error kicking {member}: {e}")

TOKEN = os.getenv('TOKEN')
bot.run(TOKEN)
