import discord
from discord import app_commands
from discord.ext import commands
import re

def strip_emoji(text):
    return re.sub(r'<a?:\w+:\d+>\s*', '', text).strip()
import random
import json
from datetime import datetime, timezone
from database import execute, fetchone, fetchall

COOLDOWN_MINUTES = 1
XP_PER_TICKET_MULTIPLIER = 50

def xp_needed_for_level(level):
    return int(100 * (1.25 ** (level - 1)))

def get_level_title(level):
    if level >= 50:
        return "Dungeon Delver"
    elif level >= 40:
        return "Vanguard Ally"
    elif level >= 30:
        return "Quest Confidant"
    elif level >= 20:
        return "Campfire Companion"
    elif level >= 10:
        return "Wandering Nomad"
    elif level >= 1:
        return "Greenie Stranger"
    return "None"

def get_all_unlocked_level_titles(level):
    titles = []
    if level >= 1:
        titles.append("Greenie Stranger")
    if level >= 10:
        titles.append("Wandering Nomad")
    if level >= 20:
        titles.append("Campfire Companion")
    if level >= 30:
        titles.append("Quest Confidant")
    if level >= 40:
        titles.append("Vanguard Ally")
    if level >= 50:
        titles.append("Dungeon Delver")
    return titles

def generate_xp_bar(xp, level, length=10):
    needed = xp_needed_for_level(level)
    
    if needed <= 0:
        percent = 1.0
    else:
        percent = max(0.0, min(1.0, xp / needed))
        
    filled_length = int(round(length * percent))
    bar = '▰' * filled_length + '▱' * (length - filled_length)
    return f"`{bar}` {percent*100:.1f}%"

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cooldowns = {} # Key: (guild_id, user_id), Value: datetime

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # Simple rate limit for earning XP (60 seconds)
        guild_id = message.guild.id
        user_id = message.author.id
        now = datetime.now(timezone.utc)
        key = (guild_id, user_id)

        if key in self.xp_cooldowns:
            last_earned = self.xp_cooldowns[key]
            if (now - last_earned).total_seconds() < 60:
                return

        self.xp_cooldowns[key] = now

        # Add XP
        xp_to_add = random.randint(10, 25)
        await self.add_xp_and_coins(message.guild, user_id, xp_to_add, 0, channel=message.channel)

    async def add_xp_and_coins(self, guild, user_id, xp_to_add, coins_to_add, tickets_to_add=0, channel=None):
        guild_id = guild.id

        # Get current profile
        profile = await fetchone(
            "SELECT xp, level, coins, completed_tickets, achievements FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        if not profile:
            current_xp = 0
            current_level = 1
            current_coins = 0
            current_tickets = 0
            achievements_raw = "[]"
        else:
            current_xp = profile["xp"]
            current_level = profile["level"]
            current_coins = profile["coins"]
            current_tickets = profile.get("completed_tickets") or 0
            achievements_raw = profile.get("achievements") or "[]"

        try:
            user_achievements = json.loads(achievements_raw)
        except Exception:
            user_achievements = []

        new_xp = current_xp + xp_to_add
        new_coins = current_coins + coins_to_add
        new_tickets = current_tickets + tickets_to_add

        # Check level up (resets XP on level up, with 1.25x scaling needed for the next level)
        new_level = current_level
        while True:
            needed = xp_needed_for_level(new_level)
            if new_xp >= needed:
                new_xp -= needed
                new_level += 1
            else:
                break

        unlocked_achievements = []

        # 1. Level 2 Achievement: "Wumpus Friend"
        if new_level >= 2:
            level_ach_name = "Wumpus Friend"
            if not any(a.lower() == level_ach_name.lower() for a in user_achievements):
                user_achievements.append(level_ach_name)
                unlocked_achievements.append(level_ach_name)

        # 2. Level titles milestones (10, 20, 30, 40, 50)
        LEVEL_TITLES_MILESTONES = [
            (10, "Wandering Nomad"),
            (20, "Campfire Companion"),
            (30, "Quest Confidant"),
            (40, "Vanguard Ally"),
            (50, "Dungeon Delver")
        ]
        for threshold, name in LEVEL_TITLES_MILESTONES:
            if new_level >= threshold:
                if not any(a.lower() == name.lower() for a in user_achievements):
                    user_achievements.append(name)
                    unlocked_achievements.append(name)

        # 3. Ticket Achievements
        if tickets_to_add > 0:
            TICKET_ACHIEVEMENTS = [
                (10, "Newcomer"),
                (20, "Apprentice"),
                (30, "Journeyman"),
                (40, "Adventurer"),
                (50, "Huntsman"),
                (60, "Mercenary"),
                (70, "Slayer"),
                (80, "Lord"),
                (90, "Conquerer"),
                (100, "That One Guy")
            ]
            for threshold, name in TICKET_ACHIEVEMENTS:
                if new_tickets >= threshold:
                    if not any(a.lower() == name.lower() for a in user_achievements):
                        user_achievements.append(name)
                        unlocked_achievements.append(name)

        # Update DB
        await execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, xp, level, coins, completed_tickets, achievements)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                xp = VALUES(xp),
                level = VALUES(level),
                coins = VALUES(coins),
                completed_tickets = VALUES(completed_tickets),
                achievements = VALUES(achievements)
            """,
            (guild_id, user_id, new_xp, new_level, new_coins, new_tickets, json.dumps(user_achievements))
        )

        if new_level > current_level and channel:
            # Check level up channel config
            config = await fetchone(
                "SELECT announcement_channel_id FROM level_config WHERE guild_id = %s",
                (guild_id,)
            )
            target_channel = None
            if config and config["announcement_channel_id"]:
                target_channel = guild.get_channel(config["announcement_channel_id"])

            if not target_channel:
                target_channel = channel

            member = guild.get_member(user_id)
            if member and target_channel:
                embed = discord.Embed(
                    title="🎉 <:levelicon:1513888070066241737> LEVEL UP!",
                    description=f"{member.mention} has advanced to **Level {new_level}**! 🚀",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                try:
                    await target_channel.send(embed=embed)
                except Exception as e:
                    print(f"[LEVEL UP ERROR] Failed to send level up message: {e}")

        # Send achievement notifications
        if unlocked_achievements and channel:
            config = await fetchone(
                "SELECT announcement_channel_id FROM level_config WHERE guild_id = %s",
                (guild_id,)
            )
            target_channel = None
            if config and config["announcement_channel_id"]:
                target_channel = guild.get_channel(config["announcement_channel_id"])

            if not target_channel:
                target_channel = channel

            member = guild.get_member(user_id)
            if member and target_channel:
                ACHIEVEMENT_EMOJIS = {
                    "Newcomer": "<:10tixhelp:1513506260467712008>",
                    "Apprentice": "<:20tixhelp:1513506264674603121>",
                    "Journeyman": "<:30tixhelp:1513506267606417418>",
                    "Adventurer": "<:40tixhelp:1513506270265741372>",
                    "Huntsman": "<:50tixhelp:1513506273461665883>",
                    "Mercenary": "<:60tixhelp:1513506275873525940>",
                    "Slayer": "<:70tixhelp:1513506279166054474>",
                    "Lord": "<:80tixhelp:1513506282202468453>",
                    "Conquerer": "<:90tixhelp:1513506285906165802>",
                    "That One Guy": "<:100tixhelp:1513506288779268106>",
                    "Wumpus Friend": "<:achievementicon:1513431554536509570>",
                    "Greenie Stranger": "<:levelicon:1513888070066241737>",
                    "Wandering Nomad": "<:levelicon:1513888070066241737>",
                    "Campfire Companion": "<:levelicon:1513888070066241737>",
                    "Quest Confidant": "<:levelicon:1513888070066241737>",
                    "Vanguard Ally": "<:levelicon:1513888070066241737>",
                    "Dungeon Delver": "<:levelicon:1513888070066241737>"
                }
                for name in unlocked_achievements:
                    emoji = ACHIEVEMENT_EMOJIS.get(name, "<:achievementicon:1513431554536509570>")
                    embed = discord.Embed(
                        title=f"{emoji} Achievement Unlocked!",
                        description=f"Congratulations {member.mention}! You have earned the achievement title: **`{name}`**! 🎉",
                        color=discord.Color.gold()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    try:
                        await target_channel.send(embed=embed)
                    except Exception as e:
                        print(f"[ACHIEVEMENT ERROR] Failed to send achievement message: {e}")

    @app_commands.command(name="profile", description="Show player stats profile card")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        guild_id = interaction.guild.id
        user_id = target.id

        profile = await fetchone(
            "SELECT * FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )
        points_data = await fetchone(
            "SELECT points FROM helper_points WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )
        verified_data = await fetchone(
            "SELECT ign FROM verified_users WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        xp = profile["xp"] if profile else 0
        level = profile["level"] if profile else 1
        coins = profile["coins"] if profile else 0
        active_title = profile["active_title"] if (profile and profile["active_title"]) else "None"
        if active_title == "None":
            active_title = get_level_title(level)
        embed_color_hex = profile["embed_color"] if (profile and profile["embed_color"]) else "#5865F2"
        daily_streak = profile["daily_streak"] if profile else 0
        points = points_data["points"] if points_data else 0
        ign = verified_data["ign"] if verified_data else "Not Verified"

        # Fetch achievements
        achievements_raw = profile["achievements"] if (profile and profile["achievements"]) else "[]"
        try:
            achievements = json.loads(achievements_raw)
        except Exception:
            achievements = []

        # Dynamically append unlocked level titles to achievements list for the command context
        unlocked_level_titles = get_all_unlocked_level_titles(level)
        for lt in unlocked_level_titles:
            if not any(a.lower() == lt.lower() for a in achievements):
                achievements.append(lt)

        display_title = active_title
        if active_title != "None":
            # Check achievement emojis mapping to prepend them
            ACHIEVEMENT_EMOJIS = {
                "Newcomer": "<:10tixhelp:1513506260467712008>",
                "Apprentice": "<:20tixhelp:1513506264674603121>",
                "Journeyman": "<:30tixhelp:1513506267606417418>",
                "Adventurer": "<:40tixhelp:1513506270265741372>",
                "Huntsman": "<:50tixhelp:1513506273461665883>",
                "Mercenary": "<:60tixhelp:1513506275873525940>",
                "Slayer": "<:70tixhelp:1513506279166054474>",
                "Lord": "<:80tixhelp:1513506282202468453>",
                "Conquerer": "<:90tixhelp:1513506285906165802>",
                "That One Guy": "<:100tixhelp:1513506288779268106>",
                "Wumpus Friend": "<:achievementicon:1513431554536509570>",
                "Greenie Stranger": "<:levelicon:1513888070066241737>",
                "Wandering Nomad": "<:levelicon:1513888070066241737>",
                "Campfire Companion": "<:levelicon:1513888070066241737>",
                "Quest Confidant": "<:levelicon:1513888070066241737>",
                "Vanguard Ally": "<:levelicon:1513888070066241737>",
                "Dungeon Delver": "<:levelicon:1513888070066241737>"
            }
            matched_emoji = None
            for key, val in ACHIEVEMENT_EMOJIS.items():
                if key.lower() == active_title.lower():
                    matched_emoji = val
                    break
            
            if matched_emoji:
                display_title = f"{matched_emoji} {active_title}"
            else:
                # Fallback check if it is in achievements list
                is_ach = any(a.lower() == active_title.lower() for a in achievements)
                if is_ach:
                    display_title = f"<:achievementicon:1513431554536509570> {active_title}"

        completed_tickets = profile["completed_tickets"] if (profile and "completed_tickets" in profile) else 0

        # Try to parse embed color
        try:
            embed_color = discord.Color.from_str(embed_color_hex)
        except Exception:
            embed_color = discord.Color.blue()

        xp_bar = generate_xp_bar(xp, level)
        needed = xp_needed_for_level(level)

        title_name = ign if ign != "Not Verified" else target.display_name
        embed = discord.Embed(
            title=f"<:Playerprofileicon:1513424880274767983> Player Profile - {title_name}",
            color=embed_color
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.description = (
            f"<:levelicon:1513888070066241737> **Level:** {level}\n"
            f"<:expicon:1513888072750596276> **XP:** {xp:,} / {needed:,}\n"
            f"<:progressicon:1513888079142850721> **Progress:** {xp_bar}"
        )

        embed.add_field(name="<:activetitleicon:1513880838066929664> Active Title", value=f"{display_title}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="<:Stashicon:1513426124036640950> Stash (Mcoins)", value=f"<:MCoins:1513429245009854546> **{coins:,}**", inline=True)

        embed.add_field(name="<:HelperHeadingIcon:1513884569160388648> Helper Points", value=f"<:helperpointsicon:1513431870182785135> **{points:,}**", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="<:StreakHeadingIcon:1513884563565314198> Daily Streak", value=f"<:streakdaysicon:1513880822019784724>  **{daily_streak} day(s)**", inline=True)

        embed.add_field(name="<:achievement:1513880829405827193> Achievements", value=f"<:achievementicon:1513431554536509570> **{len(achievements)}** unlocked", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="<:Ticketcomoleteicon:1513433287304020058> Tickets Completed", value=f"<:TicketCompletedIcon:1513884560474247178> **{completed_tickets:,}**", inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="Claim daily Melayu Coins and XP")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        now_ts = datetime.now(timezone.utc).timestamp()

        profile = await fetchone(
            "SELECT daily_last_claim, daily_streak, coins, xp, level FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        last_claim = profile["daily_last_claim"] if profile else 0
        current_streak = profile["daily_streak"] if profile else 0
        level = profile["level"] if profile else 1

        cooldown = 22 * 3600  # 22 hours
        if now_ts - last_claim < cooldown:
            remaining = int(cooldown - (now_ts - last_claim))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.followup.send(f"❌ You have already claimed your daily reward. Try again in **{hours}h {minutes}m**.")
            return

        # Check if streak is broken (more than 48 hours since last claim)
        if now_ts - last_claim > 48 * 3600:
            streak = 1
        else:
            streak = current_streak + 1

        # Calculate rewards
        coins_reward = 2 + (streak // 5)
        coins_reward = min(10, coins_reward) # Cap at 10 coins

        xp_reward = 100 + (streak * 10)
        xp_reward = min(500, xp_reward) # Cap at 500 XP

        # Update profile claim details
        await execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, daily_last_claim, daily_streak)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                daily_last_claim = VALUES(daily_last_claim),
                daily_streak = VALUES(daily_streak)
            """,
            (guild_id, user_id, now_ts, streak)
        )

        await self.add_xp_and_coins(interaction.guild, user_id, xp_reward, coins_reward, channel=interaction.channel)

        await interaction.followup.send(
            f"✅ **Daily Claimed!**\n"
            f"<:MCoins:1513429245009854546> Reward: **+{coins_reward} Melayu Coins (MCoin)**\n"
            f"<:expicon:1513888072750596276> XP gained: **+{xp_reward} XP**\n"
            f"📅 Current Streak: **{streak} day(s)**"
        )

    @app_commands.command(name="shop", description="Browse the Melayu Server Shop")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild.id

        items = await fetchall(
            "SELECT * FROM shop_items WHERE guild_id = %s ORDER BY price ASC",
            (guild_id,)
        )

        if not items:
            await interaction.followup.send("🛒 The server shop is currently empty! Ask an Admin to set up some items.")
            return

        shop_lines = []
        for item in items:
            target_str = ""
            if item["type"] == "role":
                role = interaction.guild.get_role(item["target_id"])
                target_str = f"Role: {role.mention if role else 'Unknown Role'}"
            elif item["type"] == "title":
                target_str = f"Title: {item['target_text']}"
            elif item["type"] == "color":
                target_str = f"Color: `{item['target_text']}`"
            
            shop_lines.append(f"**{item['id']}. {item['name']}** — <:MCoins:1513429245009854546> **{item['price']} MCoin** ({target_str})")

        embed = discord.Embed(
            title="🛒 MELAYU Shop",
            description=(
                "Use `/buy <item_id>` to purchase items using <:MCoins:1513429245009854546> **Melayu Coins (MCoin)**!\n\n"
                + "\n".join(shop_lines)
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="MELAYU Shop System")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the server shop")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        item = await fetchone(
            "SELECT * FROM shop_items WHERE guild_id = %s AND id = %s",
            (guild_id, item_id)
        )

        if not item:
            await interaction.followup.send("❌ Shop item not found.")
            return

        # Get user balance and inventory
        profile = await fetchone(
            "SELECT coins, inventory FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        coins = profile["coins"] if profile else 0
        inventory_raw = profile["inventory"] if (profile and profile["inventory"]) else "[]"

        try:
            inventory = json.loads(inventory_raw)
        except Exception:
            inventory = []

        if coins < item["price"]:
            await interaction.followup.send(f"❌ You do not have enough Melayu Coins. You need **{item['price']} MCoin** but only have **{coins}**.")
            return

        # Check if already purchased (roles/titles)
        item_key = f"{item['type']}:{item['name']}"
        if item_key in inventory:
            await interaction.followup.send("❌ You already own this item!")
            return

        # Deduct coins and add to inventory
        new_coins = coins - item["price"]
        inventory.append(item_key)
        new_inventory = json.dumps(inventory)

        await execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, coins, inventory)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                coins = VALUES(coins),
                inventory = VALUES(inventory)
            """,
            (guild_id, user_id, new_coins, new_inventory)
        )

        # Grant target reward
        if item["type"] == "role":
            role = interaction.guild.get_role(item["target_id"])
            if role:
                try:
                    await interaction.user.add_roles(role)
                    await interaction.followup.send(f"✅ Successfully purchased **{item['name']}** for <:MCoins:1513429245009854546> **{item['price']} MCoin**! The role {role.mention} has been added to you.")
                except Exception as e:
                    await interaction.followup.send(f"✅ Purchased **{item['name']}** but failed to grant role (lack of permissions). Please ask an Admin to grant it manually.")
            else:
                await interaction.followup.send(f"✅ Purchased **{item['name']}** but the associated role was not found in the guild. Please contact an admin.")
        elif item["type"] == "title":
            await interaction.followup.send(f"✅ Successfully purchased Title **{item['name']}** for <:MCoins:1513429245009854546> **{item['price']} MCoin**! Equip it with `/equip`.")
        elif item["type"] == "color":
            await interaction.followup.send(f"✅ Successfully purchased Color **{item['name']}** (`{item['target_text']}`) for <:MCoins:1513429245009854546> **{item['price']} MCoin**! Equip it with `/equip`.")

    @app_commands.command(name="inventory", description="View your purchased shop items")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        profile = await fetchone(
            "SELECT inventory, achievements, level FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        inventory_raw = profile["inventory"] if (profile and profile["inventory"]) else "[]"
        try:
            inventory = json.loads(inventory_raw)
        except Exception:
            inventory = []

        achievements_raw = profile["achievements"] if (profile and profile["achievements"]) else "[]"
        try:
            achievements = json.loads(achievements_raw)
        except Exception:
            achievements = []

        # Dynamically append unlocked level titles to achievements list for the command context
        level = profile["level"] if profile else 1
        unlocked_level_titles = get_all_unlocked_level_titles(level)
        for lt in unlocked_level_titles:
            if not any(a.lower() == lt.lower() for a in achievements):
                achievements.append(lt)

        if not inventory and not achievements:
            await interaction.followup.send("📦 Your inventory is empty! Visit the `/shop` to buy some items or earn achievements from Officers.")
            return

        embed = discord.Embed(
            title="<:Stashicon:1513426124036640950> Your Inventory & Achievements",
            description="Use `/equip <item_name>` to set your active title or profile color!",
            color=discord.Color.blue()
        )

        titles = []
        colors = []
        roles = []

        for item in inventory:
            try:
                itype, iname = item.split(":", 1)
                if itype == "title":
                    titles.append(iname)
                elif itype == "color":
                    colors.append(iname)
                elif itype == "role":
                    roles.append(iname)
            except Exception:
                pass

        if achievements:
            ACHIEVEMENT_EMOJIS = {
                "Newcomer": "<:10tixhelp:1513506260467712008>",
                "Apprentice": "<:20tixhelp:1513506264674603121>",
                "Journeyman": "<:30tixhelp:1513506267606417418>",
                "Adventurer": "<:40tixhelp:1513506270265741372>",
                "Huntsman": "<:50tixhelp:1513506273461665883>",
                "Mercenary": "<:60tixhelp:1513506275873525940>",
                "Slayer": "<:70tixhelp:1513506279166054474>",
                "Lord": "<:80tixhelp:1513506282202468453>",
                "Conquerer": "<:90tixhelp:1513506285906165802>",
                "That One Guy": "<:100tixhelp:1513506288779268106>",
                "Wumpus Friend": "<:achievementicon:1513431554536509570>",
                "Greenie Stranger": "<:levelicon:1513888070066241737>",
                "Wandering Nomad": "<:levelicon:1513888070066241737>",
                "Campfire Companion": "<:levelicon:1513888070066241737>",
                "Quest Confidant": "<:levelicon:1513888070066241737>",
                "Vanguard Ally": "<:levelicon:1513888070066241737>",
                "Dungeon Delver": "<:levelicon:1513888070066241737>"
            }
            ach_lines = []
            for a in achievements:
                emoji = ACHIEVEMENT_EMOJIS.get(a, "<:achievementicon:1513431554536509570>")
                ach_lines.append(f"{emoji} {a}")
            embed.add_field(name="<:achievementicon:1513431554536509570> Earned Achievements (Equippable)", value="\n".join([f"• {a}" for a in ach_lines]), inline=False)
        if titles:
            embed.add_field(name="🏷️ Purchased Titles", value="\n".join([f"• {t}" for t in titles]), inline=False)
        if colors:
            embed.add_field(name="🎨 Purchased Colors", value="\n".join([f"• `{c}`" for c in colors]), inline=False)
        if roles:
            embed.add_field(name="🛡️ Purchased Roles", value="\n".join([f"• {r}" for r in roles]), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="equip", description="Equip an unlocked profile title or color")
    async def equip(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        profile = await fetchone(
            "SELECT inventory, achievements, level FROM user_profiles WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )

        inventory_raw = profile["inventory"] if (profile and profile["inventory"]) else "[]"
        try:
            inventory = json.loads(inventory_raw)
        except Exception:
            inventory = []

        achievements_raw = profile["achievements"] if (profile and profile["achievements"]) else "[]"
        try:
            achievements = json.loads(achievements_raw)
        except Exception:
            achievements = []

        # Dynamically append unlocked level titles to achievements list for the command context
        level = profile["level"] if profile else 1
        unlocked_level_titles = get_all_unlocked_level_titles(level)
        for lt in unlocked_level_titles:
            if not any(a.lower() == lt.lower() for a in achievements):
                achievements.append(lt)

        # Check achievements first
        matched_achievement = None
        for a in achievements:
            if a.lower() == name.lower() or strip_emoji(a).lower() == name.lower():
                matched_achievement = a
                break

        if matched_achievement:
            await execute(
                "UPDATE user_profiles SET active_title = %s WHERE guild_id = %s AND user_id = %s",
                (matched_achievement, guild_id, user_id)
            )
            await interaction.followup.send(f"✅ Equipped Title from Achievement: {matched_achievement}")
            return

        # Check inventory for shop items
        matched_item = None
        for item in inventory:
            try:
                itype, iname = item.split(":", 1)
                if iname.lower() == name.lower() or strip_emoji(iname).lower() == name.lower():
                    matched_item = item
                    break
            except Exception:
                pass

        if not matched_item:
            await interaction.followup.send(f"❌ You do not own any shop item or achievement named '{name}' in your inventory.")
            return

        itype, iname = matched_item.split(":", 1)

        # Retrieve the shop item value
        shop_item = await fetchone(
            "SELECT target_text FROM shop_items WHERE guild_id = %s AND name = %s AND type = %s",
            (guild_id, iname, itype)
        )

        if not shop_item:
            await interaction.followup.send("❌ Error: Shop item metadata not found. Please contact an admin.")
            return

        val = shop_item["target_text"]

        if itype == "title":
            await execute(
                "UPDATE user_profiles SET active_title = %s WHERE guild_id = %s AND user_id = %s",
                (val, guild_id, user_id)
            )
            await interaction.followup.send(f"✅ Equipped Title: {val}")
        elif itype == "color":
            await execute(
                "UPDATE user_profiles SET embed_color = %s WHERE guild_id = %s AND user_id = %s",
                (val, guild_id, user_id)
            )
            await interaction.followup.send(f"✅ Equipped Profile Embed Color: `{val}`")
        else:
            await interaction.followup.send("❌ This item type cannot be equipped (roles are active automatically).")

    @app_commands.command(name="levelboard", description="View active members level rankings")
    async def levelboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild.id

        users = await fetchall(
            "SELECT user_id, level, xp FROM user_profiles WHERE guild_id = %s ORDER BY level DESC, xp DESC LIMIT 10",
            (guild_id,)
        )

        if not users:
            await interaction.followup.send("📊 No leveling data recorded yet.")
            return

        embed = discord.Embed(
            title="🏆 MELAYU Active Level Leaderboard",
            color=discord.Color.teal()
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        board_text = ""
        for index, row in enumerate(users, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"User ID {row['user_id']}"
            board_text += f"**{index}.** {name} — **Level {row['level']}** ({row['xp']:,} XP)\n"

        embed.description = board_text
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Profile(bot))
