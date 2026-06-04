-- 002_anj_api_compatibility.sql
-- Safe MySQL 5.7-compatible migration for Anjian/automation-client tel_data APIs.
-- Does not delete or overwrite data. Run after taking a production backup and testing on staging.

SET NAMES utf8mb4;

DELIMITER $$

DROP PROCEDURE IF EXISTS `koko_add_column_if_missing`$$
CREATE PROCEDURE `koko_add_column_if_missing`(
  IN p_table_name varchar(64),
  IN p_column_name varchar(64),
  IN p_column_definition text
)
BEGIN
  IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name AND COLUMN_NAME = p_column_name
  ) THEN
    SET @koko_sql = CONCAT('ALTER TABLE `', p_table_name, '` ADD COLUMN `', p_column_name, '` ', p_column_definition);
    PREPARE stmt FROM @koko_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$

DROP PROCEDURE IF EXISTS `koko_add_index_if_missing`$$
CREATE PROCEDURE `koko_add_index_if_missing`(
  IN p_table_name varchar(64),
  IN p_index_name varchar(64),
  IN p_index_definition text
)
BEGIN
  IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name
  ) AND NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_table_name AND INDEX_NAME = p_index_name
  ) THEN
    SET @koko_sql = CONCAT('CREATE INDEX `', p_index_name, '` ON `', p_table_name, '` ', p_index_definition);
    PREPARE stmt FROM @koko_sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$

DELIMITER ;

CREATE TABLE IF NOT EXISTS `run_status` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dev` varchar(64) DEFAULT NULL,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status` varchar(255) DEFAULT '0',
  `restart` tinyint(1) DEFAULT '0' COMMENT '是否已经重启(0-否,1-是)',
  PRIMARY KEY (`id`),
  KEY `idx_run_status_dev_created` (`dev`,`create_date`),
  KEY `idx_run_status_status_created` (`status`,`create_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备运行状态';

CREATE TABLE IF NOT EXISTS `workers` (
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
  UNIQUE KEY `uk_workers_worker_id` (`worker_id`),
  KEY `idx_workers_status_heartbeat` (`status`,`last_heartbeat_at`),
  KEY `idx_workers_current_task` (`current_task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='执行节点表';

CALL `koko_add_column_if_missing`('tel_data', 'redeem_code', 'varchar(50) NULL COMMENT ''Canonical redeem/recharge code; mirrors orderID/orderid'' AFTER `orderID`');
CALL `koko_add_column_if_missing`('tel_data', 'details', 'text NULL');
CALL `koko_add_column_if_missing`('tel_data', 'pxtype', 'varchar(255) DEFAULT NULL');
CALL `koko_add_column_if_missing`('tel_data', 'userid', 'char(20) DEFAULT NULL');
CALL `koko_add_column_if_missing`('tel_data', 'dev', 'char(20) DEFAULT NULL');
CALL `koko_add_column_if_missing`('user_data', 'redeem_code', 'varchar(50) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy order_id'' AFTER `order_id`');
ALTER TABLE `run_status` MODIFY COLUMN `dev` varchar(64) DEFAULT NULL;

UPDATE `tel_data` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
UPDATE `user_data` SET `redeem_code` = `order_id` WHERE `redeem_code` IS NULL AND `order_id` IS NOT NULL;

CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_anj_claim', '(`status`, `yzm_status`, `r_status`, `id`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_redeem_status', '(`redeem_code`, `status`, `yzm_status`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_dev_created', '(`dev`, `create_date`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_redeem_created', '(`redeem_code`, `create_date`)');

DROP PROCEDURE IF EXISTS `koko_add_index_if_missing`;
DROP PROCEDURE IF EXISTS `koko_add_column_if_missing`;
