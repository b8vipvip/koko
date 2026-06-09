-- Runtime system settings used by PHP/Python backends and the admin frontend.
CREATE TABLE IF NOT EXISTS system_settings (
  setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
  setting_value TEXT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO system_settings (setting_key, setting_value) VALUES
  ('redeem_url', 'https://ka.k2n.cn/usrvip/'),
  ('notify_device_offline', '1'),
  ('notify_new_recharge_task', '1'),
  ('notify_backend_error', '1');
