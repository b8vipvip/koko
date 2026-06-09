# Koko 数据库字段约定

## 验证码字段统一规则

验证码统一使用字段名：yzm

tel_data 标准字段：
- tel_data.yzm

user_data 标准字段：
- user_data.yzm

user_data 旧兼容字段：
- user_data.code

user_data.code 是历史字段，保留兼容旧数据。新代码不要再直接使用 code，应统一使用 yzm。

## 禁止新增的字段名

不要新增或使用：
- redeem_code
- verification_code
- sms_code

除非先同步修改数据库结构、前端、后端、PHP 管理端，并更新本文档。

## 代码修改要求

涉及验证码时：
- 查询 tel_data 用 yzm
- 查询 user_data 用 yzm
- 不要在 SQL 中写 redeem_code
- 不要自动新增验证码字段
- 如果需要兼容旧 user_data.code，必须显式写兼容逻辑，例如 COALESCE(yzm, code)

## 部署注意

真实密钥、.env、Nginx 里生成的 X-Admin-Token 配置，禁止提交 GitHub。

部署脚本可以读取 /opt/koko/.env 生成服务器本地 Nginx 配置，但不能把真实 token 写入仓库。

## system_settings 系统配置

`system_settings` 保存可在后台调整的运行配置。PHP/Python 后端启动或首次读取时会自动创建表并补齐默认值，部署时也可以执行 `migrations/003_system_settings.sql`。

表字段：
- `setting_key`：配置键，主键
- `setting_value`：配置值，统一按字符串保存
- `updated_at`：最近更新时间

当前配置键及默认值：
- `redeem_url = https://ka.k2n.cn/usrvip/`：会员兑换流程提示使用的兑换链接
- `notify_device_offline = 1`：设备离线邮件通知开关
- `notify_new_recharge_task = 1`：新充值任务邮件通知开关
- `notify_backend_error = 1`：后端运行报错邮件通知开关

通知开关只允许 `1`（开启）或 `0`（关闭）。PHP 代码应使用 `koko_get_setting($key, $default)` 读取，Python 代码应使用 `get_system_setting(key, default)` 读取；不得把这些运行配置写死在前端。
