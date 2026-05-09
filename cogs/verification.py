import os
import json
import time
import requests
import discord
from bs4 import BeautifulSoup
from discord.ext import commands

ROLE_NAME = "MELAYU member"
AQW_GUILD_NAME = "M E L A Y U"

DATA_FILE = "data/verified_users.json"
COOLDOWN_SECONDS = 7200


def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def check_aqw_guild(ign: str):
    url = f"https://account.aq.com/CharPage?id={ign}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return False, "Could not connect to AQW character page."

    if response.status_code != 200:
        return False, "Character page not found."

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    title = soup.find("h1")
    if not title:
        return False, "Could not read character name."

    page_ign = title.get_text(strip=True)

    if page_ign.lower() != ign.lower():
        return False, "IGN does not exactly match the AQW character page."

    guild_value = None
    lines = text.split("\n")

    for i, line in enumerate(lines):
        clean_line = line.strip().lower()

        if clean_line == "guild:":
            if i + 1 < len(lines):
                guild_value = lines[i + 1].strip()
            break

        if clean_line.startswith("guild:"):
            guild_value = line.split(":", 1)[1].strip()
            break

    if not guild_value:
        return False, "No guild found on this character page."

    if guild_value.upper() != AQW_GUILD_NAME.upper():
        return False, f"Your guild is `{guild_value}`, not `{AQW_GUILD_NAME}`."

    return True, f"IGN `{page_ign}` is verified in guild `{guild_value}`."


class VerifyModal(discord.ui.Modal, title="AQW Guild Verification"):
    ign = discord.ui.TextInput(
        label="AdventureQuest Worlds IGN",
        placeholder="Enter your AQW character name",
        required=True,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ign = self.ign.value.strip()
        user_id = str(interaction.user.id)

        data = load_data()
        now = time.time()

        if user_id in data:
            last_verified = data[user_id]["time"]

            if now - last_verified < COOLDOWN_SECONDS:
                remaining_seconds = int(COOLDOWN_SECONDS - (now - last_verified))
                remaining_minutes = remaining_seconds // 60

                await interaction.followup.send(
                    f"⏳ You already verified recently.\n"
                    f"Try again in `{remaining_minutes}` minutes.",
                    ephemeral=True
                )
                return

        for uid, info in data.items():
            if info["ign"].lower() == ign.lower() and uid != user_id:
                await interaction.followup.send(
                    f"❌ IGN `{ign}` is already claimed by another Discord user.",
                    ephemeral=True
                )
                return

        success, message = check_aqw_guild(ign)

        if not success:
            await interaction.followup.send(
                f"❌ Verification failed.\n{message}",
                ephemeral=True
            )
            return

        role = discord.utils.get(interaction.guild.roles, name=ROLE_NAME)

        if role is None:
            await interaction.followup.send(
                f"❌ Role `{ROLE_NAME}` does not exist.",
                ephemeral=True
            )
            return

        try:
            if role not in interaction.user.roles:
                await interaction.user.add_roles(role)

            data[user_id] = {
                "ign": ign,
                "time": now
            }

            save_data(data)

            await interaction.followup.send(
                f"✅ Verification successful!\n"
                f"{message}\n\n"
                f"You have received the `{ROLE_NAME}` role.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I cannot give the role. Move my bot role above the MELAYU member role.",
                ephemeral=True
            )


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify AQW Guild",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="verify_aqw_button"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerifyView())

    @discord.app_commands.command(
        name="verification",
        description="Send the AQW guild verification panel"
    )
    async def verification(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can use this command.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="AQW MELAYU Guild Verification",
            description=(
                "Klik butang bawah untuk verify korang punya AdventureQuest Worlds character.\n\n"
                "**Requirement:**\n"
                "AQW character must be in the guild **M E L A Y U**.\n\n"
                "After successful verification, korang akan dapat **MELAYU member** role."
            ),
            color=discord.Color.green()
        )

        embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")
        embed.set_footer(text="MELAYU Guild Verification System")

        await interaction.response.send_message(embed=embed, view=VerifyView())


async def setup(bot):
    await bot.add_cog(Verification(bot))