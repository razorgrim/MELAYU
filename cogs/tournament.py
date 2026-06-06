import discord
from discord import app_commands
from discord.ext import commands
import random
from database import execute, fetchone, fetchall

class PvPRegisterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_registration(self, interaction: discord.Interaction, join: bool):
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        # 1. Fetch tournament config
        config = await fetchone(
            "SELECT * FROM tournament_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config:
            await interaction.response.send_message(
                "❌ PvP Tournament is not configured yet on this server. Officers must run `/pvp_setup` first.",
                ephemeral=True
            )
            return

        if config["status"] != "registration":
            await interaction.response.send_message(
                "❌ Registration is currently closed or the tournament has already started.",
                ephemeral=True
            )
            return

        # 2. Check if user is verified in verified_users table
        verified = await fetchone(
            "SELECT * FROM verified_users WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )
        if not verified:
            await interaction.response.send_message(
                "❌ You must verify your AQW character page first before joining the PvP tournament!\n"
                "Please use the `/verification` command to link your account.",
                ephemeral=True
            )
            return

        ign = verified["ign"]

        # 3. Handle JOIN
        if join:
            # Check player limit
            current_players = await fetchall(
                "SELECT * FROM tournament_players WHERE guild_id = %s",
                (guild_id,)
            )
            if len(current_players) >= config["player_limit"]:
                await interaction.response.send_message(
                    f"❌ The tournament is full! Maximum slots: `{config['player_limit']}` players.",
                    ephemeral=True
                )
                return

            # Check if already joined
            already_joined = any(p["user_id"] == user_id for p in current_players)
            if already_joined:
                await interaction.response.send_message(
                    "❌ You are already registered for this tournament!",
                    ephemeral=True
                )
                return

            # Insert into database
            next_seed = len(current_players) + 1
            await execute(
                "INSERT INTO tournament_players (guild_id, user_id, ign, seed) VALUES (%s, %s, %s, %s)",
                (guild_id, user_id, ign, next_seed)
            )
            await interaction.response.send_message(
                f"✅ Successfully registered! You have been seeded as player `{ign}`.",
                ephemeral=True
            )

        # 4. Handle LEAVE
        else:
            # Check if registered
            registered = await fetchone(
                "SELECT * FROM tournament_players WHERE guild_id = %s AND user_id = %s",
                (guild_id, user_id)
            )
            if not registered:
                await interaction.response.send_message(
                    "❌ You are not registered for this tournament.",
                    ephemeral=True
                )
                return

            # Delete from database
            await execute(
                "DELETE FROM tournament_players WHERE guild_id = %s AND user_id = %s",
                (guild_id, user_id)
            )
            
            # Reorder remaining player seeds
            players = await fetchall(
                "SELECT * FROM tournament_players WHERE guild_id = %s ORDER BY seed ASC",
                (guild_id,)
            )
            for idx, player in enumerate(players, start=1):
                await execute(
                    "UPDATE tournament_players SET seed = %s WHERE guild_id = %s AND user_id = %s",
                    (idx, guild_id, player["user_id"])
                )

            await interaction.response.send_message(
                "❌ Cancelled your registration successfully.",
                ephemeral=True
            )

        # 5. Refresh static dashboard message
        cog = interaction.client.get_cog("PvPTournament")
        if cog:
            await cog.update_dashboard(guild_id)

    @discord.ui.button(label="⚔️ Register for PvP", style=discord.ButtonStyle.success, custom_id="pvp_register_join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, join=True)

    @discord.ui.button(label="❌ Cancel Registration", style=discord.ButtonStyle.danger, custom_id="pvp_register_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_registration(interaction, join=False)


class PvPTournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(PvPRegisterView())




    async def get_player_name(self, guild_id, user_id):
        if not user_id:
            return "BYE 💤"
        player = await fetchone(
            "SELECT ign FROM tournament_players WHERE guild_id = %s AND user_id = %s",
            (guild_id, user_id)
        )
        return player["ign"] if player else f"User {user_id}"

    async def create_match_thread(self, guild, channel, match_id, round_num, p1_id, p2_id):
        try:
            p1_ign = await self.get_player_name(guild.id, p1_id)
            p2_ign = await self.get_player_name(guild.id, p2_id)
            
            # 1. Create a private thread inside the channel
            thread_name = f"🔒-match-{match_id}-{p1_ign}-vs-{p2_ign}"
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason=f"Private PvP thread for Match {match_id}"
            )
            
            # 2. Add both contestants explicitly
            for p_id in [p1_id, p2_id]:
                if p_id:
                    member = guild.get_member(p_id)
                    if not member:
                        try:
                            member = await guild.fetch_member(p_id)
                        except Exception:
                            pass
                    if member:
                        await thread.add_user(member)
                
            # 3. Fetch officer role from ticket config to mention them/notify them
            from cogs.tickets import get_server_config
            ticket_config = await get_server_config(guild.id)
            officer_role = None
            if ticket_config and ticket_config.get("officer_role_id"):
                officer_role = guild.get_role(ticket_config["officer_role_id"])
                
            # 4. Send initial welcome embed
            embed = discord.Embed(
                title=f"⚔️ Match {match_id} - Round {round_num}",
                description=(
                    f"Welcome to the private PvP match thread for **Match {match_id}**!\n\n"
                    f"• **Player 1:** `{p1_ign}` (<@{p1_id}>)\n"
                    f"• **Player 2:** `{p2_ign}` (<@{p2_id}>)\n\n"
                    f"Please coordinate your duel coordinates and details here. "
                    f"Officers will record the winner of this match using `/pvp_setwinner`."
                ),
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
            embed.set_footer(text="AQW MELAYU • PvP Arena")
            
            mention_str = ""
            if officer_role:
                mention_str += f"{officer_role.mention} "
            mention_str += f"<@{p1_id}> <@{p2_id}>"
                
            await thread.send(content=mention_str, embed=embed)
            return thread.id
        except Exception as e:
            print(f"Failed to create private match thread for Match {match_id}: {e}")
            return None

    async def check_and_create_pending_match_threads(self, guild, channel, guild_id):
        # Find all active/pending matches that don't have a thread created yet
        matches = await fetchall(
            "SELECT * FROM tournament_matches WHERE guild_id = %s AND winner_id IS NULL AND thread_id IS NULL",
            (guild_id,)
        )
        for match in matches:
            p1 = match["player1_id"]
            p2 = match["player2_id"]
            
            # We only create a thread if both players are determined and neither is a BYE (0)
            if p1 is not None and p1 != 0 and p2 is not None and p2 != 0:
                thread_id = await self.create_match_thread(
                    guild,
                    channel,
                    match["match_id"],
                    match["round"],
                    p1,
                    p2
                )
                if thread_id:
                    await execute(
                        "UPDATE tournament_matches SET thread_id = %s WHERE guild_id = %s AND match_id = %s",
                        (thread_id, guild_id, match["match_id"])
                    )

    async def archive_all_pvp_threads(self, guild, guild_id):
        matches = await fetchall(
            "SELECT thread_id FROM tournament_matches WHERE guild_id = %s",
            (guild_id,)
        )
        for m in matches:
            if m.get("thread_id"):
                try:
                    thread = guild.get_thread(m["thread_id"])
                    if not thread:
                        thread = await guild.fetch_channel(m["thread_id"])
                    if thread:
                        await thread.edit(locked=True, archived=True, reason="PvP Tournament Reset/Re-setup")
                except Exception as e:
                    print(f"Failed to archive thread {m['thread_id']}: {e}")




    async def update_dashboard(self, guild_id):
        config = await fetchone(
            "SELECT * FROM tournament_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config or not config["message_id"]:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        channel = guild.get_channel(config["channel_id"])
        if not channel:
            try:
                channel = await guild.fetch_channel(config["channel_id"])
            except Exception:
                return

        try:
            message = await channel.fetch_message(config["message_id"])
        except Exception:
            return

        embed = await self.generate_bracket_embed(guild_id)
        if not embed:
            return

        # Show buttons only during registration phase
        view = PvPRegisterView() if config["status"] == "registration" else None
        await message.edit(embed=embed, view=view)

    async def generate_bracket_embed(self, guild_id):
        config = await fetchone(
            "SELECT * FROM tournament_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config:
            return None

        players = await fetchall(
            "SELECT * FROM tournament_players WHERE guild_id = %s ORDER BY seed ASC",
            (guild_id,)
        )

        embed = discord.Embed(
            title="⚔️ AQW MELAYU PvP Arena Tournament",
            description="",
            color=discord.Color.gold()
        )

        embed.set_thumbnail(url="https://imgur.com/ILiLVM7.png")
        embed.set_image(url="https://i.imgur.com/vBeUbYo.jpeg")

        if config["status"] == "registration":
            player_list = "\n".join(
                f"**{idx}.** `{p['ign']}` (Seed {p['seed']})"
                for idx, p in enumerate(players, start=1)
            ) if players else "*No players registered yet. Be the first!*"

            embed.description = (
                "🏆 **PVP TOURNAMENT REGISTRATION IS OPEN!** 🏆\n\n"
                f"Gunakan butang di bawah untuk join PvP Tournament!\n"
                f"• **Format:** Single-Elimination 1v1 Arena duels.\n"
                f"• **Tournament Limit:** `{config['player_limit']}` players max.\n"
                f"• **Requirement:** Must verify your IGN via `/verification` first.\n\n"
                f"📢 **Registered Participants ({len(players)}/{config['player_limit']}):**\n"
                f"{player_list}"
            )
            embed.set_footer(text="AQW MELAYU • PvP Season 1 • Click Register to join!")
            return embed

        # Running or completed bracket rendering
        matches = await fetchall(
            "SELECT * FROM tournament_matches WHERE guild_id = %s ORDER BY match_id ASC",
            (guild_id,)
        )

        # Structure matches mapping
        matches_dict = {m["match_id"]: m for m in matches}

        # Format bracket diagram text
        bracket_lines = []

        # Determine rounds
        rounds_config = []
        limit = config["player_limit"]
        round_start_id = 1
        current_limit = limit // 2
        round_num = 1
        
        while current_limit > 0:
            match_ids = list(range(round_start_id, round_start_id + current_limit))
            
            # Determine title
            if current_limit == 1:
                title = "GRAND FINALS"
            elif current_limit == 2:
                title = f"ROUND {round_num} (Semi-Finals)"
            elif current_limit == 4:
                title = f"ROUND {round_num} (Quarter-Finals)"
            elif current_limit == 8:
                title = f"ROUND {round_num} (1/8 Finals)"
            else:
                title = f"ROUND {round_num}"
                
            rounds_config.append((title, match_ids))
            
            round_start_id += current_limit
            current_limit = current_limit // 2
            round_num += 1

        for round_title, match_ids in rounds_config:
            bracket_lines.append(f"🟢 **{round_title}**")
            
            for m_id in match_ids:
                match = matches_dict.get(m_id)
                if not match:
                    continue
 
                p1_name = await self.get_player_name(guild_id, match["player1_id"])
                p2_name = await self.get_player_name(guild_id, match["player2_id"])
 
                score_str = ""
                if match["winner_id"] or (match["player1_score"] > 0 or match["player2_score"] > 0):
                    score_str = f" `({match['player1_score']} - {match['player2_score']})`"
 
                winner_name = await self.get_player_name(guild_id, match["winner_id"]) if match["winner_id"] else None
                winner_str = f"👑 Winner: **`{winner_name}`**" if winner_name else "Winner: *Pending*"
 
                bracket_lines.append(
                    f"• **Match {m_id}:** `{p1_name}` vs `{p2_name}`{score_str}\n"
                    f"  └─ {winner_str}"
                )
            
            bracket_lines.append("") # Spacer between rounds
 
        embed.description = (
            "🏆 **PVP TOURNAMENT BRACKETS & STANDINGS** 🏆\n\n"
            f"Here is the active PvP tournament status. Keep coordinate duels in PvP map `/join doomarena`.\n\n"
            + "\n".join(bracket_lines)
        )
 
        # Declare overall winner if Grand Final is complete
        final_match_id = limit - 1
        final_match = matches_dict.get(final_match_id)
        if final_match and final_match["winner_id"]:
            champion_name = await self.get_player_name(guild_id, final_match["winner_id"])
            embed.description += (
                f"\n🎉 **CONGRATULATIONS TO OUR PVP CHAMPION!** 🎉\n"
                f"🥇 👑 **`{champion_name}`** 👑 🥇\n\n"
                "Thank you everyone for participating! Awards will be distributed by Officers."
            )
            embed.color = discord.Color.from_rgb(255, 215, 0) # Bright Gold
            embed.set_footer(text="AQW MELAYU • Tournament Completed! 🎉")
        else:
            embed.set_footer(text="AQW MELAYU • Running Phase • Officers will set winners")

        return embed

    async def check_and_resolve_byes(self, guild_id, limit):
        # Automatically resolve matches that have BYEs recursively
        rounds_to_process = True
        
        while rounds_to_process:
            rounds_to_process = False
            matches = await fetchall(
                "SELECT * FROM tournament_matches WHERE guild_id = %s ORDER BY match_id ASC",
                (guild_id,)
            )
            matches_dict = {m["match_id"]: m for m in matches}

            for match in matches:
                # Only check pending matches
                if match["winner_id"]:
                    continue

                p1 = match["player1_id"]
                p2 = match["player2_id"]

                # If both are BYEs
                if p1 == 0 and p2 == 0 and (p1 is not None and p2 is not None):
                    await execute(
                        "UPDATE tournament_matches SET winner_id = 0, player1_score = 0, player2_score = 0 WHERE guild_id = %s AND match_id = %s",
                        (guild_id, match["match_id"])
                    )
                    await self.advance_player(guild_id, match["match_id"], 0, limit)
                    rounds_to_process = True
                    break

                # If Player 1 is BYE
                elif p1 == 0 and p1 is not None:
                    # Player 2 advances automatically
                    await execute(
                        "UPDATE tournament_matches SET winner_id = %s, player1_score = 0, player2_score = 1 WHERE guild_id = %s AND match_id = %s",
                        (p2, guild_id, match["match_id"])
                    )
                    await self.advance_player(guild_id, match["match_id"], p2, limit)
                    rounds_to_process = True
                    break

                # If Player 2 is BYE
                elif p2 == 0 and p2 is not None:
                    # Player 1 advances automatically
                    await execute(
                        "UPDATE tournament_matches SET winner_id = %s, player1_score = 1, player2_score = 0 WHERE guild_id = %s AND match_id = %s",
                        (p1, guild_id, match["match_id"])
                    )
                    await self.advance_player(guild_id, match["match_id"], p1, limit)
                    rounds_to_process = True
                    break

    async def advance_player(self, guild_id, match_id, winner_id, limit):
        # We find which round match_id belongs to
        round_start_id = 1
        current_limit = limit // 2
        
        while current_limit > 0:
            round_end_id = round_start_id + current_limit - 1
            if round_start_id <= match_id <= round_end_id:
                # Found the round!
                if current_limit == 1:
                    # This is the final match, no advancement
                    return
                
                offset = match_id - round_start_id
                next_round_start_id = round_end_id + 1
                next_match_id = next_round_start_id + (offset // 2)
                slot = "p1" if offset % 2 == 0 else "p2"
                
                if slot == "p1":
                    await execute(
                        "UPDATE tournament_matches SET player1_id = %s WHERE guild_id = %s AND match_id = %s",
                        (winner_id, guild_id, next_match_id)
                    )
                else:
                    await execute(
                        "UPDATE tournament_matches SET player2_id = %s WHERE guild_id = %s AND match_id = %s",
                        (winner_id, guild_id, next_match_id)
                    )
                return
            
            round_start_id = round_end_id + 1
            current_limit = current_limit // 2

    @app_commands.command(
        name="pvp_setup",
        description="Set up a new persistent PvP Tournament dashboard."
    )
    @app_commands.describe(
        player_limit="Maximum size of the tournament bracket (8 or 16 players)"
    )
    async def pvp_setup(self, interaction: discord.Interaction, player_limit: int = 8):
        # 1. Authorize Officer status
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only PvP Officers or Admins can setup the PvP tournament.",
                ephemeral=True
            )
            return

        if player_limit not in [2, 4, 8, 16, 32, 64]:
            await interaction.response.send_message(
                "❌ PvP Brackets only support powers of 2: `2`, `4`, `8`, `16`, `32`, or `64` players.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id

        # Archive any active threads before deleting database configuration
        await self.archive_all_pvp_threads(interaction.guild, guild_id)

        # 2. Delete any existing configuration to prevent orphan dashboards
        await execute("DELETE FROM tournament_matches WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_players WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_config WHERE guild_id = %s", (guild_id,))

        # 3. Create active config record
        await execute(
            "INSERT INTO tournament_config (guild_id, channel_id, player_limit, status) VALUES (%s, %s, %s, 'registration')",
            (guild_id, interaction.channel.id, player_limit)
        )

        # 4. Generate first static dashboard message
        embed = await self.generate_bracket_embed(guild_id)
        view = PvPRegisterView()
        await interaction.response.send_message("⚙️ Initializing tournament dashboard...", ephemeral=True)
        message = await interaction.channel.send(embed=embed, view=view)

        # Update message_id reference
        await execute(
            "UPDATE tournament_config SET message_id = %s WHERE guild_id = %s",
            (message.id, guild_id)
        )

    @app_commands.command(
        name="pvp_start",
        description="Lock registrations and seed the tournament bracket."
    )
    async def pvp_start(self, interaction: discord.Interaction):
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only PvP Officers can start the tournament.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        config = await fetchone(
            "SELECT * FROM tournament_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config:
            await interaction.response.send_message(
                "❌ Tournament dashboard not configured yet. Run `/pvp_setup`.",
                ephemeral=True
            )
            return

        if config["status"] != "registration":
            await interaction.response.send_message(
                "❌ Tournament has already started or completed.",
                ephemeral=True
            )
            return

        # Fetch registered players
        players = await fetchall(
            "SELECT * FROM tournament_players WHERE guild_id = %s ORDER BY seed ASC",
            (guild_id,)
        )
        if len(players) < 2:
            await interaction.response.send_message(
                "❌ Cannot start tournament with less than 2 players! Please wait for more members to register.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Determine smallest power of 2 that is >= len(players)
        limit = 2
        while limit < len(players):
            limit *= 2

        # Update player_limit in the database to reflect the actual dynamic limit
        await execute(
            "UPDATE tournament_config SET player_limit = %s WHERE guild_id = %s",
            (limit, guild_id)
        )

        # Shuffle players to keep seeding fresh and exciting
        random.shuffle(players)

        # Seed players list (fill up empty slots with 0 to represent BYEs)
        seeded_slots = [0] * limit
        for idx, player in enumerate(players):
            seeded_slots[idx] = player["user_id"]

        # Clean existing matches (safety check)
        await execute("DELETE FROM tournament_matches WHERE guild_id = %s", (guild_id,))

        # Initialize Brackets Matchups Dynamically
        seeded_order = [0]
        while len(seeded_order) < limit:
            new_order = []
            for x in seeded_order:
                new_order.append(x)
                new_order.append(2 * len(seeded_order) - 1 - x)
            seeded_order = new_order

        matchups = []
        # Round 1 Matchups
        for i in range(0, limit, 2):
            match_id = (i // 2) + 1
            p1 = seeded_slots[seeded_order[i]]
            p2 = seeded_slots[seeded_order[i+1]]
            matchups.append((match_id, 1, p1, p2))
            
        # Subsequent Rounds Matchups
        match_id = (limit // 2) + 1
        round_num = 2
        matches_in_round = limit // 4
        while matches_in_round > 0:
            for _ in range(matches_in_round):
                matchups.append((match_id, round_num, None, None))
                match_id += 1
            round_num += 1
            matches_in_round = matches_in_round // 2

        # Insert matches into DB
        for m_id, rnd, p1, p2 in matchups:
            await execute(
                "INSERT INTO tournament_matches (guild_id, match_id, round, player1_id, player2_id) VALUES (%s, %s, %s, %s, %s)",
                (guild_id, m_id, rnd, p1, p2)
            )

        # Resolve any BYE matchups automatically
        await self.check_and_resolve_byes(guild_id, limit)

        # Create private threads for Round 1 matches that are ready (have two real players)
        await self.check_and_create_pending_match_threads(interaction.guild, interaction.channel, guild_id)


        # Lock registration state
        await execute(
            "UPDATE tournament_config SET status = 'ongoing' WHERE guild_id = %s",
            (guild_id,)
        )

        # Re-render dashboard
        await self.update_dashboard(guild_id)
        await interaction.followup.send("🚀 Tournament bracket seeded and started successfully!")

    @app_commands.command(
        name="pvp_setwinner",
        description="Record score and declare winner of a specific PvP match."
    )
    @app_commands.describe(
        match_id="The Match ID (e.g. 1, 2, 5)",
        winner_ign="The IGN of the winning player",
        winner_score="Score achieved by the winner (e.g. 2)",
        loser_score="Score achieved by the loser (e.g. 1)"
    )
    async def pvp_setwinner(
        self,
        interaction: discord.Interaction,
        match_id: int,
        winner_ign: str,
        winner_score: int,
        loser_score: int
    ):
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only PvP Officers can record PvP matches.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        config = await fetchone(
            "SELECT * FROM tournament_config WHERE guild_id = %s",
            (guild_id,)
        )
        if not config or config["status"] != "ongoing":
            await interaction.response.send_message(
                "❌ PvP Tournament is not currently running.",
                ephemeral=True
            )
            return

        # Fetch match data
        match = await fetchone(
            "SELECT * FROM tournament_matches WHERE guild_id = %s AND match_id = %s",
            (guild_id, match_id)
        )
        if not match:
            await interaction.response.send_message(
                f"❌ Match ID `{match_id}` does not exist.",
                ephemeral=True
            )
            return

        if match["winner_id"]:
            await interaction.response.send_message(
                "❌ This match already has a winner declared. Purge / reset first if you made a mistake.",
                ephemeral=True
            )
            return

        # Map winner_ign to user_id
        winner_ign = winner_ign.strip().lower()
        
        p1_ign = (await self.get_player_name(guild_id, match["player1_id"])).lower()
        p2_ign = (await self.get_player_name(guild_id, match["player2_id"])).lower()

        if winner_ign not in [p1_ign, p2_ign]:
            await interaction.response.send_message(
                f"❌ Player `{winner_ign}` is not in Match `{match_id}`. Candidates: `{p1_ign}` or `{p2_ign}`.",
                ephemeral=True
            )
            return

        winner_id = match["player1_id"] if winner_ign == p1_ign else match["player2_id"]
        
        # Determine score assignment based on who won
        if winner_id == match["player1_id"]:
            p1_score = winner_score
            p2_score = loser_score
        else:
            p1_score = loser_score
            p2_score = winner_score

        await execute(
            "UPDATE tournament_matches SET winner_id = %s, player1_score = %s, player2_score = %s WHERE guild_id = %s AND match_id = %s",
            (winner_id, p1_score, p2_score, guild_id, match_id)
        )

        limit = config["player_limit"]

        # Advance player to the next match
        await self.advance_player(guild_id, match_id, winner_id, limit)

        # Resolve any newly created BYEs recursively
        await self.check_and_resolve_byes(guild_id, limit)

        # Post match record to the specific match thread and archive it
        if match.get("thread_id"):
            try:
                thread = interaction.guild.get_thread(match["thread_id"])
                if not thread:
                    thread = await interaction.guild.fetch_channel(match["thread_id"])
                if thread:
                    p1_db = await fetchone(
                        "SELECT * FROM tournament_players WHERE guild_id = %s AND user_id = %s",
                        (guild_id, match["player1_id"])
                    )
                    p2_db = await fetchone(
                        "SELECT * FROM tournament_players WHERE guild_id = %s AND user_id = %s",
                        (guild_id, match["player2_id"])
                    )
                    round_name = f"Round {match['round']}"
                    p1_name = p1_db["ign"] if p1_db else "BYE"
                    p2_name = p2_db["ign"] if p2_db else "BYE"
                    winner_display = p1_db["ign"] if winner_id == match["player1_id"] else (p2_db["ign"] if p2_db else "BYE")
                    
                    embed = discord.Embed(
                        title="🏆 MATCH RESULT RECORDED",
                        description=f"An Officer has recorded the final results for this match. This thread is now closed.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Match ID", value=f"`{match_id}`", inline=True)
                    embed.add_field(name="Round", value=f"`{round_name}`", inline=True)
                    embed.add_field(name="Matchup", value=f"`{p1_name}` vs `{p2_name}`", inline=False)
                    embed.add_field(name="Score", value=f"**`{p1_score} - {p2_score}`**", inline=True)
                    embed.add_field(name="Winner", value=f"👑 **`{winner_display}`**", inline=True)
                    embed.set_footer(text="AQW MELAYU • PvP Arena")

                    await thread.send(embed=embed)
                    
                    # Lock and archive the thread
                    await thread.edit(locked=True, archived=True, reason=f"Match {match_id} completed. Winner: {winner_display}")
            except Exception as e:
                print(f"Failed to post result/archive match thread {match['thread_id']}: {e}")

        # Dynamic match thread creation for newly populated matches in subsequent rounds
        await self.check_and_create_pending_match_threads(interaction.guild, interaction.channel, guild_id)

        # Check if tournament is completely completed (final match has winner)
        final_match_id = limit - 1
        final_match = await fetchone(
            "SELECT winner_id FROM tournament_matches WHERE guild_id = %s AND match_id = %s",
            (guild_id, final_match_id)
        )
        if final_match and final_match["winner_id"]:
            await execute(
                "UPDATE tournament_config SET status = 'completed' WHERE guild_id = %s",
                (guild_id,)
            )

        # Refresh dashboard
        await self.update_dashboard(guild_id)
        await interaction.response.send_message(
            f"✅ Recorded Match `{match_id}` Winner: **`{winner_ign}`** `{p1_score}-{p2_score}`! Live brackets updated."
        )

    @app_commands.command(
        name="pvp_reset",
        description="Reset and purge the active tournament configuration."
    )
    async def pvp_reset(self, interaction: discord.Interaction):
        from cogs.tickets import is_officer
        if not await is_officer(interaction.user):
            await interaction.response.send_message(
                "❌ Only PvP Officers can reset the tournament.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        
        # Archive all active contestant threads before clearing database config
        await self.archive_all_pvp_threads(interaction.guild, guild_id)

        await execute("DELETE FROM tournament_matches WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_players WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_config WHERE guild_id = %s", (guild_id,))

        await interaction.response.send_message(
            "🧹 PvP Tournament has been fully reset and cleared. Ready for next setup!"
        )


async def setup(bot):
    await bot.add_cog(PvPTournament(bot))
