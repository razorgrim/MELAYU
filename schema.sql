CREATE DATABASE IF NOT EXISTS `melayu_bot` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `melayu_bot`;

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
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
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
  ADD PRIMARY KEY (`id`),
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
COMMIT;
