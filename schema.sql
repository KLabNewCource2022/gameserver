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
  `id` bigint not null auto_increment,
  `live_id` int not null,
  `owner` int not null,
  `status` int not null,
  `member_count` int not null,
  primary key (`id`)
);

drop table if exists `room_member`;
create table `room_member` (
  `room_id` bigint not null,
  `user_id` bigint not null,
  `difficulty` int not null,
  `result` varchar(512),
  primary key (`room_id`, `user_id`)
);