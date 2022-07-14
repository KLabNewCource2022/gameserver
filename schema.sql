DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `room_member`;

CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);


CREATE TABLE `room` (
  `room_id` bigint not null AUTO_INCREMENT primary key,
  `live_id` bigint not null,
  `select_difficulty`bigint not null,
  `status` bigint not null,
  `owner` varchar(255) DEFAULT NULL,
  UNIQUE KEY `room_id` (`room_id`)
);

CREATE TABLE `room_member` (
  `room_id` bigint not null AUTO_INCREMENT primary key,
  `user1` varchar(255) DEFAULT NULL,
  `user2` varchar(255) DEFAULT NULL,
  `user3` varchar(255) DEFAULT NULL,
  `user4` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  UNIQUE KEY `room_id` (`room_id`)
);
