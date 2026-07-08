import os
import json
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

STATE_FILE = "proxy_state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"locked_by": None, "locked_at": None, "log": []}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def fmt_time(ts):
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M UTC")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="claim", description="Claim the shared proxy so others know it's in use")
async def claim(interaction: discord.Interaction):
    state = load_state()
    user = interaction.user.display_name

    if state["locked_by"] and state["locked_by"] != user:
        since = fmt_time(state["locked_at"])
        await interaction.response.send_message(
            f"⛔ Already claimed by **{state['locked_by']}** since {since}. "
            f"Ask them to `/release` first.",
            ephemeral=False
        )
        return

    state["locked_by"] = user
    state["locked_at"] = time.time()
    state["log"].append({"name": user, "action": "claim", "ts": time.time()})
    state["log"] = state["log"][-20:]
    save_state(state)

    await interaction.response.send_message(
        f"🔒 **{user}** claimed the proxy at {fmt_time(state['locked_at'])}. "
        f"Release it with `/release` when you're done."
    )

@bot.tree.command(name="release", description="Release the shared proxy so someone else can use it")
async def release(interaction: discord.Interaction):
    state = load_state()
    user = interaction.user.display_name

    if not state["locked_by"]:
        await interaction.response.send_message("✅ Proxy is already free.", ephemeral=True)
        return

    state["log"].append({"name": user, "action": "release", "ts": time.time()})
    state["log"] = state["log"][-20:]
    state["locked_by"] = None
    state["locked_at"] = None
    save_state(state)

    await interaction.response.send_message(f"🟢 **{user}** released the proxy. It's free to use.")

@bot.tree.command(name="status", description="Check who currently has the proxy")
async def status(interaction: discord.Interaction):
    state = load_state()
    if state["locked_by"]:
        since = fmt_time(state["locked_at"])
        await interaction.response.send_message(
            f"🔒 In use by **{state['locked_by']}** since {since}.", ephemeral=True
        )
    else:
        await interaction.response.send_message("🟢 Proxy is free.", ephemeral=True)

@bot.tree.command(name="force_release", description="Force-release the proxy if someone forgot")
async def force_release(interaction: discord.Interaction):
    state = load_state()
    prev = state["locked_by"]
    state["log"].append({"name": interaction.user.display_name, "action": "force_release", "ts": time.time()})
    state["log"] = state["log"][-20:]
    state["locked_by"] = None
    state["locked_at"] = None
    save_state(state)

    if prev:
        await interaction.response.send_message(
            f"⚠️ **{interaction.user.display_name}** force-released the proxy (was held by **{prev}**)."
        )
    else:
        await interaction.response.send_message("Proxy was already free.", ephemeral=True)

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Set the DISCORD_BOT_TOKEN environment variable before running.")

bot.run(TOKEN)
