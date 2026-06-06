import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import re
import aiohttp
from urllib.parse import quote_plus
import math
import datetime
import emojis


class CharPage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_charpage(self, ign: str):
        ign = ign.strip()
        encoded_ign = quote_plus(ign)
        url = f"https://account.aq.com/CharPage?id={encoded_ign}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status != 200:
                        return None, url

                    html = await response.text()
        except Exception:
            return None, url

        return html, url
    
    async def fetch_badge_count(self, character_id):
        badges = await self.fetch_badges(character_id)
        return str(len(badges))

    async def fetch_badges(self, character_id):
        url = f"https://account.aq.com/Charpage/Badges?ccid={character_id}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        return []

                    badges = await response.json()
                    if isinstance(badges, dict):
                        for key in ("badges", "data", "items"):
                            if key in badges and isinstance(badges[key], list):
                                return badges[key]
                        return []

                    if isinstance(badges, list):
                        return badges

        except Exception as e:
            print(f"[BADGE ERROR] {e}")

        return []

    def normalize_badge_category(self, badge):
        if not isinstance(badge, dict):
            return ""

        for key in ("scategory", "category", "sCategory", "Category"):
            value = badge.get(key)
            if value:
                return str(value).strip().lower()

        link = str(badge.get("link") or badge.get("Link") or "")
        if link:
            match = re.search(r"scategory\s*[:=]\s*[\"']?([^\"'&<>]+)", link, re.IGNORECASE)
            if match:
                return match.group(1).strip().lower()

            match = re.search(r"[?&]scategory=([^&]+)", link, re.IGNORECASE)
            if match:
                return match.group(1).strip().lower()

        return ""

    def get_badge_display_name(self, badge):
        if isinstance(badge, str):
            return badge

        if not isinstance(badge, dict):
            return str(badge)

        for key in ("name", "Name", "badge", "Badge", "sname", "SName"):
            value = badge.get(key)
            if value:
                return str(value).strip()

        link = badge.get("link") or badge.get("Link")
        if link:
            return self.clean_text(str(link))

        return "Unknown Badge"

    def get_badge_display_url(self, badge):
        if not isinstance(badge, dict):
            return None

        for key in ("link", "Link", "url", "Url"):
            value = badge.get(key)
            if value:
                return str(value).strip()

        return None

    def filter_badges_by_category(self, badges, category):
        if not category:
            return []

        category_value = category.strip().lower()
        filtered = []

        for badge in badges:
            badge_category = self.normalize_badge_category(badge)
            if badge_category == category_value or category_value in badge_category:
                filtered.append(badge)

        return filtered

    def get_badge_category_display_name(self, badge):
        for key in ("scategory", "category", "sCategory", "Category"):
            value = badge.get(key) if isinstance(badge, dict) else None
            if value:
                return str(value).strip()

        normalized = self.normalize_badge_category(badge)
        return normalized.title() if normalized else "Uncategorized"

    def aggregate_badge_categories(self, badges):
        counts = {}
        display_names = {}

        for badge in badges:
            category_key = self.normalize_badge_category(badge) or "uncategorized"
            display_name = self.get_badge_category_display_name(badge)

            counts[category_key] = counts.get(category_key, 0) + 1
            display_names.setdefault(category_key, display_name)

        return [
            (display_names[key], counts[key])
            for key in sorted(counts, key=lambda k: counts[k], reverse=True)
        ]

    def format_badge_list(self, badges):
        lines = []
        for badge in badges:
            name = self.get_badge_display_name(badge)
            url = self.get_badge_display_url(badge)
            if url and name:
                line = f"[{discord.utils.escape_markdown(name)}](<{url}>)"
            else:
                line = discord.utils.escape_markdown(name)

            if len("\n".join(lines + [line])) > 900:
                break
            lines.append(line)

        if not lines:
            return "None"

        remaining = len(badges) - len(lines)
        if remaining > 0:
            lines.append(f"...and {remaining} more")

        return "\n".join(lines)

    async def fetch_treasure_points(self, character_id):
        url = f"https://account.aq.com/CharPage/Inventory?ccid={character_id}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        return "0"

                    html = await response.text()
                    return self.parse_treasure_points(html)

        except Exception as e:
            print(f"[TREASURE ERROR] {e}")

        return "0"

    def parse_treasure_points(self, html):
        soup = BeautifulSoup(html, "html.parser")
        treasure_text = soup.find(text=re.compile(r"treasure potion", re.I))

        if treasure_text:
            parent = treasure_text.parent
            if parent:
                next_count = parent.find_next(class_=re.compile(r"intCount", re.I))
                if next_count:
                    value = self.clean_text(next_count.get_text())
                    if value.isdigit():
                        return value

        match = re.search(
            r"treasure potion.*?class=[\"']intCount[\"'][^>]*>(\d+)<",
            html,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            return match.group(1)

        match = re.search(r"treasure potion.*?(\d+)", html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)

        return "0"

    def clean_text(self, text):
        if not text:
            return "None"

        text = re.sub(r"\s+", " ", text).strip()
        return text if text else "None"

    def find_value(self, soup, label):
        text = soup.get_text("\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        for i, line in enumerate(lines):
            if line.lower().replace(":", "") == label.lower():
                if i + 1 < len(lines):
                    return self.clean_text(lines[i + 1])

        return "None"
    
    def find_linked_value_raw(self, html, label):
        pattern = (
            rf"<label>{re.escape(label)}:</label>\s*"
            rf"<a[^>]*href=['\"](.*?)['\"]>"
            rf"(.*?)</a>"
        )

        match = re.search(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            return "None"

        href = match.group(1).strip()
        name = self.clean_text(match.group(2))

        if (
            not href
            or href in [
                "http://aqwwiki.wikidot.com/",
                "https://aqwwiki.wikidot.com/"
            ]
            or not name
        ):
            return "None"

        # AQWiki URL formatting
        href = (
            href
            .replace(" ", "-")
            .replace("'", "-")
        )

        return f"[{name}](<{href}>)"


    def find_ccid(self, html, soup):
        # Look for a labeled Character ID field in the rendered page.
        match = re.search(
            r"Character\s*ID\s*[:\-]?\s*</?label>\s*([0-9]+)",
            html,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

        match = re.search(r"ccid\s*[:=]\s*['\"]?(\d+)['\"]?", html, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"[?&]ccid=(\d+)", html)
        if match:
            return match.group(1)

        # Fallback: try to extract the label text from the parsed HTML
        if soup:
            label = soup.find(lambda tag: tag.name in ["label", "span"] and "character id" in tag.get_text(strip=True).lower())
            if label:
                text = label.get_text(" ", strip=True)
                digits = re.search(r"(\d+)", text)
                if digits:
                    return digits.group(1)

        return None


    def parse_charpage(self, html):
        soup = BeautifulSoup(html, "html.parser")

        data = {}

        # Normal text fields
        data["level"] = self.find_value(soup, "Level")
        data["faction"] = self.find_value(soup, "Faction")
        data["guild"] = self.find_value(soup, "Guild")

        # Extract Title
        title_val = "None"
        h1 = soup.find("h1")
        if h1:
            h4 = h1.find_next_sibling("h4")
            if not h4:
                parent = h1.parent
                if parent:
                    h4 = parent.find("h4")
            if h4:
                em = h4.find("em")
                title_val = self.clean_text(em.get_text() if em else h4.get_text())
        data["title"] = title_val

        data["character_id"] = self.find_ccid(html, soup)

        # Linked item fields
        data["class"] = self.find_linked_value_raw(html, "Class")
        data["weapon"] = self.find_linked_value_raw(html, "Weapon")
        data["armor"] = self.find_linked_value_raw(html, "Armor")
        data["helm"] = self.find_linked_value_raw(html, "Helm")
        data["cape"] = self.find_linked_value_raw(html, "Cape")
        data["pet"] = self.find_linked_value_raw(html, "Pet")
        data["misc"] = self.find_linked_value_raw(html, "Misc")

        avatar = None
        img = soup.find(
            "img",
            src=re.compile("characters|avatar|profile|CharPage", re.I)
        )

        if img and img.get("src"):
            avatar = img["src"]

            if avatar.startswith("//"):
                avatar = "https:" + avatar
            elif avatar.startswith("/"):
                avatar = "https://account.aq.com" + avatar

        data["avatar"] = avatar

        return data

    @app_commands.command(
        name="charpage",
        description="Show AQW character information"
    )
    @app_commands.describe(
        ign="AQW in-game name"
    )
    async def charpage(self, interaction: discord.Interaction, ign: str):
        await interaction.response.defer()

        html, url = await self.fetch_charpage(ign)

        if not html:
            await interaction.followup.send(
                f"Could not find character page for `{ign}`."
            )
            return

        data = self.parse_charpage(html)
        if data["character_id"]:
            data["total_badges"] = await self.fetch_badge_count(
                data["character_id"]
            )
            data["treasure_points"] = await self.fetch_treasure_points(
                data["character_id"]
            )
        else:
            data["total_badges"] = "0"
            data["treasure_points"] = "0"

        embed = discord.Embed(
            title=f"{ign}'s char page {emojis.MELAYU_EMOJI_ALT}:",
            url=url,
            color=discord.Color.gold()
        )

        embed.add_field(name="🏆 Title:", value=data["title"], inline=True)
        embed.add_field(name=f"{emojis.EXP_BOOST}Level:", value=data["level"], inline=True)
        embed.add_field(name=f"{emojis.CLASS_ICON}Class:", value=data["class"], inline=True)
        embed.add_field(name=f"{emojis.SWORD_ICON}Weapon:", value=data["weapon"], inline=True)

        embed.add_field(name=f"{emojis.ARMOR_ICON}Armor:", value=data["armor"], inline=True)
        embed.add_field(name=f"{emojis.HELM_ICON}Helm:", value=data["helm"], inline=True)
        embed.add_field(name=f"{emojis.CAPE_ICON}Cape:", value=data["cape"], inline=True)

        embed.add_field(name=f"{emojis.PET_ICON}Pet:", value=data["pet"], inline=True)
        embed.add_field(name=f"{emojis.AC_ICON_2}Misc:", value=data["misc"], inline=True)
        # Faction emoji mapping
        faction_emojis = {
            "chaos": emojis.CHAOS_FACTION,
            "good": emojis.GOOD_FACTION,
            "evil": emojis.EVIL_FACTION,
            "neutral": emojis.NEUTRAL_FACTION
        }
        faction_val = data["faction"] or "None"
        faction_emoji = faction_emojis.get(faction_val.lower(), "")
        embed.add_field(name=f"{faction_emoji}Faction:", value=faction_val, inline=True)

        embed.add_field(name=f"{emojis.MEMBER_BOOST}Guild:", value=data["guild"], inline=True)
        embed.add_field(name=f"{emojis.CHARPAGE_ICON_2}Character ID:", value=data["character_id"] or "None", inline=True)

        embed.add_field(
            name=f"{emojis.CHARPAGE_ICON}Total Badges:",
            value=data["total_badges"],
            inline=True
        )
        embed.add_field(
            name=f"{emojis.TREASURE_POTION}Treasure Potions:",
            value=data["treasure_points"],
            inline=True
        )

        embed.set_thumbnail(
            url="https://imgur.com/ILiLVM7.png"
        )

        embed.set_author(
            name="AQW MELAYU",
            icon_url="https://imgur.com/ILiLVM7.png"
        )

        if data["avatar"]:
            embed.set_image(url=data["avatar"])

        embed.set_footer(text="AdventureQuest Worlds Character Page")

        await interaction.followup.send(embed=embed)


    @app_commands.command(
        name="badges",
        description="Show badge counts by AQW badge category"
    )
    @app_commands.describe(
        ign="AQW in-game name"
    )
    async def badges(self, interaction: discord.Interaction, ign: str):
        await interaction.response.defer()

        html, url = await self.fetch_charpage(ign)
        if not html:
            await interaction.followup.send(
                f"Could not find character page for `{ign}`."
            )
            return

        char_id = self.find_ccid(html, BeautifulSoup(html, "html.parser"))
        if not char_id:
            await interaction.followup.send(
                "Could not determine the character ID from the page."
            )
            return

        badges = await self.fetch_badges(char_id)
        if not badges:
            await interaction.followup.send(
                f"No badge data found for `{ign}`."
            )
            return

        category_counts = self.aggregate_badge_categories(badges)
        total = sum(count for _, count in category_counts)
        lines = [f"{name}\n{count} badges" for name, count in category_counts]

        embed = discord.Embed(
            title=f"Badge Count {ign}",
            url=url,
            color=discord.Color.gold()
        )
        embed.add_field(name="Total Badges", value=f"{total} badges total.", inline=False)
        embed.add_field(name="Categories", value="\n\n".join(lines), inline=False)

        embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
        embed.set_author(name="AQW MELAYU", icon_url="https://imgur.com/ILiLVM7.png")

        await interaction.followup.send(embed=embed)

    def simulate_spins(self, today: datetime.date, spins_needed: int, daily: bool) -> tuple[int, datetime.date]:
        if spins_needed <= 0:
            return 0, today
            
        current_spins = 0
        d = 0
        while True:
            current_date = today + datetime.timedelta(days=d)
            spins_today = 0
            
            # Daily spin
            if daily:
                spins_today += 1
                
            # Weekly spin on Wednesdays (weekday == 2 in Python)
            if current_date.weekday() == 2:
                spins_today += 1
                
            if spins_today > 0:
                current_spins += spins_today
                if current_spins >= spins_needed:
                    return d, current_date
            
            d += 1

    def generate_progress_bar(self, current: int, target: int = 1000, length: int = 10) -> str:
        pct = min(100.0, (current / target) * 100.0)
        filled = int(pct / (100 / length))
        filled = max(0, min(length, filled))
        bar = "▰" * filled + "▱" * (length - filled)
        return f"`[{bar}]` `{pct:.1f}%`"

    @app_commands.command(
        name="ioda",
        description="Calculate Wheel of Doom IoDA progression and estimates by IGN"
    )
    @app_commands.describe(
        ign="AQW in-game name"
    )
    async def ioda(self, interaction: discord.Interaction, ign: str):
        await interaction.response.defer()

        html, url = await self.fetch_charpage(ign)

        if not html:
            await interaction.followup.send(
                f"Could not find character page for `{ign}`."
            )
            return

        soup = BeautifulSoup(html, "html.parser")
        char_id = self.find_ccid(html, soup)
        
        if not char_id:
            await interaction.followup.send(
                f"Could not retrieve Character ID for `{ign}`."
            )
            return

        tp_str = await self.fetch_treasure_points(char_id)
        try:
            tp_current = int(tp_str)
        except ValueError:
            tp_current = 0

        tp_target = 1000
        tp_remaining = max(0, tp_target - tp_current)

        # Main progress bar (10 blocks)
        main_progress = self.generate_progress_bar(tp_current, tp_target, length=10)

        # Create beautiful Embed
        embed = discord.Embed(
            title=f"IoDA's Calculator {emojis.MELAYU_EMOJI_ALT}:",
            description=f"[{ign}](<{url}>) has `{tp_current}` Treasure Potions 🍖\n\n{main_progress}",
            color=discord.Color.gold()
        )
        embed.set_author(
            name="AQW MELAYU",
            icon_url="https://imgur.com/ILiLVM7.png"
        )
        embed.set_thumbnail(
            url="https://imgur.com/ILiLVM7.png"
        )
        embed.set_footer(
            text="Wheel of Doom IoDA Calculator | Powered by AQW Melayu",
            icon_url="https://imgur.com/ILiLVM7.png"
        )

        scenarios = [2, 6]
        today = datetime.date.today()

        for rate in scenarios:
            spins_needed = math.ceil(tp_remaining / rate)
            ac_cost = spins_needed * 200
            
            # Daily + Weekly simulation
            days_dw, date_dw = self.simulate_spins(today, spins_needed, daily=True)
            weeks_dw = days_dw / 7
            months_dw = days_dw // 30
            due_dw = f"{date_dw.day} {date_dw.strftime('%B')}, {date_dw.year}"
            
            # Weekly only simulation
            days_w, date_w = self.simulate_spins(today, spins_needed, daily=False)
            weeks_w = days_w / 7
            months_w = days_w // 30
            due_w = f"{date_w.day} {date_w.strftime('%B')}, {date_w.year}"

            field_name = f"`{rate} Treasure Potions per spin`"
            field_value = (
                f"__With {emojis.AC_ICON}s__\n"
                f"**Spins:** {spins_needed} ({ac_cost:,} {emojis.AC_ICON}s)\n\n"
                f"__With {emojis.MEMBER_BOOST} daily + weekly spins__\n"
                f"**Days:** {days_dw} ({weeks_dw:.1f} W/ {months_dw} M)\n"
                f"**Due:** `{due_dw}`\n\n"
                f"__With weekly spins only__\n"
                f"**Days:** {days_w} ({weeks_w:.1f} W/ {months_w} M)\n"
                f"**Due:** `{due_w}`"
            )
            
            embed.add_field(
                name=field_name,
                value=field_value,
                inline=True
            )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CharPage(bot))