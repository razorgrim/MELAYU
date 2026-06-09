
CREATE TABLE IF NOT EXISTS `active_tickets` (
  `id` int(11) NOT NULL,
  `guild_id` bigint(20) NOT NULL,
  `requester_id` bigint(20) NOT NULL,
  `channel_id` bigint(20) NOT NULL,
  `activity` varchar(255) DEFAULT NULL,
  `category` varchar(255) DEFAULT NULL,
  `points` int(11) DEFAULT 0,
  `manual_points` tinyint(1) DEFAULT 0,
  `max_helpers` int(11) DEFAULT 3,
  `room_number` int(11) DEFAULT NULL,
  `completed` tinyint(1) DEFAULT 0,
  `helpers_locked` tinyint(1) DEFAULT 0,
  `warned` tinyint(1) DEFAULT 0,
  `ign` varchar(100) DEFAULT NULL,
  `server_name` varchar(100) DEFAULT NULL,
  `room_name` varchar(100) DEFAULT NULL,
  `details` text DEFAULT NULL,
  `created_at` double DEFAULT NULL,
  `last_activity` double DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;




CREATE TABLE IF NOT EXISTS `active_ticket_helpers` (
  `ticket_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `active_ticket_helper_points` (
  `ticket_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `points` int(11) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS `helper_points` (
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `points` int(11) DEFAULT 0,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS `server_settings` (
  `guild_id` bigint(20) NOT NULL,
  `boost_channel_id` bigint(20) DEFAULT NULL,
  `boost_notify_enabled` tinyint(1) DEFAULT 0,
  `boost_last_sent_date` date DEFAULT NULL,
  `boost_weekly_last_sent_date` date DEFAULT NULL,
  `ticket_category_id` bigint(20) DEFAULT NULL,
  `ticket_log_channel_id` bigint(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;





CREATE TABLE IF NOT EXISTS `ticket_config` (
  `guild_id` bigint(20) NOT NULL,
  `officer_role_id` bigint(20) NOT NULL,
  `helper_role_id` bigint(20) NOT NULL,
  `bonus_role_id` bigint(20) NOT NULL,
  `ticket_category_id` bigint(20) NOT NULL,
  `ticket_log_channel_id` bigint(20) NOT NULL,
  `active_tickets_channel_id` bigint(20) DEFAULT NULL,
  `completed_stats_message_id` bigint(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `leaderboard_config` (
  `guild_id` bigint(20) NOT NULL,
  `channel_id` bigint(20) DEFAULT NULL,
  `message_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `verification_config` (
  `guild_id` bigint(20) NOT NULL,
  `aqw_guild_name` varchar(100) NOT NULL,
  `adventure_role_id` bigint(20) NOT NULL,
  `member_role_id` bigint(20) NOT NULL,
  `image_url` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS `verified_users` (
  `id` int(11) NOT NULL,
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `nickname` varchar(100) DEFAULT NULL,
  `ign` varchar(100) NOT NULL,
  `discord_nickname` varchar(100) DEFAULT NULL,
  `aqw_guild` varchar(100) DEFAULT NULL,
  `in_target_guild` tinyint(1) DEFAULT 0,
  `verified_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



ALTER TABLE `active_tickets`
  ADD UNIQUE KEY `channel_id` (`channel_id`),
  ADD UNIQUE KEY `unique_user_ticket` (`guild_id`,`requester_id`),
  ADD KEY `idx_active_tickets_channel` (`channel_id`),
  ADD KEY `idx_active_tickets_guild` (`guild_id`),
  ADD KEY `idx_active_tickets_requester` (`requester_id`);

ALTER TABLE `active_ticket_helpers`
  ADD PRIMARY KEY (`ticket_id`,`user_id`);

ALTER TABLE `active_ticket_helper_points`
  ADD PRIMARY KEY (`ticket_id`,`user_id`);


ALTER TABLE `helper_points`
  ADD PRIMARY KEY (`guild_id`,`user_id`),
  ADD KEY `idx_helper_points_guild` (`guild_id`),
  ADD KEY `idx_helper_points_points` (`points`);

CREATE TABLE IF NOT EXISTS `helper_config` (
  `guild_id` bigint(20) NOT NULL,
  `officer_role_id` bigint(20) NOT NULL,
  `helper_role_id` bigint(20) DEFAULT NULL,
  `review_channel_id` bigint(20) DEFAULT NULL,
  `review_category_id` bigint(20) DEFAULT NULL,
  `helper_ticket_counter` int(11) DEFAULT 0,
  PRIMARY KEY (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `helper_applications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `message_id` bigint(20) DEFAULT NULL,
  `channel_id` bigint(20) DEFAULT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'pending',
  `reviewer_id` bigint(20) DEFAULT NULL,
  `review_reason` text DEFAULT NULL,
  `answers` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_helper_application` (`guild_id`,`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `server_settings`
  ADD PRIMARY KEY (`guild_id`);


ALTER TABLE `ticket_config`
  ADD PRIMARY KEY (`guild_id`);


ALTER TABLE `verification_config`
  ADD PRIMARY KEY (`guild_id`);


ALTER TABLE `verified_users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_user_per_server` (`guild_id`,`user_id`),
  ADD UNIQUE KEY `unique_ign_per_server` (`guild_id`,`ign`);


ALTER TABLE `active_tickets`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;


ALTER TABLE `verified_users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

CREATE TABLE IF NOT EXISTS `tournament_config` (
  `guild_id` bigint(20) NOT NULL,
  `channel_id` bigint(20) DEFAULT NULL,
  `message_id` bigint(20) DEFAULT NULL,
  `player_limit` int(11) DEFAULT 8,
  `status` varchar(32) NOT NULL DEFAULT 'registration',
  PRIMARY KEY (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tournament_players` (
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `ign` varchar(100) NOT NULL,
  `seed` int(11) NOT NULL,
  `thread_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`guild_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tournament_matches` (
  `guild_id` bigint(20) NOT NULL,
  `match_id` int(11) NOT NULL,
  `round` int(11) NOT NULL,
  `player1_id` bigint(20) DEFAULT NULL,
  `player2_id` bigint(20) DEFAULT NULL,
  `player1_score` int(11) DEFAULT 0,
  `player2_score` int(11) DEFAULT 0,
  `winner_id` bigint(20) DEFAULT NULL,
  `thread_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`guild_id`, `match_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `class_guides` (
  `guild_id` bigint(20) NOT NULL,
  `class_name` varchar(100) NOT NULL,
  `note` text DEFAULT NULL,
  `enchant_non_forge` text DEFAULT NULL,
  `enchant_solo` text DEFAULT NULL,
  `enchant_ultra` text DEFAULT NULL,
  `potion` text DEFAULT NULL,
  `combo` text DEFAULT NULL,
  PRIMARY KEY (`guild_id`, `class_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `class_config` (
  `guild_id` bigint(20) NOT NULL,
  `panel_channel_id` bigint(20) DEFAULT NULL,
  `panel_message_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `rpg_notifications` (
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  PRIMARY KEY (`guild_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_profiles` (
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `xp` int(11) NOT NULL DEFAULT 0,
  `level` int(11) NOT NULL DEFAULT 1,
  `coins` int(11) NOT NULL DEFAULT 0,
  `active_title` varchar(100) DEFAULT NULL,
  `embed_color` varchar(7) DEFAULT '#5865F2',
  `daily_last_claim` double DEFAULT 0,
  `daily_streak` int(11) NOT NULL DEFAULT 0,
  `inventory` text DEFAULT NULL,
  `achievements` text DEFAULT NULL,
  `completed_tickets` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`guild_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `shop_items` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `guild_id` bigint(20) NOT NULL,
  `name` varchar(100) NOT NULL,
  `type` varchar(32) NOT NULL,
  `price` int(11) NOT NULL,
  `target_id` bigint(20) DEFAULT NULL,
  `target_text` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `level_config` (
  `guild_id` bigint(20) NOT NULL,
  `announcement_channel_id` bigint(20) DEFAULT NULL,
  PRIMARY KEY (`guild_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `daily_stats` (
  `guild_id` bigint(20) NOT NULL,
  `stat_date` date NOT NULL,
  `completed_tickets` int(11) NOT NULL DEFAULT 0,
  `cancelled_tickets` int(11) NOT NULL DEFAULT 0,
  `total_points_given` int(11) NOT NULL DEFAULT 0,
  `helpers` text DEFAULT NULL,
  `requesters` text DEFAULT NULL,
  `activities` text DEFAULT NULL,
  PRIMARY KEY (`guild_id`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

COMMIT;
