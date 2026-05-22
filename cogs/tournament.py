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
        if config["player_limit"] == 8:
            rounds_config = [
                ("ROUND 1 (Quarter-Finals)", [1, 2, 3, 4]),
                ("ROUND 2 (Semi-Finals)", [5, 6]),
                ("GRAND FINALS", [7])
            ]
        else:  # 16 players
            rounds_config = [
                ("ROUND 1 (1/8 Finals)", [1, 2, 3, 4, 5, 6, 7, 8]),
                ("ROUND 2 (Quarter-Finals)", [9, 10, 11, 12]),
                ("ROUND 3 (Semi-Finals)", [13, 14]),
                ("GRAND FINALS", [15])
            ]

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
        final_match_id = 7 if config["player_limit"] == 8 else 15
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
        # Helper mapping of current match to next match index
        if limit == 8:
            advancement_map = {
                1: (5, "p1"),
                2: (5, "p2"),
                3: (6, "p1"),
                4: (6, "p2"),
                5: (7, "p1"),
                6: (7, "p2")
            }
        else: # 16 players
            advancement_map = {
                1: (9, "p1"),
                2: (9, "p2"),
                3: (10, "p1"),
                4: (10, "p2"),
                5: (11, "p1"),
                6: (11, "p2"),
                7: (12, "p1"),
                8: (12, "p2"),
                9: (13, "p1"),
                10: (13, "p2"),
                11: (14, "p1"),
                12: (14, "p2"),
                13: (15, "p1"),
                14: (15, "p2")
            }

        if match_id not in advancement_map:
            return # Final match winner does not advance

        next_match_id, slot = advancement_map[match_id]
        
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

        if player_limit not in [8, 16]:
            await interaction.response.send_message(
                "❌ PvP Brackets only support `8` or `16` players at this time.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id

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
        if not players:
            await interaction.response.send_message(
                "❌ Cannot start tournament with 0 players! Please wait for members to register.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        limit = config["player_limit"]

        # Shuffle players to keep seeding fresh and exciting
        random.shuffle(players)

        # Seed players list (fill up empty slots with 0 to represent BYEs)
        seeded_slots = [0] * limit
        for idx, player in enumerate(players):
            seeded_slots[idx] = player["user_id"]

        # Clean existing matches (safety check)
        await execute("DELETE FROM tournament_matches WHERE guild_id = %s", (guild_id,))

        # Initialize Brackets Matchups
        if limit == 8:
            # Round 1 Matchups
            matchups = [
                (1, 1, seeded_slots[0], seeded_slots[7]), # Seed 1 vs 8
                (2, 1, seeded_slots[3], seeded_slots[4]), # Seed 4 vs 5
                (3, 1, seeded_slots[1], seeded_slots[6]), # Seed 2 vs 7
                (4, 1, seeded_slots[2], seeded_slots[5]), # Seed 3 vs 6
                # Empty Round 2 and 3 matches to be filled dynamically
                (5, 2, None, None),
                (6, 2, None, None),
                (7, 3, None, None)
            ]
        else: # 16 players
            matchups = [
                (1, 1, seeded_slots[0], seeded_slots[15]), # Seed 1 vs 16
                (2, 1, seeded_slots[7], seeded_slots[8]),  # Seed 8 vs 9
                (3, 1, seeded_slots[3], seeded_slots[12]), # Seed 4 vs 13
                (4, 1, seeded_slots[4], seeded_slots[11]), # Seed 5 vs 12
                (5, 1, seeded_slots[1], seeded_slots[14]), # Seed 2 vs 15
                (6, 1, seeded_slots[6], seeded_slots[9]),  # Seed 7 vs 10
                (7, 1, seeded_slots[2], seeded_slots[13]), # Seed 3 vs 14
                (8, 1, seeded_slots[5], seeded_slots[10]), # Seed 6 vs 11
                # Semi-Final / Final Slots
                (9, 2, None, None),
                (10, 2, None, None),
                (11, 2, None, None),
                (12, 2, None, None),
                (13, 3, None, None),
                (14, 3, None, None),
                (15, 4, None, None)
            ]

        # Insert matches into DB
        for m_id, rnd, p1, p2 in matchups:
            await execute(
                "INSERT INTO tournament_matches (guild_id, match_id, round, player1_id, player2_id) VALUES (%s, %s, %s, %s, %s)",
                (guild_id, m_id, rnd, p1, p2)
            )

        # Resolve any BYE matchups automatically
        await self.check_and_resolve_byes(guild_id, limit)

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

        # Check if tournament is completely completed (final match has winner)
        final_match_id = 7 if limit == 8 else 15
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
        
        await execute("DELETE FROM tournament_matches WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_players WHERE guild_id = %s", (guild_id,))
        await execute("DELETE FROM tournament_config WHERE guild_id = %s", (guild_id,))

        await interaction.response.send_message(
            "🧹 PvP Tournament has been fully reset and cleared. Ready for next setup!"
        )


async def setup(bot):
    await bot.add_cog(PvPTournament(bot))
