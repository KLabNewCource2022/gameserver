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
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `max_user_count` int DEFAULT NULL,
  `started` bit DEFAULT 0,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `member_id` bigint NOT NULL AUTO_INCREMENT,
  `room_id` bigint NOT NULL,
  `select_difficulty` int DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `is_host` bit DEFAULT 0,
  `judge_count_list` varchar(255) DEFAULT NULL,
  `score` bigint DEFAULT NULL,
  PRIMARY KEY (`member_id`)
);
