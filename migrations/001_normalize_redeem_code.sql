-- 001_normalize_redeem_code.sql
-- Safe compatibility migration for old Koko databases.
--
-- Purpose:
--   * Add the canonical redeem_code column while keeping legacy orderID/order_id.
--   * Add missing new-backend compatibility columns such as admin_override.
--   * Create missing new-backend tables without deleting or overwriting production data.
--   * Add indexes used by high-frequency Python/PHP queries.
--
-- BEFORE RUNNING IN PRODUCTION:
--   1. Take a full logical backup, for example:
--      mysqldump --single-transaction --routines --events --databases koko > koko_backup_$(date +%F_%H%M%S).sql
--   2. Run during a low-traffic window.
--   3. Test on a restored staging database first.
--
-- Safety notes:
--   * This migration intentionally does NOT delete data and does NOT remove production tables.
--   * This file uses MySQL 5.7-compatible INFORMATION_SCHEMA checks before ALTER/CREATE INDEX.
--   * DDL in MySQL causes implicit commits; failed DDL cannot be fully rolled back with ROLLBACK.
--   * Re-running is designed to be harmless for the guarded ALTER/CREATE INDEX operations, but
--     production procedure should still execute it once per database change window and record it.

SET NAMES utf8mb4;

-- -----------------------------------------------------------------------------
-- Helper procedures: MySQL 5.7-compatible guarded DDL.
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- Create missing new-backend tables. Existing tables are not modified here.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `api_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `token` varchar(128) NOT NULL,
  `type` enum('admin','worker') NOT NULL,
  `status` enum('active','disabled') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_api_tokens_token` (`token`),
  KEY `idx_api_tokens_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API访问令牌';

CREATE TABLE IF NOT EXISTS `code_data` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `code` varchar(255) NOT NULL COMMENT '券码/领取URL',
  `uploaded_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '上传时间',
  `fetch_status` tinyint(4) NOT NULL DEFAULT '0' COMMENT '0=未取,1=已取',
  `fetched_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_code_data_uploaded_at_id` (`uploaded_at`,`id`),
  KEY `idx_code_data_fetch_fetched` (`fetch_status`,`fetched_at`),
  KEY `idx_code_data_fetch_uploaded` (`fetch_status`,`uploaded_at`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='优惠券队列表（FIFO，取出即删）';

CREATE TABLE IF NOT EXISTS `device_fund_details` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `device_id` int(11) NOT NULL,
  `fund_in` decimal(10,2) DEFAULT '0.00',
  `manual_fund_out` decimal(10,2) DEFAULT '0.00',
  `auto_fund_out` decimal(10,2) DEFAULT '0.00',
  `balance` decimal(10,2) DEFAULT '0.00',
  `operation_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_device_fund_device_time` (`device_id`,`operation_time`,`id`),
  KEY `idx_device_fund_device_id` (`device_id`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备资金流水';

CREATE TABLE IF NOT EXISTS `submissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `idempotency_key` varchar(128) NOT NULL,
  `order_id` varchar(64) NOT NULL,
  `redeem_code` varchar(64) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors order_id',
  `response_json` text NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_submissions_idempotency_key` (`idempotency_key`),
  KEY `idx_submissions_order_created` (`order_id`,`created_at`),
  KEY `idx_submissions_redeem_created` (`redeem_code`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='接口幂等提交记录';

CREATE TABLE IF NOT EXISTS `task_batches` (
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
  UNIQUE KEY `uk_task_batches_batch_no` (`batch_no`),
  KEY `idx_task_batches_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批次表';

CREATE TABLE IF NOT EXISTS `recharge_tasks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `task_no` varchar(64) NOT NULL COMMENT '任务编号',
  `source_batch_id` bigint(20) unsigned DEFAULT NULL COMMENT '批次ID',
  `account_identifier` varchar(64) NOT NULL COMMENT '账号标识',
  `account_remark` varchar(255) DEFAULT NULL COMMENT '备注',
  `plan_type` enum('month','season','year') NOT NULL COMMENT '套餐类型',
  `sale_price` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '售价',
  `recharge_cost` decimal(10,2) DEFAULT NULL,
  `profit` decimal(10,2) DEFAULT NULL,
  `kugou_id` varchar(64) DEFAULT NULL,
  `validity_value` int(11) DEFAULT NULL,
  `validity_unit` varchar(16) DEFAULT NULL,
  `app_month_price` decimal(10,2) DEFAULT NULL,
  `app_season_price` decimal(10,2) DEFAULT NULL,
  `app_year_price` decimal(10,2) DEFAULT NULL,
  `web_month_price` decimal(10,2) DEFAULT NULL,
  `web_season_price` decimal(10,2) DEFAULT NULL,
  `web_year_price` decimal(10,2) DEFAULT NULL,
  `pc_month_price` decimal(10,2) DEFAULT NULL,
  `pc_season_price` decimal(10,2) DEFAULT NULL,
  `pc_year_price` decimal(10,2) DEFAULT NULL,
  `status` enum('pending','queued','claimed','processing','success','failed','cancelled') NOT NULL DEFAULT 'pending',
  `fail_code` varchar(64) DEFAULT NULL,
  `fail_reason` varchar(500) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL,
  `queued_at` datetime DEFAULT NULL,
  `claimed_at` datetime DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  `failed_at` datetime DEFAULT NULL,
  `worker_id` varchar(64) DEFAULT NULL,
  `retry_count` int(11) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_recharge_tasks_task_no` (`task_no`),
  KEY `idx_recharge_tasks_status_created` (`status`,`created_at`),
  KEY `idx_recharge_tasks_batch` (`source_batch_id`),
  KEY `idx_recharge_tasks_account` (`account_identifier`),
  KEY `idx_recharge_tasks_worker` (`worker_id`),
  KEY `idx_recharge_tasks_claim` (`status`,`worker_id`,`claimed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='充值任务表';

CREATE TABLE IF NOT EXISTS `task_logs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `task_id` bigint(20) unsigned NOT NULL,
  `worker_id` varchar(64) DEFAULT NULL,
  `action` varchar(64) NOT NULL,
  `content` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_logs_task_id` (`task_id`),
  KEY `idx_task_logs_worker` (`worker_id`),
  KEY `idx_task_logs_action_created` (`action`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务日志表';

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

-- -----------------------------------------------------------------------------
-- Add compatibility columns to existing legacy tables.
-- -----------------------------------------------------------------------------
CALL `koko_add_column_if_missing`('order_id', 'redeem_code', 'varchar(255) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy orderID'' AFTER `orderID`');
CALL `koko_add_column_if_missing`('order_data_anj', 'redeem_code', 'varchar(255) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy orderID'' AFTER `orderID`');
CALL `koko_add_column_if_missing`('order_data', 'redeem_code', 'varchar(255) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy orderID'' AFTER `orderID`');
CALL `koko_add_column_if_missing`('tel_data', 'redeem_code', 'varchar(50) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy orderID/orderid'' AFTER `orderID`');
CALL `koko_add_column_if_missing`('user_data', 'redeem_code', 'varchar(50) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy order_id'' AFTER `order_id`');
CALL `koko_add_column_if_missing`('submissions', 'redeem_code', 'varchar(64) NULL COMMENT ''Canonical redeem/recharge code; mirrors legacy order_id'' AFTER `order_id`');
CALL `koko_add_column_if_missing`('user_data', 'code_err', 'int(11) NOT NULL DEFAULT ''1''');
CALL `koko_add_column_if_missing`('user_data', 'submitstatus', 'tinyint(4) DEFAULT ''1'' COMMENT ''1=未提交充值, 2=已提交充值''');
CALL `koko_add_column_if_missing`('user_data', 'admin_override', 'tinyint(1) NOT NULL DEFAULT ''0''');
CALL `koko_add_column_if_missing`('tel_data', 'email_sent', 'tinyint(1) DEFAULT ''0''');
CALL `koko_add_column_if_missing`('tel_data', 'userid', 'char(20) DEFAULT NULL');
CALL `koko_add_column_if_missing`('tel_data', 'dev', 'char(20) DEFAULT NULL');
CALL `koko_add_column_if_missing`('code_data', 'fetch_status', 'tinyint(4) NOT NULL DEFAULT ''0''');
CALL `koko_add_column_if_missing`('code_data', 'fetched_at', 'datetime DEFAULT NULL');

-- Populate canonical columns from legacy fields; no existing real data is deleted.
UPDATE `order_id` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
UPDATE `order_data_anj` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
UPDATE `order_data` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
UPDATE `tel_data` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
UPDATE `user_data` SET `redeem_code` = `order_id` WHERE `redeem_code` IS NULL AND `order_id` IS NOT NULL;
UPDATE `submissions` SET `redeem_code` = `order_id` WHERE `redeem_code` IS NULL AND `order_id` IS NOT NULL;

-- -----------------------------------------------------------------------------
-- Add high-frequency query indexes. Existing indexes with these names are kept.
-- -----------------------------------------------------------------------------
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_orderID_status', '(`orderID`, `status`)');
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_redeem_status', '(`redeem_code`, `status`)');
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_status_created', '(`status`, `created_at`)');
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_getstatus_id', '(`getstatus`, `id`)');
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_admin_get', '(`adminkami`, `getadminkami`, `status`)');
CALL `koko_add_index_if_missing`('order_data_anj', 'idx_order_data_anj_orderID', '(`orderID`)');
CALL `koko_add_index_if_missing`('order_data_anj', 'idx_order_data_anj_redeem_status', '(`redeem_code`, `status`)');
CALL `koko_add_index_if_missing`('order_data_anj', 'idx_order_data_anj_status_time', '(`status`, `time`)');
CALL `koko_add_index_if_missing`('order_data', 'idx_order_data_orderID_time', '(`orderID`, `time`)');
CALL `koko_add_index_if_missing`('order_data', 'idx_order_data_redeem_time', '(`redeem_code`, `time`)');
CALL `koko_add_index_if_missing`('order_data', 'idx_order_data_status_time', '(`status`, `time`)');
CALL `koko_add_index_if_missing`('order_data', 'idx_order_data_processed_dev', '(`processed`, `dev`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_tel_created', '(`tel`, `create_date`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_orderID', '(`orderID`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_redeem_status', '(`redeem_code`, `status`, `yzm_status`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_status_created', '(`status`, `create_date`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_r_status_created', '(`r_status`, `create_date`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_c_status', '(`c_status`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_yzm_status', '(`yzm_status`)');
CALL `koko_add_index_if_missing`('tel_data', 'idx_tel_data_init_tel', '(`init`, `tel`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_phone_created', '(`phone`, `create_date`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_order_id_created', '(`order_id`, `create_date`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_redeem_created', '(`redeem_code`, `create_date`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_status_created', '(`status`, `create_date`)');
CALL `koko_add_index_if_missing`('user_data', 'idx_user_data_submitstatus', '(`submitstatus`)');
CALL `koko_add_index_if_missing`('submissions', 'idx_submissions_order_created', '(`order_id`, `created_at`)');
CALL `koko_add_index_if_missing`('submissions', 'idx_submissions_redeem_created', '(`redeem_code`, `created_at`)');
CALL `koko_add_index_if_missing`('code_data', 'idx_code_data_fetch_fetched', '(`fetch_status`, `fetched_at`)');
CALL `koko_add_index_if_missing`('code_data', 'idx_code_data_fetch_uploaded', '(`fetch_status`, `uploaded_at`, `id`)');
CALL `koko_add_index_if_missing`('device_fund_details', 'idx_device_fund_device_time', '(`device_id`, `operation_time`, `id`)');
CALL `koko_add_index_if_missing`('run_status', 'idx_run_status_dev_created', '(`dev`, `create_date`)');
CALL `koko_add_index_if_missing`('img_data', 'idx_img_data_tel_id', '(`tel_id`)');

-- Cleanup helper procedures created only for this migration.
DROP PROCEDURE IF EXISTS `koko_add_index_if_missing`;
DROP PROCEDURE IF EXISTS `koko_add_column_if_missing`;
