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
  `id` bigint not null AUTO_INCREMENT primary key,
  `live_id` bigint not null,
  `owner` bigint not null
);

CREATE TABLE `room_member` (
  `id` bigint not null AUTO_INCREMENT primary key,
  `room_id` bigint not null,
  `user_id` bigint not null
);
