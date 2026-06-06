import discord
from discord.ext import commands
from database import execute, fetchone, fetchall

class Rpg(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore own messages
        if message.author.id == self.bot.user.id:
            return

        if not message.guild:
            return

        # 1. Handle "rpg notify" toggle command
        content_clean = message.content.strip().lower()
        if content_clean == "rpg notify":
            guild_id = message.guild.id
            user_id = message.author.id

            # Check if user is already registered in this guild
            existing = await fetchone(
                "SELECT * FROM rpg_notifications WHERE guild_id = %s AND user_id = %s",
                (guild_id, user_id)
            )

            if existing:
                # Remove registration
                await execute(
                    "DELETE FROM rpg_notifications WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id)
                )
                await message.reply("🔕 **RPG Notifications OFF**: You will no longer receive pings for `EPIC GUARD`.")
            else:
                # Add registration
                await execute(
                    "INSERT INTO rpg_notifications (guild_id, user_id) VALUES (%s, %s)",
                    (guild_id, user_id)
                )
                await message.reply("🔔 **RPG Notifications ON**: I will ping you whenever an `EPIC GUARD` is spotted!")
            return

        # 2. Check for "EPIC GUARD" keyword in message content or embeds
        has_guard = "epic guard" in message.content.lower()

        if not has_guard and message.embeds:
            for embed in message.embeds:
                # Check embed title
                if embed.title and "epic guard" in embed.title.lower():
                    has_guard = True
                    break
                # Check embed description
                if embed.description and "epic guard" in embed.description.lower():
                    has_guard = True
                    break
                # Check embed fields
                if embed.fields:
                    for field in embed.fields:
                        if (field.name and "epic guard" in field.name.lower()) or (field.value and "epic guard" in field.value.lower()):
                            has_guard = True
                            break
                    if has_guard:
                        break

        if has_guard:
            # Query all registered users in this guild
            rows = await fetchall(
                "SELECT user_id FROM rpg_notifications WHERE guild_id = %s",
                (message.guild.id,)
            )
            if rows:
                mentions = [f"<@{row['user_id']}>" for row in rows]
                ping_content = " ".join(mentions)
                await message.channel.send(
                    f"⚔️ **EPIC GUARD SPOTTED!** {ping_content}"
                )

async def setup(bot):
    await bot.add_cog(Rpg(bot))
