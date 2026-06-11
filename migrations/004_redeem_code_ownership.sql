-- 004_redeem_code_ownership.sql
-- MySQL 5.7-compatible ownership fields used by code generation and admin extraction.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `agent_account` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `agent_code` varchar(30) NOT NULL,
  `agent_name` varchar(100) NOT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `status` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_account_code` (`agent_code`),
  KEY `idx_agent_account_status_id` (`status`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='兑换码代理账户';

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

CALL `koko_add_column_if_missing`('agent_account', 'status', 'tinyint(1) NOT NULL DEFAULT ''1''');
CALL `koko_add_column_if_missing`('order_id', 'source_type', 'varchar(20) DEFAULT NULL COMMENT ''retail or agent''');
CALL `koko_add_column_if_missing`('order_id', 'agent_id', 'bigint(20) unsigned DEFAULT NULL');
CALL `koko_add_column_if_missing`('order_id', 'agent_code', 'varchar(30) DEFAULT NULL');
CALL `koko_add_column_if_missing`('order_id', 'agent_name', 'varchar(100) DEFAULT NULL');
CALL `koko_add_column_if_missing`('order_data_anj', 'source_type', 'varchar(20) DEFAULT NULL COMMENT ''retail or agent''');
CALL `koko_add_column_if_missing`('order_data_anj', 'agent_id', 'bigint(20) unsigned DEFAULT NULL');
CALL `koko_add_column_if_missing`('order_data_anj', 'agent_code', 'varchar(30) DEFAULT NULL');
CALL `koko_add_column_if_missing`('order_data_anj', 'agent_name', 'varchar(100) DEFAULT NULL');

CALL `koko_add_index_if_missing`('agent_account', 'idx_agent_account_status_id', '(`status`, `id`)');
CALL `koko_add_index_if_missing`('order_id', 'idx_order_id_ownership', '(`source_type`, `agent_code`, `agent_id`, `id`)');
CALL `koko_add_index_if_missing`('order_data_anj', 'idx_order_data_anj_ownership', '(`source_type`, `agent_code`, `agent_id`, `id`)');

DROP PROCEDURE IF EXISTS `koko_add_index_if_missing`;
DROP PROCEDURE IF EXISTS `koko_add_column_if_missing`;
