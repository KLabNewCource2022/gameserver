DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `room_id` int(255) DEFAULT NULL,
  `live_id` int(10) DEFAULT NULL,
  `joined_user_count` int(10) DEFAULT NULL,
  `max_user_count` int(10) DEFAULT NULL,
  `status` int(10) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `room_id` (`room_id`)
);
