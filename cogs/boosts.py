import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
import json
import os

from playwright.async_api import async_playwright


SETTINGS_FILE = "data/boost_settings.json"


class Boosts(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.settings = self.load_settings()
        self.daily_boost_reminder.start()

    def cog_unload(self):
        self.daily_boost_reminder.cancel()

    def load_settings(self):

        os.makedirs("data", exist_ok=True)

        if not os.path.exists(SETTINGS_FILE):

            with open(SETTINGS_FILE, "w") as file:
                json.dump({}, file, indent=4)

        with open(SETTINGS_FILE, "r") as file:
            return json.load(file)

    def save_settings(self):

        os.makedirs("data", exist_ok=True)

        with open(SETTINGS_FILE, "w") as file:
            json.dump(self.settings, file, indent=4)

    async def fetch_artix_calendar_events(self):

        try:

            async with async_playwright() as p:

                browser = await p.chromium.launch(
                    headless=True
                )

                page = await browser.new_page()

                await page.goto(
                    "https://www.artix.com/calendar/",
                    wait_until="networkidle",
                    timeout=60000
                )

                # Wait for JS rendering
                await page.wait_for_timeout(5000)

                today_day = str(datetime.now().day)

                found_events = []

                calendar_cells = page.locator("td")

                count = await calendar_cells.count()

                for i in range(count):

                    cell = calendar_cells.nth(i)

                    try:
                        cell_text = await cell.inner_text()
                        cell_text = cell_text.strip()

                    except:
                        continue

                    if not cell_text:
                        continue

                    lines = cell_text.split("\n")

                    if not lines:
                        continue

                    first_line = lines[0].strip()

                    # Match today's date
                    if first_line == today_day:

                        events = lines[1:]

                        for event in events:

                            event = event.strip()

                            if event:
                                found_events.append(event)

                await browser.close()

                return found_events

        except Exception as e:

            print(f"[CALENDAR ERROR] {e}")

            return []

    @app_commands.command(
        name="boost_today",
        description="Show active AQW boosts/events today"
    )
    async def boost_today(self, interaction: discord.Interaction):

        await interaction.response.defer()

        try:
            import re
            from datetime import timedelta

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

                await page.wait_for_timeout(5000)

                # Get all calendar event links
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
                    except:
                        continue
                    
                    lookback_start = today - timedelta(days=3)

                    if not (lookback_start.date() <= event_start.date() <= today.date()):
                        continue

                    # Open event detail page
                    detail_page = await browser.new_page()

                    try:
                        await detail_page.goto(
                            href,
                            wait_until="networkidle",
                            timeout=60000
                        )

                        await detail_page.wait_for_timeout(2000)

                        detail_text = await detail_page.locator("body").inner_text()

                    except:
                        await detail_page.close()
                        continue

                    await detail_page.close()

                    # Default duration
                    duration_hours = 24

                    duration_match = re.search(
                        r"(\d+)\s*hour",
                        detail_text,
                        re.IGNORECASE
                    )

                    if duration_match:
                        duration_hours = int(duration_match.group(1))

                    event_end = event_start + timedelta(hours=duration_hours)
                    # Format end date text
                    end_date_text = event_end.strftime("%d %B %Y")

                    if event_start <= today < event_end:

                        active_events.append(
                            f"✨ **{title}**\n"
                            f"⏳ Duration: **{duration_hours} hours**\n"
                            f"📅 Ends: **{end_date_text}**\n"
                            f"🔗 [View Event]({href})"
                        )

                await browser.close()

            embed = discord.Embed(
                title="📢 AQW Active Boosts Today",
                description=(
                    "These boosts/events are currently active based on "
                    "the Artix Calendar event duration."
                ),
                color=discord.Color.gold()
            )

            if active_events:

                embed.add_field(
                    name="🔥 Active Now",
                    value="\n\n".join(active_events[:10]),
                    inline=False
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

            import re
            from datetime import timedelta

            async with async_playwright() as p:

                browser = await p.chromium.launch(
                    headless=True
                )

                page = await browser.new_page()

                await page.goto(
                    "https://www.artix.com/calendar/",
                    wait_until="networkidle",
                    timeout=60000
                )

                await page.wait_for_timeout(5000)

                body_text = await page.locator("body").inner_text()

                await browser.close()

            # Split page into lines
            lines = body_text.split("\n")

            # Next 7 days
            today = datetime.now()

            start_date = today.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_date = start_date + timedelta(days=7)

            weekly_events = {}

            # Match dates like 5.11.26
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
                except:
                    continue

                # Only next 7 days
                if start_date.date() <= event_date.date() <= end_date.date():

                    weekday = event_date.strftime("%A")

                    # Keep original event text including date
                    clean_event = line.strip()

                    if weekday not in weekly_events:
                        weekly_events[weekday] = []

                    if clean_event not in weekly_events[weekday]:
                        weekly_events[weekday].append(clean_event)

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

            for day in ordered_days:

                events = weekly_events.get(day, [])

                if not events:
                    continue

                formatted_events = []

                for event in events:

                    formatted_events.append(
                        f"✨ {event}"
                    )

                value = "\n".join(formatted_events)

                embed.add_field(
                    name=f"📅 {day}",
                    value=value,
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

        guild_id = str(interaction.guild.id)

        if guild_id not in self.settings:
            self.settings[guild_id] = {}

        self.settings[guild_id]["channel_id"] = channel.id
        self.settings[guild_id]["notify_enabled"] = True
        self.settings[guild_id]["last_sent_date"] = ""

        self.save_settings()

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

        guild_id = str(interaction.guild.id)

        if guild_id not in self.settings:
            self.settings[guild_id] = {}

        self.settings[guild_id]["notify_enabled"] = status == "on"

        self.save_settings()

        await interaction.response.send_message(
            f"AQW reminders are now **{status}**.",
            ephemeral=True
        )

    @tasks.loop(minutes=30)
    async def daily_boost_reminder(self):

        await self.bot.wait_until_ready()

        now = datetime.now()

        # Send between 9:00 - 9:29 AM
        if now.hour != 9 or now.minute >= 30:
            return

        today_date = now.strftime("%Y-%m-%d")

        events = await self.fetch_artix_calendar_events()

        if not events:
            return

        event_text = "\n".join(
            [f"• {event}" for event in events]
        )

        for guild_id, config in self.settings.items():

            if not config.get("notify_enabled"):
                continue

            if config.get("last_sent_date") == today_date:
                continue

            channel_id = config.get("channel_id")

            if not channel_id:
                continue

            channel = self.bot.get_channel(channel_id)

            if channel is None:
                continue

            embed = discord.Embed(
                title="AQW Daily Calendar Reminder",
                description=event_text,
                color=discord.Color.gold()
            )

            embed.set_footer(
                text="Automatic reminder from Artix Calendar"
            )

            try:

                await channel.send(embed=embed)

                self.settings[guild_id]["last_sent_date"] = today_date

                self.save_settings()

            except Exception as e:

                print(f"[REMINDER ERROR] {e}")


async def setup(bot):
    await bot.add_cog(Boosts(bot))