import discord
from discord import app_commands
from discord.ext import commands

class SelfRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view, survives bot restarts

    async def handle_role_toggle(self, interaction: discord.Interaction, role_name: str, is_faction: bool = False):
        guild = interaction.guild
        member = interaction.user

        # 1. Resolve role (search case-insensitively, or create on demand)
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            # Look up case-insensitively
            for r in guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break

        if not role:
            # Auto-create the role if it doesn't exist
            try:
                role = await guild.create_role(
                    name=role_name, 
                    reason=f"Self-assignable role '{role_name}' auto-creation."
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"❌ **Role Not Found**: The role `{role_name}` does not exist and I do not have permission to create it. "
                    "Please ask an administrator to grant me the **Manage Roles** permission.",
                    ephemeral=True
                )
                return
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ **Error**: Failed to find or create the role `{role_name}`: {e}",
                    ephemeral=True
                )
                return

        # 2. Faction Role Assignment (Chaos, Good, Evil - Mutually Exclusive)
        if is_faction:
            factions = ["Chaos", "Good", "Evil"]
            removed_factions = []
            
            # Remove any existing other factions
            for f_name in factions:
                if f_name.lower() != role_name.lower():
                    f_role = discord.utils.get(guild.roles, name=f_name)
                    if f_role and f_role in member.roles:
                        try:
                            await member.remove_roles(f_role)
                            removed_factions.append(f_role.name)
                        except Exception:
                            pass

            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    await interaction.response.send_message(
                        f"❌ You have left the **{role_name}** faction.",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to leave faction: {e}",
                        ephemeral=True
                    )
            else:
                try:
                    await member.add_roles(role)
                    removed_str = f" (Removed from: **{', '.join(removed_factions)}**)" if removed_factions else ""
                    await interaction.response.send_message(
                        f"✅ Joined faction: **{role_name}**!{removed_str}",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to join faction: {e}",
                        ephemeral=True
                    )

        # 3. Standard Roles (Streamer, Helper - Independent Toggles)
        else:
            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    await interaction.response.send_message(
                        f"❌ Removed role: **{role_name}**",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to remove role: {e}",
                        ephemeral=True
                    )
            else:
                try:
                    await member.add_roles(role)
                    await interaction.response.send_message(
                        f"✅ Added role: **{role_name}**",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to add role: {e}",
                        ephemeral=True
                    )

    @discord.ui.button(label="Chaos", style=discord.ButtonStyle.secondary, custom_id="self_role_chaos", emoji="<:chaosfaction:1506322127819767948>")
    async def chaos_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_role_toggle(interaction, "Chaos", is_faction=True)

    @discord.ui.button(label="Good", style=discord.ButtonStyle.primary, custom_id="self_role_good", emoji="<:goodfaction:1506321915114160128>")
    async def good_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_role_toggle(interaction, "Good", is_faction=True)

    @discord.ui.button(label="Evil", style=discord.ButtonStyle.danger, custom_id="self_role_evil", emoji="<:evilfaction:1506322000652796104>")
    async def evil_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_role_toggle(interaction, "Evil", is_faction=True)

    @discord.ui.button(label="Streamer", style=discord.ButtonStyle.success, custom_id="self_role_streamer", emoji="🎥")
    async def streamer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_role_toggle(interaction, "Streamer", is_faction=False)

    @discord.ui.button(label="Helper", style=discord.ButtonStyle.success, custom_id="self_role_helper", emoji="🛡️")
    async def helper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_role_toggle(interaction, "Helper", is_faction=False)


class SelfRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(SelfRolesView()) # Re-register persistent view on startup

    @app_commands.command(
        name="rolesetup",
        description="Setup and post the self-assignable roles & factions panel."
    )
    @app_commands.describe(
        channel="Channel to post the self-roles embed in"
    )
    async def rolesetup(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can configure self-assignable roles.",
                ephemeral=True
            )
            return

        target_channel = channel or interaction.channel

        # Generate a premium embed
        embed = discord.Embed(
            title="🎭  Faction & Self Roles Selection",
            description=(
                "Stand with your faction or gain access to community roles! "
                "Click the buttons below to toggle your roles.\n\n"
                "<:charpageicon:1506324498943840366> **Factions (Choose One)**\n\n"
                "• <:chaosfaction:1506322127819767948> **Chaos**: Embrace the storm and unpredictability.\n"
                "• <:goodfaction:1506321915114160128> **Good**: Stand for honor, order, and justice.\n"
                "• <:evilfaction:1506322000652796104> **Evil**: Walk in the shadows and seek dark power.\n"
                "*(Note: Factions are mutually exclusive. Selecting a new one removes your current faction.)*\n\n"
                "💼 **Community Roles**\n\n"
                "• 🎥 **Streamer**: Get access to streamer channels & ping alerts.\n"
                "• 🛡️ **Helper**: Join community helpers to support others."
            ),
            color=discord.Color.from_rgb(47, 49, 54) # Premium dark color matching Discord UI
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text="AQW MELAYU • Click buttons below to assign roles", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        view = SelfRolesView()
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Self-roles panel posted in {target_channel.mention}!",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SelfRoles(bot))
