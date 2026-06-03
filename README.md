# Koko 安全修复摘要

本仓库已完成 PHP 后台敏感配置集中化与危险管理接口鉴权加固。

## 本次主要修改

- 新增 `admin/lib/config.php`，统一读取 PHP/Python 共用的 `.env` 配置，并提供 PDO、mysqli、管理员 token 校验等公共函数。
- 新增 `admin/lib/mailer.php`，统一创建 PHPMailer 实例，SMTP Host、Port、Username、Password、From、To 均来自环境变量或 `.env`。
- 移除 `admin/*.php` 与 `admin/phpapi/*.php` 中已发现的硬编码数据库账号密码、QQ 邮箱、SMTP 授权码、发件人和收件人。
- 保持 `admin/db.php` 的 `$pdo` 调用方式与 `admin/dbclass.php` 的 `DbClass` 调用方式，避免大规模重写业务逻辑。
- 对会修改数据或发送测试邮件的 PHP HTTP 接口增加 `X-Admin-Token` 校验；定时任务脚本通过 CLI 运行时可继续执行，通过 HTTP 访问时需要 token。
- 更新 `.env.example`，补充 PHP 需要的 DB、SMTP、邮件收发件人和 `ADMIN_API_TOKEN` 配置项。
- 更新 `.gitignore`，忽略 `.env`、日志、运行状态文件和临时文件。
- 更新 `scripts/check.sh`，新增 PHP 敏感信息回归扫描和 PHP 语法检查。
- 更新 `docs/repository-audit-report.md`，补充 PHP/Python 共用 `/opt/koko/.env`、Nginx/宝塔禁止访问 `.env`、上线轮换泄露密钥、PHP token 接口清单等部署说明。

## 上线前必须配置

生产环境请在 Web 根目录之外创建 `/opt/koko/.env`，至少包含：

```dotenv
PHP_ENV_FILE=/opt/koko/.env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=koko
DB_PASSWORD=change-me
DB_NAME=kugo
DB_CHARSET=utf8mb4
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=change-me@qq.com
SMTP_PASSWORD=change-me
SMTP_ENCRYPTION=ssl
MAIL_FROM=change-me@qq.com
MAIL_FROM_NAME=Koko
MAIL_TO=admin@example.com
MAIL_TO_NAME=Admin
ADMIN_API_TOKEN=change-me
```

> 不要把真实数据库密码、SMTP 授权码或管理员 token 提交到仓库。

## 上线前必须轮换

历史代码中已经出现过数据库密码、QQ 邮箱地址、SMTP 授权码和管理员敏感配置。上线前必须更换：

- MySQL 用户密码。
- QQ 邮箱 SMTP 授权码。
- `ADMIN_API_TOKEN`。
- 如相关邮箱已不应继续使用，请同步更换 `SMTP_USERNAME`、`MAIL_FROM`、`MAIL_TO`。

## 仍需人工确认

- 前端或 Nginx/宝塔是否会为新增鉴权的 PHP 接口补充 `X-Admin-Token`。
- `admin/dev.php` 是否应在下一阶段也强制 token；本次为避免破坏设备状态展示，建议先通过站点级访问控制保护。
- `admin/vendor/` 是否由生产环境直接依赖；本次未删除 vendor，避免影响 PHPMailer 加载。
