import os
import json
import time
import requests
import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from discord import app_commands


DATA_FILE = "data/verified_users.json"
CONFIG_FILE = "data/verification_config.json"
COOLDOWN_SECONDS = 7200


def ensure_data_folder():
    os.makedirs("data", exist_ok=True)


def load_json(file_path):
    ensure_data_folder()

    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump({}, file, indent=4)

    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except:
        return {}


def save_json(file_path, data):
    ensure_data_folder()

    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def load_data():
    return load_json(DATA_FILE)


def save_data(data):
    save_json(DATA_FILE, data)


def load_config():
    return load_json(CONFIG_FILE)


def save_config(config):
    save_json(CONFIG_FILE, config)


def check_aqw_character(ign: str, target_guild_name: str):
    url = f"https://account.aq.com/CharPage?id={ign}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException:
        return {
            "found": False,
            "in_target_guild": False,
            "page_ign": None,
            "guild": None,
            "message": "Could not connect to AQW character page."
        }

    if response.status_code != 200:
        return {
            "found": False,
            "in_target_guild": False,
            "page_ign": None,
            "guild": None,
            "message": "Character page not found."
        }

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    title = soup.find("h1")

    if not title:
        return {
            "found": False,
            "in_target_guild": False,
            "page_ign": None,
            "guild": None,
            "message": "Could not read character name."
        }

    page_ign = title.get_text(strip=True)

    if page_ign.lower() != ign.lower():
        return {
            "found": False,
            "in_target_guild": False,
            "page_ign": page_ign,
            "guild": None,
            "message": "IGN does not exactly match the AQW character page."
        }

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

    in_target_guild = False

    if guild_value:
        in_target_guild = guild_value.upper() == target_guild_name.upper()

    return {
        "found": True,
        "in_target_guild": in_target_guild,
        "page_ign": page_ign,
        "guild": guild_value,
        "message": "Character checked successfully."
    }


class VerifyModal(discord.ui.Modal, title="AQW Verification"):
    ign = discord.ui.TextInput(
        label="AdventureQuest Worlds IGN",
        placeholder="Enter your AQW character name",
        required=True,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        ign = self.ign.value.strip()

        config = load_config()

        if guild_id not in config:
            await interaction.followup.send(
                "❌ Verification is not set up for this server yet.\n"
                "Ask an admin to use `/verification_setup` first.",
                ephemeral=True
            )
            return

        server_config = config[guild_id]

        target_guild_name = server_config["aqw_guild_name"]
        adventure_role_id = server_config["adventure_role_id"]
        member_role_id = server_config["member_role_id"]

        adventure_role = interaction.guild.get_role(adventure_role_id)
        member_role = interaction.guild.get_role(member_role_id)

        if adventure_role is None:
            await interaction.followup.send(
                "❌ Adventure role not found. Ask admin to run `/verification_setup` again.",
                ephemeral=True
            )
            return

        if member_role is None:
            await interaction.followup.send(
                "❌ Guild member role not found. Ask admin to run `/verification_setup` again.",
                ephemeral=True
            )
            return

        data = load_data()

        if guild_id not in data:
            data[guild_id] = {}

        now = time.time()

        if user_id in data[guild_id]:
            last_verified = data[guild_id][user_id]["time"]

            if now - last_verified < COOLDOWN_SECONDS:
                remaining_seconds = int(COOLDOWN_SECONDS - (now - last_verified))
                remaining_minutes = remaining_seconds // 60

                await interaction.followup.send(
                    f"⏳ You already verified recently.\n"
                    f"Try again in `{remaining_minutes}` minutes.",
                    ephemeral=True
                )
                return

        for uid, info in data[guild_id].items():
            if info["ign"].lower() == ign.lower() and uid != user_id:
                await interaction.followup.send(
                    f"❌ IGN `{ign}` is already claimed by another Discord user in this server.",
                    ephemeral=True
                )
                return

        result = check_aqw_character(ign, target_guild_name)

        if not result["found"]:
            await interaction.followup.send(
                f"❌ Verification failed.\n{result['message']}",
                ephemeral=True
            )
            return

        try:
            roles_given = []

            if adventure_role not in interaction.user.roles:
                await interaction.user.add_roles(adventure_role)
                roles_given.append(adventure_role.mention)

            if result["in_target_guild"]:
                if member_role not in interaction.user.roles:
                    await interaction.user.add_roles(member_role)
                    roles_given.append(member_role.mention)

            data[guild_id][user_id] = {
                "ign": result["page_ign"],
                "guild": result["guild"],
                "in_target_guild": result["in_target_guild"],
                "time": now
            }

            save_data(data)

            if result["in_target_guild"]:
                message = (
                    f"✅ Verification successful!\n\n"
                    f"IGN: `{result['page_ign']}`\n"
                    f"AQW Guild: `{result['guild']}`\n\n"
                    f"You received:\n"
                    f"• {adventure_role.mention}\n"
                    f"• {member_role.mention}"
                )
            else:
                guild_text = result["guild"] if result["guild"] else "No guild"

                message = (
                    f"✅ Character verified as AQW player.\n\n"
                    f"IGN: `{result['page_ign']}`\n"
                    f"AQW Guild: `{guild_text}`\n\n"
                    f"You are not in `{target_guild_name}`, so you received only:\n"
                    f"• {adventure_role.mention}"
                )

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I cannot give the role. Move my bot role above the roles I need to assign.",
                ephemeral=True
            )


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify AQW Character",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="verify_aqw_button"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(VerifyModal())


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerifyView())

    @app_commands.command(
        name="verification_setup",
        description="Set up AQW verification roles for this server"
    )
    @app_commands.describe(
        aqw_guild_name="AQW guild name to check, example: M E L A Y U",
        adventure_role="Role for all verified AQW players",
        member_role="Role for users inside the target AQW guild",
        image_url="Optional image URL for the verification panel"
    )
    async def verification_setup(
        self,
        interaction: discord.Interaction,
        aqw_guild_name: str,
        adventure_role: discord.Role,
        member_role: discord.Role,
        image_url: str = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can use this command.",
                ephemeral=True
            )
            return

        config = load_config()
        guild_id = str(interaction.guild.id)

        config[guild_id] = {
            "aqw_guild_name": aqw_guild_name,
            "adventure_role_id": adventure_role.id,
            "member_role_id": member_role.id,
            "image_url": image_url
        }

        save_config(config)

        await interaction.response.send_message(
            f"✅ Verification setup completed.\n\n"
            f"AQW Guild: `{aqw_guild_name}`\n"
            f"Adventure Role: {adventure_role.mention}\n"
            f"Guild Member Role: {member_role.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="verification",
        description="Send the AQW verification panel"
    )
    async def verification(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can use this command.",
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)
        config = load_config()

        if guild_id not in config:
            await interaction.response.send_message(
                "❌ Verification is not set up yet.\n\n"
                "Use:\n"
                "`/verification_setup aqw_guild_name:<guild> adventure_role:<role> member_role:<role>`",
                ephemeral=True
            )
            return

        server_config = config[guild_id]

        aqw_guild_name = server_config["aqw_guild_name"]
        adventure_role = interaction.guild.get_role(server_config["adventure_role_id"])
        member_role = interaction.guild.get_role(server_config["member_role_id"])
        image_url = server_config.get("image_url")

        embed = discord.Embed(
            title="AQW Guild Verification",
            description=(
                "Click the button below to verify your AdventureQuest Worlds character.\n\n"
                "**How it works:**\n"
                f"• All valid AQW players receive {adventure_role.mention if adventure_role else '`Adventure Role`'}\n"
                f"• Players inside **{aqw_guild_name}** also receive {member_role.mention if member_role else '`Guild Member Role`'}\n\n"
                "**Requirement:**\n"
                "Your AQW character page must be public and accessible."
            ),
            color=discord.Color.green()
        )

        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")

        embed.set_footer(text="AQW Verification System")

        await interaction.response.send_message(
            embed=embed,
            view=VerifyView()
        )


async def setup(bot):
    await bot.add_cog(Verification(bot))