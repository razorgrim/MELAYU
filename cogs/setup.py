import discord
from discord.ext import commands
import json
from database import execute, fetchone

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="setup")
    async def setup_group(self, ctx):
        """Root command for configuring bot features."""
        if ctx.invoked_subcommand is None:
            # Check permissions: only moderators can see setup help
            from cogs.tickets import is_officer
            is_mod = ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild or await is_officer(ctx.author)
            if not is_mod:
                await ctx.send("❌ Only administrators and moderators can configure this bot.")
                return

            await ctx.invoke(self.bot.get_command('help'))

    @commands.command(name="help")
    async def help_cmd(self, ctx):
        """Displays help information for moderators and administrators."""
        from cogs.tickets import is_officer
        is_mod = ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild or await is_officer(ctx.author)
        if not is_mod:
            await ctx.send("❌ Only administrators and moderators can view configuration commands.")
            return

        embed = discord.Embed(
            title="⚙️ MELAYU Bot Configuration Help",
            description="Detailed guide for server Administrators and Officers to configure and setup bot features using prefix commands.",
            color=discord.Color.gold()
        )
        
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.add_field(
            name="🎫 Ticket Setup",
            value=(
                "**Command:** `!setup ticket <officer_role> <helper_role> <bonus_role> <ticket_category> <log_channel> [active_tickets_channel]`\n"
                "**Description:** Setup the ticket support system for this server.\n"
                "**Example:** `!setup ticket @Officer @Helper @VipRole \"Ticket Support\" #ticket-logs`"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Verification Setup",
            value=(
                "**Command:** `!setup verification <aqw_guild_name> <adventure_role> <member_role> [image_url]`\n"
                "**Description:** Configure AQW guild verification and cosmetic roles.\n"
                "**Example:** `!setup verification \"M E L A Y U\" @Verified @GuildMember`"
            ),
            inline=False
        )

        embed.add_field(
            name="📢 Boost Reminders Setup",
            value=(
                "**Command:** `!setup boosts <channel> <on/off>`\n"
                "**Description:** Enable/disable daily & weekly AQW boost reminders.\n"
                "**Example:** `!setup boosts #announcements on`"
            ),
            inline=False
        )

        embed.add_field(
            name="⚔️ PvP Tournament Setup",
            value=(
                "**Command:** `!setup pvp [player_limit]`\n"
                "**Description:** Initialize tournament brackets and post a persistent matchmaking board.\n"
                "**Example:** `!setup pvp 16`"
            ),
            inline=False
        )

        embed.add_field(
            name="🎭 Self-Assign Roles Panel",
            value=(
                "**Command:** `!setup roles [channel]`\n"
                "**Description:** Post the self-assignable roles and factions toggle panel.\n"
                "**Example:** `!setup roles #choose-roles`"
            ),
            inline=False
        )

        embed.add_field(
            name="📚 Class Guide Panel",
            value=(
                "**Command:** `!setup class [channel]`\n"
                "**Description:** Post the interactive dropdown panel for the AQW Class Guide Library.\n"
                "**Example:** `!setup class #class-guides`"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 Leveling, Shop & Achievements Setup",
            value=(
                "**Commands:**\n"
                "• `!setup levelchannel <#channel>` — Set level-up announcement channel.\n"
                "• `!setup addshop <role | title | color> <price> <\"Name\"> <target>` — Add item to the server shop.\n"
                "• `!setup delshop <item_id>` — Delete item from the server shop.\n"
                "• `!setup achievement give <@member> <\"Achievement\">` — Award an achievement title.\n"
                "• `!setup achievement remove <@member> <\"Achievement\">` — Remove an achievement.\n"
                "**Examples:**\n"
                "• `!setup levelchannel #level-ups`\n"
                "• `!setup addshop role 50 \"VIP Helper\" @VipRole`\n"
                "• `!setup achievement give @User \"Legion Champion\"`\n"
                "• `!setup achievement remove @User \"Legion Champion\"`"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ Management & Panels (Standalone Commands)",
            value=(
                "🔹 `!verification` — Post the AQW verification panel in current channel.\n"
                "🔹 `!ticketpanel` — Post the interactive Ultra Ticket panel in current channel.\n"
                "🔹 `!resetleaderboard` — Reset all helper points on the ticket leaderboard.\n"
                "🔹 `!pvp_start` — Seed brackets and start the tournament.\n"
                "🔹 `!pvp_reset` — Clear brackets, reset registration status, and archive threads."
            ),
            inline=False
        )

        embed.set_footer(
            text="Use double quotes around arguments with spaces (e.g. \"M E L A Y U\") • Admin/Officer Only",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )
        await ctx.send(embed=embed)

    @setup_group.command(name="levelchannel")
    async def levelchannel_setup(self, ctx, channel: discord.TextChannel):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command.")
            return

        guild_id = ctx.guild.id

        await execute(
            """
            INSERT INTO level_config (guild_id, announcement_channel_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE announcement_channel_id = VALUES(announcement_channel_id)
            """,
            (guild_id, channel.id)
        )
        await ctx.send(f"✅ Level-up announcements will be posted in {channel.mention}.")

    @setup_group.command(name="addshop")
    async def addshop_setup(self, ctx, item_type: str, price: int, name: str, target: str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command.")
            return

        item_type = item_type.lower()
        if item_type not in ["role", "title", "color"]:
            await ctx.send("❌ Invalid item type. Use `role`, `title`, or `color`.")
            return

        guild_id = ctx.guild.id
        target_id = None
        target_text = None

        if item_type == "role":
            import re
            cleaned_target = re.sub(r"[<@&>]", "", target)
            try:
                role_id = int(cleaned_target)
                role = ctx.guild.get_role(role_id)
                if not role:
                    await ctx.send("❌ Role not found in this server.")
                    return
                target_id = role.id
            except ValueError:
                await ctx.send("❌ Invalid role mention or ID.")
                return
        elif item_type == "title":
            target_text = target
        elif item_type == "color":
            if not target.startswith("#") or len(target) != 7:
                await ctx.send("❌ Invalid hex color format. E.g., `#FFD700`.")
                return
            target_text = target

        await execute(
            """
            INSERT INTO shop_items (guild_id, name, type, price, target_id, target_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (guild_id, name, item_type, price, target_id, target_text)
        )
        await ctx.send(f"✅ Successfully added shop item **{name}** ({item_type.upper()}) for **{price} MCoin**.")

    @setup_group.command(name="delshop")
    async def delshop_setup(self, ctx, item_id: int):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command.")
            return

        guild_id = ctx.guild.id
        item = await fetchone(
            "SELECT * FROM shop_items WHERE guild_id = %s AND id = %s",
            (guild_id, item_id)
        )

        if not item:
            await ctx.send("❌ Shop item not found.")
            return

        await execute(
            "DELETE FROM shop_items WHERE guild_id = %s AND id = %s",
            (guild_id, item_id)
        )
        await ctx.send(f"✅ Successfully deleted shop item **{item['name']}** (ID: {item_id}).")

    @setup_group.group(name="achievement")
    async def achievement_group(self, ctx):
        """Management commands for player achievements."""
        if ctx.invoked_subcommand is None:
            await ctx.send("❓ Usage: `!setup achievement <give | remove> <@member> <\"Achievement\">`")

    @achievement_group.command(name="give")
    async def achievement_give(self, ctx, member: discord.Member, *, achievement: str):
        from cogs.tickets import is_officer
        is_mod = ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild or await is_officer(ctx.author)
        if not is_mod:
            await ctx.send("❌ Only administrators and moderators/officers can give achievements.")
            return

        guild_id = ctx.guild.id
        user_id = member.id

        # Fetch current achievements
        profile = await fetchone(
            "SELECT achievements FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        achievements = []
        if profile and profile["achievements"]:
            try:
                achievements = json.loads(profile["achievements"])
            except Exception:
                achievements = []

        # Avoid duplicates case-insensitively
        ach_lower = achievement.lower()
        if any(a.lower() == ach_lower for a in achievements):
            await ctx.send(f"❌ {member.mention} already has the achievement `{achievement}`.")
            return

        achievements.append(achievement)
        new_achievements_raw = json.dumps(achievements)

        # Upsert
        await execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, achievements)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE achievements = VALUES(achievements)
            """,
            (guild_id, user_id, new_achievements_raw)
        )

        await ctx.send(f"🏆 Successfully awarded the achievement **`{achievement}`** to {member.mention}! They can now equip it using `/equip`.")

    @achievement_group.command(name="remove")
    async def achievement_remove(self, ctx, member: discord.Member, *, achievement: str):
        from cogs.tickets import is_officer
        is_mod = ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild or await is_officer(ctx.author)
        if not is_mod:
            await ctx.send("❌ Only administrators and moderators/officers can remove achievements.")
            return

        guild_id = ctx.guild.id
        user_id = member.id

        profile = await fetchone(
            "SELECT achievements, active_title FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        if not profile or not profile["achievements"]:
            await ctx.send(f"❌ {member.mention} has no achievements to remove.")
            return

        try:
            achievements = json.loads(profile["achievements"])
        except Exception:
            achievements = []

        ach_lower = achievement.lower()
        matched = [a for a in achievements if a.lower() == ach_lower]
        if not matched:
            await ctx.send(f"❌ {member.mention} does not have the achievement `{achievement}`.")
            return

        # Remove it
        ach_to_remove = matched[0]
        achievements.remove(ach_to_remove)
        new_achievements_raw = json.dumps(achievements)

        # If they had it equipped, clear it
        active_title = profile["active_title"]
        clear_title_sql = ""
        params = [new_achievements_raw, guild_id, user_id]
        if active_title and active_title.lower() == ach_lower:
            clear_title_sql = ", active_title = NULL"

        await execute(
            f"UPDATE user_profiles SET achievements = %s{clear_title_sql} WHERE guild_id = %s AND user_id = %s",
            tuple(params)
        )

        await ctx.send(f"✅ Removed the achievement **`{ach_to_remove}`** from {member.mention}.")

async def setup(bot):
    await bot.add_cog(Setup(bot))
