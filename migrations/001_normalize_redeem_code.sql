-- 001_normalize_redeem_code.sql
-- Purpose: introduce a non-breaking canonical redeem_code column while keeping
-- legacy orderID/order_id columns during a compatibility window.
--
-- BEFORE RUNNING IN PRODUCTION:
--   1. Take a full logical backup, for example:
--      mysqldump --single-transaction --routines --events kugo > kugo_backup_$(date +%F_%H%M%S).sql
--   2. Run during a low-traffic window.
--   3. Test on a restored staging database first.
--
-- This migration intentionally does NOT DROP or truncate any table/column.

START TRANSACTION;

-- order_id: legacy table name, legacy field orderID.
ALTER TABLE `order_id`
  ADD COLUMN `redeem_code` varchar(255) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID' AFTER `orderID`;
UPDATE `order_id` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
CREATE INDEX `idx_order_id_redeem_code_status` ON `order_id` (`redeem_code`, `status`);
CREATE INDEX `idx_order_id_status_created` ON `order_id` (`status`, `create_date`);

-- order_data_anj: generated/imported card-code table.
ALTER TABLE `order_data_anj`
  ADD COLUMN `redeem_code` varchar(255) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID' AFTER `orderID`;
UPDATE `order_data_anj` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
CREATE INDEX `idx_order_data_anj_redeem_code_status` ON `order_data_anj` (`redeem_code`, `status`);

-- order_data: historical recharge result table.
ALTER TABLE `order_data`
  ADD COLUMN `redeem_code` varchar(255) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID' AFTER `orderID`;
UPDATE `order_data` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
CREATE INDEX `idx_order_data_redeem_code_time` ON `order_data` (`redeem_code`, `time`);

-- tel_data: SMS / task pipeline table.
ALTER TABLE `tel_data`
  ADD COLUMN `redeem_code` varchar(50) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID/orderid' AFTER `orderID`;
UPDATE `tel_data` SET `redeem_code` = `orderID` WHERE `redeem_code` IS NULL AND `orderID` IS NOT NULL;
CREATE INDEX `idx_tel_data_redeem_code_status` ON `tel_data` (`redeem_code`, `status`, `yzm_status`);
CREATE INDEX `idx_tel_data_tel_created` ON `tel_data` (`tel`, `create_date`);

-- user_data and submissions already use order_id; keep it but add canonical alias.
ALTER TABLE `user_data`
  ADD COLUMN `redeem_code` varchar(50) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy order_id' AFTER `order_id`;
UPDATE `user_data` SET `redeem_code` = `order_id` WHERE `redeem_code` IS NULL AND `order_id` IS NOT NULL;
CREATE INDEX `idx_user_data_redeem_code_created` ON `user_data` (`redeem_code`, `create_date`);
CREATE INDEX `idx_user_data_phone_created` ON `user_data` (`phone`, `create_date`);

ALTER TABLE `submissions`
  ADD COLUMN `redeem_code` varchar(64) NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy order_id' AFTER `order_id`;
UPDATE `submissions` SET `redeem_code` = `order_id` WHERE `redeem_code` IS NULL AND `order_id` IS NOT NULL;
CREATE INDEX `idx_submissions_redeem_code_created` ON `submissions` (`redeem_code`, `created_at`);

COMMIT;

-- Optional sync triggers (review manually before enabling; they affect write path).
-- DELIMITER $$
-- CREATE TRIGGER bi_order_id_sync_redeem_code
-- BEFORE INSERT ON `order_id` FOR EACH ROW
-- BEGIN
--   IF NEW.redeem_code IS NULL THEN SET NEW.redeem_code = NEW.orderID; END IF;
--   IF NEW.orderID IS NULL THEN SET NEW.orderID = NEW.redeem_code; END IF;
-- END$$
-- DELIMITER ;

-- Rollback guidance (manual, only if application has not started writing redeem_code):
--   DROP INDEX idx_order_id_redeem_code_status ON order_id;
--   DROP INDEX idx_order_id_status_created ON order_id;
--   ALTER TABLE order_id DROP COLUMN redeem_code;
-- Repeat the same pattern for the other added indexes/columns after confirming no
-- application version depends on redeem_code. Do not run rollback blindly on prod.
