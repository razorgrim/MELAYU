import discord
from discord import app_commands
from discord.ext import commands
from bs4 import BeautifulSoup
import re
import aiohttp
from urllib.parse import quote_plus
import emojis

class InventoryPaginationView(discord.ui.View):
    def __init__(self, author_id, pages, embed_title, embed_url, ign, type_name):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.pages = pages
        self.current_page = 0
        self.embed_title = embed_title
        self.embed_url = embed_url
        self.ign = ign
        self.type_name = type_name
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    def make_embed(self):
        page_items = self.pages[self.current_page]
        description = "\n".join(page_items)
        
        embed = discord.Embed(
            title=self.embed_title,
            url=self.embed_url,
            description=description,
            color=discord.Color.gold()
        )
        embed.set_author(name="AQW MELAYU", icon_url="https://imgur.com/ILiLVM7.png")
        embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)} | {self.ign}'s {self.type_name}s")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

class CheckInv(commands.Cog):
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

    async def fetch_inventory(self, character_id):
        url = f"https://account.aq.com/CharPage/Inventory?ccid={character_id}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        return []

                    inventory = await response.json()
                    if isinstance(inventory, list):
                        return inventory
                    return []
        except Exception as e:
            print(f"[INVENTORY ERROR] {e}")

        return []

    def get_class_rank(self, points: int) -> int:
        thresholds = [0, 900, 3600, 9900, 20700, 37800, 61200, 91800, 129600, 174600]
        for rank, req in enumerate(thresholds, start=1):
            if points < req:
                return rank - 1
        return 10

    @app_commands.command(
        name="checkinv",
        description="Show all classes or items in a player's AQW inventory"
    )
    @app_commands.describe(
        ign="AQW in-game name",
        type="The inventory category to list"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Class", value="class"),
        app_commands.Choice(name="Item", value="item")
    ])
    async def checkinv(self, interaction: discord.Interaction, ign: str, type: str):
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

        h1 = soup.find("h1")
        page_ign = h1.get_text(strip=True) if h1 else ign

        inventory = await self.fetch_inventory(char_id)
        if not inventory:
            await interaction.followup.send(
                f"No inventory data found for `{page_ign}`."
            )
            return

        # Filter and format items
        formatted_lines = []
        
        if type == "class":
            classes = [item for item in inventory if item.get("strType", "").lower() == "class"]
            # Sort classes alphabetically by name
            classes.sort(key=lambda x: x.get("strName", "").lower())
            
            for item in classes:
                name = item.get("strName", "Unknown Class")
                points = item.get("intCount", 0)
                rank = self.get_class_rank(points)
                formatted_lines.append(
                    f"{emojis.CLASS_ICON} **{name}** (Rank {rank} | {points:,} CP)"
                )
        else:
            items = [item for item in inventory if item.get("strType", "").lower() == "item"]
            # Sort items alphabetically by name
            items.sort(key=lambda x: x.get("strName", "").lower())
            
            for item in items:
                name = item.get("strName", "Unknown Item")
                count = item.get("intCount", 1)
                formatted_lines.append(
                    f"{emojis.BAG_ICON_ALT} **{name}** (x{count})"
                )

        embed_title = f"{page_ign}'s Inventory: {type.capitalize()}es" if type == "class" else f"{page_ign}'s Inventory: {type.capitalize()}s"

        if not formatted_lines:
            embed = discord.Embed(
                title=embed_title,
                url=url,
                description=f"No {type}s found in {page_ign}'s inventory.",
                color=discord.Color.red()
            )
            embed.set_author(name="AQW MELAYU", icon_url="https://imgur.com/ILiLVM7.png")
            embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
            await interaction.followup.send(embed=embed)
            return

        # Paginate results (15 items per page)
        items_per_page = 15
        pages = [formatted_lines[i:i + items_per_page] for i in range(0, len(formatted_lines), items_per_page)]

        # Send page 1
        description = "\n".join(pages[0])
        embed = discord.Embed(
            title=embed_title,
            url=url,
            description=description,
            color=discord.Color.gold()
        )
        embed.set_author(name="AQW MELAYU", icon_url="https://imgur.com/ILiLVM7.png")
        embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
        embed.set_footer(text=f"Page 1 of {len(pages)} | {page_ign}'s {type.capitalize()}s")

        if len(pages) <= 1:
            await interaction.followup.send(embed=embed)
        else:
            view = InventoryPaginationView(interaction.user.id, pages, embed_title, url, page_ign, type.capitalize())
            await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(CheckInv(bot))
