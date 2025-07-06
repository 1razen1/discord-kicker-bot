import discord
from discord.ext import tasks
from discord import app_commands
import asyncio
from datetime import datetime, time as dtime
import os
import json

TOKEN = os.getenv('TOKEN')

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Store user settings in JSON
DATA_FILE = "user_settings.json"
user_settings = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_settings, f)

def load_data():
    global user_settings
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE) as f:
            user_settings = json.load(f)

load_data()

@client.event
async def on_ready():
    print(f"✨ Logged in as {client.user}")
    await tree.sync()
    kicker_loop.start()

def apply_offset(t, offset):
    result = (t.hour + offset) % 24
    return dtime(result, t.minute)

@tree.command(name="kicktime", description="Set your daily kick time (HH:MM)")
async def kicktime(interaction: discord.Interaction, time: str):
    author_id = str(interaction.user.id)
    try:
        parts = [int(x) for x in time.split(':')]
        _ = dtime(hour=parts[0], minute=parts[1])

        if author_id not in user_settings:
            await interaction.response.send_message("🌍 I don't know your timezone yet! Please tell me your current local time (HH:MM).", ephemeral=True)
            msg = await client.wait_for(
                "message",
                check=lambda m: m.author == interaction.user and ':' in m.content,
                timeout=60
            )
            now_utc = datetime.utcnow().time()
            reply_parts = [int(x) for x in msg.content.split(':')]
            local_time = dtime(hour=reply_parts[0], minute=reply_parts[1])
            offset = (local_time.hour - now_utc.hour) % 24
            user_settings[author_id] = {"offset": offset}
        else:
            offset = user_settings[author_id].get("offset", 0)

        user_settings[author_id]["kick_time"] = time
        save_data()

        await interaction.followup.send(f"✅ Your daily kick time is set to **{time}** (UTC offset: {offset}).", ephemeral=True)
    except Exception as e:
        print(e)
        await interaction.response.send_message("❗ **Error:** Please use format `HH:MM` (example: `01:30`).", ephemeral=True)

@tree.command(name="setrange", description="Set your restricted time range (HH:MM HH:MM)")
async def setrange(interaction: discord.Interaction, start: str, end: str):
    author_id = str(interaction.user.id)
    try:
        _ = dtime(hour=int(start.split(':')[0]), minute=int(start.split(':')[1]))
        _ = dtime(hour=int(end.split(':')[0]), minute=int(end.split(':')[1]))

        if author_id not in user_settings:
            await interaction.response.send_message("🌍 I don't know your timezone yet! Please tell me your current local time (HH:MM).", ephemeral=True)
            msg = await client.wait_for(
                "message",
                check=lambda m: m.author == interaction.user and ':' in m.content,
                timeout=60
            )
            now_utc = datetime.utcnow().time()
            reply_parts = [int(x) for x in msg.content.split(':')]
            local_time = dtime(hour=reply_parts[0], minute=reply_parts[1])
            offset = (local_time.hour - now_utc.hour) % 24
            user_settings[author_id] = {"offset": offset}
        else:
            offset = user_settings[author_id].get("offset", 0)

        user_settings[author_id]["range"] = [start, end]
        save_data()

        await interaction.response.send_message(f"✅ Your kick range is set from **{start}** to **{end}** (UTC offset: {offset}).", ephemeral=True)
    except Exception as e:
        print(e)
        await interaction.response.send_message("❗ **Error:** Please use format `HH:MM HH:MM` (example: `23:00 08:00`).", ephemeral=True)

@tree.command(name="removetime", description="Remove your daily kick time setting")
async def removetime(interaction: discord.Interaction):
    author_id = str(interaction.user.id)
    if author_id in user_settings and "kick_time" in user_settings[author_id]:
        del user_settings[author_id]["kick_time"]
        save_data()
        await interaction.response.send_message("✅ Your daily kick time has been removed.", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ You don't have a kick time set.", ephemeral=True)

@tree.command(name="removerange", description="Remove your restricted range setting")
async def removerange(interaction: discord.Interaction):
    author_id = str(interaction.user.id)
    if author_id in user_settings and "range" in user_settings[author_id]:
        del user_settings[author_id]["range"]
        save_data()
        await interaction.response.send_message("✅ Your kick range has been removed.", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ You don't have a kick range set.", ephemeral=True)

@tree.command(name="status", description="View your current kick settings")
async def status(interaction: discord.Interaction):
    author_id = str(interaction.user.id)
    settings = user_settings.get(author_id)
    if not settings:
        await interaction.response.send_message("ℹ️ You don't have any settings yet.", ephemeral=True)
        return

    offset = settings.get("offset", 0)
    kick_time = settings.get("kick_time", "Not set")
    kick_range = settings.get("range", "Not set")

    await interaction.response.send_message(
        f"📋 **Your Settings:**\n• Kick Time: `{kick_time}`\n• Range: `{kick_range}`\n• UTC Offset: `{offset}`",
        ephemeral=True
    )

@tree.command(name="help", description="Show available commands")
async def bothelp(interaction: discord.Interaction):
    help_text = (
        "**🤖 Bot Slash Commands:**\n"
        "• `/kicktime HH:MM` — Set your daily kick time.\n"
        "• `/setrange HH:MM HH:MM` — Set restricted time range.\n"
        "• `/removetime` — Remove your daily kick time.\n"
        "• `/removerange` — Remove your restricted range.\n"
        "• `/status` — View your current settings.\n"
        "• `/help` — Show this help message."
    )
    await interaction.response.send_message(help_text, ephemeral=True)

@tasks.loop(seconds=2)
async def kicker_loop():
    for guild in client.guilds:
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

client.run(TOKEN)
