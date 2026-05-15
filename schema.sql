CREATE DATABASE IF NOT EXISTS melayu_bot;

USE melayu_bot;

CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id BIGINT PRIMARY KEY,

    officer_role_id BIGINT NOT NULL,
    helper_role_id BIGINT NOT NULL,
    bonus_role_id BIGINT NOT NULL,

    ticket_category_id BIGINT NOT NULL,
    ticket_log_channel_id BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS helper_points (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    points INT DEFAULT 0,

    PRIMARY KEY(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS active_tickets (
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

CREATE TABLE IF NOT EXISTS active_ticket_helpers (
    ticket_id INT NOT NULL,
    user_id BIGINT NOT NULL,

    PRIMARY KEY(ticket_id, user_id)
);

CREATE TABLE IF NOT EXISTS active_ticket_helper_points (
    ticket_id INT NOT NULL,
    user_id BIGINT NOT NULL,
    points INT DEFAULT 0,

    PRIMARY KEY(ticket_id, user_id)
);

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