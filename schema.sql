
DROP TABLE IF EXISTS `room_member`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `wait_room_status` tinyint NOT NULL,
  `created_by` bigint NOT NULL,
  `max_user_count` tinyint DEFAULT 4,
  `can_join` boolean NOT NULL DEFAULT 1,
  `room_status` tinyint DEFAULT 1,
  PRIMARY KEY (`id`)
  -- FOREIGN KEY `room` (`created_by`) references `user` (`id`)
);

CREATE TABLE `room_member` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` tinyint NOT NULL,
  PRIMARY KEY (`id`)
  -- FOREIGN KEY `room_member` (`room_id`) references `room` (`id`),
  -- FOREIGN KEY `room_member` (`user_id`) references `user` (`id`)
);