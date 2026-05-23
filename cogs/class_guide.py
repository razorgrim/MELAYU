import discord
from discord import app_commands
from discord.ext import commands
from database import execute, fetchone, fetchall

class ClassDropdown(discord.ui.Select):
    def __init__(self, classes):
        options = [
            discord.SelectOption(
                label=cls["class_name"],
                description=f"View guide for {cls['class_name']}",
                emoji="⚔️"
            )
            for cls in classes[:25] # Select menus can have max 25 options
        ]
        super().__init__(
            placeholder="Choose a class guide to view...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="class_guide_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        class_name = self.values[0]
        
        # Query details
        guild_id = interaction.guild.id
        row = await fetchone(
            """
            SELECT * FROM class_guides
            WHERE guild_id = %s AND class_name = %s
            """,
            (guild_id, class_name)
        )
        
        if not row:
            await interaction.followup.send("❌ Error: Class guide not found.", ephemeral=True)
            return

        embed = ClassGuide.generate_guide_embed(row, interaction.guild)
        await interaction.followup.send(embed=embed, ephemeral=True)


class ClassDropdownView(discord.ui.View):
    def __init__(self, classes):
        super().__init__(timeout=None) # Persistent-like static menu (can be rendered dynamically)
        self.add_item(ClassDropdown(classes))


class ClassGuide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Auto-create the class_guides SQL table on startup
        await execute(
            """
            CREATE TABLE IF NOT EXISTS `class_guides` (
                `guild_id` bigint(20) NOT NULL,
                `class_name` varchar(100) NOT NULL,
                `note` text DEFAULT NULL,
                `enchant_non_forge` text DEFAULT NULL,
                `enchant_solo` text DEFAULT NULL,
                `enchant_ultra` text DEFAULT NULL,
                `potion` text DEFAULT NULL,
                `combo` text DEFAULT NULL,
                PRIMARY KEY (`guild_id`, `class_name`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )
        print("[DATABASE] Verified class_guides SQL table schema")

    @staticmethod
    def generate_guide_embed(row, guild) -> discord.Embed:
        class_name = row["class_name"]
        
        embed = discord.Embed(
            title=f"⚔️ AQW Class Guide: **{class_name}**",
            description=f"Detailed specifications and setups for **{class_name}**.",
            color=discord.Color.gold()
        )
        
        # Note / Description
        note = row["note"] or "No notes provided."
        embed.add_field(name="📝 Note / Description", value=f"```\n{note}\n```", inline=False)
        
        # Enchantments
        enchant_text = (
            f"1. **Non-Forge Setup:**\n└─ `{row['enchant_non_forge'] or 'N/A'}`\n\n"
            f"2. **Solo Setup:**\n└─ `{row['enchant_solo'] or 'N/A'}`\n\n"
            f"3. **Ultra Boss Setup:**\n└─ `{row['enchant_ultra'] or 'N/A'}`"
        )
        embed.add_field(name="🛡️ Enchantments Configuration", value=enchant_text, inline=False)
        
        # Potion
        potion = row["potion"] or "N/A"
        embed.add_field(name="🧪 Recommended Potions", value=f"`{potion}`", inline=True)
        
        # Combo
        combo = row["combo"] or "N/A"
        embed.add_field(name="🔄 Attack Rotation Combo", value=f"```\n{combo}\n```", inline=False)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            embed.set_author(name=f"{guild.name} Library", icon_url=guild.icon.url)
            
        embed.set_footer(text="AQW MELAYU Library • Select dropdown or slash command to search")
        return embed

    # --- SLASH COMMANDS ---

    @app_commands.command(
        name="class_add",
        description="Add or overwrite a class guide (Officer Only)"
    )
    @app_commands.describe(
        class_name="AQW Class Name (e.g., ArchPaladin, Legion DoomKnight)",
        note="General notes or class description",
        enchant_non_forge="Default non-forge enhancement configuration",
        enchant_solo="Recommended solo enhancement",
        enchant_ultra="Recommended ultra enhancement",
        potion="Best potions to use",
        combo="Combos or rotation sequence"
    )
    async def class_add(
        self,
        interaction: discord.Interaction,
        class_name: str,
        note: str,
        enchant_non_forge: str,
        enchant_solo: str,
        enchant_ultra: str,
        potion: str,
        combo: str
    ):
        # 1. Authorize Officer status
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Faction Officers or Administrators can write class guides.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        class_name_clean = class_name.strip()

        # 2. Insert or update guide (overwrite if duplicate)
        await execute(
            """
            INSERT INTO class_guides
            (
                guild_id,
                class_name,
                note,
                enchant_non_forge,
                enchant_solo,
                enchant_ultra,
                potion,
                combo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                note = VALUES(note),
                enchant_non_forge = VALUES(enchant_non_forge),
                enchant_solo = VALUES(enchant_solo),
                enchant_ultra = VALUES(enchant_ultra),
                potion = VALUES(potion),
                combo = VALUES(combo)
            """,
            (
                guild_id,
                class_name_clean,
                note,
                enchant_non_forge,
                enchant_solo,
                enchant_ultra,
                potion,
                combo
            )
        )

        await interaction.response.send_message(
            f"✅ **AQW Class Guide Registered!**\n"
            f"Successfully recorded specifications for **{class_name_clean}**. "
            f"If it existed before, the old data was overwritten.",
            ephemeral=True
        )

    @app_commands.command(
        name="class_guide",
        description="Search and view an AQW class guide"
    )
    @app_commands.describe(
        class_name="Name of the class to search"
    )
    async def class_guide(self, interaction: discord.Interaction, class_name: str):
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        row = await fetchone(
            """
            SELECT * FROM class_guides
            WHERE guild_id = %s AND class_name = %s
            """,
            (guild_id, class_name)
        )

        if not row:
            await interaction.followup.send(
                f"❌ Class guide for `{class_name}` not found in library.\n"
                f"Officers can add new setups using the `/class_add` command."
            )
            return

        embed = self.generate_guide_embed(row, interaction.guild)
        await interaction.followup.send(embed=embed)

    @class_guide.autocomplete("class_name")
    async def class_guide_autocomplete(self, interaction: discord.Interaction, current: str):
        # Case-insensitive autocomplete search capability query
        try:
            guild_id = interaction.guild.id
            query = """
                SELECT class_name FROM class_guides
                WHERE guild_id = %s AND class_name LIKE %s
                LIMIT 25
            """
            rows = await fetchall(query, (guild_id, f"%{current}%"))
            return [
                app_commands.Choice(name=row["class_name"], value=row["class_name"])
                for row in rows
            ]
        except Exception:
            return []

    @app_commands.command(
        name="class_panel",
        description="Post the interactive AQW Class Guide dropdown panel (Officer Only)"
    )
    @app_commands.describe(
        channel="Optional channel to send the panel in"
    )
    async def class_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        # 1. Authorize Officer status
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Faction Officers or Administrators can configure the library panel.",
                ephemeral=True
            )
            return

        target_channel = channel or interaction.channel
        guild_id = interaction.guild.id

        # 2. Query classes
        classes = await fetchall(
            "SELECT class_name FROM class_guides WHERE guild_id = %s ORDER BY class_name ASC",
            (guild_id,)
        )

        if not classes:
            await interaction.response.send_message(
                "❌ Cannot create panel because there are no class guides stored yet!\n"
                "Please add some classes first using `/class_add`.",
                ephemeral=True
            )
            return

        # 3. Build panel embed and view
        embed = discord.Embed(
            title="⚔️ AQW Class Setup Library",
            description=(
                "Welcome to the official **AQW Class Setup Library**!\n\n"
                "Gunakan menu di bawah untuk select and view class guides, enchants, and attack rotations.\n\n"
                "📌 **Categories in Guide:**\n"
                "• **Note:** Description and usage tips\n"
                "• **Enchantments:** 3 Types (Non-Forge, Solo, and Ultra)\n"
                "• **Potions:** Best elixirs and tonics\n"
                "• **Combo:** Recommended skill sequence rotations\n\n"
                "*(Note: You can also search guides case-insensitively using `/class_guide`!)*"
            ),
            color=discord.Color.gold()
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_footer(text=f"{interaction.guild.name} Library Panel", icon_url=interaction.guild.icon.url)

        view = ClassDropdownView(classes)
        await target_channel.send(embed=embed, view=view)
        
        await interaction.response.send_message(
            f"✅ Class Setup Library panel has been posted in {target_channel.mention}!",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ClassGuide(bot))
