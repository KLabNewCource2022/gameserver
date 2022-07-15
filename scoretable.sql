DROP TABLE IF EXISTS `user_score`;
CREATE TABLE `user_score` (
  `user_id` int(10) NOT NULL,
  `perfect` int(10),
  `great` int(10),
  `good` int(10),
  `bad` int(10),
  `miss` int(10),
  `score` int(10) DEFAULT NULL,
  PRIMARY KEY (`user_id`)
);
