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

bot = commands.Bot(command_prefix="!", intents=intents)


async def load_cogs():
    cogs = [
        "cogs.verification",
        "cogs.tickets",
        "cogs.boosts",
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
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync error: {e}")

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN is not set in the environment or .env file")

async def main():
    async with bot:
        await connect_db()
        await load_cogs()
        await bot.start(TOKEN)

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
        
asyncio.run(main())