# Koko 生产环境与部署上下文（新会话必读）

> 目的：记录本项目在生产服务器上的真实目录关系、源码与运行配置边界，以及更新时必须遵守的规则。以后使用新的 ChatGPT / Codex 会话修改本仓库前，应先阅读本文件，避免重复确认或错误覆盖线上代码。

## 1. 生产服务器源码根目录

GitHub 仓库生产部署目录：

```text
/opt/koko
```

Python 服务代码：

```text
/opt/koko/server/kugo_mergedl.py
/opt/koko/server/app_optimized-cdp.py
```

当前服务约定：

```text
koko-backend  -> /opt/koko/server/kugo_mergedl.py      （通常监听 9999）
koko-selenium -> /opt/koko/server/app_optimized-cdp.py （通常监听 5000）
```

## 2. 宝塔站点目录与 `/opt/koko/admin` 是同一套文件

生产环境已确认：宝塔站点 `ka.k2n.cn` 的站点目录映射到：

```text
/opt/koko/admin
```

因此下面两个路径看到的是同一套实际文件：

```text
/opt/koko/admin/
/www/wwwroot/ka.k2n.cn/
```

例如：

```text
/opt/koko/admin/index.html
/www/wwwroot/ka.k2n.cn/index.html
```

是同一个实际文件。执行 `cp` 时可能直接提示 `are the same file`，这是正常现象。

### 重要规则

- 不要把 `/opt/koko/admin` 和 `/www/wwwroot/ka.k2n.cn` 当作两个独立目录互相 `cp` / `rsync`。
- 修改 `/opt/koko/admin` 下的文件即等于修改线上 `ka.k2n.cn` 对应文件。
- 部署脚本不要在 Git 拉取完成后，再从旧备份恢复 `admin/index.html`、`admin/phpapi/*.php` 等 GitHub 管理的源码，否则会把新版本重新覆盖成旧版本。
- 其他站点目录是否采用相同映射方式，必须先在服务器上通过 `readlink -f`、`mount`、`findmnt` 或实际文件 inode 检查确认，不能直接类推。

## 3. GitHub 是程序源码的最终来源

以下属于程序源码，正常更新时应以 GitHub `main` 为准；若服务器曾经手工修改，应先做三方对比再合并，不能直接用旧备份覆盖新版本。

### 关键前端与后端

```text
admin/index.html
usrvip/index.html
server/kugo_mergedl.py
server/app_optimized-cdp.py
server/koko_task_helpers.py
```

### 企业微信通知相关源码

```text
admin/phpapi/system_settings.php
admin/lib/config.php
admin/lib/mailer.php
admin/api.php
admin/dev.php
admin/email.php
admin/mail_test.php
admin/cron_balance_monitor.php
server/koko_task_helpers.py
```

当前通知系统已经从 SMTP / 邮件迁移到企业微信自建应用。`admin/index.html` 的“系统配置”负责填写企业微信参数，后端统一通过企业微信 API 发送通知。

## 4. 不应从 GitHub 覆盖的服务器运行配置

以下属于服务器运行态或敏感配置，不应该在普通代码更新时从 GitHub 覆盖，也不应该提交真实值到 GitHub：

```text
/opt/koko/.env
/opt/koko/server/.env
Nginx / 宝塔站点配置
后台 Nginx Key
Cookie Guard 配置
SSL 证书
systemd 本机运行配置
日志文件
浏览器运行缓存 / Selenium 临时数据
数据库中 system_settings 表保存的真实配置值
```

企业微信真实配置（CorpID、应用 Secret、AgentId、接收成员/部门/标签）保存在数据库 `system_settings` 中。真实 Secret 不应写入仓库。

## 5. 当前企业微信通知配置链路

后台页面：

```text
admin/index.html
```

配置接口：

```text
admin/phpapi/system_settings.php
```

PHP 企业微信发送实现：

```text
admin/lib/mailer.php
```

Python 企业微信发送与新任务通知公共逻辑：

```text
server/koko_task_helpers.py
```

当前系统配置支持：

```text
wecom_corp_id
wecom_agent_secret
wecom_agent_id
wecom_to_user
wecom_to_party
wecom_to_tag
```

`wecom_agent_secret` 已按“只写不回显”方式处理：浏览器读取设置时不会返回已保存的 Secret，留空保存表示保持原 Secret 不变。

## 6. 充值进度与验证码记录隔离规则

正式充值记录与“获取验证码”记录必须严格隔离。

验证码流程记录：

```text
init = 1
yzm_status = 1 / 2
```

正式充值记录：

```text
init = 0
yzm_status = 3
```

关键规则：

- 获取验证码记录不得参与充值进度条。
- `r_status='等待'` 只能更新正式充值记录。
- `usrvip/index.html` 在正式充值 `/api` 成功后保存后端返回的 `tel_data_id`。
- 进度到 95% 后优先使用 `tel_data_id` 精确查询正式充值记录。
- 只有 `r_status` 为 `成功`、`已成功`、`失败`、`已失败` 时进度才到 100%；其他状态保持 95% 并继续轮询。

主要实现文件：

```text
usrvip/index.html
server/kugo_mergedl.py
```

## 7. 部署脚本的安全边界

部署脚本可以备份旧 `/opt/koko`，但必须区分“源码”和“运行配置”。

### 可以恢复的运行态内容

```text
.env
服务器本机 Nginx 配置
后台登录 Key / Cookie Guard
证书和其他本机 Secret
必要的运行状态文件
```

### 不允许在部署成功后从旧备份恢复的源码

```text
admin/index.html
admin/phpapi/*.php
admin/lib/*.php
usrvip/index.html
server/*.py
以及其他由 GitHub 管理的业务源码
```

尤其不要使用无条件的：

```bash
trap restore_runtime_state EXIT
```

如果 `restore_runtime_state` 会恢复源码，这会导致“GitHub 新代码部署成功后，脚本退出时又恢复成旧代码”。正确做法是：

- 只在部署失败时回滚；或
- `restore_runtime_state` 只恢复明确列出的运行配置，绝不恢复 GitHub 管理源码。

## 8. 更新前推荐的三方对比方式

当怀疑服务器曾经手工改过代码时，对比：

```text
A. 最近一次 /opt/koko_backup_* 里的部署前服务器版本
B. 当前 /opt/koko
C. GitHub origin/main
```

只比较源码文件，不比较 `.env`、Nginx、Key 等运行配置。

常用命令：

```bash
LATEST_BACKUP="$(ls -dt /opt/koko_backup_* | head -1)"

git -C /opt/koko fetch origin main

diff -u \
  "$LATEST_BACKUP/server/kugo_mergedl.py" \
  /opt/koko/server/kugo_mergedl.py

git -C /opt/koko diff origin/main -- server/kugo_mergedl.py
```

如果当前服务器文件与 GitHub 一致，就不要从旧备份恢复该文件。

## 9. 新会话处理本项目时的默认原则

后续 AI / 开发者处理本仓库时，应默认遵守：

1. 先读本文件和根目录 `README.md`。
2. GitHub `main` 是程序源码基线。
3. 生产机真实配置不进入 GitHub。
4. `/www/wwwroot/ka.k2n.cn` 与 `/opt/koko/admin` 是同一套映射文件，不做重复同步。
5. 涉及服务器旧版本代码时先 diff，再决定合并，禁止整文件盲目覆盖。
6. 部署成功后禁止旧“运行态恢复脚本”覆盖 GitHub 管理源码。
7. 企业微信通知已经替代原邮件通知；新功能不要重新引入 SMTP/PHPMailer/smtplib 发送链路。
