# 新加坡公开 API + 国内 worker 主动轮询部署说明

本文档描述当前仓库适配后的推荐部署架构：新加坡 CN02 作为唯一公开站点和数据库节点，国内 2核4G 服务器只作为主动轮询 worker。

## 1. 架构原则

- 用户浏览器只访问新加坡服务器的 `usrvip` 静态前端和公开 API。
- 国内服务器不开放公网 API，不让用户浏览器直接访问。
- 国内 worker 只主动请求新加坡公开 API：先调用 `/api/worker/fetch` 拉取任务，再调用 `/api/worker/report` 回传执行结果。
- 国内 worker 不建议、也不需要直接连接新加坡 MySQL；优先通过 HTTPS API 和 `X-Worker-Token` 通信。
- `admin`、`admvip`、`usrvip` 均保留，不在本次架构适配中删除。

## 2. 新增/整理的 API

### 用户公开 API

- `POST /api/task/create`
  - 用途：`usrvip` 用户提交充值任务。
  - 参数：`order_id`/`redeem_code`、`phone`、`code`、可选 `account`/`zhanghu`、可选 `plan_type`。
  - 行为：校验并锁定兑换码、防重复提交、写入 `user_data`，返回 `task_id`/`record_id`。

- `GET /api/task/status`
  - 用途：`usrvip` 查询进度和结果。
  - 参数：`task_id`/`record_id`，或 `order_id`/`redeem_code`，或 `phone`。
  - 行为：只返回用户需要看的状态、进度、账号结果和必要详情，不返回数据库异常、token、内部日志。

### worker 专用 API

- `POST /api/worker/fetch`
  - 必须带 Header：`X-Worker-Token: <WORKER_API_TOKEN>`。
  - 从 `.env` 读取 `WORKER_API_TOKEN`；为空时拒绝访问。
  - 使用事务和 `FOR UPDATE` 行锁领取 `user_data.status=1 AND submitstatus=1` 的任务。
  - 领取后标记为 `status=4`，表示 processing/running。

- `POST /api/worker/report`
  - 必须带 Header：`X-Worker-Token: <WORKER_API_TOKEN>`。
  - 根据 `task_id`/`record_id`/`user_data_id` 或 `tel_data_id` 更新任务状态和结果。
  - 可回传：`success`/`failed`/`running`、`r_status`、`c_status`、`details`、`userid`、`screenshot`/`image_url`、`error_message`。
  - 后端异常只向调用方返回通用错误，详细异常写入服务端日志。

## 3. 兼容保留的旧接口

本次没有删除旧路径，便于现有 `usrvip` 和历史脚本继续运行。已识别并保留的相关接口包括：

- `/submit`：旧用户提交接口。
- `/check_order_id`：旧兑换码校验接口。
- `/submituserinfo`：旧用户信息提交接口。
- `/getUserStatus/<record_id>`：旧用户状态查询接口。
- `/getTelData`、`/getyzm`、`/getTel`、`/getTelYzm`：旧任务/手机号/验证码获取接口。
- `/update_r_status`、`/update_re_status`、`/checkAndUpdateCStatus`、`/c_status`、`/img_updata`：旧状态和图片回写接口。

后续前端可以逐步迁移到更清晰的 `/api/task/create` 和 `/api/task/status`，无需一次性替换全部旧逻辑。

## 4. 新加坡 CN02 服务器部署

1. 部署代码到 `/opt/koko`，创建 Python 虚拟环境并安装依赖：
   ```bash
   cd /opt/koko
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. 配置 `/opt/koko/.env`。至少设置：
   ```dotenv
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_USER=koko
   DB_PASSWORD=change-me
   DB_NAME=kugo
   DB_CHARSET=utf8mb4
   ADMIN_API_TOKEN=change-me
   WORKER_API_TOKEN=change-me
   CORS_ORIGINS=https://your-usrvip-domain.example.com
   APP_LOG_FILE=/opt/koko/logs/all.log
   USER_LOG_FILE=/opt/koko/logs/userpy.log
   ```
3. 部署 MySQL/MariaDB，导入现有 schema 或历史数据库。不要在本次操作中自动执行迁移。
4. 部署 Python gunicorn，可参考 `deploy/koko.service`。
5. 部署 PHP-FPM 和 Nginx，使 `admin`、`admvip`、`usrvip` 静态/ PHP 文件按现有站点规则提供服务。
6. Nginx 将 `/api/`、旧 Flask 路径和需要的后端路径反向代理到 gunicorn。
7. 确保 `.env` 不在 Web 根目录直接暴露；宝塔/Nginx 需禁止访问 `.env`、日志和运行状态文件。
8. 将 `usrvip` 前端请求目标指向新加坡公开 API 域名。

## 5. 国内 worker 服务器部署

1. 部署代码到 `/opt/koko`，创建虚拟环境并安装依赖：
   ```bash
   cd /opt/koko
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. 配置 `/opt/koko/.env`。国内 worker 只需要 API 和 worker 配置，不需要 MySQL：
   ```dotenv
   PUBLIC_API_BASE_URL=https://your-api-domain.example.com
   WORKER_API_TOKEN=change-me
   WORKER_ID=worker-cn-01
   WORKER_POLL_INTERVAL=3
   ```
3. 安装 Selenium / Chrome / Chromedriver / 自动化脚本需要的运行环境。
4. 将现有充值自动化逻辑接入 `worker/worker_client.py` 的 `execute_task(task)` TODO 钩子。
5. 安装 systemd 服务：
   ```bash
   sudo cp deploy/koko-worker.service /etc/systemd/system/koko-worker.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now koko-worker.service
   sudo journalctl -u koko-worker.service -f
   ```
6. 国内服务器不需要 Nginx，不需要 PHP-FPM，不需要 MySQL，不开放公网 API 端口。

## 6. .env 新增配置

```dotenv
PUBLIC_API_BASE_URL=https://your-api-domain.example.com
WORKER_API_TOKEN=change-me
WORKER_ID=worker-cn-01
WORKER_POLL_INTERVAL=3
```

`ADMIN_API_TOKEN`、`DB_HOST`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`、`SMTP_*`、`APP_*` 等原有配置继续保留。

## 7. 数据库变更

本次实现复用现有表：

- `order_id`：校验和锁定兑换码。
- `user_data`：保存用户任务、状态和账号识别结果。
- `tel_data`：保存充值流水、`r_status`、`c_status`、详情和图片 URL。
- `workers`：记录 worker 心跳和当前任务。

当前不需要新增字段或表，因此没有执行数据库迁移，也没有必须执行的迁移 SQL。若后续需要更细粒度的 worker 领取时间、失败次数、任务租约超时等能力，建议只新增迁移 SQL，由人工审核后再执行。

## 8. 上线前安全检查

上线前必须更换所有已泄露过或可能泄露过的敏感信息：

- 数据库密码。
- SMTP 授权码。
- `ADMIN_API_TOKEN`。
- `WORKER_API_TOKEN`。

不要把国内服务器 IP、数据库密码、真实 token 写死到代码或提交到仓库。
