# panel_config.py
# Centralized configurations for all setup panels (verification, self-roles, and class setup library).
# Edit these texts to customize the embeds sent by setup commands.

import emojis

# ==========================================
# 1. VERIFICATION PANEL
# ==========================================
VERIFICATION_TITLE = "AQW Guild Verification"
VERIFICATION_FOOTER = "AQW Verification System"
VERIFICATION_COLOR = 0x2ecc71  # Hex color (Green)
VERIFICATION_DEFAULT_IMAGE = "https://i.imgur.com/vBeUbYo.jpeg"

# Template for description. Variables inside {curly_brackets} are dynamic.
VERIFICATION_DESCRIPTION_TEMPLATE = (
    "**Welcome to Community AQW MALAYSIA 🔥 **\n\n"
    "**Rules :**\n"
    "❗Dilarang maki / toxic\n"
    "❗Hormat sesama bangsa\n"
    "❗Dilarang OGs\n"
    "❗Dilarang EGoiS\n"
    "❗Dilarang Malu (Berpada)\n"
    "❗Dilarang Sepuh\n\n"
    "**Info Channel :**\n"
    "‼️  <#1421387103874580540> - update event @ server ***AQW MALAYSIA***\n"
    f"{emojis.PEAK_EMOJI}  <#1417856460959911937><#1476205076476329984>  - update event **photoshoot / GiveAway*AQW MALAYSIA***\n"
    "🚨  <#1499820764155744508>  - perlukan bantuan, Just info❗ \n"
    f"{emojis.AC_EMOJI_ALT}  <#1420637572698472522> - promote / jual-beli account and heromart\n\n"
    "**Info update AQW :**\n"
    f"{emojis.MEMBER_EMOJI_ALT}   <#1416994105086705694> - Update  Server boost daily / weekly / seasonal\n"
    f"{emojis.MELAYU_EMOJI}   <#1417017084407189565> - remind update / seasonal / rare item & update\n"
    f"{emojis.ARMOR_EMOJI_ALT}   <#1417851796155666555> - drop & merge shop update\n"
    f"{emojis.FORGE_EMOJI}   <#1458693247357685833>  - Enhancement detail\n\n"
    "**Support LiveStream / Content Creator Malaysia :**\n"
    f"{emojis.TIKTOK_EMOJI} : mannn_aqw by <@1268595767082483832> \n"
    f"{emojis.TIKTOK_EMOJI} : chimikopunyayuka by <@530444863393759232> \n"
    f"{emojis.TIKTOK_EMOJI} : mirulz_aqw by <@1421902432308297739> \n"
    f"{emojis.TIKTOK_EMOJI} : ris_anime0 by <@1439948797282095125> \n\n"
    "** Link AQW MALAYSIA COMMUNITY : **\n"
    f"{emojis.WHATSAPP_EMOJI} Whatsapp : https://chat.whatsapp.com/I5a6BRWtdYBClgbBiSA7J5\n\n"
    "**#AQWMALAYSIA**\n\n"
    "Click the button below to verify your AdventureQuest Worlds character.\n\n"
    "**How it works:**\n"
    "• All valid AQW players receive {adventure_role_mention}\n"
    "• Players inside **{aqw_guild_name}** also receive {member_role_mention}\n\n"
    "**Nickname Format:**\n"
    "`nickname ● ign ● Nationality`\n\n"
    "**Requirement:**\n"
    "Your AQW character page must be public and accessible."
)

# ==========================================
# 2. SELF ROLES PANEL
# ==========================================
ROLES_TITLE = "🎭  Faction & Self Roles Selection"
ROLES_FOOTER = "AQW MELAYU • Click buttons below to assign roles"
ROLES_COLOR = 0x2f3136  # Hex color (Premium dark matching Discord UI)

ROLES_DESCRIPTION = (
    "Stand with your faction or gain access to community roles! "
    "Click the buttons below to toggle your roles.\n\n"
    f"{emojis.CHARPAGE_ICON} **Factions (Choose One)**\n\n"
    f"• {emojis.CHAOS_FACTION} **Chaos**: Embrace the storm and unpredictability.\n"
    f"• {emojis.GOOD_FACTION} **Good**: Stand for honor, order, and justice.\n"
    f"• {emojis.EVIL_FACTION} **Evil**: Walk in the shadows and seek dark power.\n"
    "*(Note: Factions are mutually exclusive. Selecting a new one removes your current faction.)*\n\n"
    "⚔️ **Special Sub-Factions**\n\n"
    f"• {emojis.NATION_FACTION} **Nation**: Archfiend Nulgath's loyal follower.\n"
    f"• {emojis.LEGION_FACTION} **Legion**: Dage the Evil's Undead Legion warrior.\n\n"
    "💼 **Community Roles**\n\n"
    "• 🎥 **Streamer**: Get access to streamer channels & ping alerts.\n"
    "• 🛡️ **Helper**: Join community helpers to support others."
)

# ==========================================
# 3. CLASS SETUP LIBRARY PANEL
# ==========================================
CLASS_TITLE = "⚔️ AQW Class Setup Library"
CLASS_FOOTER_TEMPLATE = "{guild_name} Library Panel"
CLASS_COLOR = 0xd4af37  # Hex color (Gold)

CLASS_DESCRIPTION = (
    "Welcome to the official **AQW Class Setup Library**!\n\n"
    "Gunakan menu di bawah untuk select and view class guides, enchants, and attack rotations.\n\n"
    "📌 **Categories in Guide:**\n"
    "• **Note:** Description and usage tips\n"
    "• **Enchantments:** 3 Types (Non-Forge, Solo, and Ultra)\n"
    "• **Potions:** Best elixirs and tonics\n"
    "• **Combo:** Recommended skill sequence rotations\n\n"
    "*(Note: You can also search guides case-insensitively using `/class_guide`!)*"
)
