# Koko 项目说明

## 新会话 / 修改代码前必读

处理本仓库前，必须先阅读：

```text
docs/DEPLOYMENT_RUNTIME_CONTEXT.md
```

该文档记录了生产服务器真实目录映射、GitHub 源码与服务器运行配置边界、企业微信通知链路、充值记录隔离规则以及部署脚本禁止覆盖源码的约定。

其中最重要的生产环境事实是：

```text
/www/wwwroot/ka.k2n.cn/
        ↕ 宝塔站点目录映射
/opt/koko/admin/
```

这两个路径是同一套实际文件，不要把它们当成两个独立目录互相复制或恢复。

## 开发前必读：数据库字段命名约定

每次修改代码前必须遵守以下数据库字段命名约定：

- 禁止在代码中使用 `redeem_code` 作为数据库字段名。
- 验证码字段统一使用 `yzm`。
- 订单号和兑换码字段统一使用 `orderID`。

## 当前生产源码目录

```text
/opt/koko
```

关键服务：

```text
koko-backend  -> /opt/koko/server/kugo_mergedl.py
koko-selenium -> /opt/koko/server/app_optimized-cdp.py
```

关键前后端源码：

```text
admin/index.html
usrvip/index.html
server/kugo_mergedl.py
server/app_optimized-cdp.py
server/koko_task_helpers.py
```

服务器曾有手工修改时，必须先对比部署前备份、当前服务器版本和 GitHub `main`，再决定如何合并，禁止直接用旧文件整份覆盖最新源码。

## 当前通知系统：企业微信自建应用

项目的业务通知已经从 SMTP / 邮件迁移到企业微信自建应用。

后台配置入口：

```text
admin/index.html
```

配置接口：

```text
admin/phpapi/system_settings.php
```

PHP 通知实现：

```text
admin/lib/mailer.php
```

Python 通知公共逻辑：

```text
server/koko_task_helpers.py
```

当前支持的企业微信配置项：

```text
wecom_corp_id
wecom_agent_secret
wecom_agent_id
wecom_to_user
wecom_to_party
wecom_to_tag
```

真实企业微信配置保存在数据库 `system_settings` 中。`wecom_agent_secret` 只写不回显，不应提交真实值到仓库。

## 充值记录与验证码记录隔离

验证码记录：

```text
init = 1
yzm_status = 1 / 2
```

正式充值记录：

```text
init = 0
yzm_status = 3
```

必须遵守：

- 获取验证码记录不得参与充值进度条。
- `r_status='等待'` 只能更新正式充值记录。
- `usrvip/index.html` 在正式充值创建成功后保存 `tel_data_id`。
- 95% 进度后的状态查询优先使用 `tel_data_id` 精确定位正式充值记录。

## GitHub 源码与服务器运行配置边界

以下属于程序源码，应以 GitHub `main` 为代码基线：

```text
admin/*.php
admin/phpapi/*.php
admin/lib/*.php
admin/*.html
usrvip/*
server/*.py
```

以下属于生产服务器运行配置或敏感信息，普通代码部署不得从 GitHub 覆盖：

```text
/opt/koko/.env
/opt/koko/server/.env
Nginx / 宝塔配置
后台 Nginx Key
Cookie Guard
SSL 证书
systemd 本机配置
日志和运行缓存
数据库 system_settings 中的真实配置值
```

## 部署脚本重要规则

部署成功后，不允许从旧备份恢复 GitHub 管理的业务源码。

特别注意：如果部署脚本使用类似下面的逻辑：

```bash
trap restore_runtime_state EXIT
```

必须确保 `restore_runtime_state` 只恢复 `.env`、Nginx、Key 等运行配置，而不能恢复 `admin/index.html`、`admin/phpapi/*.php`、`usrvip/index.html`、`server/*.py` 等源码。

否则会出现：

```text
GitHub 新代码部署成功
→ EXIT trap 执行
→ 从旧备份恢复源码
→ 线上重新变成旧版本
```

完整生产环境约定与排查方法见：

```text
docs/DEPLOYMENT_RUNTIME_CONTEXT.md
```
