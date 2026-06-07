import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
from database import connect_db

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


async def load_cogs():
    cogs = [
        "cogs.setup",
        "cogs.profile",
        "cogs.verification",
        "cogs.self_roles",
        "cogs.tickets",
        "cogs.boosts",
        "cogs.charpage",
        "cogs.tournament",
        "cogs.class_guide",
        "cogs.checkinv",
        "cogs.rpg",
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"[COG] Loaded {cog}")
        except Exception as e:
            print(f"[COG ERROR] Failed to load {cog}: {type(e).__name__}: {e}")



@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Synced {len(synced)} slash commands")
        for cmd in synced:
            print(f"- /{cmd.name}")
    except Exception as e:
        print(f"[SYNC ERROR] {type(e).__name__}: {e}")

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN is not set in the environment or .env file")

async def main():
    async with bot:
        await connect_db()
        await load_cogs()

        while True:
            try:
                await bot.start(TOKEN)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(e.response.headers.get("retry-after", 5))
                    wait = max(retry_after, 5)
                    print(f"Rate limited on login (429). Waiting {wait:.1f}s before retrying...")
                    await asyncio.sleep(wait)
                    continue
                raise

@bot.tree.error
async def on_app_command_error(interaction, error):
    print(f"[COMMAND ERROR] /{interaction.command.name if interaction.command else 'unknown'}")
    print(type(error).__name__)
    print(error)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                "❌ Command error. Check bot terminal logs.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Command error. Check bot terminal logs.",
                ephemeral=True
            )
    except Exception as e:
        print(f"[ERROR HANDLER FAILED] {e}")
if __name__ == "__main__":
    asyncio.run(main())