-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: May 15, 2026 at 07:05 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `melayu_bot`
--

-- --------------------------------------------------------

--
-- Table structure for table `active_tickets`
--

CREATE TABLE `active_tickets` (
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

-- --------------------------------------------------------

--
-- Table structure for table `active_ticket_helpers`
--

CREATE TABLE `active_ticket_helpers` (
  `ticket_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `active_ticket_helper_points`
--

CREATE TABLE `active_ticket_helper_points` (
  `ticket_id` int(11) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `points` int(11) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `helper_points`
--

CREATE TABLE `helper_points` (
  `guild_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `points` int(11) DEFAULT 0,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- --------------------------------------------------------

--
-- Table structure for table `server_settings`
--

CREATE TABLE `server_settings` (
  `guild_id` bigint(20) NOT NULL,
  `boost_channel_id` bigint(20) DEFAULT NULL,
  `boost_notify_enabled` tinyint(1) DEFAULT 0,
  `boost_last_sent_date` date DEFAULT NULL,
  `ticket_category_id` bigint(20) DEFAULT NULL,
  `ticket_log_channel_id` bigint(20) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;




-- --------------------------------------------------------

--
-- Table structure for table `ticket_config`
--

CREATE TABLE `ticket_config` (
  `guild_id` bigint(20) NOT NULL,
  `officer_role_id` bigint(20) NOT NULL,
  `helper_role_id` bigint(20) NOT NULL,
  `bonus_role_id` bigint(20) NOT NULL,
  `ticket_category_id` bigint(20) NOT NULL,
  `ticket_log_channel_id` bigint(20) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- --------------------------------------------------------

--
-- Table structure for table `verification_config`
--

CREATE TABLE `verification_config` (
  `guild_id` bigint(20) NOT NULL,
  `aqw_guild_name` varchar(100) NOT NULL,
  `adventure_role_id` bigint(20) NOT NULL,
  `member_role_id` bigint(20) NOT NULL,
  `image_url` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- --------------------------------------------------------

--
-- Table structure for table `verified_users`
--

CREATE TABLE `verified_users` (
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


--
-- Indexes for dumped tables
--

--
-- Indexes for table `active_tickets`
--
ALTER TABLE `active_tickets`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `channel_id` (`channel_id`),
  ADD UNIQUE KEY `unique_user_ticket` (`guild_id`,`requester_id`),
  ADD KEY `idx_active_tickets_channel` (`channel_id`),
  ADD KEY `idx_active_tickets_guild` (`guild_id`),
  ADD KEY `idx_active_tickets_requester` (`requester_id`);

--
-- Indexes for table `active_ticket_helpers`
--
ALTER TABLE `active_ticket_helpers`
  ADD PRIMARY KEY (`ticket_id`,`user_id`);

--
-- Indexes for table `active_ticket_helper_points`
--
ALTER TABLE `active_ticket_helper_points`
  ADD PRIMARY KEY (`ticket_id`,`user_id`);

--
-- Indexes for table `helper_points`
--
ALTER TABLE `helper_points`
  ADD PRIMARY KEY (`guild_id`,`user_id`),
  ADD KEY `idx_helper_points_guild` (`guild_id`),
  ADD KEY `idx_helper_points_points` (`points`);

--
-- Indexes for table `server_settings`
--
ALTER TABLE `server_settings`
  ADD PRIMARY KEY (`guild_id`);

--
-- Indexes for table `ticket_config`
--
ALTER TABLE `ticket_config`
  ADD PRIMARY KEY (`guild_id`);

--
-- Indexes for table `verification_config`
--
ALTER TABLE `verification_config`
  ADD PRIMARY KEY (`guild_id`);

--
-- Indexes for table `verified_users`
--
ALTER TABLE `verified_users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `unique_user_per_server` (`guild_id`,`user_id`),
  ADD UNIQUE KEY `unique_ign_per_server` (`guild_id`,`ign`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `active_tickets`
--
ALTER TABLE `active_tickets`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `verified_users`
--
ALTER TABLE `verified_users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
