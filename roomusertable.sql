DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` int(255) NOT NULL,
  `user_id` int(10) NOT NULL,
  `name` varchar(255) ,
  `leader_card_id` int(10),
  `select_difficulty` int(10),
  `is_me` boolean,
  `is_host` boolean,
  PRIMARY KEY (`room_id`,`user_id`)
);
