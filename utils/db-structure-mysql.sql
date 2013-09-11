-- MySQL dump 10.13  Distrib 5.6.12, for osx10.7 (x86_64)
--
-- Host: localhost    Database: qa
-- ------------------------------------------------------
-- Server version	5.6.12

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `cascade_best_categories`
--

DROP TABLE IF EXISTS `cascade_best_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cascade_best_categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `question_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `idea_id` int(11) DEFAULT NULL,
  `best_category` varchar(255) DEFAULT NULL,
  `none_of_the_above` tinyint(4) DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`),
  KEY `question_idea_index` (`question_id`,`idea_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cascade_fit_categories_phase1`
--

DROP TABLE IF EXISTS `cascade_fit_categories_phase1`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cascade_fit_categories_phase1` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `question_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `idea_id` int(11) DEFAULT NULL,
  `category` varchar(255) DEFAULT NULL,
  `fit` int(11) DEFAULT '-1',
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`),
  KEY `question_user_index` (`question_id`,`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cascade_stats`
--

DROP TABLE IF EXISTS `cascade_stats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cascade_stats` (
  `question_id` int(11) NOT NULL,
  `idea_count` int(11) DEFAULT '0',
  `category_count` int(11) DEFAULT '0',
  `uncategorized_count` int(11) DEFAULT '0',
  `user_count` int(11) DEFAULT '0',
  `total_duration` int(11) DEFAULT '0',
  `step1_unsaved_count` int(11) DEFAULT '0',
  `step2_unsaved_count` int(11) DEFAULT '0',
  `step3_unsaved_count` int(11) DEFAULT '0',
  PRIMARY KEY (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cascade_suggested_categories`
--

DROP TABLE IF EXISTS `cascade_suggested_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cascade_suggested_categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `question_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `idea_id` int(11) DEFAULT NULL,
  `suggested_category` varchar(255) DEFAULT NULL,
  `skipped` tinyint(4) DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`),
  KEY `question_idea_index` (`question_id`,`idea_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `categories`
--

DROP TABLE IF EXISTS `categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `category` varchar(255) DEFAULT NULL,
  `same_as` text,
  `subcategories` text,
  `question_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `question_categories`
--

DROP TABLE IF EXISTS `question_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `question_categories` (
  `question_id` int(11) DEFAULT NULL,
  `idea_id` int(11) DEFAULT NULL,
  `category_id` int(11) DEFAULT NULL,
  KEY `question_index` (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `question_ideas`
--

DROP TABLE IF EXISTS `question_ideas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `question_ideas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `question_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `idea` varchar(255) DEFAULT NULL,
  `item_set` int(11) DEFAULT '0',
  `created_on` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `questions`
--

DROP TABLE IF EXISTS `questions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `questions` (
  `id` int(11) NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `question` varchar(255) DEFAULT NULL,
  `nickname_authentication` tinyint(4) DEFAULT '0',
  `user_id` int(11) DEFAULT NULL,
  `active` tinyint(4) DEFAULT '0',
  `last_update` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `cascade_complete` tinyint(4) DEFAULT '0',
  `cascade_k` int(11) DEFAULT '0',
  `cascade_k2` int(11) DEFAULT '0',
  `cascade_m` int(11) DEFAULT '0',
  `cascade_s` int(11) DEFAULT '0',
  `cascade_t` int(11) DEFAULT '0',
  `cascade_p` int(11) DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_clients`
--

DROP TABLE IF EXISTS `user_clients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_clients` (
  `user_id` int(11) DEFAULT NULL,
  `client_id` varchar(255) DEFAULT NULL,
  `waiting_since` timestamp NULL DEFAULT NULL,
  KEY `user_index` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `authenticated_user_id` varchar(255) DEFAULT NULL,
  `authenticated_nickname` varchar(255) DEFAULT NULL,
  `nickname` varchar(50) DEFAULT NULL,
  `question_id` int(11) DEFAULT NULL,
  `latest_login_timestamp` timestamp NULL DEFAULT NULL,
  `latest_logout_timestamp` timestamp NULL DEFAULT NULL,
  `session_sid` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `question_index` (`question_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2013-09-10 16:36:48
