import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import re
from database import execute, fetchone, fetchall
from playwright.async_api import async_playwright

CACHE_MINUTES = 60


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

    def cog_unload(self):
        self.daily_boost_reminder.cancel()

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

                event_end = event_start + timedelta(
                    hours=duration_hours
                )

                end_date_text = event_end.strftime(
                    "%d %B %Y"
                )

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

                    active_events.append({
                        "title": title,
                        "duration": duration_hours,
                        "end_date": end_date_text,
                        "link": href,
                        "image": image_url
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
                clean_event = line.strip()

                if weekday not in weekly_events:
                    weekly_events[weekday] = []

                if clean_event not in weekly_events[weekday]:
                    weekly_events[weekday].append(clean_event)

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
                        f"📅 Ends: **{event['end_date']}**\n"
                        f"🔗 [View Event]({event['link']})"
                    )

                    embed.add_field(
                        name=f"✨ {event['title']}",
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

            embed.timestamp = datetime.utcnow()

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

            embed.set_image(
                url="https://www.artix.com/images/artix-entertainment-share.png"
            )

            ordered_days = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday"
            ]

            has_events = False

            for day in ordered_days:
                events = weekly_events.get(day, [])

                if not events:
                    continue

                has_events = True

                value = "\n".join(
                    [f"✨ {event}" for event in events]
                )

                embed.add_field(
                    name=f"📅 {day}",
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

            embed.timestamp = datetime.utcnow()

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

        print(f"[BOOST LOOP] {now}")
        
        if now.hour != 12 or now.minute != 0:
            return

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

            embed.add_field(
                name=f"✨ {event['title']}",
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

        embed.timestamp = datetime.utcnow()

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

            if channel is None:
                continue

            try:
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


async def setup(bot):
    await bot.add_cog(Boosts(bot))