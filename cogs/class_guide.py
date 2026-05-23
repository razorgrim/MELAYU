import discord
from discord import app_commands
from discord.ext import commands
from database import execute, fetchone, fetchall
import re

class ClassDropdown(discord.ui.Select):
    def __init__(self, classes, page=0, total_pages=1):
        options = [
            discord.SelectOption(
                label=cls["class_name"],
                description=f"View guide for {cls['class_name']}",
                emoji="⚔️"
            )
            for cls in classes[:25]
        ]
        
        if not options:
            options = [
                discord.SelectOption(
                    label="No classes found",
                    description="Please add class guides first",
                    emoji="❌"
                )
            ]
            
        placeholder = f"Choose a class (Page {page + 1}/{total_pages})...."
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
            custom_id="class_guide_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "No classes found":
            await interaction.response.send_message("❌ No class guide configuration selected.", ephemeral=True)
            return

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


class ClassNavButton(discord.ui.Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        current_page = 0
        try:
            for row in interaction.message.components:
                for child in row.children:
                    if child.custom_id == "class_guide_select":
                        match = re.search(r"Page (\d+)/(\d+)", child.placeholder)
                        if match:
                            current_page = int(match.group(1)) - 1
        except Exception:
            pass

        guild_id = interaction.guild.id
        all_classes = await fetchall(
            "SELECT class_name FROM class_guides WHERE guild_id = %s ORDER BY class_name ASC",
            (guild_id,)
        )

        if not all_classes:
            await interaction.response.send_message("❌ Error: No class guides found in database.", ephemeral=True)
            return

        total_pages = max(1, (len(all_classes) + 24) // 25)

        if self.custom_id == "class_panel_prev":
            new_page = max(0, current_page - 1)
        else:
            new_page = min(total_pages - 1, current_page + 1)

        view = ClassDropdownView(all_classes, page=new_page)
        await interaction.response.edit_message(view=view)


class ClassDropdownView(discord.ui.View):
    def __init__(self, classes, page=0):
        super().__init__(timeout=None)
        
        total_classes = len(classes)
        total_pages = max(1, (total_classes + 24) // 25)
        page = max(0, min(page, total_pages - 1))
        
        page_classes = classes[page*25 : (page+1)*25]
        
        self.add_item(ClassDropdown(page_classes, page=page, total_pages=total_pages))
        self.add_item(ClassNavButton(style=discord.ButtonStyle.secondary, label="◀ Prev", custom_id="class_panel_prev", disabled=(page == 0)))
        self.add_item(ClassNavButton(style=discord.ButtonStyle.secondary, label="Next ▶", custom_id="class_panel_next", disabled=(page >= total_pages - 1)))


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
        # Auto-create the class_config SQL table on startup for persistent message syncing
        await execute(
            """
            CREATE TABLE IF NOT EXISTS `class_config` (
                `guild_id` bigint(20) NOT NULL,
                `panel_channel_id` bigint(20) DEFAULT NULL,
                `panel_message_id` bigint(20) DEFAULT NULL,
                PRIMARY KEY (`guild_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )
        print("[DATABASE] Verified class_guides and class_config SQL table schemas")
        self.bot.add_view(ClassDropdownView([]))
        print("[CLASS PANEL] Registered persistent ClassDropdownView listener")

    @staticmethod
    def format_enchant_details(raw_str) -> str:
        if not raw_str or raw_str.lower() in ["n/a", "none"]:
            return "*No configuration set.*"
        
        # Split by comma or slash
        parts = [p.strip() for p in raw_str.replace("/", ",").split(",")]
        
        # Ensure we have precisely 4 items (Helm, Class, Cape, Weapon)
        while len(parts) < 4:
            parts.append("N/A")
            
        helm = parts[0]
        cls = parts[1]
        cape = parts[2]
        weapon = parts[3]
        
        return (
            f"<:helmicon:1506182631887339560> **Helm:** `{helm}`\n"
            f"<:classicon:1506184256894926898> **Class:** `{cls}`\n"
            f"<:capeicon:1506183156024344687> **Cape:** `{cape}`\n"
            f"<:swordicon:1506182453398601749> **Weapon:** `{weapon}`"
        )

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
        embed.add_field(
            name="🛡️ 1. Non-Forge Setup",
            value=ClassGuide.format_enchant_details(row["enchant_non_forge"]),
            inline=False
        )
        embed.add_field(
            name="🛡️ 2. Solo Setup",
            value=ClassGuide.format_enchant_details(row["enchant_solo"]),
            inline=False
        )
        embed.add_field(
            name="🛡️ 3. Ultra Boss Setup",
            value=ClassGuide.format_enchant_details(row["enchant_ultra"]),
            inline=False
        )
        
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

    async def update_persistent_panel(self, guild_id):
        # 1. Fetch config from MySQL
        config = await fetchone(
            "SELECT panel_channel_id, panel_message_id FROM class_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config or not config["panel_channel_id"] or not config["panel_message_id"]:
            return # No active panel configured in database
            
        # 2. Fetch all classes
        classes = await fetchall(
            "SELECT class_name FROM class_guides WHERE guild_id = %s ORDER BY class_name ASC",
            (guild_id,)
        )
        
        # 3. Retrieve channel & message in-place
        try:
            channel = self.bot.get_channel(config["panel_channel_id"])
            if not channel:
                channel = await self.bot.fetch_channel(config["panel_channel_id"])
                
            message = await channel.fetch_message(config["panel_message_id"])
            
            # Recreate view with the new list of classes
            view = ClassDropdownView(classes)
            
            # Edit the existing message in-place with the updated view dropdown
            await message.edit(view=view)
            print(f"[CLASS PANEL] Automatically updated persistent dropdown list for guild {guild_id}")
        except Exception as e:
            print(f"[CLASS PANEL ERROR] Failed to auto-update panel for guild {guild_id}: {e}")

    # --- SLASH COMMANDS ---

    @app_commands.command(
        name="class_add",
        description="Add a new class guide or selectively edit/update an existing one (Officer Only)"
    )
    @app_commands.describe(
        class_name="AQW Class Name (e.g., ArchPaladin, Legion DoomKnight)",
        note="General notes or class description (Leave blank to keep current)",
        enchant_non_forge="Format: Helm, Class, Cape, Weapon (e.g., Vim, Luck, Valiance, Spiral)",
        enchant_solo="Format: Helm, Class, Cape, Weapon (e.g., Vim, Luck, Valiance, Spiral)",
        enchant_ultra="Format: Helm, Class, Cape, Weapon (e.g., Vim, Luck, Valiance, Spiral)",
        potion="Best potions to use (Leave blank to keep current)",
        combo="Combos or rotation sequence (Leave blank to keep current)"
    )
    async def class_add(
        self,
        interaction: discord.Interaction,
        class_name: str,
        note: str = None,
        enchant_non_forge: str = None,
        enchant_solo: str = None,
        enchant_ultra: str = None,
        potion: str = None,
        combo: str = None
    ):
        # 1. Authorize Officer status
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Faction Officers or Administrators can manage class guides.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        class_name_clean = class_name.strip()

        # 2. Check if the guide already exists in the database
        existing = await fetchone(
            """
            SELECT * FROM class_guides
            WHERE guild_id = %s AND class_name = %s
            """,
            (guild_id, class_name_clean)
        )

        is_update = False

        if existing:
            is_update = True
            # Merge: Use new inputs if provided, otherwise preserve existing DB values
            final_note = note if note is not None else existing["note"]
            final_non_forge = enchant_non_forge if enchant_non_forge is not None else existing["enchant_non_forge"]
            final_solo = enchant_solo if enchant_solo is not None else existing["enchant_solo"]
            final_ultra = enchant_ultra if enchant_ultra is not None else existing["enchant_ultra"]
            final_potion = potion if potion is not None else existing["potion"]
            final_combo = combo if combo is not None else existing["combo"]
        else:
            # New class guide setup: Default missing values to N/A
            final_note = note if note is not None else "No description provided."
            final_non_forge = enchant_non_forge if enchant_non_forge is not None else "N/A"
            final_solo = enchant_solo if enchant_solo is not None else "N/A"
            final_ultra = enchant_ultra if enchant_ultra is not None else "N/A"
            final_potion = potion if potion is not None else "N/A"
            final_combo = combo if combo is not None else "N/A"

        # 3. Write/Overwrite inside database
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
                final_note,
                final_non_forge,
                final_solo,
                final_ultra,
                final_potion,
                final_combo
            )
        )

        # 4. Automatically update persistent in-place dropdown select panel (if it exists)
        await self.update_persistent_panel(guild_id)

        action_msg = "updated/edited" if is_update else "newly registered"
        await interaction.response.send_message(
            f"✅ **AQW Class Guide Success!**\n"
            f"Specifications for **{class_name_clean}** have been successfully **{action_msg}** in the library. "
            f"Only the fields you entered were changed; all others were preserved.",
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
        message = await target_channel.send(embed=embed, view=view)
        
        # 4. Save channel and message references in MySQL for auto-updating
        await execute(
            """
            INSERT INTO class_config (guild_id, panel_channel_id, panel_message_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                panel_channel_id = VALUES(panel_channel_id),
                panel_message_id = VALUES(panel_message_id)
            """,
            (guild_id, target_channel.id, message.id)
        )
        
        await interaction.response.send_message(
            f"✅ Class Setup Library panel has been posted in {target_channel.mention}!\n"
            f"This panel will automatically self-update in real-time whenever you add or edit class guides.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ClassGuide(bot))
