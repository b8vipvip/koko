-- koko_full_schema.sql
-- Full empty schema for Koko deployments.
-- Compatible with MySQL 5.7 / 8.0. Uses utf8mb4 and contains no real data.
--
-- Field relationship for redeem codes:
--   * redeem_code is the canonical field recommended for new backend code.
--   * order_id.orderID, order_data.orderID, order_data_anj.orderID and tel_data.orderID
--     are retained for legacy Python/PHP callers and should store the same value.
--   * user_data.order_id and submissions.order_id are retained for current callers and
--     should store the same value as redeem_code.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

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

CREATE TABLE IF NOT EXISTS `img_data` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `img_name` varchar(255) NOT NULL,
  `status` int(11) NOT NULL,
  `tel_id` int(11) NOT NULL,
  `url` varchar(500) DEFAULT NULL,
  `thumbnail_url` varchar(500) DEFAULT NULL,
  `cz_status` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_img_data_tel_id` (`tel_id`),
  KEY `idx_img_data_status_created` (`status`,`create_date`),
  KEY `idx_img_data_create_date` (`create_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='截图/图片记录';

CREATE TABLE IF NOT EXISTS `order_data` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `orderID` varchar(255) DEFAULT NULL COMMENT 'Legacy redeem code field; keep equal to redeem_code',
  `redeem_code` varchar(255) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID',
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
  KEY `idx_order_data_orderID_time` (`orderID`,`time`),
  KEY `idx_order_data_redeem_time` (`redeem_code`,`time`),
  KEY `idx_order_data_status_time` (`status`,`time`),
  KEY `idx_order_data_phone` (`phone`),
  KEY `idx_order_data_processed_dev` (`processed`,`dev`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='历史充值结果表';

CREATE TABLE IF NOT EXISTS `order_data_anj` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `orderID` varchar(255) NOT NULL COMMENT 'Legacy redeem code field; keep equal to redeem_code',
  `redeem_code` varchar(255) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID',
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
  PRIMARY KEY (`id`),
  KEY `idx_order_data_anj_orderID` (`orderID`),
  KEY `idx_order_data_anj_redeem_status` (`redeem_code`,`status`),
  KEY `idx_order_data_anj_status_time` (`status`,`time`),
  KEY `idx_order_data_anj_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生成/导入卡密表';

CREATE TABLE IF NOT EXISTS `order_id` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `orderID` varchar(255) DEFAULT NULL COMMENT 'Legacy redeem code field; keep equal to redeem_code',
  `redeem_code` varchar(255) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors legacy orderID',
  `status` int(11) DEFAULT NULL COMMENT '1=可用,2=锁定,3=已用',
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
  PRIMARY KEY (`id`),
  KEY `idx_order_id_orderID_status` (`orderID`,`status`),
  KEY `idx_order_id_redeem_status` (`redeem_code`,`status`),
  KEY `idx_order_id_status_created` (`status`,`created_at`),
  KEY `idx_order_id_getstatus_id` (`getstatus`,`id`),
  KEY `idx_order_id_admin_get` (`adminkami`,`getadminkami`,`status`),
  KEY `idx_order_id_91kami_status` (`91kami`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='兑换码/订单码主表';

CREATE TABLE IF NOT EXISTS `recharge_tasks` (
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
  `uploaded_at` datetime NOT NULL,
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
  UNIQUE KEY `uk_recharge_tasks_task_no` (`task_no`),
  KEY `idx_recharge_tasks_status_created` (`status`,`created_at`),
  KEY `idx_recharge_tasks_batch` (`source_batch_id`),
  KEY `idx_recharge_tasks_account` (`account_identifier`),
  KEY `idx_recharge_tasks_worker` (`worker_id`),
  KEY `idx_recharge_tasks_claim` (`status`,`worker_id`,`claimed_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='充值任务表';

CREATE TABLE IF NOT EXISTS `run_status` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dev` int(11) DEFAULT NULL,
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status` varchar(255) DEFAULT '0',
  `restart` tinyint(1) DEFAULT '0' COMMENT '是否已经重启(0-否,1-是)',
  PRIMARY KEY (`id`),
  KEY `idx_run_status_dev_created` (`dev`,`create_date`),
  KEY `idx_run_status_status_created` (`status`,`create_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备运行状态';

CREATE TABLE IF NOT EXISTS `submissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `idempotency_key` varchar(128) NOT NULL,
  `order_id` varchar(64) NOT NULL COMMENT 'Current API order id/redeem code field; keep equal to redeem_code',
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

CREATE TABLE IF NOT EXISTS `task_logs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `task_id` bigint(20) unsigned NOT NULL,
  `worker_id` varchar(64) DEFAULT NULL,
  `action` varchar(64) NOT NULL COMMENT '操作类型',
  `content` text COMMENT '日志内容',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_logs_task_id` (`task_id`),
  KEY `idx_task_logs_worker` (`worker_id`),
  KEY `idx_task_logs_action_created` (`action`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务日志表';

CREATE TABLE IF NOT EXISTS `tel_data` (
  `id` int(10) NOT NULL AUTO_INCREMENT,
  `tel` varchar(50) DEFAULT NULL,
  `yzm` varchar(255) DEFAULT NULL,
  `details` text,
  `status` varchar(255) DEFAULT '1',
  `create_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `zhanghu` varchar(255) DEFAULT NULL,
  `c_status` varchar(50) DEFAULT NULL,
  `huiyuanguize` varchar(255) DEFAULT NULL,
  `r_status` varchar(50) DEFAULT NULL,
  `orderID` varchar(50) DEFAULT NULL COMMENT 'Legacy redeem code field; keep equal to redeem_code',
  `redeem_code` varchar(50) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors orderID/orderid',
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
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_tel_data_tel_created` (`tel`,`create_date`),
  KEY `idx_tel_data_phone_created` (`tel`,`create_date`),
  KEY `idx_tel_data_orderID` (`orderID`),
  KEY `idx_tel_data_redeem_status` (`redeem_code`,`status`,`yzm_status`),
  KEY `idx_tel_data_status_created` (`status`,`create_date`),
  KEY `idx_tel_data_r_status_created` (`r_status`,`create_date`),
  KEY `idx_tel_data_c_status` (`c_status`),
  KEY `idx_tel_data_yzm_status` (`yzm_status`),
  KEY `idx_tel_data_init_tel` (`init`,`tel`),
  KEY `idx_tel_data_dev_created` (`dev`,`create_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短信/充值流水表';

CREATE TABLE IF NOT EXISTS `user_data` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `phone` varchar(20) NOT NULL,
  `code` varchar(10) NOT NULL,
  `order_id` varchar(50) DEFAULT NULL COMMENT 'Current API order id/redeem code field; keep equal to redeem_code',
  `redeem_code` varchar(50) DEFAULT NULL COMMENT 'Canonical redeem/recharge code; mirrors order_id',
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
  PRIMARY KEY (`id`),
  KEY `idx_user_data_phone_created` (`phone`,`create_date`),
  KEY `idx_user_data_order_id_created` (`order_id`,`create_date`),
  KEY `idx_user_data_redeem_created` (`redeem_code`,`create_date`),
  KEY `idx_user_data_status_created` (`status`,`create_date`),
  KEY `idx_user_data_submitstatus` (`submitstatus`),
  KEY `idx_user_data_userid1` (`userid1`),
  KEY `idx_user_data_userid2` (`userid2`),
  KEY `idx_user_data_userid3` (`userid3`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户提交与账号识别记录';

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

SET FOREIGN_KEY_CHECKS = 1;
