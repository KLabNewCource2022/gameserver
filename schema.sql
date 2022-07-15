DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL PRIMARY KEY AUTO_INCREMENT,
  `owner_token` varchar(255) DEFAULT NULL,
  `live_id` INT DEFAULT NULL,
  `select_difficulty` INT DEFAULT NULL,
  `joined_user_count` INT NOT NULL DEFAULT 0,
  `max_user_count` INT NOT NULL DEFAULT 1,
  `status` INT NOT NULL DEFAULT 1
);

DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` INT DEFAULT NULL,
  `score` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`room_id`, `user_id`)
);
