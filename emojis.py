# emojis.py
# Centralized configurations for custom Discord emojis used by the bot.
# Replace these with your own custom Discord emoji strings if cloning the repo.

# --- Boost & Tag Emojis ---
CLASS_BOOST = "<:ClassBoost:1505372617014775928>"
EXP_BOOST = "<:ExpBoost:1505372494922780753>"
REP_BOOST = "<:RepBoost:1505372317650255984>"
GOLD_BOOST = "<:GoldBoost:1505359354780586065>"
MEMBER_BOOST = "<:Member:1505373039267680457>"
ACS_BOOST = "<:Acs:1505374359445831730>"
SEASONAL_TAG = "<:seasonaltag:1505375179923263649>"
RARE_TAG = "<:raretag:1505375179923263649>"
LEGEND_TAG = "<:legendtag:1505375321816436757>"
BAG_ICON = "<:bagicon2:1505377192236814439>"

# --- Equipment Emojis ---
HELM_ICON = "<:helmicon:1506182631887339560>"
CLASS_ICON = "<:classicon:1506184256894926898>"
CAPE_ICON = "<:capeicon:1506183156024344687>"
SWORD_ICON = "<:swordicon:1506182453398601749>"
ARMOR_ICON = "<:armoricon:1506182318765641738>"
PET_ICON = "<:peticon:1506318442590896230>"
BAG_ICON_ALT = "<:bagicon:1505377192236814439>"

# --- Faction Emojis ---
CHAOS_FACTION = "<:chaosfaction:1506322127819767948>"
GOOD_FACTION = "<:goodfaction:1506321915114160128>"
EVIL_FACTION = "<:evilfaction:1506322000652796104>"
NEUTRAL_FACTION = "<:neutralfaction:1506322065668440106>"
NATION_FACTION = "<:nulgathicon:1507433966393622619>"
LEGION_FACTION = "<:dageicon:1507434313270951946>"

# --- UI & Calc Emojis ---
AC_ICON = "<:acicon:1506189807699759176>"
AC_ICON_2 = "<:acicon2:1506190761543340072>"
CHARPAGE_ICON = "<:charpageicon:1506324498943840366>"
CHARPAGE_ICON_2 = "<:charpageicon2:1506324684092866591>"
TREASURE_POTION = "<:treasurepotionicon:1506323420906782912>"

# --- Branding & Info Emojis ---
PEAK_EMOJI = "<:peak:1506207568194834553>"
AC_EMOJI_ALT = "<:AC:1505181977140007013>"
MEMBER_EMOJI_ALT = "<:Member:1505181901462442104>"
MELAYU_EMOJI = "<:MELAYU:1505185518730739742>"
MELAYU_EMOJI_ALT = "<:Melayu:1505432584090423476>"
ARMOR_EMOJI_ALT = "<:armoricon:1506286259965005976>"
FORGE_EMOJI = "<:Forge:1506289845507592252>"
TIKTOK_EMOJI = "<:Tiktok:1506290622762455091>"
WHATSAPP_EMOJI = "<:whatsapp:1506285343618629653>"

# Dictionary access helper
EMOJIS = {
    # Boosts / Tags
    "class_boost": CLASS_BOOST,
    "exp_boost": EXP_BOOST,
    "rep_boost": REP_BOOST,
    "gold_boost": GOLD_BOOST,
    "member_boost": MEMBER_BOOST,
    "acs_boost": ACS_BOOST,
    "seasonal_tag": SEASONAL_TAG,
    "rare_tag": RARE_TAG,
    "legend_tag": LEGEND_TAG,
    "bag_icon": BAG_ICON,

    # Equipment
    "helm_icon": HELM_ICON,
    "class_icon": CLASS_ICON,
    "cape_icon": CAPE_ICON,
    "sword_icon": SWORD_ICON,
    "armor_icon": ARMOR_ICON,
    "pet_icon": PET_ICON,
    "bag_icon_alt": BAG_ICON_ALT,

    # Factions
    "chaos": CHAOS_FACTION,
    "good": GOOD_FACTION,
    "evil": EVIL_FACTION,
    "neutral": NEUTRAL_FACTION,
    "nation": NATION_FACTION,
    "legion": LEGION_FACTION,

    # UI / Calculator
    "ac_icon": AC_ICON,
    "ac_icon_2": AC_ICON_2,
    "charpage_icon": CHARPAGE_ICON,
    "charpage_icon_2": CHARPAGE_ICON_2,
    "treasure_potion": TREASURE_POTION,

    # Branding & Info
    "peak": PEAK_EMOJI,
    "ac_alt": AC_EMOJI_ALT,
    "member_alt": MEMBER_EMOJI_ALT,
    "melayu": MELAYU_EMOJI,
    "melayu_alt": MELAYU_EMOJI_ALT,
    "armor_alt": ARMOR_EMOJI_ALT,
    "forge": FORGE_EMOJI,
    "tiktok": TIKTOK_EMOJI,
    "whatsapp": WHATSAPP_EMOJI,
}

def get_emoji(name, default=""):
    return EMOJIS.get(name, default)
