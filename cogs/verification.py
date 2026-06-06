import time
import discord
import aiohttp
from bs4 import BeautifulSoup
from discord.ext import commands
from discord import app_commands
from database import execute, fetchone
import emojis
import panel_config

COOLDOWN_SECONDS = 7200

async def check_aqw_character(ign: str, target_guild_name: str):
    url = f"https://account.aq.com/CharPage?id={ign}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return {
                        "found": False,
                        "in_target_guild": False,
                        "page_ign": None,
                        "guild": None,
                        "message": "Character page not found."
                    }
                html_text = await response.text()
    except Exception:
        return {
            "found": False,
            "in_target_guild": False,
            "page_ign": None,
            "guild": None,
            "message": "Could not connect to AQW character page."
        }

    soup = BeautifulSoup(html_text, "html.parser")
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


async def perform_verification(interaction: discord.Interaction, nickname: str, ign: str, nationality: str):
    guild_id = interaction.guild.id
    user_id = interaction.user.id

    # Get server config from MySQL
    server_config = await fetchone(
        """
        SELECT * FROM verification_config
        WHERE guild_id = %s
        """,
        (guild_id,)
    )

    if not server_config:
        await interaction.followup.send(
            "❌ Verification is not set up for this server yet.\n"
            "Ask an admin to use `/verification_setup` first.",
            ephemeral=True
        )
        return

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

    # Check existing verified user
    existing_user = await fetchone(
        """
        SELECT * FROM verified_users
        WHERE guild_id = %s AND user_id = %s
        """,
        (guild_id, user_id)
    )

    now = time.time()

    if existing_user:
        last_verified = existing_user["verified_at"].timestamp()

        if now - last_verified < COOLDOWN_SECONDS:
            remaining_seconds = int(
                COOLDOWN_SECONDS - (now - last_verified)
            )

            remaining_minutes = remaining_seconds // 60

            await interaction.followup.send(
                f"⏳ You already verified recently.\n"
                f"Try again in `{remaining_minutes}` minutes.",
                ephemeral=True
            )
            return

    # Check duplicate IGN
    existing_ign = await fetchone(
        """
        SELECT * FROM verified_users
        WHERE guild_id = %s
        AND ign = %s
        AND user_id != %s
        """,
        (
            guild_id,
            ign,
            user_id
        )
    )

    if existing_ign:
        await interaction.followup.send(
            f"❌ IGN `{ign}` is already claimed by another Discord user in this server.",
            ephemeral=True
        )
        return

    result = await check_aqw_character(
        ign,
        target_guild_name
    )

    if not result["found"]:
        await interaction.followup.send(
            f"❌ Verification failed.\n{result['message']}",
            ephemeral=True
        )
        return

    try:

        if adventure_role not in interaction.user.roles:
            await interaction.user.add_roles(adventure_role)

        if result["in_target_guild"]:
            if member_role not in interaction.user.roles:
                await interaction.user.add_roles(member_role)

        # Nickname format: "nickname ● ign ● Nationality"
        new_nickname = f"{nickname} ● {result['page_ign']} ● {nationality}"

        if len(new_nickname) > 32:
            new_nickname = new_nickname[:32]

        nickname_changed = True

        try:
            await interaction.user.edit(
                nick=new_nickname
            )

        except discord.Forbidden:
            nickname_changed = False

        # Save to MySQL
        await execute(
            """
            INSERT INTO verified_users
            (
                guild_id,
                user_id,
                nickname,
                ign,
                discord_nickname,
                aqw_guild,
                in_target_guild
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)

            ON DUPLICATE KEY UPDATE
                nickname = VALUES(nickname),
                ign = VALUES(ign),
                discord_nickname = VALUES(discord_nickname),
                aqw_guild = VALUES(aqw_guild),
                in_target_guild = VALUES(in_target_guild),
                verified_at = CURRENT_TIMESTAMP
            """,
            (
                guild_id,
                user_id,
                nickname,
                result["page_ign"],
                new_nickname,
                result["guild"],
                result["in_target_guild"]
            )
        )

        if result["in_target_guild"]:

            message = (
                f"✅ Verification successful!\n\n"
                f"Name: `{nickname}`\n"
                f"IGN: `{result['page_ign']}`\n"
                f"AQW Guild: `{result['guild']}`\n"
                f"Nationality: `{nationality}`\n\n"
                f"You received:\n"
                f"• {adventure_role.mention}\n"
                f"• {member_role.mention}"
            )

        else:

            guild_text = (
                result["guild"]
                if result["guild"]
                else "No guild"
            )

            message = (
                f"✅ Character verified as AQW player.\n\n"
                f"Name: `{nickname}`\n"
                f"IGN: `{result['page_ign']}`\n"
                f"AQW Guild: `{guild_text}`\n"
                f"Nationality: `{nationality}`\n\n"
                f"You are not in `{target_guild_name}`, so you received only:\n"
                f"• {adventure_role.mention}"
            )

        if nickname_changed:
            message += (
                f"\n\nNickname changed to:\n"
                f"`{new_nickname}`"
            )

        else:
            message += (
                "\n\n⚠️ I could not change your nickname. "
                "Please make sure my bot role is above your role."
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


class VerifyPredefinedModal(discord.ui.Modal):
    nickname = discord.ui.TextInput(
        label="Your nickname / name",
        placeholder="Example: Danish",
        required=True,
        max_length=24
    )

    ign = discord.ui.TextInput(
        label="AdventureQuest Worlds IGN",
        placeholder="Enter your AQW character name",
        required=True,
        max_length=32
    )

    def __init__(self, nationality: str):
        super().__init__(title=f"AQW Verification ({nationality})")
        self.nationality = nationality

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        nickname_val = self.nickname.value.strip()
        ign_val = self.ign.value.strip()
        await perform_verification(interaction, nickname_val, ign_val, self.nationality)


class VerifyOthersModal(discord.ui.Modal, title="AQW Verification"):
    nickname = discord.ui.TextInput(
        label="Your nickname / name",
        placeholder="Example: Danish",
        required=True,
        max_length=24
    )

    ign = discord.ui.TextInput(
        label="AdventureQuest Worlds IGN",
        placeholder="Enter your AQW character name",
        required=True,
        max_length=32
    )

    nationality = discord.ui.TextInput(
        label="Your Nationality / Country",
        placeholder="Example: TH, VN, US, etc.",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        nickname_val = self.nickname.value.strip()
        ign_val = self.ign.value.strip()
        nationality_val = self.nationality.value.strip().upper()
        await perform_verification(interaction, nickname_val, ign_val, nationality_val)


class NationalitySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Malaysia (MY)", value="MY", emoji="🇲🇾"),
            discord.SelectOption(label="Indonesia (ID)", value="ID", emoji="🇮🇩"),
            discord.SelectOption(label="Philippines (PH)", value="PH", emoji="🇵🇭"),
            discord.SelectOption(label="Singapore (SG)", value="SG", emoji="🇸🇬"),
            discord.SelectOption(label="Others (Specify in form)", value="Others", emoji="🌐")
        ]
        super().__init__(
            placeholder="Select your nationality...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "Others":
            await interaction.response.send_modal(VerifyOthersModal())
        else:
            await interaction.response.send_modal(VerifyPredefinedModal(nationality=val))


class NationalitySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(NationalitySelect())


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
        view = NationalitySelectView()
        await interaction.response.send_message(
            "📋 **AQW Character Verification**\nPlease select your nationality from the dropdown below to start verification:",
            view=view,
            ephemeral=True
        )


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

        guild_id = interaction.guild.id

        await execute(
            """
            INSERT INTO verification_config
            (
                guild_id,
                aqw_guild_name,
                adventure_role_id,
                member_role_id,
                image_url
            )
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                aqw_guild_name = VALUES(aqw_guild_name),
                adventure_role_id = VALUES(adventure_role_id),
                member_role_id = VALUES(member_role_id),
                image_url = VALUES(image_url)
            """,
            (
                guild_id,
                aqw_guild_name,
                adventure_role.id,
                member_role.id,
                image_url
            )
        )

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

        guild_id = interaction.guild.id

        server_config = await fetchone(
            """
            SELECT * FROM verification_config
            WHERE guild_id = %s
            """,
            (guild_id,)
        )

        if not server_config:
            await interaction.response.send_message(
                "❌ Verification is not set up yet.\n\n"
                "Use:\n"
                "`/verification_setup aqw_guild_name:<guild> adventure_role:<role> member_role:<role>`",
                ephemeral=True
            )
            return

        aqw_guild_name = server_config["aqw_guild_name"]
        adventure_role = interaction.guild.get_role(server_config["adventure_role_id"])
        member_role = interaction.guild.get_role(server_config["member_role_id"])
        image_url = server_config.get("image_url")

        description_text = panel_config.VERIFICATION_DESCRIPTION_TEMPLATE.format(
            adventure_role_mention=adventure_role.mention if adventure_role else '`Adventure Role`',
            member_role_mention=member_role.mention if member_role else '`Guild Member Role`',
            aqw_guild_name=aqw_guild_name
        )

        embed = discord.Embed(
            title=panel_config.VERIFICATION_TITLE,
            description=description_text,
            color=discord.Color(panel_config.VERIFICATION_COLOR)
        )

        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.set_image(url=panel_config.VERIFICATION_DEFAULT_IMAGE)

        embed.set_footer(text=panel_config.VERIFICATION_FOOTER)

        await interaction.response.send_message(
            embed=embed,
            view=VerifyView()
        )


async def setup(bot):
    await bot.add_cog(Verification(bot))