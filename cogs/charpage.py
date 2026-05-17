import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import re


class CharPage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_charpage(self, ign: str):
        url = f"https://account.aq.com/CharPage?id={ign}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20) as response:
                if response.status != 200:
                    return None, url

                html = await response.text()

        return html, url

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


    def parse_charpage(self, html):
        soup = BeautifulSoup(html, "html.parser")

        data = {}

        # Normal text fields
        data["level"] = self.find_value(soup, "Level")
        data["faction"] = self.find_value(soup, "Faction")
        data["guild"] = self.find_value(soup, "Guild")

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

        embed = discord.Embed(
            title=f"{ign}'s char page <:Melayu:1505432584090423476>:",
            url=url,
            color=discord.Color.gold()
        )

        embed.add_field(name="Level:", value=data["level"], inline=True)
        embed.add_field(name="Class:", value=data["class"], inline=True)
        embed.add_field(name="Weapon:", value=data["weapon"], inline=True)

        embed.add_field(name="Armor:", value=data["armor"], inline=True)
        embed.add_field(name="Helm:", value=data["helm"], inline=True)
        embed.add_field(name="Cape:", value=data["cape"], inline=True)

        embed.add_field(name="Pet:", value=data["pet"], inline=True)
        embed.add_field(name="Misc:", value=data["misc"], inline=True)
        embed.add_field(name="Faction:", value=data["faction"], inline=True)

        embed.add_field(name="Guild:", value=data["guild"], inline=True)
        

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


async def setup(bot):
    await bot.add_cog(CharPage(bot))