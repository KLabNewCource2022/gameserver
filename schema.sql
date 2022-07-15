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
  `joined_user_count` bigint not null,
  `max_user_count` bigint not null,
  `owner` varchar(255) DEFAULT NULL,
  UNIQUE KEY `room_id` (`room_id`)
);

CREATE TABLE `room_member` (
  `room_id` bigint not null primary key,
  `user_id` varchar(255) default null,
  `select_difficulty` bigint not null,
  UNIQUE KEY `room_id` (`room_id`)
);
