import json
import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from database import execute, fetchone, fetchall


HELPER_QUESTIONS = [
    ("comp_class", "What basic Comp/Class for ultras?"),
    ("loop_taunt", "How do we Loop Taunt?"),
    ("drakath_taunt", "When we need to taunt on Champion Drakath?"),
    ("counter_attack", "What need to do if \"Counter Attack\"?"),
    ("cannot_resist", "What need to do if \"You Cannot Resist\"?"),
    ("moon_sun_coverage", "What need to do if \"Moon Coverage / Sun Coverage\"?")
]
OPTIONAL_QUESTIONS = set()


async def get_helper_config(guild_id):
    return await fetchone(
        """
        SELECT * FROM helper_config
        WHERE guild_id = %s
        """,
        (guild_id,)
    )


def get_review_category_id(config):
    return config.get("review_category_id") or config.get("review_channel_id")


async def get_helper_log_channel(guild, review_category, officer_role):
    log_channel = discord.utils.get(review_category.text_channels, name="helper-log")
    if log_channel:
        return log_channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        officer_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )
    }
    return await guild.create_text_channel(
        name="helper-log",
        category=review_category,
        overwrites=overwrites,
        reason="Officer-only helper application log channel"
    )


async def send_helper_log(guild, application, action, reviewer_id=None, review_reason=None):
    config = await get_helper_config(guild.id)
    if not config:
        return

    review_category = guild.get_channel(config.get("review_category_id")) if config.get("review_category_id") else None
    if not isinstance(review_category, discord.CategoryChannel):
        return

    officer_role = guild.get_role(config.get("officer_role_id")) if config.get("officer_role_id") else None
    if not officer_role:
        return

    try:
        log_channel = await get_helper_log_channel(guild, review_category, officer_role)
        applicant_mention = f"<@{application['user_id']}>"
        reviewer_mention = f"<@{reviewer_id}>" if reviewer_id else "Pending review"
        embed = discord.Embed(
            title="Helper Application Log",
            description=(
                f"Applicant: {applicant_mention}\n"
                f"Reviewer: {reviewer_mention}\n"
                f"Result: {action.capitalize()}"
            ),
            color=(
                discord.Color.green() if action == "accepted"
                else discord.Color.red() if action == "rejected"
                else discord.Color.purple()
            )
        )
        if action == "rejected":
            embed.add_field(name="Reason", value=review_reason or "No reason provided.", inline=False)
        embed.set_footer(text=f"Application ID {application['id']}")
        await log_channel.send(embed=embed)
    except Exception:
        pass


async def helper_is_officer(member):
    config = await get_helper_config(member.guild.id)

    if not config:
        return False

    return any(role.id == config["officer_role_id"] for role in member.roles)


async def get_helper_application(guild_id, user_id):
    return await fetchone(
        """
        SELECT * FROM helper_applications
        WHERE guild_id = %s AND user_id = %s
        """,
        (guild_id, user_id)
    )


async def get_helper_application_by_id(application_id):
    return await fetchone(
        """
        SELECT * FROM helper_applications
        WHERE id = %s
        """,
        (application_id,)
    )


async def build_application_embed(application, guild):
    answers = json.loads(application["answers"])
    applicant = guild.get_member(application["user_id"])
    applicant_name = applicant.display_name if applicant else f"User ID {application['user_id']}"

    embed = discord.Embed(
        title="Helper Application",
        description=(
            f"Applicant: {applicant_name} ({application['user_id']})\n"
            f"Status: {application['status'].capitalize()}"
        ),
        color=discord.Color.gold()
    )

    for key, question in HELPER_QUESTIONS:
        value = answers.get(key) or "(No answer)"
        if key in OPTIONAL_QUESTIONS and not value.strip():
            value = "(Optional answer not provided)"
        embed.add_field(name=question, value=value, inline=False)

    if application["status"] != "pending":
        reviewer = guild.get_member(application["reviewer_id"]) if application.get("reviewer_id") else None
        embed.add_field(
            name="Review Result",
            value=(
                f"Status: **{application['status'].capitalize()}**\n"
                f"Reviewer: {reviewer.mention if reviewer else 'Unknown'}\n"
                f"Reason: {application['review_reason'] or 'None'}"
            ),
            inline=False
        )

    return embed


async def submit_helper_application(interaction: discord.Interaction, applicant_id: int, answers: dict, bot):
    config = await get_helper_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message(
            "❌ Helper application is not configured yet. Ask an administrator to run /helpersetup.",
            ephemeral=True
        )
        return

    existing_application = await get_helper_application(interaction.guild.id, applicant_id)
    if existing_application and existing_application["status"] == "pending":
        await interaction.response.send_message(
            "❌ You already have a pending helper application. Please wait for an officer to review it.",
            ephemeral=True
        )
        return

    if existing_application and existing_application["status"] == "accepted":
        await interaction.response.send_message(
            "✅ Your helper application is already accepted. No further application is needed.",
            ephemeral=True
        )
        return

    serialized_answers = json.dumps(answers, ensure_ascii=False)
    review_category_id = get_review_category_id(config)
    review_category = interaction.guild.get_channel(review_category_id)
    officer_role = interaction.guild.get_role(config["officer_role_id"])

    if review_category is None or not isinstance(review_category, discord.CategoryChannel):
        await interaction.response.send_message(
            "❌ The configured helper review category was not found. Ask an administrator to update the setup.",
            ephemeral=True
        )
        return

    if officer_role is None:
        await interaction.response.send_message(
            "❌ The configured officer role was not found. Ask an administrator to update the setup.",
            ephemeral=True
        )
        return

    applicant_member = interaction.guild.get_member(applicant_id)
    if applicant_member is None:
        try:
            applicant_member = await interaction.guild.fetch_member(applicant_id)
        except Exception:
            applicant_member = None

    if applicant_member is None:
        await interaction.response.send_message(
            "❌ Unable to locate the applicant in the server.",
            ephemeral=True
        )
        return

    if existing_application and existing_application["status"] == "rejected":
        await execute(
            """
            UPDATE helper_applications
            SET status = %s,
                reviewer_id = NULL,
                review_reason = NULL,
                answers = %s,
                updated_at = CURRENT_TIMESTAMP(),
                message_id = NULL,
                channel_id = NULL
            WHERE id = %s
            """,
            (
                "pending",
                serialized_answers,
                existing_application["id"]
            )
        )
        application_id = existing_application["id"]
    else:
        await execute(
            """
            INSERT INTO helper_applications
            (guild_id, user_id, status, answers)
            VALUES (%s, %s, %s, %s)
            """,
            (
                interaction.guild.id,
                applicant_id,
                "pending",
                serialized_answers
            )
        )
        application = await get_helper_application(interaction.guild.id, applicant_id)
        application_id = application["id"]

    application = await get_helper_application_by_id(application_id)

    ticket_number = (config.get("helper_ticket_counter") or 0) + 1
    await execute(
        """
        UPDATE helper_config
        SET helper_ticket_counter = %s
        WHERE guild_id = %s
        """,
        (ticket_number, interaction.guild.id)
    )

    try:
        log_channel = await get_helper_log_channel(interaction.guild, review_category, officer_role)
        log_embed = discord.Embed(
            title="Helper Application Submitted",
            description=(
                f"Applicant: {applicant_member.mention} ({applicant_id})\n"
                f"Review ticket: helper-application-{ticket_number}"
            ),
            color=discord.Color.purple()
        )
        await log_channel.send(embed=log_embed)
    except Exception:
        pass

    channel_name = f"helper-application-{ticket_number}"

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        applicant_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        officer_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),
        interaction.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True
        )
    }

    try:
        review_ticket_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=review_category,
            overwrites=overwrites,
            reason="Helper application review ticket"
        )

        await execute(
            """
            UPDATE helper_applications
            SET channel_id = %s
            WHERE id = %s
            """,
            (review_ticket_channel.id, application_id)
        )

        review_view = HelperReviewView(application_id, bot)
        review_embed = await build_application_embed(application, interaction.guild)
        review_message = await review_ticket_channel.send(embed=review_embed, view=review_view)
        await execute(
            """
            UPDATE helper_applications
            SET message_id = %s
            WHERE id = %s
            """,
            (review_message.id, application_id)
        )
    except Exception as exc:
        print(f"[helper] submit_helper_application error: {exc}")
        await interaction.response.send_message(
            "❌ Something went wrong while creating the helper review ticket. Please ask an administrator to check the bot permissions and category settings.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"✅ Your helper application has been submitted and is under review: {review_ticket_channel.mention}",
        ephemeral=True
    )


class HelperApplicationModal1(discord.ui.Modal, title="Helper Application - Part 1"):
    comp_class = discord.ui.TextInput(
        label="Comp/Class for ultras",
        placeholder="What basic Comp/Class do you use for ultras?",
        required=True,
        max_length=200
    )
    loop_taunt = discord.ui.TextInput(
        label="How do we Loop Taunt?",
        placeholder="Explain loop taunting steps / timing...",
        required=True,
        max_length=200
    )
    drakath_taunt = discord.ui.TextInput(
        label="When to taunt on Champion Drakath?",
        placeholder="At what HP percentages or events?",
        required=True,
        max_length=200
    )

    def __init__(self, applicant_id, bot):
        super().__init__()
        self.applicant_id = applicant_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        part1_answers = {
            "comp_class": self.comp_class.value.strip(),
            "loop_taunt": self.loop_taunt.value.strip(),
            "drakath_taunt": self.drakath_taunt.value.strip()
        }
        
        view = ApplyHelperPart2View(self.applicant_id, part1_answers, self.bot)
        await interaction.response.send_message(
            "📋 **Part 1 complete!** Please click the button below to fill out the remaining 3 questions in **Part 2**.",
            view=view,
            ephemeral=True
        )


class ApplyHelperPart2View(discord.ui.View):
    def __init__(self, applicant_id, part1_answers, bot):
        super().__init__(timeout=300)
        self.applicant_id = applicant_id
        self.part1_answers = part1_answers
        self.bot = bot

    @discord.ui.button(label="Fill Part 2", style=discord.ButtonStyle.primary, custom_id="apply_as_helper_part2_btn")
    async def fill_part2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            HelperApplicationModal2(self.applicant_id, self.part1_answers, self.bot)
        )


class HelperApplicationModal2(discord.ui.Modal, title="Helper Application - Part 2"):
    counter_attack = discord.ui.TextInput(
        label="What to do if Counter Attack?",
        placeholder="What should you do when Counter Attack happens?",
        required=True,
        max_length=200
    )
    cannot_resist = discord.ui.TextInput(
        label="What to do if You Cannot Resist?",
        placeholder="What action should be taken when You Cannot Resist?",
        required=True,
        max_length=200
    )
    moon_sun_coverage = discord.ui.TextInput(
        label="Moon Coverage / Sun Coverage?",
        placeholder="What should you do during Moon/Sun Coverage?",
        required=True,
        max_length=200
    )

    def __init__(self, applicant_id, part1_answers, bot):
        super().__init__()
        self.applicant_id = applicant_id
        self.part1_answers = part1_answers
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            **self.part1_answers,
            "counter_attack": self.counter_attack.value.strip(),
            "cannot_resist": self.cannot_resist.value.strip(),
            "moon_sun_coverage": self.moon_sun_coverage.value.strip()
        }

        try:
            await interaction.message.delete()
        except Exception:
            pass

        await submit_helper_application(interaction, self.applicant_id, answers, self.bot)


class ApplyHelperView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Apply as Helper", style=discord.ButtonStyle.primary, custom_id="apply_as_helper_btn")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HelperApplicationModal1(interaction.user.id, self.bot))


class RejectReviewModal(discord.ui.Modal, title="Helper Application Rejection"):
    reason = discord.ui.TextInput(
        label="Why is this application rejected?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="Optional review notes for the applicant"
    )

    def __init__(self, application_id, bot):
        super().__init__()
        self.application_id = application_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not await helper_is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only officers can reject helper applications.",
                ephemeral=True
            )
            return

        application = await get_helper_application_by_id(self.application_id)

        if not application or application["status"] != "pending":
            await interaction.response.send_message(
                "❌ This application has already been reviewed.",
                ephemeral=True
            )
            return

        review_reason = self.reason.value.strip() or None

        await execute(
            """
            UPDATE helper_applications
            SET status = %s,
                reviewer_id = %s,
                review_reason = %s
            WHERE id = %s
            """,
            (
                "rejected",
                interaction.user.id,
                review_reason,
                self.application_id
            )
        )

        application = await get_helper_application_by_id(self.application_id)
        await send_helper_log(interaction.guild, application, "rejected", reviewer_id=interaction.user.id, review_reason=review_reason)

        # Get review channel from guild using channel_id
        review_channel = None
        if application.get("channel_id"):
            review_channel = interaction.guild.get_channel(int(application["channel_id"]))
            if not review_channel:
                try:
                    review_channel = await interaction.guild.fetch_channel(int(application["channel_id"]))
                except Exception:
                    review_channel = None

        if not review_channel:
            review_channel = interaction.channel

        if review_channel:
            try:
                original_message = await review_channel.fetch_message(application["message_id"])
            except Exception:
                original_message = None

            if original_message:
                updated_application = await get_helper_application_by_id(self.application_id)
                embed = await build_application_embed(updated_application, interaction.guild)
                disabled_view = discord.ui.View(timeout=None)
                disabled_view.add_item(discord.ui.Button(label="Accept", style=discord.ButtonStyle.success, disabled=True, custom_id=f"disabled_helper_accept:{self.application_id}"))
                disabled_view.add_item(discord.ui.Button(label="Reject", style=discord.ButtonStyle.danger, disabled=True, custom_id=f"disabled_helper_reject:{self.application_id}"))
                await original_message.edit(embed=embed, view=disabled_view)

        applicant = self.bot.get_user(application["user_id"]) or await self.bot.fetch_user(application["user_id"])
        if applicant:
            reject_embed = discord.Embed(
                title="Helper Application Rejected",
                description=(
                    "Your helper application has been rejected by an officer.\n"
                    f"Reason: {review_reason or 'No reason provided.'}"
                ),
                color=discord.Color.red()
            )
            try:
                await applicant.send(embed=reject_embed)
            except Exception:
                pass

        await interaction.response.send_message(
            "✅ Application rejected and the applicant has been notified.",
            ephemeral=True
        )

        if review_channel:
            try:
                await asyncio.sleep(1)
                await review_channel.delete(reason="Helper application reviewed and completed")
            except Exception as e:
                print(f"[HELPER ERROR] Failed to delete review channel: {e}")



class HelperReviewView(discord.ui.View):
    def __init__(self, application_id, bot):
        super().__init__(timeout=None)
        self.application_id = application_id
        self.bot = bot

        accept_button = discord.ui.Button(
            label="Accept",
            style=discord.ButtonStyle.success,
            custom_id=f"helper_accept:{application_id}"
        )
        reject_button = discord.ui.Button(
            label="Reject",
            style=discord.ButtonStyle.danger,
            custom_id=f"helper_reject:{application_id}"
        )

        accept_button.callback = self.accept_application
        reject_button.callback = self.reject_application

        self.add_item(accept_button)
        self.add_item(reject_button)

    async def accept_application(self, interaction: discord.Interaction):
        if not await helper_is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only officers can accept helper applications.",
                ephemeral=True
            )
            return

        application = await get_helper_application_by_id(self.application_id)

        if not application or application["status"] != "pending":
            await interaction.response.send_message(
                "❌ This application has already been reviewed.",
                ephemeral=True
            )
            return

        await execute(
            """
            UPDATE helper_applications
            SET status = %s,
                reviewer_id = %s,
                review_reason = %s
            WHERE id = %s
            """,
            (
                "accepted",
                interaction.user.id,
                None,
                self.application_id
            )
        )

        application = await get_helper_application_by_id(self.application_id)
        await send_helper_log(interaction.guild, application, "accepted", reviewer_id=interaction.user.id)

        config = await get_helper_config(interaction.guild.id)
        helper_role = interaction.guild.get_role(config.get("helper_role_id")) if config else None
        applicant_member = interaction.guild.get_member(application["user_id"])
        if applicant_member is None:
            try:
                applicant_member = await interaction.guild.fetch_member(application["user_id"])
            except Exception:
                applicant_member = None

        if helper_role and applicant_member:
            try:
                await applicant_member.add_roles(helper_role, reason="Helper application accepted")
            except Exception:
                pass

        # Get review channel from guild using channel_id
        review_channel = None
        if application.get("channel_id"):
            review_channel = interaction.guild.get_channel(int(application["channel_id"]))
            if not review_channel:
                try:
                    review_channel = await interaction.guild.fetch_channel(int(application["channel_id"]))
                except Exception:
                    review_channel = None

        if not review_channel:
            review_channel = interaction.channel

        if review_channel:
            try:
                original_message = await review_channel.fetch_message(application["message_id"])
            except Exception:
                original_message = None

            if original_message:
                updated_application = await get_helper_application_by_id(self.application_id)
                embed = await build_application_embed(updated_application, interaction.guild)
                for child in self.children:
                    child.disabled = True
                await original_message.edit(embed=embed, view=self)

        applicant = self.bot.get_user(application["user_id"]) or await self.bot.fetch_user(application["user_id"])
        if applicant:
            accepted_embed = discord.Embed(
                title="Helper Application Accepted",
                description="Congratulations! Your helper application has been accepted by an officer.",
                color=discord.Color.green()
            )
            try:
                await applicant.send(embed=accepted_embed)
            except Exception:
                pass

        await interaction.response.send_message(
            "✅ Application accepted and the applicant has been notified.",
            ephemeral=True
        )

        if review_channel:
            try:
                await asyncio.sleep(1)
                await review_channel.delete(reason="Helper application reviewed and completed")
            except Exception as e:
                print(f"[HELPER ERROR] Failed to delete review channel: {e}")


    async def reject_application(self, interaction: discord.Interaction):
        if not await helper_is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only officers can reject helper applications.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(RejectReviewModal(self.application_id, self.bot))


class DemoteUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="Search/Select a helper to demote...",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        officer_check = await helper_is_officer(interaction.user)
        if not officer_check:
            await interaction.response.send_message(
                "❌ Only Officer can demote helpers.",
                ephemeral=True
            )
            return

        target_member = self.values[0]
        
        config = await fetchone(
            """
            SELECT helper_role_id FROM helper_config
            WHERE guild_id = %s
            """,
            (interaction.guild.id,)
        )
        if not config or not config.get("helper_role_id"):
            config = await fetchone(
                """
                SELECT helper_role_id FROM ticket_config
                WHERE guild_id = %s
                """,
                (interaction.guild.id,)
            )
        
        helper_role_removed = False
        
        if config and config.get("helper_role_id"):
            helper_role = interaction.guild.get_role(config["helper_role_id"])
            if helper_role and target_member:
                try:
                    await target_member.remove_roles(helper_role, reason=f"Demoted by Officer {interaction.user} via Officer Control Panel.")
                    helper_role_removed = True
                except Exception as e:
                    print(f"Failed to remove helper role: {e}")

        # Delete from active ticket helpers (purging them from all tickets they've joined)
        await execute(
            """
            DELETE FROM active_ticket_helpers
            WHERE user_id = %s
            """,
            (target_member.id,)
        )
        
        await execute(
            """
            DELETE FROM active_ticket_helper_points
            WHERE user_id = %s
            """,
            (target_member.id,)
        )

        role_status_str = "and had their **Helper role** removed" if helper_role_removed else "(failed to remove Helper role, check role hierarchy/permissions)"
        await interaction.response.edit_message(
            content=f"✅ Helper {target_member.mention} has been successfully demoted {role_status_str}.",
            view=None
        )

        await interaction.channel.send(
            f"🚫 {target_member.mention} has been **demoted** and had their Helper role removed by Officer {interaction.user.mention} due to improper conduct/scamming."
        )



        try:
            helper_config = await get_helper_config(interaction.guild.id)
            if helper_config:
                review_category = interaction.guild.get_channel(helper_config.get("review_category_id"))
                officer_role = interaction.guild.get_role(helper_config.get("officer_role_id"))
                if review_category and officer_role:
                    helper_log_channel = await get_helper_log_channel(interaction.guild, review_category, officer_role)
                    if helper_log_channel:
                        demote_log_embed = discord.Embed(
                            title="🚫 Helper Demoted",
                            description=(
                                f"**Officer:** {interaction.user.mention}\n"
                                f"**Demoted User:** {target_member.mention} ({target_member.id})\n"
                                f"**Action:** Helper role removed and user purged from active helper queues.\n"
                                f"**Trigger Channel:** {interaction.channel.mention}"
                            ),
                            color=discord.Color.red()
                        )
                        await helper_log_channel.send(embed=demote_log_embed)
        except Exception as e:
            print(f"Failed to send helper log: {e}")


class DemoteUserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DemoteUserSelect())


class GlobalOfficerControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Demote Helper",
        style=discord.ButtonStyle.danger,
        emoji="🚫",
        custom_id="global_officer_demote_helper"
    )
    async def demote_helper(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_off = await helper_is_officer(interaction.user)
        if not is_off:
            await interaction.response.send_message(
                "❌ Only Officers can manage helpers.",
                ephemeral=True
            )
            return

        view = DemoteUserSelectView()
        await interaction.response.send_message(
            "Select a helper to demote (removes their Helper role guild-wide):",
            view=view,
            ephemeral=True
        )


class Helper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ApplyHelperView(bot))
        self.bot.add_view(GlobalOfficerControlView())
        asyncio.create_task(self.register_pending_views())

    async def register_pending_views(self):
        await self.bot.wait_until_ready()
        try:
            pending_apps = await fetchall(
                """
                SELECT id, channel_id FROM helper_applications
                WHERE status = 'pending'
                """
            )
            for app in pending_apps:
                channel = None
                if app.get("channel_id"):
                    for g in self.bot.guilds:
                        channel = g.get_channel(int(app["channel_id"]))
                        if channel:
                            break

                if not channel and app.get("channel_id"):
                    await execute(
                        """
                        UPDATE helper_applications
                        SET status = 'rejected',
                            review_reason = 'Review channel was manually deleted.'
                        WHERE id = %s
                        """,
                        (app["id"],)
                    )
                    print(f"[HELPER] Cleaned up orphaned helper application ID {app['id']} (channel {app['channel_id']} deleted)")
                    continue

                self.bot.add_view(HelperReviewView(app["id"], self.bot))
                print(f"[HELPER] Registered persistent HelperReviewView for application ID {app['id']}")
        except Exception as e:
            print(f"[HELPER ERROR] Failed to register pending helper views: {e}")

    @app_commands.command(
        name="helpersetup",
        description="Setup helper application review category, officer role, and helper role"
    )
    @app_commands.describe(
        officer_role="Role allowed to review helper applications",
        helper_role="Role to assign to accepted helpers",
        review_category="Category where helper application tickets are created"
    )
    async def helpersetup(
        self,
        interaction: discord.Interaction,
        officer_role: discord.Role,
        helper_role: discord.Role,
        review_category: discord.CategoryChannel
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can configure helper applications.",
                ephemeral=True
            )
            return

        await execute(
            """
            INSERT INTO helper_config
            (guild_id, officer_role_id, helper_role_id, review_channel_id, review_category_id)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                officer_role_id = VALUES(officer_role_id),
                helper_role_id = VALUES(helper_role_id),
                review_channel_id = VALUES(review_channel_id),
                review_category_id = VALUES(review_category_id)
            """,
            (
                interaction.guild.id,
                officer_role.id,
                helper_role.id,
                None,
                review_category.id
            )
        )

        await interaction.response.send_message(
            f"✅ Helper application setup completed.\n"
            f"Officer role: {officer_role.mention}\n"
            f"Helper role: {helper_role.mention}\n"
            f"Review category: {review_category.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="helperpanel",
        description="Post a helper application embed with an apply button"
    )
    @app_commands.describe(
        post_channel="Channel to post the helper application panel into"
    )
    async def helperpanel(
        self,
        interaction: discord.Interaction,
        post_channel: discord.TextChannel = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can post the helper application panel.",
                ephemeral=True
            )
            return

        target_channel = post_channel or interaction.channel

        embed = discord.Embed(
            title="Apply for Helper",
            description=(
                "Click the button below to start your helper application. "
                "Officers will review your application in the configured category."
            ),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="How it works",
            value=(
                "1. Click **Apply as Helper**\n"
                "2. Answer the application questions\n"
                "3. Officers review your application in a private ticket channel\n"
                "4. Accepted applicants receive the helper role"
            ),
            inline=False
        )

        view = ApplyHelperView(self.bot)
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Helper application panel posted in {target_channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="officerpanel",
        description="Post the Officer Control Panel for demoting helpers"
    )
    async def officerpanel(
        self,
        interaction: discord.Interaction
    ):
        # Check if user is an Officer
        is_off = await helper_is_officer(interaction.user)
        if not is_off:
            await interaction.response.send_message(
                "❌ Only Officers can run this command.",
                ephemeral=True
            )
            return

        officer_embed = discord.Embed(
            title="🛡️ Officer Control Panel",
            description=(
                "This panel is only accessible by Officers to manage and demote helpers.\n\n"
                "**Controls:**\n"
                "• **Demote Helper**: Search and select any user in the server to completely remove their Helper role and purge them from all active queues."
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=officer_embed, view=GlobalOfficerControlView())


async def setup(bot):
    await bot.add_cog(Helper(bot))
