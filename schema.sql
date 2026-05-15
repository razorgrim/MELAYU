CREATE DATABASE IF NOT EXISTS melayu_bot;

USE melayu_bot;

-- =========================================
-- TICKET CONFIG
-- =========================================

DROP TABLE IF EXISTS ticket_config;

CREATE TABLE ticket_config (
    guild_id BIGINT PRIMARY KEY,

    officer_role_id BIGINT NOT NULL,
    helper_role_id BIGINT NOT NULL,
    bonus_role_id BIGINT NOT NULL,

    ticket_category_id BIGINT NOT NULL,
    ticket_log_channel_id BIGINT NOT NULL
);

-- =========================================
-- HELPER POINTS
-- =========================================

DROP TABLE IF EXISTS helper_points;

CREATE TABLE helper_points (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    points INT DEFAULT 0,

    PRIMARY KEY(guild_id, user_id)
);

-- =========================================
-- ACTIVE TICKETS
-- =========================================

DROP TABLE IF EXISTS active_tickets;

CREATE TABLE active_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,

    guild_id BIGINT NOT NULL,
    requester_id BIGINT NOT NULL,

    channel_id BIGINT NOT NULL UNIQUE,

    activity VARCHAR(255),
    category VARCHAR(255),

    points INT DEFAULT 0,
    manual_points BOOLEAN DEFAULT FALSE,

    max_helpers INT DEFAULT 3,
    room_number INT,

    completed BOOLEAN DEFAULT FALSE,
    helpers_locked BOOLEAN DEFAULT FALSE,
    warned BOOLEAN DEFAULT FALSE,

    ign VARCHAR(100) NULL,
    server_name VARCHAR(100) NULL,
    room_name VARCHAR(100) NULL,

    details TEXT NULL,

    created_at DOUBLE,
    last_activity DOUBLE,

    UNIQUE KEY unique_user_ticket (guild_id, requester_id)
);

-- =========================================
-- ACTIVE TICKET HELPERS
-- =========================================

DROP TABLE IF EXISTS active_ticket_helpers;

CREATE TABLE active_ticket_helpers (
    ticket_id INT NOT NULL,
    user_id BIGINT NOT NULL,

    PRIMARY KEY(ticket_id, user_id)
);

-- =========================================
-- ACTIVE TICKET HELPER CUSTOM POINTS
-- =========================================

DROP TABLE IF EXISTS active_ticket_helper_points;

CREATE TABLE active_ticket_helper_points (
    ticket_id INT NOT NULL,
    user_id BIGINT NOT NULL,
    points INT DEFAULT 0,

    PRIMARY KEY(ticket_id, user_id)
);

-- =========================================
-- VERIFICATION CONFIG
-- =========================================

DROP TABLE IF EXISTS verification_config;

CREATE TABLE verification_config (
    guild_id BIGINT PRIMARY KEY,

    aqw_guild_name VARCHAR(100) NOT NULL,

    adventure_role_id BIGINT NOT NULL,
    member_role_id BIGINT NOT NULL,

    image_url TEXT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

-- =========================================
-- VERIFIED USERS
-- =========================================

DROP TABLE IF EXISTS verified_users;

CREATE TABLE verified_users (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,

    nickname VARCHAR(100),

    ign VARCHAR(100) NOT NULL,
    aqw_guild VARCHAR(100),

    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    last_verified_at DOUBLE NULL,

    PRIMARY KEY (guild_id, user_id),

    UNIQUE KEY unique_ign_per_guild (guild_id, ign)
);

-- =========================================
-- SERVER SETTINGS (BOOSTS)
-- =========================================

DROP TABLE IF EXISTS server_settings;

CREATE TABLE server_settings (
    guild_id BIGINT PRIMARY KEY,

    boost_channel_id BIGINT NULL,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

-- =========================================
-- INDEXES
-- =========================================

CREATE INDEX idx_active_tickets_channel
ON active_tickets(channel_id);

CREATE INDEX idx_active_tickets_guild
ON active_tickets(guild_id);

CREATE INDEX idx_active_tickets_requester
ON active_tickets(requester_id);

CREATE INDEX idx_helper_points_guild
ON helper_points(guild_id);

CREATE INDEX idx_helper_points_points
ON helper_points(points DESC);