# ⚔️ AQW MALAYSIA Community Discord Bot

Welcome to the official **AQW MALAYSIA Community Discord Bot**! This bot is designed specifically for AdventureQuest Worlds (AQW) community servers, providing seamless character verification, dynamic 1v1 PvP tournament brackets, helper reward ticket systems, a structured class guide library, auto-scraping game boosters, and self-assignable faction roles.

---

## 🚀 Key Features

*   **🔒 Character Verification System**: Integrates with the official AQW Charpage to verify active accounts.
    *   Formats user server nicknames to: `nickname ● ign ● Nationality`.
    *   Automatically assigns an `Adventure` role to all verified players.
    *   Detects if the player is in your target guild (e.g. `M E L A Y U`) and assigns a guild member role.
    *   Provides a simple nationality selection dropdown panel.
*   **🏆 PvP Arena Tournaments**: Fully automated 1v1 single-elimination bracket manager.
    *   Locks registration, seeds brackets dynamically (handles powers of 2 up to 64 players).
    *   Auto-creates **private match threads** for ready opponents.
    *   Handles BYEs automatically.
    *   Renders a real-time tournament standings dashboard.
*   **🎟️ Ultra Ticket System**: Points-based guild request ticket system.
    *   Tracks helper point contributions for completing Ultra bosses (e.g., Ultra Speaker, Ultra Dage).
    *   Includes a dynamic, paginated leaderboard embed.
    *   Auto-closes inactive tickets after 2 hours with warnings.
*   **📈 Leveling & Server Shop**: Complete engagement economy system.
    *   Chatting earns random XP and levels up players with a premium level-up announcement.
    *   Earn **Melayu Coins (MCoin)** and bonus XP by completing helper request tickets.
    *   Spend coins in the server shop to buy roles, custom equippable titles, and profile card colors.
    *   Assign specific custom achievements to players via Officer setup commands.
    *   Displays a stunning, customizable `/profile` card showing level, progress bar, MCoin, streak, achievements count, and total tickets completed.
*   **📚 Class Setup Library**: A database for sharing the best class guides.
    *   Stores notes, Non-Forge, Solo, and Ultra boss enchantments, recommended potions, and skill combos.
    *   Interactive paginated dropdown selection menu that automatically updates on edits.
    *   Case-insensitive search autocomplete for `/class_guide`.
*   **🔥 AQW Boost Calendar Scraper**: Auto-scrapes the official Artix Calendar for daily, weekly, and seasonal resource boosts.
    *   Formats descriptions cleanly.
    *   Calculates server resets and displays an active, live countdown timer to the expiration of current boosts.
*   **🎭 Factions & Self Roles**: Mutual-exclusion faction selection (`Chaos`, `Good`, `Evil`) and specialty roles (`Nation`, `Legion`, `Streamer`, `Helper`).
*   **🔍 Charpage & Inventory Lookups**: Instantly query stats, equipment, active inventory, and classes of any player via Discord.

---
## 🛠️ Installation & Setup

> [!NOTE]
> This bot is easiest and recommended to be run on **Linux (Ubuntu/Debian)**, where the entire installation and database setup process is fully automated via the installer script.

You can complete the entire installation (system packages, MariaDB database, virtual environment, python requirements, and playwright browsers) automatically using the setup script:

```bash
# Clone the repository and navigate into the folder
git clone <your-repo-url>
cd MELAYU

# Make scripts executable and run the installer
chmod +x setup.sh start.sh
sudo ./setup.sh
```

### ⚙️ Configure Environment Variables
After the installation completes, edit the generated `.env` file to add your Discord Bot Token:
```env
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ROLE_NAME=MELAYU member
AQW_GUILD_NAME=M E L A Y U

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=melayu_bot
```

### 🚀 Running the Bot
Once configured, run the startup script:
```bash
./start.sh
```

---

## ⚙️ Customizing the Bot (No Coding Required)

Anyone cloning this repository can completely customize the bot for their own server by editing only two configuration files:

### 1. Emojis Mapping: `emojis.py`
To update the custom Discord emojis used in stats lookup, class guide cards, or tournament embeds:
- Open [emojis.py](file:///c:/Users/User/Documents/DISCORD/MELAYU/emojis.py).
- Replace the emoji IDs/strings with the custom emojis matching your server (e.g., `AC_EMOJI = "<:AC:123456789012345678>"`).

### 2. Panel Setup Configs: `panel_config.py`
To customize the embeds, text layouts, images, and colors shown in panels:
- Open [panel_config.py](file:///c:/Users/User/Documents/DISCORD/MELAYU/panel_config.py).
- You can change:
  - **Verification Panel**: Titles, rules, channel directory links, live-stream credits, and default banner image.
  - **Self Roles Panel**: Faction names, roles, instructions, and dark theme colors.
  - **Class Setup Library**: Titles, guide summaries, and gold/embed themes.

---

## 🤖 Commands List

### ⚙️ Server Configuration (Prefix Commands • Admin & Officer Only)
All configuration is performed using the `!setup` command prefix:
*   `!setup verification <aqw_guild_name> <adventure_role> <member_role> [image_url]` — Setup verification config.
*   `!setup ticket <officer_role> <helper_role> <bonus_role> <category> <log_channel> [active_channel]` — Setup tickets config.
*   `!setup boosts <channel> <on/off>` — Toggle daily & weekly automatic AQW boost announcements.
*   `!setup pvp [player_limit]` — Initialize PvP tournament registration and brackets.
*   `!setup roles [channel]` — Setup the Factions & self-assignable roles toggle panel.
*   `!setup class [channel]` — Post the interactive Class Setup Library dropdown.
*   `!setup levelchannel <#channel>` — Set level-up announcement channel.
*   `!setup addshop <role | title | color> <price> <"Name"> <target>` — Add item to server shop.
*   `!setup delshop <item_id>` — Delete item from server shop.
*   `!setup achievement give <@member> <"Achievement">` — Award an achievement to a member.
*   `!setup achievement remove <@member> <"Achievement">` — Revoke/remove an achievement.

### 🛡️ Admin Management Panels (Prefix Commands • Admin Only)
*   `!verification` — Post the interactive AQW character verification board.
*   `!ticketpanel` — Post the Ultra Ticket boss helper request panel.
*   `!resetleaderboard` — Reset helper points on the ticket leaderboard.
*   `!pvp_start` — Seed brackets and start tournament match threads.
*   `!pvp_reset` — Clear brackets, reset player registry, and archive threads.

### 👤 Player Leveling & Shop (Slash Commands)
*   `/profile [user]` — View leveling stats, MCoin balance, achievements count, and completed tickets.
*   `/daily` — Claim daily MCoin and XP rewards with streak bonuses.
*   `/shop` — Browse items, titles, and profile colors.
*   `/buy <item_id>` — Purchase an item using Melayu Coins.
*   `/inventory` — View your purchased shop items and earned achievements.
*   `/equip <name>` — Highlight an unlocked achievement title or custom profile color.
*   `/levelboard` — View the top active members by XP ranking.

### 📚 Class Guides (Slash Commands)
*   `/class_guide [class_name]` — View class setups, enchantments, potions, and combos (includes search autocomplete).
*   `/class_add [class_name] [note] [enchant_non_forge] [enchant_solo] [enchant_ultra] [potion] [combo]` — Adds/updates a guide.
*   `/class_delete [class_name]` — Deletes a guide.

### 🏆 PVP Tournaments (Slash Commands)
*   `/pvp_setwinner [match_id] [winner_ign] [winner_score] [loser_score]` — Record match scores (Officer Only).

### 🎟️ Ultra Ticket System (Slash Commands)
*   `/points` — Check your helper points balance.
*   `/leaderboard` — View the paginated top helper rankings.
*   `/dailystats` — View ticket completion statistics.

### 🔍 Charpage Lookups (Slash Commands)
*   `/charpage [ign]` — Displays player level, class, equipment, and badges.
*   `/checkinv [ign]` — Lists active inventory items and equipment.
*   `/boost_today` — Views the active resource boosts today.
*   `/boost_week` — Views the calendar boosts scheduled for this week.
