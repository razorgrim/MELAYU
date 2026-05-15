import json
import discord
import random
from discord.ext import commands
from discord import app_commands
import time
from discord.ext import tasks
from datetime import datetime
from database import execute, fetchone, fetchall

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


def get_max_helpers(category):
    if "7-Man" in category or "Daily" in category:
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
        stats[today]["completed_tickets"] += 1
    elif status == "cancelled":
        stats[today]["cancelled_tickets"] += 1

    stats[today]["activities"][activity] = stats[today]["activities"].get(activity, 0) + 1

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

    @discord.ui.button(label="Ultra Weeklies", style=discord.ButtonStyle.primary, emoji="🔷")
    async def ultra_weeklies(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Ultra Weeklies** activity:",
            view=ActivityButtonView("Ultra Weeklies"),
            ephemeral=True
        )

    @discord.ui.button(label="Ultra Dailies 4-Man", style=discord.ButtonStyle.success, emoji="🔶")
    async def ultra_dailies_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Ultra Dailies 4-Man** activity:",
            view=ActivityButtonView("Ultra Dailies 4-Man"),
            ephemeral=True
        )

    @discord.ui.button(label="Daily Quests", style=discord.ButtonStyle.success, emoji="🔷")
    async def ultra_dailies_7(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **Daily Quests** activity:",
            view=ActivityButtonView("Daily Quests"),
            ephemeral=True
        )

    @discord.ui.button(label="TempleShrine", style=discord.ButtonStyle.secondary, emoji="⛩️")
    async def temple_shrine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **TempleShrine** activity:",
            view=ActivityButtonView("TempleShrine"),
            ephemeral=True
        )

    @discord.ui.button(label="GrimChallenge 7-Man", style=discord.ButtonStyle.danger, emoji="👹")
    async def grim_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Select **GrimChallenge 7-Man** activity:",
            view=ActivityButtonView("GrimChallenge 7-Man"),
            ephemeral=True
        )
    
    @discord.ui.button(label="Hard Farm/Others", style=discord.ButtonStyle.secondary, emoji="🛠️")
    async def hard_farm_others(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HardFarmModal())


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
            placeholder="Select one or more ultras...",
            options=options,
            min_values=1,
            max_values=len(options)
        )

    async def callback(self, interaction: discord.Interaction):
        # No role restriction for creating ticket

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

        selected_activities = self.values
        total_points = sum(ACTIVITIES[self.category][activity] for activity in selected_activities)

        config = await get_server_config(interaction.guild.id)

        if not config:
            await interaction.response.send_message(
                "❌ Ticket system not setup. Admin must run /ticketsetup.",
                ephemeral=True
            )
            return

        helper_role = interaction.guild.get_role(config["helper_role_id"])
        max_helpers = get_max_helpers(self.category)

        ticket_category = interaction.guild.get_channel(config["ticket_category_id"])

        if ticket_category is None:
            await interaction.response.send_message(
                "❌ Category `Ticket Category` does not exist. Please create it first.",
                ephemeral=True
            )
            return

        import random

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

        first_activity = selected_activities[0].lower().replace(" ", "-")
        channel_name = f"ticket-{first_activity}-{room_number}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            ),
        }

        if helper_role:
            overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=ticket_category,
            overwrites=overwrites,
            reason="Combined ultra ticket created"
        )

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
                created_at,
                last_activity
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """,
            (
                interaction.guild.id,
                interaction.user.id,
                channel.id,
                " + ".join(selected_activities),
                self.category,
                total_points,
                False,
                max_helpers,
                room_number,
                False,
                False,
                False,
                time.time(),
                time.time()
            )
        )

        activity_list = "\n".join(
            f"- {activity} = {ACTIVITIES[self.category][activity]} point(s)"
            for activity in selected_activities
        )

        embed = discord.Embed(
            title="🎟️ Combined Ultra Ticket Created",
            description=(
                f"**Room:** `{room_number}`\n"
                f"**Requester:** {interaction.user.mention}\n"
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

        await interaction.response.send_message(
            f"✅ Combined ticket created: {channel.mention}",
            ephemeral=True
        )
        


class ActivityButtonView(discord.ui.View):
    def __init__(self, category):
        super().__init__(timeout=120)
        self.add_item(ActivityMultiSelect(category))

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

        channel_name = f"ticket-hardfarm-{room_number}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            ),
        }

        if helper_role:
            overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=ticket_category,
            overwrites=overwrites,
            reason="Hard Farm/Others ticket created"
        )

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

        helper_id = int(
            extract_user_id(self.helper.value)
        )

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

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join as Helper",
        style=discord.ButtonStyle.success,
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

        if not user_has_role_id(
            interaction.user,
            config["helper_role_id"]
        ):
            await interaction.response.send_message(
                "❌ You do not have the Helper role.",
                ephemeral=True
            )
            return

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
        style=discord.ButtonStyle.primary,
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
                    f"**Ticket:** `{interaction.channel.name}`\n"
                    f"**Activity:** {ticket_data['activity']}\n"
                    f"**Points Given:** `0`"
                ),
                discord.Color.red()
            )

            await execute(
                """
                DELETE FROM active_ticket_helpers
                WHERE ticket_id = %s
                """,
                (ticket_data["id"],)
            )

            await execute(
                """
                DELETE FROM active_ticket_helper_points
                WHERE ticket_id = %s
                """,
                (ticket_data["id"],)
            )

            await execute(
                """
                DELETE FROM active_tickets
                WHERE id = %s
                """,
                (ticket_data["id"],)
            )

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

            await interaction.channel.delete(
                reason="Ticket cancelled"
            )

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
        await execute(
            """
            DELETE FROM active_ticket_helpers
            WHERE ticket_id = %s
            """,
            (ticket_data["id"],)
        )

        await execute(
            """
            DELETE FROM active_ticket_helper_points
            WHERE ticket_id = %s
            """,
            (ticket_data["id"],)
        )

        await execute(
            """
            DELETE FROM active_tickets
            WHERE id = %s
            """,
            (ticket_data["id"],)
        )

        update_daily_stats(
            status="completed",
            activity=ticket_data["activity"],
            points=points,
            requester_id=requester_id,
            helper_ids=helper_ids
        )

        await send_ticket_log(
            interaction.guild,
            "🏆 Ticket Completed",
            (
                f"**Closed by:** {interaction.user.mention}\n"
                f"**Ticket:** `{interaction.channel.name}`\n"
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

        await interaction.channel.delete(
            reason="Ticket completed"
        )     

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketControlView())
        self.auto_close_inactive_tickets.start()

    def cog_unload(self):
        self.auto_close_inactive_tickets.cancel()

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
                channel = g.get_channel(
                    int(data["channel_id"])
                )

                if channel:
                    break

            if not channel:
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

                await execute(
                    """
                    DELETE FROM active_ticket_helpers
                    WHERE ticket_id = %s
                    """,
                    (data["id"],)
                )

                await execute(
                    """
                    DELETE FROM active_ticket_helper_points
                    WHERE ticket_id = %s
                    """,
                    (data["id"],)
                )

                await execute(
                    """
                    DELETE FROM active_tickets
                    WHERE id = %s
                    """,
                    (data["id"],)
                )

                update_daily_stats(
                    status="cancelled",
                    activity=data["activity"],
                    points=0,
                    requester_id=data["requester_id"],
                    helper_ids=[]
                )

                try:
                    await channel.delete(
                        reason="Inactive for 2 hours"
                    )
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
        log_channel="Channel for completed ticket logs"
    )
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        officer_role: discord.Role,
        helper_role: discord.Role,
        bonus_role: discord.Role,
        ticket_category: discord.CategoryChannel,
        log_channel: discord.TextChannel
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
                ticket_log_channel_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)

            ON DUPLICATE KEY UPDATE
                officer_role_id = VALUES(officer_role_id),
                helper_role_id = VALUES(helper_role_id),
                bonus_role_id = VALUES(bonus_role_id),
                ticket_category_id = VALUES(ticket_category_id),
                ticket_log_channel_id = VALUES(ticket_log_channel_id)
            """,
            (
                interaction.guild.id,
                officer_role.id,
                helper_role.id,
                bonus_role.id,
                ticket_category.id,
                log_channel.id
            )
        )

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
                "Welcome to the **AQW MELAYU Ticket System**.\n"
                "Gunakan panel ini untuk request bantuan Ultra, Daily Quest, TempleShrine, GrimChallenge, atau Hard Farm/Others.\n\n"
                "📌 **How to Create Ticket**\n"
                "1. Click category button below.\n"
                "2. Select one or more activity.\n"
                "3. Bot akan create private ticket channel.\n"
                "4. Tunggu helper join.\n"
                "5. Bila run selesai, tekan **Complete Ticket**.\n"
                "6. Officer akan review, set points jika perlu, dan close ticket.\n\n"
                "✅ **Requirement**\n"
                f"• One user can only have **1 active ticket** at a time.\n"
                "• Verify your role to gain **extra points bonus**.\n\n"
                "🙋 **For Helpers**\n"
                f"• Must have **{HELPER_ROLE}** role to join as helper.\n"
                "• Helper boleh **Join** atau **Leave** sebelum ticket completed.\n"
                "• Points hanya diberi selepas Officer close completed ticket.\n\n"
                "🏆 **Points System**\n"
                "• Normal Ultra/Daily points are calculated automatically.\n"
                "• Hard Farm/Others points will be manually set by Officer.\n"
                "• Requester and helpers will receive points after approval.\n"
                "• MELAYU member may receive bonus points if eligible.\n\n"
                "⏰ **Auto-Close System**\n"
                "• Ticket inactive for **1 hour 30 minutes** will receive warning.\n"
                "• Ticket inactive for **2 hours** will be auto-closed.\n"
                "• Auto-closed/cancelled tickets will not give points.\n\n"
                "⚠️ **Important**\n"
                "• Please only create ticket when you are ready to run.\n"
                "• Helper who leave ticket will not receive points."
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
            LIMIT 10
            """,
            (interaction.guild.id,)
        )

        if not data:
            await interaction.response.send_message(
                "No points recorded yet.",
                ephemeral=True
            )
            return

        description = ""

        for index, row in enumerate(data, start=1):
            member = interaction.guild.get_member(row["user_id"])

            name = (
                member.mention
                if member
                else f"User ID {row['user_id']}"
            )

            description += (
                f"**{index}.** {name} — "
                f"**{row['points']} points**\n"
            )

        embed = discord.Embed(
            title="🏆 Points Leaderboard",
            description=description,
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)

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

        top_activities = sorted(
            data["activities"].items(),
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
async def setup(bot):
    await bot.add_cog(Tickets(bot))