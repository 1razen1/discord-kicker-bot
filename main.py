import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
import json
import asyncio
import os

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

settings_file = "settings.json"
try:
    with open(settings_file, "r") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}

def get_user_offset(user_id):
    data = settings.get(str(user_id))
    if isinstance(data, dict) and "offset" in data:
        return data["offset"]
    return 0

def local_time(user_id):
    offset = get_user_offset(user_id)
    return (datetime.utcnow() + timedelta(minutes=offset)).time()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    check_times.start()
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@tasks.loop(seconds=2)  # 2-second interval
async def check_times():
    for guild in client.guilds:
        for member in guild.members:
            if member.bot:
                continue

            user_setting = settings.get(str(member.id))
            if not user_setting:
                continue

            now = local_time(member.id)
            to_kick = False

            if isinstance(user_setting, str):
                try:
                    target = datetime.strptime(user_setting, "%H:%M").time()
                    if now.hour == target.hour and now.minute == target.minute:
                        to_kick = True
                except ValueError:
                    pass

            elif isinstance(user_setting, dict) and "range" in user_setting:
                try:
                    start_str, end_str = user_setting["range"].split("-")
                    start = datetime.strptime(start_str, "%H:%M").time()
                    end = datetime.strptime(end_str, "%H:%M").time()
                    if start < end:
                        in_range = start <= now <= end
                    else:
                        in_range = now >= start or now <= end
                    if in_range:
                        to_kick = True
                except ValueError:
                    pass

            if to_kick:
                try:
                    await member.move_to(None)
                    print(f"Kicked {member} at {now}")
                except Exception as e:
                    print(f"Error kicking {member}: {e}")

@tree.command(name="settime", description="Set kick time for a user (HH:MM)")
@app_commands.describe(member="User to kick", time="Time in HH:MM")
async def settime(interaction: discord.Interaction, member: discord.Member, time: str):
    settings[str(member.id)] = time
    with open(settings_file, "w") as f:
        json.dump(settings, f)
    await interaction.response.send_message(
        f"✅ Kick **time** for {member.mention} set to **{time}**! They will be kicked at that time daily.",
        ephemeral=False
    )

@tree.command(name="setrange", description="Set time range during which user is kicked repeatedly")
@app_commands.describe(member="User to kick", time_range="Format: HH:MM-HH:MM")
async def setrange(interaction: discord.Interaction, member: discord.Member, time_range: str):
    if "-" not in time_range:
        await interaction.response.send_message(
            "❗ Please provide the range in format **HH:MM-HH:MM**.",
            ephemeral=False
        )
        return
    settings[str(member.id)] = {"range": time_range}
    with open(settings_file, "w") as f:
        json.dump(settings, f)
    await interaction.response.send_message(
        f"✅ Kick **range** for {member.mention} set to **{time_range}**! They will be kicked repeatedly during this time window.",
        ephemeral=False
    )

@tree.command(name="settimezone", description="Tell the bot your current local time for timezone calibration")
@app_commands.describe(current_time="Your current local time in HH:MM")
async def settimezone(interaction: discord.Interaction, current_time: str):
    try:
        now_utc = datetime.utcnow()
        local = datetime.strptime(current_time, "%H:%M")
        offset_minutes = (local.hour * 60 + local.minute) - (now_utc.hour * 60 + now_utc.minute)
        settings[str(interaction.user.id)] = {"offset": offset_minutes}
        with open(settings_file, "w") as f:
            json.dump(settings, f)
        await interaction.response.send_message(
            f"✅ Your timezone offset has been set to **{offset_minutes:+} minutes** from UTC. All kick times will use this.",
            ephemeral=False
        )
    except ValueError:
        await interaction.response.send_message(
            "❗ Please enter time in **HH:MM** format.",
            ephemeral=False
        )

@tree.command(name="status", description="Show your current kicking settings")
async def status(interaction: discord.Interaction):
    user_setting = settings.get(str(interaction.user.id))
    if not user_setting:
        await interaction.response.send_message(
            "❗ You don't have any kicking settings yet.",
            ephemeral=False
        )
        return

    if isinstance(user_setting, str):
        msg = f"⏰ You have a single daily kick time set at **{user_setting}**."
    elif isinstance(user_setting, dict):
        msg_parts = []
        if "range" in user_setting:
            msg_parts.append(f"🔁 Repeating **range**: **{user_setting['range']}**")
        if "offset" in user_setting:
            msg_parts.append(f"🌎 Timezone offset: **{user_setting['offset']} minutes** from UTC")
        msg = "\n".join(msg_parts)
    else:
        msg = "❗ Couldn't read your settings."

    await interaction.response.send_message(msg, ephemeral=False)

@tree.command(name="help", description="Show help for bot commands")
async def help(interaction: discord.Interaction):
    help_text = (
        "🛠️ **Kicker Bot Commands**\n\n"
        "• `/settime <user> <HH:MM>` – Kick them once daily at specific time.\n"
        "• `/setrange <user> <HH:MM-HH:MM>` – Kick them repeatedly during a time range.\n"
        "• `/settimezone <HH:MM>` – Tell bot your current local time for timezone calibration.\n"
        "• `/status` – See your current settings.\n"
        "• `/help` – Show this help message."
    )
    await interaction.response.send_message(help_text, ephemeral=False)

# Load token from env
TOKEN = os.getenv('TOKEN')
client.run(TOKEN)
