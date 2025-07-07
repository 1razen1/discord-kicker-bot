import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
import json
import os

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.guilds = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

SETTINGS_FILE = "settings.json"
try:
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}

def get_user_offset(user_id):
    user_data = settings.get(str(user_id))
    if isinstance(user_data, dict) and "offset" in user_data:
        return user_data["offset"]
    return 0

def get_local_time(user_id):
    offset = get_user_offset(user_id)
    return (datetime.utcnow() + timedelta(minutes=offset)).time()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    try:
        await tree.sync()
    except Exception as e:
        print(f"Error syncing commands: {e}")
    kicker_loop.start()

@tasks.loop(seconds=2)
async def kicker_loop():
    now_utc = datetime.utcnow()
    for guild in client.guilds:
        for member in guild.members:
            if member.bot:
                continue

            user_id = str(member.id)
            user_data = settings.get(user_id)
            if not user_data:
                continue

            offset = get_user_offset(user_id)
            local_now = (now_utc + timedelta(minutes=offset)).time()
            current_minutes = local_now.hour * 60 + local_now.minute

            try:
                if not member.voice or not member.voice.channel:
                    continue

                if isinstance(user_data, str):
                    target_time = datetime.strptime(user_data, "%H:%M").time()
                    target_minutes = target_time.hour * 60 + target_time.minute
                    diff = abs(current_minutes - target_minutes)
                    if diff <= 1:
                        await member.move_to(None)

                elif isinstance(user_data, dict) and "range" in user_data:
                    start_s, end_s = user_data["range"]
                    start_time = datetime.strptime(start_s, "%H:%M").time()
                    end_time = datetime.strptime(end_s, "%H:%M").time()
                    start_minutes = start_time.hour * 60 + start_time.minute
                    end_minutes = end_time.hour * 60 + end_time.minute

                    in_range = False
                    if start_minutes < end_minutes:
                        in_range = start_minutes <= current_minutes <= end_minutes
                    else:
                        in_range = current_minutes >= start_minutes or current_minutes <= end_minutes

                    if in_range:
                        await member.move_to(None)

            except Exception as e:
                pass  # Silent fail

def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

@tree.command(name="settime", description="Set your daily kick time (HH:MM)")
@app_commands.describe(time="Time in HH:MM")
async def settime(interaction: discord.Interaction, time: str):
    user_id = str(interaction.user.id)
    settings[user_id] = time
    save_settings()
    await interaction.response.send_message(
        f"✅ Your daily kick **time** is set to **{time}**. You'll be kicked at this time every day.",
        ephemeral=False
    )

@tree.command(name="setrange", description="Set a time range to get kicked repeatedly")
@app_commands.describe(start="Start time (HH:MM)", end="End time (HH:MM)")
async def setrange(interaction: discord.Interaction, start: str, end: str):
    user_id = str(interaction.user.id)
    settings[user_id] = {"range": [start, end]}
    save_settings()
    await interaction.response.send_message(
        f"✅ Your kick **range** is set from **{start}** to **{end}**. You'll be kicked repeatedly in this window.",
        ephemeral=False
    )

@tree.command(name="removetime", description="Remove your daily kick time")
async def removetime(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in settings and isinstance(settings[user_id], str):
        del settings[user_id]
        save_settings()
        await interaction.response.send_message(
            "✅ Your daily kick **time** has been removed.",
            ephemeral=False
        )
    else:
        await interaction.response.send_message(
            "ℹ️ You don't have a kick **time** set.",
            ephemeral=False
        )

@tree.command(name="removerange", description="Remove your kick range")
async def removerange(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id in settings and isinstance(settings[user_id], dict) and "range" in settings[user_id]:
        del settings[user_id]
        save_settings()
        await interaction.response.send_message(
            "✅ Your kick **range** has been removed.",
            ephemeral=False
        )
    else:
        await interaction.response.send_message(
            "ℹ️ You don't have a kick **range** set.",
            ephemeral=False
        )

@tree.command(name="settimezone", description="Tell the bot your local time for timezone calibration")
@app_commands.describe(current_time="Your current local time in HH:MM")
async def settimezone(interaction: discord.Interaction, current_time: str):
    try:
        now_utc = datetime.utcnow()
        local = datetime.strptime(current_time, "%H:%M")
        offset_minutes = (local.hour * 60 + local.minute) - (now_utc.hour * 60 + now_utc.minute)
        if offset_minutes < -720 or offset_minutes > 720:
            await interaction.response.send_message(
                "❗ The calculated timezone offset seems too large. Please check your time and try again.",
                ephemeral=False
            )
            return
        settings[str(interaction.user.id)] = {"offset": offset_minutes}
        save_settings()
        await interaction.response.send_message(
            f"✅ Your timezone offset has been set to **{offset_minutes:+} minutes** from UTC.",
            ephemeral=False
        )
    except ValueError:
        await interaction.response.send_message(
            "❗ Please enter time in **HH:MM** format.",
            ephemeral=False
        )

@tree.command(name="status", description="Show your current kicking settings")
async def status(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = settings.get(user_id)
    if not user_data:
        await interaction.response.send_message(
            "ℹ️ You don't have any kicking settings yet.",
            ephemeral=False
        )
        return

    lines = []
    if isinstance(user_data, str):
        lines.append(f"⏰ Daily kick time: **{user_data}**")
    elif isinstance(user_data, dict):
        if "range" in user_data:
            lines.append(f"🔁 Kick range: **{user_data['range'][0]}** to **{user_data['range'][1]}**")
        if "offset" in user_data:
            lines.append(f"🌎 Timezone offset: **{user_data['offset']} minutes** from UTC")

    msg = "\n".join(lines)
    await interaction.response.send_message(msg, ephemeral=False)

@tree.command(name="help", description="Show help for bot commands")
async def help(interaction: discord.Interaction):
    help_text = (
        "🛠️ **Kicker Bot Commands:**\n\n"
        "• `/settime <HH:MM>` – Kick yourself daily at specific time.\n"
        "• `/setrange <start> <end>` – Kick yourself repeatedly in a time range.\n"
        "• `/removetime` – Remove your daily kick time.\n"
        "• `/removerange` – Remove your range.\n"
        "• `/settimezone <HH:MM>` – Tell bot your local time for timezone calibration.\n"
        "• `/status` – View your current settings.\n"
        "• `/help` – Show this help message."
    )
    await interaction.response.send_message(help_text, ephemeral=False)

TOKEN = os.getenv('TOKEN')
client.run(TOKEN)
