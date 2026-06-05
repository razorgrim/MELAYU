import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import re
import unicodedata
from database import execute, fetchone, fetchall
from playwright.async_api import async_playwright

CACHE_MINUTES = 60

BOOST_EMOJIS = {
    "class": "<:ClassBoost:1505372617014775928>",
    "exp": "<:ExpBoost:1505372494922780753>",
    "rep": "<:RepBoost:1505372317650255984>",
    "gold": "<:GoldBoost:1505359354780586065>",
    "member": "<:Member:1505373039267680457>",
    "acs": "<:Acs:1505374359445831730>",
    "seasonal": "<:seasonaltag:1505375179923263649>",
    "rare": "<:raretag:1505375179923263649>",
    "legend": "<:legendtag:1505375321816436757>",
    
    
}


def get_boost_emoji(title):
    title = title.lower()

    if "class" in title:
        return BOOST_EMOJIS["class"]

    if "exp" in title or "xp" in title:
        return BOOST_EMOJIS["exp"]

    if "rep" in title or "reputation" in title:
        return BOOST_EMOJIS["rep"]

    if "gold" in title:
        return BOOST_EMOJIS["gold"]

    if "member" in title:
        return BOOST_EMOJIS["member"]

    if "acs" in title or "ac" in title:
        return BOOST_EMOJIS["acs"]
    
    if "seasonal" in title:
        return BOOST_EMOJIS["seasonal"]
    
    if "rare" in title:
        return BOOST_EMOJIS["rare"]
    
    if "legend" in title:
        return BOOST_EMOJIS["legend"]

    return "<:bagicon2:1505377192236814439>"

def format_short_date(date_obj):
    return f"{date_obj.day}.{date_obj.month}.{date_obj.year}"

class Boosts(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        
        # Cache for /boost_today
        self.cached_active_events = None
        self.active_cache_timestamp = None

        # Cache for /boost_week
        self.cached_week_events = None
        self.week_cache_timestamp = None

        self.daily_boost_reminder.start()
        self.weekly_boost_reminder.start()

    def cog_unload(self):
        self.daily_boost_reminder.cancel()
        self.weekly_boost_reminder.cancel()

    def cache_is_valid(self, timestamp):
        if timestamp is None:
            return False

        return datetime.now() - timestamp < timedelta(minutes=CACHE_MINUTES)

    async def fetch_artix_body_text(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(
                "https://www.artix.com/calendar/",
                wait_until="networkidle",
                timeout=60000
            )

            await page.wait_for_timeout(2000)

            body_text = await page.locator("body").inner_text()

            await browser.close()

            return body_text

    async def scrape_active_events(self):

        today = datetime.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        active_events = []

        date_pattern = r"(\d{1,2})\.(\d{1,2})\.(\d{2})"

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await page.goto(
                "https://www.artix.com/calendar/",
                wait_until="networkidle",
                timeout=60000
            )

            await page.wait_for_timeout(2000)

            event_links = await page.locator("a").evaluate_all("""
                links => links
                    .map(a => ({
                        text: a.innerText,
                        href: a.href
                    }))
                    .filter(a =>
                        a.text &&
                        a.href &&
                        a.href.includes("artix.com/calendar/")
                    )
            """)

            for event in event_links:

                title = event["text"].strip()
                href = event["href"]

                match = re.search(date_pattern, title)

                if not match:
                    continue

                month = int(match.group(1))
                day = int(match.group(2))
                year = int("20" + match.group(3))

                try:
                    event_start = datetime(year, month, day)

                except Exception:
                    continue

                # Only recent boosts can still be active
                lookback_start = today - timedelta(days=3)

                if not (
                    lookback_start.date()
                    <= event_start.date()
                    <= today.date()
                ):
                    continue

                detail_page = await browser.new_page()

                try:

                    await detail_page.goto(
                        href,
                        wait_until="networkidle",
                        timeout=60000
                    )

                    await detail_page.wait_for_timeout(1000)

                    detail_text = await detail_page.locator(
                        "body"
                    ).inner_text()

                    # Scrape description
                    description_text = ""
                    try:
                        container = detail_page.locator("div.container.newsPost.full")
                        if await container.count() > 0:
                            raw_desc = await container.evaluate("""
                                element => {
                                    const col = element.querySelector('.col-xs-12');
                                    if (!col) return '';
                                    
                                    function toMarkdown(node, parentBold = false, parentItalic = false) {
                                        if (node.nodeType === Node.TEXT_NODE) {
                                            return node.textContent;
                                        }
                                        if (node.nodeType !== Node.ELEMENT_NODE) {
                                            return '';
                                        }
                                        
                                        const tagName = node.tagName.toLowerCase();
                                        if (tagName === 'h1' || tagName === 'script' || tagName === 'style' || tagName === 'img') {
                                            return '';
                                        }
                                        
                                        let currentBold = parentBold;
                                        let currentItalic = parentItalic;
                                        
                                        if (tagName === 'strong' || tagName === 'b') {
                                            currentBold = true;
                                        }
                                        if (tagName === 'em' || tagName === 'i') {
                                            currentItalic = true;
                                        }
                                        
                                        let childrenContent = '';
                                        for (const child of node.childNodes) {
                                            childrenContent += toMarkdown(child, currentBold, currentItalic);
                                        }
                                        
                                        if (tagName === 'strong' || tagName === 'b') {
                                            if (parentBold) return childrenContent;
                                            const trimmed = childrenContent.trim();
                                            return trimmed ? '**' + trimmed + '**' : '';
                                        }
                                        if (tagName === 'em' || tagName === 'i') {
                                            if (parentItalic) return childrenContent;
                                            const trimmed = childrenContent.trim();
                                            return trimmed ? '*' + trimmed + '*' : '';
                                        }
                                        if (tagName === 'li') {
                                            return '\\n• ' + childrenContent.trim();
                                        }
                                        if (tagName === 'br') {
                                            return '\\n';
                                        }
                                        if (tagName === 'p' || tagName === 'div' || tagName === 'h2' || tagName === 'h3' || tagName === 'h4' || tagName === 'ul' || tagName === 'ol') {
                                            return '\\n' + childrenContent.trim() + '\\n';
                                        }
                                        
                                        return childrenContent;
                                    }
                                    
                                    return toMarkdown(col).trim();
                                }
                            """)
                            normalized_desc = unicodedata.normalize("NFKD", raw_desc)
                            lines = [line.strip() for line in normalized_desc.split("\n")]
                            cleaned_lines = []
                            prev_empty = False
                            for line in lines:
                                if "log in each day for a new reward" in line.lower():
                                    continue
                                if line:
                                    cleaned_lines.append(line)
                                    prev_empty = False
                                else:
                                    if not prev_empty:
                                        cleaned_lines.append("")
                                        prev_empty = True
                            description_text = "\n".join(cleaned_lines).strip()
                            if len(description_text) > 800:
                                description_text = description_text[:797] + "..."
                    except Exception as e:
                        print(f"[SCRAPE WARNING] Failed to scrape description: {e}")

                except Exception:

                    await detail_page.close()
                    continue

                # Default duration
                duration_hours = 24

                duration_match = re.search(
                    r"(\d+)\s*hour",
                    detail_text,
                    re.IGNORECASE
                )

                if duration_match:
                    duration_hours = int(
                        duration_match.group(1)
                    )

                event_end = event_start + timedelta(hours=duration_hours)

                # Display the last active calendar date.
                # Example: Monday 18.5.2026 + 48 hours = active until 19.5.2026
                display_end_date = event_end - timedelta(seconds=1)

                end_date_text = format_short_date(display_end_date)

                if event_start <= today < event_end:

                   # Try getting event image from img#__mcenew
                    image_url = None

                    try:

                        image_element = detail_page.locator("img#__mcenew").first

                        src = await image_element.get_attribute("src")

                        if src:

                            # Convert relative URL
                            if src.startswith("/"):
                                src = "https://www.artix.com" + src

                            image_url = src

                    except Exception:
                        image_url = None

                    # Remove original MM.DD.YY from title
                    clean_title = re.sub(date_pattern, "", title).strip()
                    clean_title = clean_title.strip("-–—:| ")

                    # Add formatted DD.MM.YYYY beside title
                    formatted_start_date = format_short_date(event_start)

                    active_events.append({
                        "title": f"{clean_title} {formatted_start_date}",
                        "duration": duration_hours,
                        "end_date": end_date_text,
                        "link": href,
                        "image": image_url,
                        "description": description_text
                    })

                # CLOSE PAGE AFTER EVERYTHING
                await detail_page.close()

            await browser.close()

        return active_events

    async def get_cached_active_events(self):
        if (
            self.cached_active_events is not None
            and self.cache_is_valid(self.active_cache_timestamp)
        ):
            print("[CACHE] Using cached active AQW boosts")
            return self.cached_active_events

        print("[CACHE] Refreshing active AQW boosts")

        active_events = await self.scrape_active_events()

        self.cached_active_events = active_events
        self.active_cache_timestamp = datetime.now()

        return active_events

    async def scrape_week_events(self):
        body_text = await self.fetch_artix_body_text()
        lines = body_text.split("\n")

        today = datetime.now()

        start_date = today.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        end_date = start_date + timedelta(days=7)
        weekly_events = {}

        date_pattern = r"(\d{1,2})\.(\d{1,2})\.(\d{2})"

        for line in lines:
            line = line.strip()

            if not line:
                continue

            match = re.search(date_pattern, line)

            if not match:
                continue

            month = int(match.group(1))
            day = int(match.group(2))
            year = int("20" + match.group(3))

            try:
                event_date = datetime(year, month, day)
            except Exception:
                continue

            if start_date.date() <= event_date.date() <= end_date.date():
                weekday = event_date.strftime("%A")
                date_text = format_short_date(event_date)

                day_key = f"{weekday} {date_text}"

                # Remove date from boost description
                clean_event = re.sub(date_pattern, "", line).strip()
                clean_event = clean_event.strip("-–—:| ")

                if day_key not in weekly_events:
                    weekly_events[day_key] = []

                if clean_event not in weekly_events[day_key]:
                    weekly_events[day_key].append(clean_event)

        return weekly_events

    async def get_cached_week_events(self):
        if (
            self.cached_week_events is not None
            and self.cache_is_valid(self.week_cache_timestamp)
        ):
            print("[CACHE] Using cached weekly AQW boosts")
            return self.cached_week_events

        print("[CACHE] Refreshing weekly AQW boosts")

        weekly_events = await self.scrape_week_events()

        self.cached_week_events = weekly_events
        self.week_cache_timestamp = datetime.now()

        return weekly_events

    @app_commands.command(
        name="boost_today",
        description="Show active AQW boosts/events today"
    )
    async def boost_today(self, interaction: discord.Interaction):

        await interaction.response.defer()

        try:

            active_events = await self.get_cached_active_events()

            embed = discord.Embed(
                title="📢 AQW Active Boosts Today",
                description=(
                    "These boosts/events are currently active based on "
                    "the Artix Calendar event duration."
                ),
                color=discord.Color.gold()
            )

            embed.set_thumbnail(
                url="https://www.aq.com/images/aqw-icon.png"
            )

            if active_events:

                for event in active_events[:5]:

                    value = (
                        f"⏳ Duration: **{event['duration']} hours**\n"
                        f"🕧 Ends: **{event['end_date']}**\n"
                        f"🔗 [View Event]({event['link']})"
                    )

                    if event.get("description"):
                        value += f"\n\n{event['description']}"

                    embed.add_field(
                        name=f"{get_boost_emoji(event['title'])} {event['title']}",
                        value=value,
                        inline=False
                    )

                    # Use first image found
                    if event.get("image"):
                        embed.set_image(
                            url=event["image"]
                        )

            else:

                embed.add_field(
                    name="No Active Boosts Detected",
                    value="No active boost/event was detected today.",
                    inline=False
                )

            embed.set_footer(
                text="AdventureQuest Worlds • Artix Calendar"
            )

            embed.timestamp = datetime.now(timezone.utc)

            await interaction.followup.send(embed=embed)

        except Exception as e:

            embed = discord.Embed(
                title="Calendar Error",
                description=str(e),
                color=discord.Color.red()
            )

            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="boost_week",
        description="Show upcoming AQW boosts/events"
    )
    async def boost_week(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            weekly_events = await self.get_cached_week_events()

            embed = discord.Embed(
                title="📢 AQW Upcoming Boost Schedule",
                description=(
                    "Here are the upcoming AQW boosts "
                    "and events for the next 7 days."
                ),
                color=discord.Color.gold()
            )

            embed.set_thumbnail(
                url="https://www.aq.com/images/aqw-icon.png"
            )

            embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")

            has_events = False

            for day in weekly_events:
                events = weekly_events.get(day, [])

                if not events:
                    continue

                has_events = True

                value = "\n".join(
                    [f"{get_boost_emoji(event)} {event}" for event in events]
                )

                embed.add_field(
                    name=f"<:Member:1505373039267680457>  {day}",
                    value=value,
                    inline=False
                )

            if not has_events:
                embed.add_field(
                    name="No Upcoming Events Detected",
                    value="No boosts/events were detected for the next 7 days.",
                    inline=False
                )

            embed.set_footer(
                text="AdventureQuest Worlds • Artix Calendar"
            )

            embed.timestamp = datetime.now(timezone.utc)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="Calendar Error",
                description=str(e),
                color=discord.Color.red()
            )

            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="boost_setchannel",
        description="Set AQW reminder channel"
    )
    @app_commands.describe(
        channel="Channel for AQW reminders"
    )
    async def boost_setchannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You do not have permission.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        await execute(
            """
            INSERT INTO server_settings
            (
                guild_id,
                boost_channel_id,
                boost_notify_enabled
            )
            VALUES (%s, %s, %s)

            ON DUPLICATE KEY UPDATE
                boost_channel_id = VALUES(boost_channel_id),
                boost_notify_enabled = VALUES(boost_notify_enabled)
            """,
            (
                guild_id,
                channel.id,
                True
            )
        )

        await interaction.response.send_message(
            f"AQW reminders will be sent to {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="boost_notify",
        description="Enable or disable AQW reminders"
    )
    @app_commands.describe(
        status="on or off"
    )
    async def boost_notify(
        self,
        interaction: discord.Interaction,
        status: str
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You do not have permission.",
                ephemeral=True
            )
            return

        status = status.lower()

        if status not in ["on", "off"]:
            await interaction.response.send_message(
                "Use `on` or `off`.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id

        await execute(
            """
            INSERT INTO server_settings
            (
                guild_id,
                boost_notify_enabled
            )
            VALUES (%s, %s)

            ON DUPLICATE KEY UPDATE
                boost_notify_enabled = VALUES(boost_notify_enabled)
            """,
            (
                guild_id,
                status == "on"
            )
        )

        await interaction.response.send_message(
            f"AQW reminders are now **{status}**.",
            ephemeral=True
        )

    @tasks.loop(minutes=1)
    async def daily_boost_reminder(self):
        await self.bot.wait_until_ready()

        now = datetime.now()

        if now.hour != 12 or now.minute != 0:
            return

        print(f"[BOOST LOOP] Sending daily boost reminder at {now}")

        today_date = now.strftime("%Y-%m-%d")
        active_events = await self.get_cached_active_events()

        if not active_events:
            return
        
        embed = discord.Embed(
            title="📢 AQW Daily Boost Reminder",
            description=(
                "These boosts/events are currently active based on "
                "the Artix Calendar event duration."
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url="https://www.aq.com/images/aqw-icon.png"
        )

        for event in active_events[:5]:

            value = (
                f"⏳ Duration: **{event['duration']} hours**\n"
                f"📅 Ends: **{event['end_date']}**\n"
                f"🔗 [View Event]({event['link']})"
            )

            if event.get("description"):
                value += f"\n\n{event['description']}"

            embed.add_field(
                name=f"{get_boost_emoji(event['title'])} {event['title']}",
                value=value,
                inline=False
            )

            # Use first image found
            if event.get("image"):
                embed.set_image(
                    url=event["image"]
                )

        embed.set_footer(
            text="AdventureQuest Worlds • Artix Calendar"
        )

        embed.timestamp = datetime.now(timezone.utc)

        settings = await fetchall(
            """
            SELECT * FROM server_settings
            WHERE boost_notify_enabled = TRUE
            """
        )

        for config in settings:
            
            if config["boost_last_sent_date"] and str(config["boost_last_sent_date"]) == today_date:
                continue

            channel_id = config["boost_channel_id"]

            if not channel_id:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    continue

            if channel is None:
                continue

            verification_config = await fetchone(
                """
                SELECT adventure_role_id
                FROM verification_config
                WHERE guild_id = %s
                """,
                (config["guild_id"],)
            )

            role_mention = ""

            if verification_config:

                role = channel.guild.get_role(
                    verification_config["adventure_role_id"]
                )

                if role:
                    role_mention = role.mention

            try:
                if role_mention:
                    await channel.send(
                        content=f"{role_mention} AQW boosts are now active!",
                        embed=embed
                    )
                else:
                    await channel.send(embed=embed)

                await execute(
                    """
                    UPDATE server_settings
                    SET boost_last_sent_date = %s
                    WHERE guild_id = %s
                    """,
                    (
                        today_date,
                        config["guild_id"]
                    )
                )

            except Exception as e:
                print(f"[REMINDER ERROR] {e}")

    @tasks.loop(minutes=1)
    async def weekly_boost_reminder(self):
        await self.bot.wait_until_ready()

        now = datetime.now()

        # Check if today is Monday morning at 09:00 AM
        if now.weekday() != 0 or now.hour != 9 or now.minute != 0:
            return

        print(f"[BOOST LOOP] Sending weekly boost announcement at {now}")

        today_date = now.strftime("%Y-%m-%d")
        weekly_events = await self.get_cached_week_events()

        if not weekly_events:
            return

        embed = discord.Embed(
            title="📢 AQW Upcoming Boost Schedule",
            description=(
                "Here are the upcoming AQW boosts "
                "and events for the next 7 days."
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url="https://www.aq.com/images/aqw-icon.png"
        )

        embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")

        has_events = False

        for day in weekly_events:
            events = weekly_events.get(day, [])

            if not events:
                continue

            has_events = True

            value = "\n".join(
                [f"{get_boost_emoji(event)} {event}" for event in events]
            )

            embed.add_field(
                name=f"<:Member:1505373039267680457>  {day}",
                value=value,
                inline=False
            )

        if not has_events:
            embed.add_field(
                name="No Upcoming Events Detected",
                value="No boosts/events were detected for the next 7 days.",
                inline=False
            )

        embed.set_footer(
            text="AdventureQuest Worlds • Artix Calendar"
        )

        embed.timestamp = datetime.now(timezone.utc)

        settings = await fetchall(
            """
            SELECT * FROM server_settings
            WHERE boost_notify_enabled = TRUE
            """
        )

        for config in settings:
            
            if config.get("boost_weekly_last_sent_date") and str(config["boost_weekly_last_sent_date"]) == today_date:
                continue

            channel_id = config["boost_channel_id"]

            if not channel_id:
                continue

            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    continue

            if channel is None:
                continue

            verification_config = await fetchone(
                """
                SELECT adventure_role_id
                FROM verification_config
                WHERE guild_id = %s
                """,
                (config["guild_id"],)
            )

            role_mention = ""

            if verification_config:

                role = channel.guild.get_role(
                    verification_config["adventure_role_id"]
                )

                if role:
                    role_mention = role.mention

            try:
                if role_mention:
                    await channel.send(
                        content=f"{role_mention} AQW Weekly Boost Schedule is out!",
                        embed=embed
                    )
                else:
                    await channel.send(embed=embed)

                await execute(
                    """
                    UPDATE server_settings
                    SET boost_weekly_last_sent_date = %s
                    WHERE guild_id = %s
                    """,
                    (
                        today_date,
                        config["guild_id"]
                    )
                )

            except Exception as e:
                print(f"[WEEKLY REMINDER ERROR] {e}")


async def setup(bot):
    await bot.add_cog(Boosts(bot))