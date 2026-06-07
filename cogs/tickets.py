import json
import discord
import random
import re
import asyncio
from discord.ext import commands
from discord import app_commands
import time
from discord.ext import tasks
from datetime import datetime
from database import execute, fetchone, fetchall


async def cleanup_ticket(ticket_id):
    await execute(
        "DELETE FROM active_ticket_helpers WHERE ticket_id = %s",
        (ticket_id,)
    )
    await execute(
        "DELETE FROM active_ticket_helper_points WHERE ticket_id = %s",
        (ticket_id,)
    )
    await execute(
        "DELETE FROM active_tickets WHERE id = %s",
        (ticket_id,)
    )


async def remove_requester_overwrite(guild, requester_id, ticket_id):
    # Fetch ticket Category ID from config
    config = await get_server_config(guild.id)
    if not config:
        return
    
    ticket_category = guild.get_channel(config["ticket_category_id"])
    
    # 1. Fetch parent channel from config or fallback to active-tickets inside category
    parent_channel = None
    active_channel_id = config.get("active_tickets_channel_id")
    if active_channel_id:
        parent_channel = guild.get_channel(active_channel_id)
        if not parent_channel:
            try:
                parent_channel = await guild.fetch_channel(active_channel_id)
            except Exception:
                parent_channel = None

    if not parent_channel and ticket_category:
        parent_channel = discord.utils.get(guild.text_channels, name="active-tickets", category=ticket_category)
        
    if not parent_channel:
        return
        
    # Check if the requester has any OTHER active tickets
    other_tickets = await fetchone(
        """
        SELECT COUNT(*) as count FROM active_tickets
        WHERE guild_id = %s AND requester_id = %s AND id != %s
        """,
        (guild.id, requester_id, ticket_id)
    )
    if not other_tickets or other_tickets["count"] == 0:
        # Remove parent channel view overwrite for requester
        requester_member = guild.get_member(requester_id)
        if not requester_member:
            try:
                requester_member = await guild.fetch_member(requester_id)
            except Exception:
                requester_member = None
        if requester_member:
            try:
                await parent_channel.set_permissions(requester_member, overwrite=None)
            except Exception as e:
                print(f"Failed to remove parent channel overwrite for requester {requester_id}: {e}")


async def close_ticket_channel(channel, reason):
    guild = getattr(channel, "guild", None)
    if guild:
        # Resolve PartialMessageable or incomplete channel objects
        resolved_channel = guild.get_thread(channel.id) or guild.get_channel(channel.id)
        if not resolved_channel:
            try:
                resolved_channel = await guild.fetch_channel(channel.id)
            except Exception:
                pass
        if resolved_channel:
            channel = resolved_channel

    is_thread = isinstance(channel, discord.Thread) or hasattr(channel, "archived") or getattr(channel, "type", None) in (
        discord.ChannelType.public_thread,
        discord.ChannelType.private_thread,
        discord.ChannelType.news_thread
    )

    if is_thread:
        try:
            await channel.edit(locked=True, archived=True, reason=reason)
        except discord.Forbidden:
            # Fallback: if locking is forbidden, try just archiving
            try:
                await channel.edit(archived=True, reason=reason)
            except Exception as e:
                print(f"Failed to archive thread after lock forbidden: {e}")
        except Exception as e:
            print(f"Failed to lock and archive thread: {e}")
    else:
        try:
            await channel.delete(reason=reason)
        except Exception as e:
            print(f"Failed to delete channel: {e}")


INACTIVE_TIMEOUT_SECONDS = 7200  # 2 hours
WARNING_BEFORE_CLOSE = 1800  # 30 minutes before (in seconds)
DAILY_STATS_FILE = "data/daily_stats.json"
HELPER_ROLE = "Helper"
BONUS_MULTIPLIER = 1.5

def load_json(path):
    try:
        with open(path, "r") as file:
            return json.load(file)
    except:
        return {}


def save_json(path, data):
    with open(path, "w") as file:
        json.dump(data, file, indent=4)

ACTIVITIES = {
    "Ultra Weeklies": {
        "UltraSpeaker": 7,
        "UltraGramiel": 7,
        "ChampionDrakath": 5,
        "UltraDage": 5,
        "UltraDarkon": 5,
        "UltraDrago": 5,
        "UltraNulgath": 5,
    },
    "Ultra Dailies 4-Man": {
        "UltraEngineer": 2,
        "UltraEzrajal": 2,
        "UltraTyndarius": 2,
        "UltraWarden": 2,
        "UltraDage": 2,
    },
    "Daily Quests": {
        "AstralShrine": 4,
        "KathoolDepths": 4,
        "ApexAzalith": 1,
        "VoidFlibbi": 2,
        "VoidNightbane": 2,
        "VoidXyfrag": 2,
        "Deimos": 1,
        "Frozenlair": 1,
        "Sevencircleswar": 1,
        "Flameusurper": 2,
        "Lavarockshore": 2,
    },
    "TempleShrine": {
        "TempleShrine Mid": 5,
        "TempleShrine Left": 2,
        "TempleShrine Right": 2,
    },
    "GrimChallenge 7-Man": {
        "GrimChallenge": 10,
    },
}


def get_max_helpers(category, selected_activities=None):
    if category == "Daily Quests":
        if selected_activities == ["Flameusurper"]:
            return 1
        return 6

    if "7-Man" in category:
        return 6

    return 3

async def get_server_config(guild_id):
    return await fetchone(
        """
        SELECT * FROM ticket_config
        WHERE guild_id = %s
        """,
        (guild_id,)
    )

def user_has_role_id(member, role_id):
    return any(role.id == role_id for role in member.roles)

async def is_officer(member):
    config = await get_server_config(member.guild.id)

    if not config:
        return False

    return user_has_role_id(member, config["officer_role_id"])

def extract_user_id(text):
    text = text.strip()

    if text.startswith("<@") and text.endswith(">"):
        return text.replace("<@", "").replace("!", "").replace(">", "")

    return text

async def calculate_member_points(guild, user_id, base_points):
    member = guild.get_member(int(user_id))
    config = await get_server_config(guild.id)

    if not config or not member:
        return base_points

    if user_has_role_id(member, config["bonus_role_id"]):
        return int(base_points * BONUS_MULTIPLIER)

    return base_points

async def get_active_ticket_by_user(guild_id, user_id):
    return await fetchone(
        """
        SELECT * FROM active_tickets
        WHERE guild_id = %s AND requester_id = %s
        """,
        (guild_id, user_id)
    )


async def get_active_ticket_by_channel(channel_id):
    return await fetchone(
        """
        SELECT * FROM active_tickets
        WHERE channel_id = %s
        """,
        (channel_id,)
    )


async def get_ticket_helpers(ticket_id):
    rows = await fetchall(
        """
        SELECT user_id
        FROM active_ticket_helpers
        WHERE ticket_id = %s
        """,
        (ticket_id,)
    )

    return [row["user_id"] for row in rows]


async def get_helper_custom_points(ticket_id):
    rows = await fetchall(
        """
        SELECT user_id, points
        FROM active_ticket_helper_points
        WHERE ticket_id = %s
        """,
        (ticket_id,)
    )

    return {
        str(row["user_id"]): row["points"]
        for row in rows
    }


async def update_ticket_activity(ticket_id):
    await execute(
        """
        UPDATE active_tickets
        SET last_activity = %s, warned = FALSE
        WHERE id = %s
        """,
        (time.time(), ticket_id)
    )
def today_key():
    return datetime.now().strftime("%Y-%m-%d")


def update_daily_stats(status, activity, points=0, requester_id=None, helper_ids=None):
    stats = load_json(DAILY_STATS_FILE)
    today = today_key()

    if today not in stats:
        stats[today] = {
            "completed_tickets": 0,
            "cancelled_tickets": 0,
            "total_points_given": 0,
            "helpers": {},
            "requesters": {},
            "activities": {}
        }

    if status == "completed":
        num_activities = len([act.strip() for act in activity.split(" + ") if act.strip()]) if activity else 1
        stats[today]["completed_tickets"] += num_activities
    elif status == "cancelled":
        stats[today]["cancelled_tickets"] += 1

    if activity:
        individual_activities = [act.strip() for act in activity.split(" + ")]
        for act in individual_activities:
            if act:
                stats[today]["activities"][act] = stats[today]["activities"].get(act, 0) + 1


    if requester_id:
        requester_id = str(requester_id)
        stats[today]["requesters"][requester_id] = stats[today]["requesters"].get(requester_id, 0) + points
        stats[today]["total_points_given"] += points

    if helper_ids:
        for helper_id in helper_ids:
            helper_id = str(helper_id)
            stats[today]["helpers"][helper_id] = stats[today]["helpers"].get(helper_id, 0) + points
            stats[today]["total_points_given"] += points

    save_json(DAILY_STATS_FILE, stats)

async def send_ticket_log(guild, title, description, color=discord.Color.blue()):
    config = await get_server_config(guild.id)

    if not config:
        return

    log_channel = guild.get_channel(config["ticket_log_channel_id"])

    if log_channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    await log_channel.send(embed=embed)    


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ultra Weeklies", style=discord.ButtonStyle.primary, emoji="🔷", custom_id="ticket_panel_ultra_weeklies")
    async def ultra_weeklies(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Ultra Weeklies** activity and server:",
            view=TicketCreationView("Ultra Weeklies"),
            ephemeral=True
        )

    @discord.ui.button(label="Ultra Dailies 4-Man", style=discord.ButtonStyle.success, emoji="🔶", custom_id="ticket_panel_ultra_dailies_4")
    async def ultra_dailies_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Ultra Dailies 4-Man** activity and server:",
            view=TicketCreationView("Ultra Dailies 4-Man"),
            ephemeral=True
        )

    @discord.ui.button(label="Daily Quests", style=discord.ButtonStyle.success, emoji="🔷", custom_id="ticket_panel_daily_quests")
    async def ultra_dailies_7(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Daily Quests** activity and server:",
            view=TicketCreationView("Daily Quests"),
            ephemeral=True
        )

    @discord.ui.button(label="TempleShrine", style=discord.ButtonStyle.secondary, emoji="⛩️", custom_id="ticket_panel_temple_shrine")
    async def temple_shrine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **TempleShrine** activity and server:",
            view=TicketCreationView("TempleShrine"),
            ephemeral=True
        )

    @discord.ui.button(label="GrimChallenge 7-Man", style=discord.ButtonStyle.danger, emoji="👹", custom_id="ticket_panel_grim_challenge")
    async def grim_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **GrimChallenge 7-Man** activity and server:",
            view=TicketCreationView("GrimChallenge 7-Man"),
            ephemeral=True
        )
    
    @discord.ui.button(label="Hard Farm/Others", style=discord.ButtonStyle.secondary, emoji="🛠️", custom_id="ticket_panel_hard_farm_others")
    async def hard_farm_others(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HardFarmModal())


class ServerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Galanoth", value="Galanoth", default=True),
            discord.SelectOption(label="Artix", value="Artix"),
            discord.SelectOption(label="Yorumi", value="Yorumi"),
            discord.SelectOption(label="Safiria", value="Safiria"),
            discord.SelectOption(label="Sir Ver", value="Sir Ver"),
            discord.SelectOption(label="Twilly", value="Twilly"),
            discord.SelectOption(label="Twig", value="Twig"),
            discord.SelectOption(label="Sepulchure", value="Sepulchure"),
            discord.SelectOption(label="Gravelyn", value="Gravelyn"),
            discord.SelectOption(label="Swordhaven (EU)", value="Swordhaven (EU)"),
            discord.SelectOption(label="Alteon", value="Alteon"),
            discord.SelectOption(label="Yokai (SEA)", value="Yokai (SEA)"),
            discord.SelectOption(label="Espada", value="Espada"),
        ]
        super().__init__(
            placeholder="Select AQW Server...",
            options=options,
            min_values=1,
            max_values=1,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_server = self.values[0]
        await interaction.response.defer()


class ActivityMultiSelect(discord.ui.Select):
    def __init__(self, category):
        self.category = category

        options = [
            discord.SelectOption(
                label=activity,
                description=f"{points} helper point(s)"
            )
            for activity, points in ACTIVITIES[category].items()
        ]

        super().__init__(
            placeholder="Select one or more activities...",
            options=options,
            min_values=1,
            max_values=len(options),
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_activities = self.values
        await interaction.response.defer()


class TicketCreationView(discord.ui.View):
    def __init__(self, category):
        super().__init__(timeout=120)
        self.category = category
        self.selected_activities = []
        self.selected_server = "Galanoth"

        self.activity_select = ActivityMultiSelect(category)
        self.server_select = ServerSelect()

        self.add_item(self.activity_select)
        self.add_item(self.server_select)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.success, emoji="🎟️", row=2)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_activities:
            await interaction.response.send_message(
                "❌ Please select at least one activity first.",
                ephemeral=True
            )
            return

        existing_ticket = await get_active_ticket_by_user(
            interaction.guild.id,
            interaction.user.id
        )

        if existing_ticket:
            await interaction.response.send_message(
                "❌ You already have an active ticket. Close it first before creating another.",
                ephemeral=True
            )
            return

        config = await get_server_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "❌ Ticket system not setup. Admin must run /ticketsetup.",
                ephemeral=True
            )
            return

        helper_role = interaction.guild.get_role(config["helper_role_id"])
        ticket_category = interaction.guild.get_channel(config["ticket_category_id"])

        if ticket_category is None:
            await interaction.response.send_message(
                "❌ Category `Ticket Category` does not exist. Please create it first.",
                ephemeral=True
            )
            return

        existing_rooms = await fetchall(
            """
            SELECT room_number
            FROM active_tickets
            WHERE guild_id = %s
            """,
            (interaction.guild.id,)
        )

        used_numbers = [
            row["room_number"]
            for row in existing_rooms
        ]

        while True:
            room_number = random.randint(1000, 9999)
            if room_number not in used_numbers:
                break

        server_name = self.selected_server
        total_points = sum(ACTIVITIES[self.category][activity] for activity in self.selected_activities)
        max_helpers = get_max_helpers(self.category, self.selected_activities)

        # Get requester's IGN from verified_users table
        verified_user = await fetchone(
            """
            SELECT ign FROM verified_users
            WHERE guild_id = %s AND user_id = %s
            """,
            (interaction.guild.id, interaction.user.id)
        )
        ign = verified_user["ign"] if verified_user else interaction.user.display_name

        category_slug = self.category.lower().replace(" ", "-")
        ign_slug = ign.lower().replace(" ", "-")
        channel_name = f"{category_slug}-{ign_slug}"

        # 1. Get or create parent text channel inside ticket_category
        parent_channel = None
        active_channel_id = config.get("active_tickets_channel_id")
        if active_channel_id:
            parent_channel = interaction.guild.get_channel(active_channel_id)
            if not parent_channel:
                try:
                    parent_channel = await interaction.guild.fetch_channel(active_channel_id)
                except Exception:
                    parent_channel = None

        if not parent_channel:
            parent_channel = discord.utils.get(interaction.guild.text_channels, name="active-tickets", category=ticket_category)
            if not parent_channel:
                parent_overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True, manage_threads=True),
                }
                if helper_role:
                    parent_overwrites[helper_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                if config and config.get("officer_role_id"):
                    officer_role = interaction.guild.get_role(config["officer_role_id"])
                    if officer_role:
                        parent_overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                
                parent_channel = await interaction.guild.create_text_channel(
                    name="active-tickets",
                    category=ticket_category,
                    overwrites=parent_overwrites,
                    reason="Parent channel for active ticket threads"
                )

        # 2. Grant temporary view permission to requester on `#active-tickets` parent channel
        try:
            await parent_channel.set_permissions(interaction.user, view_channel=True, send_messages=False)
        except Exception as e:
            print(f"Failed to set temporary permission for requester: {e}")

        # 3. Create a public thread inside `#active-tickets`
        channel = await parent_channel.create_thread(
            name=channel_name,
            type=discord.ChannelType.public_thread,
            reason="Combined ultra ticket thread created"
        )

        # 4. Add the requester explicitly to the thread
        try:
            await channel.add_user(interaction.user)
        except Exception as e:
            print(f"Failed to add requester to thread: {e}")

        await execute(
            """
            INSERT INTO active_tickets
            (
                guild_id,
                requester_id,
                channel_id,
                activity,
                category,
                points,
                manual_points,
                max_helpers,
                room_number,
                completed,
                helpers_locked,
                warned,
                ign,
                server_name,
                created_at,
                last_activity
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s
            )
            """,
            (
                interaction.guild.id,
                interaction.user.id,
                channel.id,
                " + ".join(self.selected_activities),
                self.category,
                total_points,
                False,
                max_helpers,
                room_number,
                False,
                False,
                False,
                ign,
                server_name,
                time.time(),
                time.time()
            )
        )

        activity_list = "\n".join(
            f"- {activity} = {ACTIVITIES[self.category][activity]} point(s)"
            for activity in self.selected_activities
        )

        embed = discord.Embed(
            title="🎟️ Combined Ultra Ticket Created",
            description=(
                f"**Room:** `{room_number}`\n"
                f"**Server:** `{server_name}`\n"
                f"**Requester:** {interaction.user.mention}\n"
                f"**IGN:** `{ign}`\n"
                f"**Category:** {self.category}\n\n"
                f"**Selected Ultras:**\n"
                f"{activity_list}\n\n"
                f"**Total Helper Reward:** {total_points} point(s) each\n"
                f"**Helper Slots:** 0/{max_helpers}\n\n"
                f"Waiting for helpers to join this ticket."
            ),
            color=discord.Color.blue()
        )

        await channel.send(
            content=f"{interaction.user.mention} {helper_role.mention if helper_role else ''}",
            embed=embed,
            view=TicketControlView()
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"✅ Combined ticket created: {channel.mention}",
            view=self
        )

class HardFarmModal(discord.ui.Modal, title="Hard Farm / Others Ticket"):
    ign = discord.ui.TextInput(
        label="Your AQW IGN",
        placeholder="Example: UltraDage",
        required=True,
        max_length=32
    )

    server = discord.ui.TextInput(
        label="AQW Server",
        placeholder="Example: Artix / Yorumi / Safiria",
        required=True,
        max_length=32
    )

    room_name = discord.ui.TextInput(
        label="Room Name",
        placeholder="Example: battleon / ultradage",
        required=True,
        max_length=50
    )

    helpers_needed = discord.ui.TextInput(
        label="Number of Helpers Needed",
        placeholder="Example: 3",
        required=True,
        max_length=2
    )
    details = discord.ui.TextInput(
        label="Details of Farm",
        placeholder="Explain what farm/help you need...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            helpers_needed = int(self.helpers_needed.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Number of helpers must be a number.",
                ephemeral=True
            )
            return

        if helpers_needed < 1 or helpers_needed > 10:
            await interaction.response.send_message(
                "❌ Helpers needed must be between 1 and 10.",
                ephemeral=True
            )
            return

        existing_ticket = await get_active_ticket_by_user(
            interaction.guild.id,
            interaction.user.id
        )

        if existing_ticket:
            await interaction.response.send_message(
                "❌ You already have an active ticket. Close it first before creating another.",
                ephemeral=True
            )
            return

        config = await get_server_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                "❌ Ticket system not setup. Admin must run /ticketsetup.",
                ephemeral=True
            )
            return

        helper_role = interaction.guild.get_role(config["helper_role_id"])

        ticket_category = interaction.guild.get_channel(config["ticket_category_id"])

        if ticket_category is None:
            await interaction.response.send_message(
                "❌ Category `Ticket` does not exist. Please create it first.",
                ephemeral=True
            )
            return

        existing_rooms = await fetchall(
            """
            SELECT room_number
            FROM active_tickets
            WHERE guild_id = %s
            """,
            (interaction.guild.id,)
        )

        used_numbers = [
            row["room_number"]
            for row in existing_rooms
        ]

        while True:
            room_number = random.randint(1000, 9999)
            if room_number not in used_numbers:
                break

        category_slug = "hard-farm"
        ign_slug = str(self.ign.value).lower().replace(" ", "-")
        channel_name = f"{category_slug}-{ign_slug}"

        # 1. Get or create parent text channel inside ticket_category
        parent_channel = None
        active_channel_id = config.get("active_tickets_channel_id")
        if active_channel_id:
            parent_channel = interaction.guild.get_channel(active_channel_id)
            if not parent_channel:
                try:
                    parent_channel = await interaction.guild.fetch_channel(active_channel_id)
                except Exception:
                    parent_channel = None

        if not parent_channel:
            parent_channel = discord.utils.get(interaction.guild.text_channels, name="active-tickets", category=ticket_category)
            if not parent_channel:
                parent_overwrites = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                    interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True, manage_threads=True),
                }
                if helper_role:
                    parent_overwrites[helper_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                if config and config.get("officer_role_id"):
                    officer_role = interaction.guild.get_role(config["officer_role_id"])
                    if officer_role:
                        parent_overwrites[officer_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                
                parent_channel = await interaction.guild.create_text_channel(
                    name="active-tickets",
                    category=ticket_category,
                    overwrites=parent_overwrites,
                    reason="Parent channel for active ticket threads"
                )

        # 2. Grant temporary view permission to requester on `#active-tickets` parent channel
        try:
            await parent_channel.set_permissions(interaction.user, view_channel=True, send_messages=False)
        except Exception as e:
            print(f"Failed to set temporary permission for requester: {e}")

        # 3. Create a public thread inside `#active-tickets`
        channel = await parent_channel.create_thread(
            name=channel_name,
            type=discord.ChannelType.public_thread,
            reason="Hard Farm/Others ticket thread created"
        )

        # 4. Add the requester explicitly to the thread
        try:
            await channel.add_user(interaction.user)
        except Exception as e:
            print(f"Failed to add requester to thread: {e}")

        await execute(
            """
            INSERT INTO active_tickets
            (
                guild_id,
                requester_id,
                channel_id,
                activity,
                category,
                points,
                manual_points,
                max_helpers,
                room_number,
                completed,
                helpers_locked,
                warned,
                ign,
                server_name,
                room_name,
                details,
                created_at,
                last_activity
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            """,
            (
                interaction.guild.id,
                interaction.user.id,
                channel.id,
                "Hard Farm/Others",
                "Hard Farm/Others",
                0,
                True,
                helpers_needed,
                room_number,
                False,
                False,
                False,
                str(self.ign.value),
                str(self.server.value),
                str(self.room_name.value),
                str(self.details.value),
                time.time(),
                time.time()
            )
        )

        embed = discord.Embed(
            title="🛠️ Hard Farm / Others Ticket Created",
            description=(
                f"**Room:** `{room_number}`\n"
                f"**Requester:** {interaction.user.mention}\n"
                f"**IGN:** `{self.ign.value}`\n"
                f"**Server:** `{self.server.value}`\n"
                f"**Room Name:** `{self.room_name.value}`\n"
                f"**Helpers Needed:** `{helpers_needed}`\n\n"
                f"**Details:**\n{self.details.value}\n\n"
                f"**Points:** Officer will decide manually.\n"
                f"**Helper Slots:** 0/{helpers_needed}\n\n"
                f"Waiting for helpers to join this ticket."
            ),
            color=discord.Color.orange()
        )

        await channel.send(
            content=f"{interaction.user.mention} {helper_role.mention if helper_role else ''}",
            embed=embed,
            view=TicketControlView()
        )


        await interaction.response.send_message(
            f"✅ Hard Farm/Others ticket created: {channel.mention}",
            ephemeral=True
        )



class SetPointsModal(discord.ui.Modal, title="Set Manual Ticket Points"):
    points = discord.ui.TextInput(
        label="Points to give",
        placeholder="Example: 5",
        required=True,
        max_length=3
        
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points = int(self.points.value)

        except ValueError:
            await interaction.response.send_message(
                "❌ Points must be a number.",
                ephemeral=True
            )
            return

        if points < 0:
            await interaction.response.send_message(
                "❌ Points cannot be negative.",
                ephemeral=True
            )
            return

        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        await execute(
            """
            UPDATE active_tickets
            SET points = %s
            WHERE id = %s
            """,
            (
                points,
                ticket_data["id"]
            )
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        await interaction.response.send_message(
            f"✅ Manual points set to **{points} point(s)**."
        )

class SetHelperPointsModal(discord.ui.Modal, title="Set Helper Points"):
    helper = discord.ui.TextInput(
        label="Helper Mention or Discord ID",
        placeholder="Example: @Aiman or 123456789",
        required=True,
        max_length=32
    )

    points = discord.ui.TextInput(
        label="Points for this helper",
        placeholder="Example: 2",
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points = int(self.points.value)

        except ValueError:
            await interaction.response.send_message(
                "❌ Points must be a number.",
                ephemeral=True
            )
            return

        if points < 0:
            await interaction.response.send_message(
                "❌ Points cannot be negative.",
                ephemeral=True
            )
            return

        try:
            helper_id = int(
                extract_user_id(self.helper.value)
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid user. Please enter a valid @mention or Discord ID.",
                ephemeral=True
            )
            return

        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        helper_ids = await get_ticket_helpers(
            ticket_data["id"]
        )

        if helper_id not in helper_ids:
            await interaction.response.send_message(
                "❌ That user is not joined as helper in this ticket.",
                ephemeral=True
            )
            return

        await execute(
            """
            INSERT INTO active_ticket_helper_points
            (
                ticket_id,
                user_id,
                points
            )
            VALUES (%s, %s, %s)

            ON DUPLICATE KEY UPDATE
                points = VALUES(points)
            """,
            (
                ticket_data["id"],
                helper_id,
                points
            )
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        await interaction.response.send_message(
            f"✅ Custom points set.\n"
            f"Helper <@{helper_id}> will receive **{points} point(s)**."
        )


class RemoveHelperSelect(discord.ui.Select):
    def __init__(self, helpers_data, ticket_data):
        self.ticket_data = ticket_data
        options = [
            discord.SelectOption(
                label=display_name,
                value=str(user_id),
                description=f"Demote and strip Helper role"
            )
            for user_id, display_name in helpers_data
        ]
        super().__init__(
            placeholder="Select a helper to demote...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        officer_check = await is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can demote helpers.",
                ephemeral=True
            )
            return

        removed_user_id = int(self.values[0])
        
        # Get server config to find the helper role ID
        config = await get_server_config(interaction.guild.id)
        helper_role_removed = False
        
        member = interaction.guild.get_member(removed_user_id)
        if not member:
            try:
                member = await interaction.guild.fetch_member(removed_user_id)
            except Exception:
                member = None
        
        if config and config.get("helper_role_id"):
            helper_role = interaction.guild.get_role(config["helper_role_id"])
            if helper_role and member:
                try:
                    await member.remove_roles(helper_role, reason=f"Demoted by Officer {interaction.user} via Officer Control Panel.")
                    helper_role_removed = True
                except Exception as e:
                    print(f"Failed to remove helper role: {e}")

        # Delete from active ticket helpers in this guild only
        await execute(
            """
            DELETE FROM active_ticket_helpers
            WHERE user_id = %s
            AND ticket_id IN (SELECT id FROM active_tickets WHERE guild_id = %s)
            """,
            (removed_user_id, interaction.guild.id)
        )
        
        await execute(
            """
            DELETE FROM active_ticket_helper_points
            WHERE user_id = %s
            AND ticket_id IN (SELECT id FROM active_tickets WHERE guild_id = %s)
            """,
            (removed_user_id, interaction.guild.id)
        )

        await update_ticket_activity(self.ticket_data["id"])

        current_helpers = await get_ticket_helpers(self.ticket_data["id"])
        helper_count = len(current_helpers)

        # Forcefully remove view permissions for this helper on this ticket channel
        if member:
            try:
                if isinstance(interaction.channel, discord.Thread):
                    await interaction.channel.remove_user(member)
                else:
                    await interaction.channel.set_permissions(member, view_channel=False)
            except Exception as e:
                print(f"Failed to remove demoted helper {removed_user_id} from ticket channel/thread: {e}")

        # Edit the ephemeral select message to clear/dismiss the select menu
        role_status_str = "and had their **Helper role** removed" if helper_role_removed else "(failed to remove Helper role, check role hierarchy)"
        await interaction.response.edit_message(
            content=f"✅ Helper <@{removed_user_id}> has been successfully demoted {role_status_str}.",
            view=None
        )

        # Send public notice in the channel
        await interaction.channel.send(
            f"🚫 <@{removed_user_id}> has been **demoted** and had their Helper role removed by Officer {interaction.user.mention} due to improper conduct/scamming.\n"
            f"Helpers remaining in this ticket: `{helper_count}/{self.ticket_data['max_helpers']}`"
        )



        try:
            await send_ticket_log(
                interaction.guild,
                "🚫 Helper Demoted (Ticket)",
                (
                    f"**Officer:** {interaction.user.mention}\n"
                    f"**Demoted User:** <@{removed_user_id}> ({removed_user_id})\n"
                    f"**Action:** Helper role removed and user purged from active helper queues.\n"
                    f"**Ticket Channel:** {interaction.channel.mention} ([Jump to Thread]({interaction.channel.jump_url}))"
                ),
                discord.Color.red()
            )
        except Exception as e:
            print(f"Failed to send helper log from ticket demote: {e}")


class RemoveHelperSelectView(discord.ui.View):
    def __init__(self, helpers_data, ticket_data):
        super().__init__(timeout=180)
        self.add_item(RemoveHelperSelect(helpers_data, ticket_data))


class OfficerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Demote Helper",
        style=discord.ButtonStyle.danger,
        emoji="🚫",
        custom_id="ticket_officer_remove_helper"
    )
    async def remove_helper(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_check = await is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can manage helpers.",
                ephemeral=True
            )
            return

        ticket_data = await get_active_ticket_by_channel(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        helper_ids = await get_ticket_helpers(ticket_data["id"])
        if not helper_ids:
            await interaction.response.send_message(
                "❌ No helpers have joined this ticket yet.",
                ephemeral=True
            )
            return

        helpers_data = []
        for helper_id in helper_ids:
            member = interaction.guild.get_member(helper_id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(helper_id)
                except Exception:
                    member = None
            display_name = member.display_name if member else f"User ID {helper_id}"
            helpers_data.append((helper_id, display_name))

        view = RemoveHelperSelectView(helpers_data, ticket_data)
        await interaction.response.send_message(
            "Select a helper to demote (removes their Helper role):",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="🔐 Lock / Unlock Helpers",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_officer_toggle_helpers"
    )
    async def toggle_helpers(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        officer_check = await is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can toggle helper lock.",
                ephemeral=True
            )
            return

        new_state = not ticket_data["helpers_locked"]
        await execute(
            """
            UPDATE active_tickets
            SET helpers_locked = %s
            WHERE id = %s
            """,
            (new_state, ticket_data["id"])
        )
        await update_ticket_activity(ticket_data["id"])

        if new_state:
            message = "🔐 Helpers are now **LOCKED**. No one can join."
        else:
            message = "🔓 Helpers are now **UNLOCKED**. Others can join."

        await interaction.response.send_message(message)

    @discord.ui.button(
        label="Set Points",
        style=discord.ButtonStyle.secondary,
        emoji="🧮",
        custom_id="ticket_officer_set_points"
    )
    async def set_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_check = await is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can set manual points.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(SetPointsModal())

    @discord.ui.button(
        label="Set Helper Points",
        style=discord.ButtonStyle.secondary,
        emoji="🎯",
        custom_id="ticket_officer_set_helper_points"
    )
    async def set_helper_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_check = await is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can set helper points.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(SetHelperPointsModal())


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join as Helper",
        style=discord.ButtonStyle.primary,
        emoji="🙋",
        custom_id="ticket_join_helper"
    )
    async def join_helper(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        if ticket_data["requester_id"] == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot join your own ticket as helper.",
                ephemeral=True
            )
            return

        if ticket_data["helpers_locked"]:
            await interaction.response.send_message(
                "🔐 Helper slots are locked for this ticket.",
                ephemeral=True
            )
            return

        config = await get_server_config(
            interaction.guild.id
        )

        helper_ids = await get_ticket_helpers(
            ticket_data["id"]
        )

        if interaction.user.id in helper_ids:
            await interaction.response.send_message(
                "❌ You already joined this ticket as helper.",
                ephemeral=True
            )
            return

        if len(helper_ids) >= ticket_data["max_helpers"]:
            await interaction.response.send_message(
                f"❌ This ticket already has maximum helpers: `{ticket_data['max_helpers']}`.",
                ephemeral=True
            )
            return
        
        await execute(
            """
            INSERT INTO active_ticket_helpers
            (ticket_id, user_id)
            VALUES (%s, %s)
            """,
            (
                ticket_data["id"],
                interaction.user.id
            )
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        helper_count = len(helper_ids) + 1

        if isinstance(interaction.channel, discord.Thread):
            try:
                await interaction.channel.add_user(interaction.user)
            except Exception as e:
                print(f"Failed to add helper to thread: {e}")

        await interaction.response.send_message(
            f"✅ {interaction.user.mention} joined as helper.\n"
            f"Helpers: `{helper_count}/{ticket_data['max_helpers']}`"
        )

    @discord.ui.button(
        label="Leave Helper",
        style=discord.ButtonStyle.secondary,
        emoji="🚪",
        custom_id="ticket_leave_helper"
    )
    async def leave_helper(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        helper_ids = await get_ticket_helpers(
            ticket_data["id"]
        )

        if interaction.user.id not in helper_ids:
            await interaction.response.send_message(
                "❌ You are not joined as helper in this ticket.",
                ephemeral=True
            )
            return

        if ticket_data["completed"]:
            await interaction.response.send_message(
                "❌ You cannot leave after the ticket has been completed.",
                ephemeral=True
            )
            return

        await execute(
            """
            DELETE FROM active_ticket_helpers
            WHERE ticket_id = %s
            AND user_id = %s
            """,
            (
                ticket_data["id"],
                interaction.user.id
            )
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        helper_count = len(helper_ids) - 1

        await interaction.response.send_message(
            f"🚪 {interaction.user.mention} left as helper.\n"
            f"Helpers: `{helper_count}/{ticket_data['max_helpers']}`"
        )

    @discord.ui.button(
        label="🔐 Lock / Unlock Helpers",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_toggle_helpers"
    )
    async def toggle_helpers(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        is_owner = ticket_data["requester_id"] == interaction.user.id
        officer_check = await is_officer(interaction.user)

        if not is_owner and not officer_check:
            await interaction.response.send_message(
                "❌ Only requester or Officer can toggle helper lock.",
                ephemeral=True
            )
            return

        new_state = not ticket_data["helpers_locked"]

        await execute(
            """
            UPDATE active_tickets
            SET helpers_locked = %s
            WHERE id = %s
            """,
            (
                new_state,
                ticket_data["id"]
            )
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        if new_state:
            message = "🔐 Helpers are now **LOCKED**. No one can join."
        else:
            message = "🔓 Helpers are now **UNLOCKED**. Others can join."

        await interaction.response.send_message(message)

    @discord.ui.button(
            label="Set Points",
            style=discord.ButtonStyle.secondary,
            emoji="🧮",
            custom_id="ticket_set_points"
        )
    async def set_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_check = await is_officer(interaction.user)

        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can set manual points.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(SetPointsModal())   

    @discord.ui.button(
        label="Set Helper Points",
        style=discord.ButtonStyle.secondary,
        emoji="🎯",
        custom_id="ticket_set_helper_points"
    )
    async def set_helper_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        officer_check = await is_officer(interaction.user)

        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can set helper points.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(SetHelperPointsModal())

    @discord.ui.button(
        label="Complete Ticket",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="ticket_complete"
    )
    async def complete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        is_owner = ticket_data["requester_id"] == interaction.user.id
        officer_check = await is_officer(interaction.user)

        if not is_owner and not officer_check:
            await interaction.response.send_message(
                "❌ Only the ticket owner or Officer can mark this ticket as complete.",
                ephemeral=True
            )
            return

        helper_ids = await get_ticket_helpers(
            ticket_data["id"]
        )

        if not helper_ids:
            await interaction.response.send_message(
                "❌ No helpers have joined this ticket yet.",
                ephemeral=True
            )
            return

        await execute(
            """
            UPDATE active_tickets
            SET completed = TRUE
            WHERE id = %s
            """,
            (ticket_data["id"],)
        )

        await update_ticket_activity(
            ticket_data["id"]
        )

        await interaction.response.send_message(
            "✅ Ticket marked as completed.\n"
            "⚠️ Points will only be given when an Officer closes this ticket."
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_data = await get_active_ticket_by_channel(
            interaction.channel.id
        )

        if not ticket_data:
            await interaction.response.send_message(
                "❌ This ticket is not registered.",
                ephemeral=True
            )
            return

        is_owner = ticket_data["requester_id"] == interaction.user.id
        officer_check = await is_officer(interaction.user)

        if not is_owner and not officer_check:
            await interaction.response.send_message(
                "❌ Only the ticket requester or Officer can close this ticket.",
                ephemeral=True
            )
            return

        # Requester cannot close completed ticket
        if (
            is_owner
            and not officer_check
            and ticket_data["completed"]
        ):
            await interaction.response.send_message(
                "❌ This ticket is already completed.\n"
                "Only Officer can close completed tickets.",
                ephemeral=True
            )
            return

        # Cancelled ticket
        if not ticket_data["completed"]:

            await send_ticket_log(
                interaction.guild,
                "🔒 Ticket Cancelled",
                (
                    f"**Closed by:** {interaction.user.mention}\n"
                    f"**Ticket:** {interaction.channel.mention} ([Jump to Thread]({interaction.channel.jump_url}))\n"
                    f"**Activity:** {ticket_data['activity']}\n"
                    f"**Points Given:** `0`"
                ),
                discord.Color.red()
            )

            await cleanup_ticket(ticket_data["id"])
            try:
                await remove_requester_overwrite(interaction.guild, ticket_data["requester_id"], ticket_data["id"])
            except Exception as e:
                print(f"Failed to remove requester overwrite on cancel: {e}")

            update_daily_stats(
                status="cancelled",
                activity=ticket_data["activity"],
                points=0,
                requester_id=ticket_data["requester_id"],
                helper_ids=[]
            )

            await interaction.response.send_message(
                "🔒 Ticket cancelled/closed.\n"
                "No points were given."
            )

            await close_ticket_channel(interaction.channel, "Ticket cancelled")

            return

        # Completed ticket → Officer only
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can close completed tickets.",
                ephemeral=True
            )
            return

        helper_ids = await get_ticket_helpers(
            ticket_data["id"]
        )

        if not helper_ids:
            await interaction.response.send_message(
                "❌ No helpers found.",
                ephemeral=True
            )
            return

        if (
            ticket_data["manual_points"]
            and ticket_data["points"] <= 0
        ):
            await interaction.response.send_message(
                "❌ Manual points have not been set yet.",
                ephemeral=True
            )
            return

        points = ticket_data["points"]

        helper_custom_points = await get_helper_custom_points(
            ticket_data["id"]
        )

        helper_mentions = []

        # 🔹 Reward helpers
        for helper_id in helper_ids:

            helper_base_points = helper_custom_points.get(
                str(helper_id),
                points
            )

            final_points = await calculate_member_points(
                interaction.guild,
                helper_id,
                helper_base_points
            )

            await execute(
                """
                INSERT INTO helper_points
                (
                    guild_id,
                    user_id,
                    points
                )
                VALUES (%s, %s, %s)

                ON DUPLICATE KEY UPDATE
                    points = points + VALUES(points)
                """,
                (
                    interaction.guild.id,
                    helper_id,
                    final_points
                )
            )

            helper = interaction.guild.get_member(helper_id)

            helper_name = (
                helper.mention
                if helper
                else f"User ID {helper_id}"
            )

            helper_mentions.append(
                f"{helper_name} (+{final_points})"
            )

        # 🔹 Reward requester
        requester_id = ticket_data["requester_id"]

        requester_points = await calculate_member_points(
            interaction.guild,
            requester_id,
            points
        )

        await execute(
            """
            INSERT INTO helper_points
            (
                guild_id,
                user_id,
                points
            )
            VALUES (%s, %s, %s)

            ON DUPLICATE KEY UPDATE
                points = points + VALUES(points)
            """,
            (
                interaction.guild.id,
                requester_id,
                requester_points
            )
        )

        requester = interaction.guild.get_member(
            requester_id
        )

        requester_mention = (
            f"{requester.mention} (+{requester_points})"
            if requester
            else f"User ID {requester_id}"
        )

        # Cleanup
        await cleanup_ticket(ticket_data["id"])
        try:
            await remove_requester_overwrite(interaction.guild, requester_id, ticket_data["id"])
        except Exception as e:
            print(f"Failed to remove requester overwrite on completion: {e}")

        update_daily_stats(
            status="completed",
            activity=ticket_data["activity"],
            points=points,
            requester_id=requester_id,
            helper_ids=helper_ids
        )

        tickets_cog = interaction.client.get_cog("Tickets")
        if tickets_cog:
            await tickets_cog.update_completed_tickets_embed(interaction.guild)

        await send_ticket_log(
            interaction.guild,
            "🏆 Ticket Completed",
            (
                f"**Closed by:** {interaction.user.mention}\n"
                f"**Ticket:** {interaction.channel.mention} ([Jump to Thread]({interaction.channel.jump_url}))\n"
                f"**Activity:** {ticket_data['activity']}\n\n"
                f"**Requester:** {requester_mention}\n"
                f"**Helpers:** {', '.join(helper_mentions)}\n\n"
                f"**Points Each:** `{points}`"
            ),
            discord.Color.green()
        )

        await interaction.response.send_message(
            f"✅ Ticket closed.\n\n"
            f"Requester: {requester_mention}\n"
            f"Helpers: {', '.join(helper_mentions)}"
        )

        try:
            await update_persistent_leaderboard(interaction.guild)
        except Exception as e:
            print(f"[LEADERBOARD] Failed to update leaderboard: {e}")

        try:
            await close_ticket_channel(interaction.channel, "Ticket completed")
        except Exception:
            pass


class LeaderboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def update_button_states(self, total_pages, page):
        self.prev_btn.disabled = page == 0
        self.next_btn.disabled = page >= total_pages - 1

    def generate_embed(self, data, guild, page, per_page=10) -> discord.Embed:
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        page = max(0, min(page, total_pages - 1))
        
        start = page * per_page
        end = start + per_page
        page_data = data[start:end]

        description = ""
        for index, row in enumerate(page_data, start=start + 1):
            member = guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            description += f"**{index}.** {name} — **{row['points']} points**\n"

        embed = discord.Embed(
            title="🏆 Points Leaderboard",
            description=description or "No points recorded.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Page {page + 1}/{total_pages} • Total Ranked: {len(data)}")
        return embed

    @discord.ui.button(
        label="◀ Prev",
        style=discord.ButtonStyle.secondary,
        custom_id="leaderboard_prev"
    )
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Fetch latest data from database
        data = await fetchall(
            """
            SELECT user_id, points
            FROM helper_points
            WHERE guild_id = %s
            ORDER BY points DESC
            """,
            (interaction.guild.id,)
        )
        per_page = 10
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        
        # 2. Parse current page from embed footer
        current_page = 0
        try:
            embed = interaction.message.embeds[0]
            footer_text = embed.footer.text
            match = re.search(r"Page (\d+)/(\d+)", footer_text)
            if match:
                current_page = int(match.group(1)) - 1
        except Exception:
            pass

        # 3. Calculate new page
        new_page = max(0, min(current_page - 1, total_pages - 1))
        
        # 4. Update button states and edit message
        self.update_button_states(total_pages, new_page)
        embed = self.generate_embed(data, interaction.guild, new_page, per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Next ▶",
        style=discord.ButtonStyle.secondary,
        custom_id="leaderboard_next"
    )
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Fetch latest data from database
        data = await fetchall(
            """
            SELECT user_id, points
            FROM helper_points
            WHERE guild_id = %s
            ORDER BY points DESC
            """,
            (interaction.guild.id,)
        )
        per_page = 10
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        
        # 2. Parse current page from embed footer
        current_page = 0
        try:
            embed = interaction.message.embeds[0]
            footer_text = embed.footer.text
            match = re.search(r"Page (\d+)/(\d+)", footer_text)
            if match:
                current_page = int(match.group(1)) - 1
        except Exception:
            pass

        # 3. Calculate new page
        new_page = max(0, min(current_page + 1, total_pages - 1))
        
        # 4. Update button states and edit message
        self.update_button_states(total_pages, new_page)
        embed = self.generate_embed(data, interaction.guild, new_page, per_page)
        await interaction.response.edit_message(embed=embed, view=self)


async def update_persistent_leaderboard(guild):
    # 1. Fetch leaderboard config from DB
    config = await fetchone(
        "SELECT channel_id, message_id FROM leaderboard_config WHERE guild_id = %s",
        (guild.id,)
    )
    if not config or not config["channel_id"] or not config["message_id"]:
        return

    # 2. Fetch fresh rankings
    data = await fetchall(
        """
        SELECT user_id, points
        FROM helper_points
        WHERE guild_id = %s
        ORDER BY points DESC
        """,
        (guild.id,)
    )
    
    # 3. Retrieve channel and message
    try:
        channel = guild.get_channel(config["channel_id"])
        if not channel:
            channel = await guild.fetch_channel(config["channel_id"])
        message = await channel.fetch_message(config["message_id"])

        # 4. Preserve page context
        current_page = 0
        try:
            embed = message.embeds[0]
            footer_text = embed.footer.text
            match = re.search(r"Page (\d+)/(\d+)", footer_text)
            if match:
                current_page = int(match.group(1)) - 1
        except Exception:
            pass

        per_page = 10
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        page = max(0, min(current_page, total_pages - 1))

        # Recreate view
        view = LeaderboardView()
        view.update_button_states(total_pages, page)
        embed = view.generate_embed(data, guild, page, per_page)
        
        await message.edit(embed=embed, view=view)
        print(f"[LEADERBOARD PANEL] Automatically updated persistent leaderboard message for guild {guild.id}")
    except Exception as e:
        print(f"[LEADERBOARD PANEL ERROR] Failed to auto-update persistent leaderboard: {e}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_lock = asyncio.Lock()
        self.bot.add_view(TicketControlView())
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(OfficerControlView())
        self.bot.add_view(LeaderboardView())
        self.migrate_stats_file()
        self.auto_close_inactive_tickets.start()

    def migrate_stats_file(self):
        stats = load_json(DAILY_STATS_FILE)
        modified = False
        if stats:
            for date, day_data in stats.items():
                activities = day_data.get("activities", {})
                new_activities = {}
                day_modified = False
                extra_completed = 0
                for activity_name, count in list(activities.items()):
                    if " + " in activity_name:
                        parts = [p.strip() for p in activity_name.split(" + ") if p.strip()]
                        for part in parts:
                            new_activities[part] = new_activities.get(part, 0) + count
                        extra_completed += (len(parts) - 1) * count
                        day_modified = True
                        modified = True
                    else:
                        new_activities[activity_name] = new_activities.get(activity_name, 0) + count
                if day_modified:
                    day_data["activities"] = new_activities
                    day_data["completed_tickets"] = day_data.get("completed_tickets", 0) + extra_completed
            if modified:
                save_json(DAILY_STATS_FILE, stats)
                print("[STATS MIGRATION] Successfully cleaned and split historical combined activities in daily_stats.json")



    async def update_completed_tickets_embed(self, guild):
        async with self.embed_lock:
            config = await get_server_config(guild.id)
            if not config:
                return

            active_channel_id = config.get("active_tickets_channel_id")
            channel = None
            if active_channel_id:
                channel = guild.get_channel(active_channel_id)
                if not channel:
                    try:
                        channel = await guild.fetch_channel(active_channel_id)
                    except Exception:
                        channel = None

            if not channel:
                ticket_category_id = config.get("ticket_category_id")
                if ticket_category_id:
                    ticket_category = guild.get_channel(ticket_category_id)
                    if ticket_category:
                        channel = discord.utils.get(guild.text_channels, name="active-tickets", category=ticket_category)

            if not channel:
                return

            # Delete previous message if it exists
            prev_msg_id = config.get("completed_stats_message_id")
            if prev_msg_id:
                try:
                    prev_msg = await channel.fetch_message(prev_msg_id)
                    await prev_msg.delete()
                except Exception:
                    pass

            # Calculate total completed tickets
            stats = load_json(DAILY_STATS_FILE)
            total_completed = 0
            if stats:
                for date, data in stats.items():
                    total_completed += data.get("completed_tickets", 0)

            # Extract today's daily stats
            today = today_key()
            today_completed = 0
            today_cancelled = 0
            today_points = 0
            helper_text = "No helpers recorded today."
            activity_text = ""

            if stats and today in stats:
                today_data = stats[today]
                today_completed = today_data.get("completed_tickets", 0)
                today_cancelled = today_data.get("cancelled_tickets", 0)
                today_points = today_data.get("total_points_given", 0)

                # Top helpers today
                top_helpers = sorted(
                    today_data.get("helpers", {}).items(),
                    key=lambda item: item[1],
                    reverse=True
                )[:5]

                if top_helpers:
                    helper_text = ""
                    for index, (user_id, points) in enumerate(top_helpers, start=1):
                        member = guild.get_member(int(user_id))
                        name = member.mention if member else f"<@{user_id}>"
                        helper_text += f"**{index}.** {name} — **{points} points**\n"

                # Most requested activities today (resolve combined ones)
                raw_activities = today_data.get("activities", {})
                separated_activities = {}
                for activity, count in raw_activities.items():
                    for act in activity.split(" + "):
                        act = act.strip()
                        if act:
                            separated_activities[act] = separated_activities.get(act, 0) + count

                top_activities = sorted(
                    separated_activities.items(),
                    key=lambda item: item[1],
                    reverse=True
                )[:5]
                if top_activities:
                    activity_text = ""
                    for activity, count in top_activities:
                        activity_text += f"• **{activity}** — {count} ticket(s)\n"

            # Create beautiful premium embed
            embed = discord.Embed(
                title="🏆 Ticket Statistics Board",
                description=(
                    f"Thank you to all our amazing helpers and members for their dedication! "
                    f"Together, we keep the server thriving. 🙌\n\n"
                    f"✨ **All-Time Completed Tickets:** `{total_completed}`\n\n"
                    f"📅 **Today's Statistics ({today}):**\n"
                    f"• **Completed:** `{today_completed}` | **Cancelled:** `{today_cancelled}`\n"
                    f"• **Points Distributed:** `{today_points}`\n"
                ),
                color=discord.Color.from_rgb(255, 215, 0)  # Gold
            )
            embed.add_field(name="🥇 Top Helpers Today", value=helper_text, inline=True)
            if activity_text:
                embed.add_field(name="⚔️ Top Bosses Today", value=activity_text, inline=True)

            embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")
            if guild.icon:
                embed.set_footer(text="AQW MELAYU • Ticket Statistics", icon_url=guild.icon.url)
            else:
                embed.set_footer(text="AQW MELAYU • Ticket Statistics")

            try:
                new_msg = await channel.send(embed=embed)
                await execute(
                    "UPDATE ticket_config SET completed_stats_message_id = %s WHERE guild_id = %s",
                    (new_msg.id, guild.id)
                )
            except Exception as e:
                print(f"[TICKETS] Failed to send completed tickets embed: {e}")

    def cog_unload(self):
        self.auto_close_inactive_tickets.cancel()

    @commands.Cog.listener()
    async def on_message(self, message):
        # Update ticket activity if message is in an active ticket thread
        if not message.author.bot:
            ticket = await get_active_ticket_by_channel(message.channel.id)
            if ticket:
                await update_ticket_activity(ticket["id"])

        # Check if the message is in the active tickets channel to keep the embed at the bottom
        if message.guild:
            config = await get_server_config(message.guild.id)
            if config:
                active_channel_id = config.get("active_tickets_channel_id")
                
                is_active_tickets_channel = False
                if active_channel_id and message.channel.id == active_channel_id:
                    is_active_tickets_channel = True
                elif not active_channel_id:
                    ticket_category_id = config.get("ticket_category_id")
                    if ticket_category_id and getattr(message.channel, "category_id", None) == ticket_category_id:
                        if message.channel.name == "active-tickets":
                            is_active_tickets_channel = True

                if is_active_tickets_channel:
                    # Ignore the bot's own stats embed to avoid infinite loops
                    if message.author == self.bot.user and message.embeds and message.embeds[0].title in ["🏆 Total Tickets Completed", "🏆 Ticket Statistics Board"]:
                        return
                    
                    # Delete the old embed and send a new one
                    await self.update_completed_tickets_embed(message.guild)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        parent_channel = thread.parent
        if not parent_channel:
            return

        config = await get_server_config(thread.guild.id)
        if not config:
            return

        active_channel_id = config.get("active_tickets_channel_id")
        is_active_tickets_channel = False
        if active_channel_id and parent_channel.id == active_channel_id:
            is_active_tickets_channel = True
        elif not active_channel_id:
            ticket_category_id = config.get("ticket_category_id")
            if ticket_category_id and getattr(parent_channel, "category_id", None) == ticket_category_id:
                if parent_channel.name == "active-tickets":
                    is_active_tickets_channel = True

        if is_active_tickets_channel:
            await self.update_completed_tickets_embed(thread.guild)

    @commands.Cog.listener()
    async def on_ready(self):
        print("[TICKETS] Cog is ready, verifying completed tickets embeds...")
        for guild in self.bot.guilds:
            try:
                await self.update_completed_tickets_embed(guild)
            except Exception as e:
                print(f"[TICKETS] Failed to initialize embed for guild {guild.id}: {e}")

    @tasks.loop(minutes=5)
    async def auto_close_inactive_tickets(self):
        await self.bot.wait_until_ready()

        active_tickets = await fetchall(
            """
            SELECT *
            FROM active_tickets
            """
        )

        if not active_tickets:
            return

        now = time.time()

        for data in active_tickets:

            last_activity = data.get(
                "last_activity",
                data.get("created_at", now)
            )

            inactive_time = now - last_activity

            channel = None

            for g in self.bot.guilds:
                channel = g.get_channel(int(data["channel_id"])) or g.get_thread(int(data["channel_id"]))

                if channel:
                    break

            if not channel:
                await cleanup_ticket(data["id"])
                print(f"[TICKETS] Cleaned up orphaned ticket database record for channel ID {data['channel_id']}")
                continue

            # 🔔 WARNING
            if (
                inactive_time >= (
                    INACTIVE_TIMEOUT_SECONDS
                    - WARNING_BEFORE_CLOSE
                )
                and not data["warned"]
            ):

                try:
                    await channel.send(
                        "⚠️ This ticket has been inactive for "
                        "**1 hour 30 minutes**.\n"
                        "It will be automatically closed in "
                        "**30 minutes** if no activity."
                    )
                except:
                    pass

                await execute(
                    """
                    UPDATE active_tickets
                    SET warned = TRUE
                    WHERE id = %s
                    """,
                    (data["id"],)
                )

            # ⛔ AUTO CLOSE
            if inactive_time >= INACTIVE_TIMEOUT_SECONDS:

                try:
                    await channel.send(
                        "⏰ Ticket auto-closed due to "
                        "**2 hours of inactivity**.\n"
                        "No points were given."
                    )
                except:
                    pass

                await cleanup_ticket(data["id"])
                
                guild_ref = channel.guild if hasattr(channel, "guild") else None
                if guild_ref:
                    try:
                        await remove_requester_overwrite(guild_ref, data["requester_id"], data["id"])
                    except Exception as e:
                        print(f"Failed to remove requester overwrite on auto-close: {e}")

                update_daily_stats(
                    status="cancelled",
                    activity=data["activity"],
                    points=0,
                    requester_id=data["requester_id"],
                    helper_ids=[]
                )

                try:
                    await close_ticket_channel(channel, "Inactive for 2 hours")
                except:
                    pass

    @app_commands.command(
        name="ticketsetup",
        description="Setup ticket system for this server"
    )
    @app_commands.describe(
        officer_role="Role allowed to manage tickets",
        helper_role="Role allowed to join as helper",
        bonus_role="Role that gets extra points",
        ticket_category="Category where ticket channels will be created",
        log_channel="Channel for completed ticket logs",
        active_tickets_channel="Optional: Specific text channel where active ticket threads will be created"
    )
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        officer_role: discord.Role,
        helper_role: discord.Role,
        bonus_role: discord.Role,
        ticket_category: discord.CategoryChannel,
        log_channel: discord.TextChannel,
        active_tickets_channel: discord.TextChannel = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only server administrators can setup this bot.",
                ephemeral=True
            )
            return

        await execute(
            """
            INSERT INTO ticket_config
            (
                guild_id,
                officer_role_id,
                helper_role_id,
                bonus_role_id,
                ticket_category_id,
                ticket_log_channel_id,
                active_tickets_channel_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)

            ON DUPLICATE KEY UPDATE
                officer_role_id = VALUES(officer_role_id),
                helper_role_id = VALUES(helper_role_id),
                bonus_role_id = VALUES(bonus_role_id),
                ticket_category_id = VALUES(ticket_category_id),
                ticket_log_channel_id = VALUES(ticket_log_channel_id),
                active_tickets_channel_id = VALUES(active_tickets_channel_id)
            """,
            (
                interaction.guild.id,
                officer_role.id,
                helper_role.id,
                bonus_role.id,
                ticket_category.id,
                log_channel.id,
                active_tickets_channel.id if active_tickets_channel else None
            )
        )

        try:
            await self.update_completed_tickets_embed(interaction.guild)
        except Exception as e:
            print(f"[TICKETS] Failed to update completed tickets embed on setup: {e}")

        await interaction.response.send_message(
            "✅ Ticket system setup completed for this server.",
            ephemeral=True
        )
    @app_commands.command(
        name="ticketpanel",
        description="Send the Ultra Ticket panel"
    )
    async def ticketpanel(self, interaction: discord.Interaction):
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Officer can use this command.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎟️ AQW MELAYU Ultra Ticket System",
            description=(
                "🔷 **Ultra Weeklies**\n"
                "• 7 Points - Ultra Speaker\n"
                "• 7 Points - Ultra Gramiel\n"
                "• 5 Points - Champion Drakath\n"
                "• 5 Points - Ultra Dage\n"
                "• 5 Points - Ultra Darkon\n"
                "• 5 Points - Ultra Drago\n"
                "• 5 Points - Ultra Nulgath\n\n"
                "🔶 **Ultra Dailies (4-Man)**\n"
                "• 2 Points - UltraEngineer\n"
                "• 2 Points - UltraEzrajal\n"
                "• 2 Points - UltraTyndarius\n"
                "• 2 Points - UltraWarden\n\n"
                "🔷 **Ultra Dailies (7-Man)**\n"
                "• 4 Points - Astral Shrine\n"
                "• 4 Points - Kathool Depths\n"
                "• 1 Point - Apex Azalith\n"
                "• 2 Points - Void Flibbi\n"
                "• 2 Points - Void Nightbane\n"
                "• 2 Points - Void Xyfrag\n"
                "• 1 Point - Deimos\n"
                "• 1 Point - Frozenlair\n"
                "• 1 Point - Sevencircleswar\n"
                "• 2 Points - Flameusurper\n"
                "• 2 Points - Lavarockshore\n\n"
                "⛩️ **TempleShrine (per side/completion)**\n"
                "• 5 Points - TempleShrine (Mid)\n"
                "• 2 Points - TempleShrine (Left)\n"
                "• 2 Points - TempleShrine (Right)\n\n"
                "_Spamming mode uses Left/Middle/Right points per kill_\n\n"
                "👹 **GrimChallenge (7-Man)**\n"
                "• 10 Points - GrimChallenge\n\n"
                "❌ **NO BOTTING** ❌\n"
                "**Penggunaan BOT CLIENT akan disuspend**"
            ),
            color=discord.Color.purple()
        )

        embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")

        embed.set_footer(text="AQW MELAYU • Ultra Ticket Testing Phase")

        await interaction.response.send_message(
            embed=embed,
            view=TicketPanelView()
        )

    @app_commands.command(
        name="points",
        description="Check your helper points"
    )
    async def points(self, interaction: discord.Interaction):
        result = await fetchone(
            """
            SELECT points FROM helper_points
            WHERE guild_id = %s
            AND user_id = %s
            """,
            (
                interaction.guild.id,
                interaction.user.id
            )
        )

        points = result["points"] if result else 0

        await interaction.response.send_message(
            f"🏆 {interaction.user.mention}, you have **{points} point(s)**.",
            ephemeral=True
        )

    @app_commands.command(
        name="leaderboard",
        description="Show helper points leaderboard"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        data = await fetchall(
            """
            SELECT user_id, points
            FROM helper_points
            WHERE guild_id = %s
            ORDER BY points DESC
            """,
            (interaction.guild.id,)
        )

        if not data:
            await interaction.response.send_message(
                "No points recorded yet.",
                ephemeral=True
            )
            return

        view = LeaderboardView()
        per_page = 10
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        view.update_button_states(total_pages, 0)
        embed = view.generate_embed(data, interaction.guild, 0, per_page)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="resetleaderboard",
        description="Reset all ticket points leaderboard"
    )
    async def resetleaderboard(self, interaction: discord.Interaction):
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Officer can reset leaderboard.",
                ephemeral=True
            )
            return

        await execute(
            """
            DELETE FROM helper_points
            WHERE guild_id = %s
            """,
            (interaction.guild.id,)
        )

        await interaction.response.send_message(
            "🧹 Ticket leaderboard has been reset successfully."
        )

        try:
            await update_persistent_leaderboard(interaction.guild)
        except Exception as e:
            print(f"[LEADERBOARD] Failed to update leaderboard on reset: {e}")

    @app_commands.command(
        name="dailystats",
        description="Show today's ticket statistics"
    )
    async def dailystats(self, interaction: discord.Interaction):
        stats = load_json(DAILY_STATS_FILE)
        today = today_key()

        if today not in stats:
            await interaction.response.send_message(
                "📊 No ticket stats recorded for today yet.",
                ephemeral=True
            )
            return

        data = stats[today]

        top_helpers = sorted(
            data["helpers"].items(),
            key=lambda item: item[1],
            reverse=True
        )[:5]

        helper_text = ""
        for index, (user_id, points) in enumerate(top_helpers, start=1):
    
            member = interaction.guild.get_member(int(user_id))
            name = member.mention if member else f"User ID {user_id}"

            helper_text += f"**{index}.** {name} — **{points} points**\n"
        if not helper_text:
            helper_text = "No helpers recorded today."

        raw_activities = data.get("activities", {})
        separated_activities = {}
        for activity, count in raw_activities.items():
            for act in activity.split(" + "):
                act = act.strip()
                if act:
                    separated_activities[act] = separated_activities.get(act, 0) + count

        top_activities = sorted(
            separated_activities.items(),
            key=lambda item: item[1],
            reverse=True
        )[:5]

        activity_text = ""
        for activity, count in top_activities:
            activity_text += f"**{activity}** — {count} ticket(s)\n"

        embed = discord.Embed(
            title=f"📊 Daily Ticket Stats — {today}",
            description=(
                f"**Completed Tickets:** {data['completed_tickets']}\n"
                f"**Cancelled Tickets:** {data['cancelled_tickets']}\n"
                f"**Total Points Given:** {data['total_points_given']}\n\n"
                f"**Top Helpers Today:**\n{helper_text}\n"
                f"**Most Requested Activities:**\n{activity_text}"
            ),
            color=discord.Color.teal()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="leaderboard_panel",
        description="Post the permanent interactive Helper Leaderboard panel (Officer Only)"
    )
    @app_commands.describe(
        channel="Optional channel to send the panel in"
    )
    async def leaderboard_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only Officers or Administrators can configure the leaderboard panel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        target_channel = channel or interaction.channel
        guild_id = interaction.guild.id

        # 1. Query points
        data = await fetchall(
            """
            SELECT user_id, points
            FROM helper_points
            WHERE guild_id = %s
            ORDER BY points DESC
            """,
            (guild_id,)
        )

        # 2. Build view and embed
        view = LeaderboardView()
        per_page = 10
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        view.update_button_states(total_pages, 0)
        embed = view.generate_embed(data, interaction.guild, 0, per_page)

        # 3. Send message
        message = await target_channel.send(embed=embed, view=view)

        # 4. Save channel and message references in MySQL for auto-updating
        await execute(
            """
            INSERT INTO leaderboard_config (guild_id, channel_id, message_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                channel_id = VALUES(channel_id),
                message_id = VALUES(message_id)
            """,
            (guild_id, target_channel.id, message.id)
        )

        await interaction.followup.send(
            f"✅ Helper Leaderboard panel has been posted in {target_channel.mention}!\n"
            f"This panel will automatically self-update in real-time whenever points are gained or reset.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))