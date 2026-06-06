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

### Verification Commands
*   `/verification_setup [aqw_guild_name] [adventure_role] [member_role] [image_url]` — Configures verification roles and target AQW guild check.
*   `/verification` — Sends the interactive character verification panel to a channel.

### Roles & Factions
*   `/rolesetup [channel]` — Sends the Factions and Self roles selection panel.

### Class Guides
*   `/class_add [class_name] [note] [enchant_non_forge] [enchant_solo] [enchant_ultra] [potion] [combo]` — Adds or updates a class guide (Officer Only).
*   `/class_guide [class_name]` — Search and view a class guide setup. Includes search autocomplete.
*   `/class_delete [class_name]` — Deletes a class guide from the library (Officer Only).
*   `/class_panel [channel]` — Sends the interactive, persistent dropdown panel for guides (Officer Only).

### PvP Tournaments
*   `/pvp_setup [player_limit]` — Instantiates a new PvP Tournament brackets registration panel (Officer Only).
*   `/pvp_start` — Locks registration, seeds bracket and creates private match threads (Officer Only).
*   `/pvp_setwinner [match_id] [winner_ign] [winner_score] [loser_score]` — Declares match outcomes and advances the winner (Officer Only).

### Ultra Ticket System
*   `/ticketsetup [officer_role] [helper_role] [bonus_role] [ticket_category] [log_channel] [active_tickets_channel]` — Setup ticket configurations.
*   `/ticketpanel` — Posts the Ultra Ticket creation board (Officer Only).
*   `/points` — Check your helper points balance.

### Charpage Lookups
*   `/charpage [ign]` — Displays player level, class, equipment, and badges.
*   `/checkinv [ign]` — Lists active inventory items and equipment.
*   `/boost` — Views the active daily/weekly boosts with Malaysia-Time countdown timer.
