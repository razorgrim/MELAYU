import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import re
import aiohttp
from urllib.parse import quote_plus


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
            rf"<a[^>]*href='(.*?)'>"
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
            title=f"{ign}'s char page <:Melayu:1505432584090423476>:",
            url=url,
            color=discord.Color.gold()
        )

        embed.add_field(name="<:XPBoost:1505372494922780753>Level:", value=data["level"], inline=True)
        embed.add_field(name="<:classicon:1506184256894926898>Class:", value=data["class"], inline=True)
        embed.add_field(name="<:swordicon:1506182453398601749>Weapon:", value=data["weapon"], inline=True)

        embed.add_field(name="<:armoricon:1506182318765641738>Armor:", value=data["armor"], inline=True)
        embed.add_field(name="<:helmicon:1506182631887339560>Helm:", value=data["helm"], inline=True)
        embed.add_field(name="<:capeicon:1506183156024344687>Cape:", value=data["cape"], inline=True)

        embed.add_field(name="<:peticon:1506318442590896230>Pet:", value=data["pet"], inline=True)
        embed.add_field(name="<:acicon2:1506190761543340072>Misc:", value=data["misc"], inline=True)
        # Faction emoji mapping
        faction_emojis = {
            "chaos": "<:chaosfaction:1506322127819767948>",
            "good": "<:goodfaction:1506321915114160128>",
            "evil": "<:evilfaction:1506322000652796104>",
            "neutral": "<:neutralfaction:1506322065668440106>"
        }
        faction_val = data["faction"] or "None"
        faction_emoji = faction_emojis.get(faction_val.lower(), "")
        embed.add_field(name=f"{faction_emoji}Faction:", value=faction_val, inline=True)

        embed.add_field(name="<:Member:1505373039267680457>Guild:", value=data["guild"], inline=True)
        embed.add_field(name="<:charpageicon2:1506324684092866591>Character ID:", value=data["character_id"] or "None", inline=True)

        embed.add_field(
            name="<:charpageicon:1506324498943840366>Total Badges:",
            value=data["total_badges"],
            inline=True
        )
        embed.add_field(
            name="<:treasurepotionicon:1506323420906782912>Treasure Potions:",
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


async def setup(bot):
    await bot.add_cog(CharPage(bot))