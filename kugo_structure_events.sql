-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: kugo
-- ------------------------------------------------------
-- Server version	5.7.44-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `api_tokens`
--

DROP TABLE IF EXISTS `api_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `api_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `token` varchar(128) NOT NULL,
  `type` enum('admin','worker') NOT NULL,
  `status` enum('active','disabled') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_token` (`token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API访问令牌';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `code_data`
--

DROP TABLE IF EXISTS `code_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `code_data` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `code` varchar(255) NOT NULL COMMENT '券码',
  `uploaded_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '上传时间',
  `fetch_status` tinyint(4) NOT NULL DEFAULT '0',
  `fetched_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_uploaded_at_id` (`uploaded_at`,`id`),
  KEY `idx_fetch_status_fetched` (`fetch_status`,`fetched_at`),
  KEY `idx_fetch_status_uploaded` (`fetch_status`,`uploaded_at`,`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9130 DEFAULT CHARSET=utf8mb4 COMMENT='优惠券队列表（FIFO，取出即删）';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `device_fund_details`
--

DROP TABLE IF EXISTS `device_fund_details`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_fund_details` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` int(11) NOT NULL,
  `fund_in` decimal(10,2) DEFAULT '0.00',
  `manual_fund_out` decimal(10,2) DEFAULT '0.00',
  `auto_fund_out` decimal(10,2) DEFAULT '0.00',
  `balance` decimal(10,2) DEFAULT '0.00',
  `operation_time` timestamp NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=27690 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `img_data`
--

DROP TABLE IF EXISTS `img_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `img_data` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `img_name` varchar(255) NOT NULL,
  `status` int(11) NOT NULL,
  `tel_id` int(11) NOT NULL,
  `url` varchar(500) DEFAULT NULL,
  `thumbnail_url` varchar(500) DEFAULT NULL,
  `cz_status` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=72546 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_data`
--

DROP TABLE IF EXISTS `order_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_data` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `orderID` varchar(255) DEFAULT NULL,
  `status` int(11) DEFAULT NULL COMMENT '状态',
  `type` varchar(255) DEFAULT NULL COMMENT '类型',
  `xp` double DEFAULT NULL COMMENT '经验',
  `result` varchar(255) DEFAULT NULL COMMENT '结果',
  `llp` varchar(255) DEFAULT NULL COMMENT 'llp',
  `time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `phone` varchar(255) DEFAULT NULL COMMENT '手机号',
  `email` varchar(255) DEFAULT NULL COMMENT '邮箱',
  `czp` varchar(255) DEFAULT NULL COMMENT 'czp',
  `dev` varchar(255) DEFAULT NULL COMMENT '设备信息',
  `processed` tinyint(1) DEFAULT '0',
  `upmysql_status` tinyint(4) NOT NULL DEFAULT '1' COMMENT '上传状态：1-未上传，2-已上传',
  PRIMARY KEY (`id`),
  KEY `idx_orderID_time` (`orderID`,`time`)
) ENGINE=InnoDB AUTO_INCREMENT=29021 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_data_anj`
--

DROP TABLE IF EXISTS `order_data_anj`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_data_anj` (
  `id` int(100) NOT NULL AUTO_INCREMENT,
  `orderID` varchar(255) NOT NULL,
  `status` int(11) DEFAULT NULL,
  `type` varchar(255) DEFAULT NULL,
  `xp` float DEFAULT NULL,
  `result` varchar(255) DEFAULT NULL,
  `llp` varchar(255) DEFAULT NULL,
  `time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `phone` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `czp` varchar(255) DEFAULT NULL,
  `dev` varchar(255) DEFAULT NULL,
  `processed` tinyint(1) DEFAULT '0',
  `upmysql_status` int(11) DEFAULT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=52737 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_id`
--

DROP TABLE IF EXISTS `order_id`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_id` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `orderID` varchar(255) DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `type` varchar(255) DEFAULT NULL,
  `xp` double DEFAULT NULL,
  `result` text,
  `llp` varchar(255) DEFAULT NULL,
  `time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `phone` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `czp` varchar(255) DEFAULT NULL,
  `dev` varchar(255) DEFAULT NULL,
  `processed` tinyint(1) DEFAULT '0',
  `upmysql_status` int(11) DEFAULT '1' COMMENT '是否已同步：1未上传，2已上传',
  `getstatus` tinyint(1) NOT NULL DEFAULT '1' COMMENT '1=未被提取, 2=已被提取',
  `91kami` tinyint(4) DEFAULT '0' COMMENT '91卡密上架标记',
  `adminkami` tinyint(4) DEFAULT '0' COMMENT '后台卡密上架标记',
  `getadminkami` tinyint(4) DEFAULT '1' COMMENT '是否已提取',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=73786 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `recharge_tasks`
--

DROP TABLE IF EXISTS `recharge_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `recharge_tasks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `task_no` varchar(64) NOT NULL COMMENT '任务编号',
  `source_batch_id` bigint(20) unsigned DEFAULT NULL COMMENT '批次ID',
  `account_identifier` varchar(64) NOT NULL COMMENT '账号标识',
  `account_remark` varchar(255) DEFAULT NULL COMMENT '备注',
  `plan_type` enum('month','season','year') NOT NULL COMMENT '套餐类型',
  `sale_price` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '售价',
  `recharge_cost` decimal(10,2) DEFAULT NULL COMMENT '充值成本',
  `profit` decimal(10,2) DEFAULT NULL COMMENT '利润（后端计算）',
  `kugou_id` varchar(64) DEFAULT NULL COMMENT '酷狗ID',
  `validity_value` int(11) DEFAULT NULL COMMENT '有效期数值',
  `validity_unit` varchar(16) DEFAULT NULL COMMENT '有效期单位',
  `app_month_price` decimal(10,2) DEFAULT NULL,
  `app_season_price` decimal(10,2) DEFAULT NULL,
  `app_year_price` decimal(10,2) DEFAULT NULL,
  `web_month_price` decimal(10,2) DEFAULT NULL,
  `web_season_price` decimal(10,2) DEFAULT NULL,
  `web_year_price` decimal(10,2) DEFAULT NULL,
  `pc_month_price` decimal(10,2) DEFAULT NULL,
  `pc_season_price` decimal(10,2) DEFAULT NULL,
  `pc_year_price` decimal(10,2) DEFAULT NULL,
  `status` enum('pending','queued','claimed','processing','success','failed','cancelled') NOT NULL DEFAULT 'pending' COMMENT '任务状态',
  `fail_code` varchar(64) DEFAULT NULL,
  `fail_reason` varchar(500) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL COMMENT '上传时间',
  `queued_at` datetime DEFAULT NULL,
  `claimed_at` datetime DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `failed_at` datetime DEFAULT NULL,
  `worker_id` varchar(64) DEFAULT NULL COMMENT '执行节点',
  `retry_count` int(11) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_no` (`task_no`),
  KEY `idx_status_created` (`status`,`created_at`),
  KEY `idx_batch` (`source_batch_id`),
  KEY `idx_account` (`account_identifier`),
  KEY `idx_worker` (`worker_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='充值任务表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `run_status`
--

DROP TABLE IF EXISTS `run_status`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `run_status` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dev` int(11) DEFAULT NULL,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status` varchar(255) DEFAULT '0',
  `restart` tinyint(1) DEFAULT '0' COMMENT '是否已经重启(0-否,1-是)',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=434045 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `submissions`
--

DROP TABLE IF EXISTS `submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `submissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `idempotency_key` varchar(128) NOT NULL,
  `order_id` varchar(64) NOT NULL,
  `response_json` text NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idempotency_key` (`idempotency_key`)
) ENGINE=InnoDB AUTO_INCREMENT=42805 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `task_batches`
--

DROP TABLE IF EXISTS `task_batches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `task_batches` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_no` varchar(64) NOT NULL,
  `batch_name` varchar(255) DEFAULT NULL,
  `total_count` int(11) NOT NULL DEFAULT '0',
  `success_count` int(11) NOT NULL DEFAULT '0',
  `failed_count` int(11) NOT NULL DEFAULT '0',
  `pending_count` int(11) NOT NULL DEFAULT '0',
  `uploaded_by` varchar(64) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_batch_no` (`batch_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批次表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `task_logs`
--

DROP TABLE IF EXISTS `task_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `task_logs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `task_id` bigint(20) unsigned NOT NULL,
  `worker_id` varchar(64) DEFAULT NULL,
  `action` varchar(64) NOT NULL COMMENT '操作类型',
  `content` text COMMENT '日志内容',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_worker` (`worker_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务日志表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tel_data`
--

DROP TABLE IF EXISTS `tel_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tel_data` (
  `id` int(10) NOT NULL AUTO_INCREMENT,
  `tel` varchar(50) DEFAULT NULL,
  `yzm` varchar(255) DEFAULT NULL,
  `details` text,
  `status` varchar(255) DEFAULT '1',
  `create_date` timestamp NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `zhanghu` varchar(255) DEFAULT NULL,
  `c_status` varchar(50) DEFAULT NULL,
  `huiyuanguize` varchar(255) DEFAULT NULL,
  `r_status` varchar(50) DEFAULT NULL,
  `orderID` varchar(50) DEFAULT NULL,
  `shougong` varchar(255) DEFAULT NULL,
  `chongzhitype` varchar(50) DEFAULT NULL,
  `qdzhb` varchar(255) DEFAULT NULL,
  `lingqu3` varchar(255) DEFAULT NULL,
  `applogin` varchar(255) DEFAULT NULL,
  `weblog` varchar(255) DEFAULT NULL,
  `init` varchar(255) DEFAULT NULL,
  `url` varchar(500) DEFAULT NULL,
  `thumbnail_url` varchar(500) DEFAULT NULL,
  `url1` varchar(500) DEFAULT NULL,
  `thumbnail_url1` varchar(500) DEFAULT NULL,
  `yzm_status` varchar(10) NOT NULL DEFAULT '3',
  `pxtype` varchar(255) DEFAULT NULL,
  `email_sent` tinyint(1) DEFAULT '0',
  `userid` char(20) DEFAULT NULL,
  `dev` char(20) DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=106080 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_data`
--

DROP TABLE IF EXISTS `user_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_data` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `phone` varchar(20) NOT NULL,
  `code` varchar(10) NOT NULL,
  `order_id` varchar(50) DEFAULT NULL,
  `status` tinyint(4) DEFAULT '0',
  `nickname1` varchar(255) DEFAULT NULL,
  `pic1` varchar(255) DEFAULT NULL,
  `userid1` bigint(20) DEFAULT NULL,
  `nickname2` varchar(255) DEFAULT NULL,
  `pic2` varchar(255) DEFAULT NULL,
  `userid2` bigint(20) DEFAULT NULL,
  `nickname3` varchar(255) DEFAULT NULL,
  `pic3` varchar(255) DEFAULT NULL,
  `userid3` bigint(20) DEFAULT NULL,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `update_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `code_err` int(11) NOT NULL DEFAULT '1',
  `submitstatus` tinyint(4) DEFAULT '1' COMMENT '1=未提交充值, 2=已提交充值',
  `admin_override` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=36631 DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `workers`
--

DROP TABLE IF EXISTS `workers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `workers` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `worker_id` varchar(64) NOT NULL,
  `worker_name` varchar(100) DEFAULT NULL,
  `status` enum('online','offline','busy') NOT NULL DEFAULT 'online',
  `last_heartbeat_at` datetime DEFAULT NULL,
  `current_task_id` bigint(20) unsigned DEFAULT NULL,
  `concurrency_limit` int(11) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_worker_id` (`worker_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='执行节点表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping events for database 'kugo'
--
/*!50106 SET @save_time_zone= @@TIME_ZONE */ ;
/*!50106 DROP EVENT IF EXISTS `clean_run_status` */;
DELIMITER ;;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;;
/*!50003 SET character_set_client  = utf8mb4 */ ;;
/*!50003 SET character_set_results = utf8mb4 */ ;;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;;
/*!50003 SET sql_mode              = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION' */ ;;
/*!50003 SET @saved_time_zone      = @@time_zone */ ;;
/*!50003 SET time_zone             = 'SYSTEM' */ ;;
/*!50106 CREATE*/ /*!50117 DEFINER=`kugo`@`%`*/ /*!50106 EVENT `clean_run_status` ON SCHEDULE EVERY 1 DAY STARTS '2026-02-11 00:00:00' ON COMPLETION NOT PRESERVE ENABLE DO DELETE FROM run_status
  WHERE create_date < CURDATE() - INTERVAL 1 DAY */ ;;
/*!50003 SET time_zone             = @saved_time_zone */ ;;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;;
/*!50003 SET character_set_client  = @saved_cs_client */ ;;
/*!50003 SET character_set_results = @saved_cs_results */ ;;
/*!50003 SET collation_connection  = @saved_col_connection */ ;;
DELIMITER ;
/*!50106 SET TIME_ZONE= @save_time_zone */ ;

--
-- Dumping routines for database 'kugo'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-03 10:11:24
