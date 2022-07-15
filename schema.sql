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
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  `host_id` int DEFAULT NULL,
  PRIMARY KEY (`id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `room_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `select_difficulty` int DEFAULT NULL,
  `is_end` int DEFAULT NULL,
  `judge_0` int DEFAULT NULL,
  `judge_1` int DEFAULT NULL,
  `judge_2` int DEFAULT NULL,
  `judge_3` int DEFAULT NULL,
  `judge_4` int DEFAULT NULL,
  `score` int DEFAULT NULL,

  PRIMARY KEY (`id`)
);