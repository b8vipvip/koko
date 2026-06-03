# Koko 仓库审查与重构报告

## 1. 当前文件树（业务视角）

- `server/`：Python Flask 后端。
  - `kugo_mergedl.py`：主接口集合，包含 `/api` 短信/充值流水入口、设备轮询接口、订单/卡密管理、查询充值状态、利润统计、批量生成/上传兑换码等接口。
  - `app_optimized-cdp.py`：Selenium/CDP 自动化充值入口，包含用户 `/submit`、管理员 `/admin/submit`、`/sfyzm` 发送验证码、`/check_order_id` 等接口。
  - `app.py`：新增的 gunicorn WSGI 入口，将两个旧 Flask 文件中的路由合并到一个 `app` 对象，便于 systemd 统一托管。
- `admin/`：管理员后台静态/PHP 混合站点。
  - `index.html`：后台主页面，调用 `api`、`/sfyzm`、`/dev.php`、`/fetch0_count.php`。
  - `kami.html`：卡密提取页面，调用 `/extract_order`。
  - `list.js`：历史记录/标记成功等逻辑，仍含外部硬编码域名，需要后续按部署域名改为相对路径或环境注入。
  - `phpapi/`、`db.php`、`dbclass.php`：余额/资金相关 PHP 接口与数据库连接代码，未能 100% 确认无用，必须保留并单独排查凭据。
- `admvip/`：管理员免输兑换码或快速充值静态站点。
  - `index.html`：调用 `/sfyzm`、`/check_recharge_duplicate`、`/submit`、`/admin/submit`、`/api`。
  - `user.html`：调用 `/sfyzm`、`/check_order_validity`、`/lock_order`、`/submit`、`/unlock_order`、`/check_recharge_duplicate`、`/api`。
  - `orderid.html`：调用 `/extract_order_ids` 批量提取兑换码。
- `usrvip/`：用户自助充值静态站点。
  - `index.html`：用户输入兑换码、手机号和验证码后提交；逻辑与 `admvip/user.html` 高度相似。
- `kugo_structure_events.sql`：当前数据库建表结构，包含 `api_tokens`、`code_data`、`device_fund_details`、`img_data`、`order_data`、`order_data_anj`、`order_id`、`recharge_tasks`、`run_status`、`submissions`、`task_batches`、`task_logs`、`tel_data`、`user_data`、`workers`。
- `migrations/001_normalize_redeem_code.sql`：新增安全迁移，添加 `redeem_code` 兼容列和必要索引，不删除旧字段。
- `scripts/deploy.sh`：新增一键部署脚本。
- `scripts/check.sh`：新增基础检查脚本。
- `deploy/koko.service`：新增 systemd 服务模板。
- `.env.example`、`requirements.txt`：新增生产配置模板和 Python 依赖清单。

## 2. 后端职责与接口关系

### `server/kugo_mergedl.py`

该文件负责主业务接口：

- `/api`：接收设备/页面提交的 `fasong`、`chongzhi` 等请求，写入 `tel_data`、更新充值状态。
- `/getTelData`、`/getyzm`、`/getTel`、`/getTelYzm`：设备轮询任务/验证码。
- `/update_tel_status`、`/update_tel_statu3`、`/update_r_status`、`/update_re_status`、`/checkAndUpdateCStatus`、`/c_status`：状态回写。
- `/check_recharge_duplicate`、`/get_recharge_status`：前端查询重复充值、进度和结果。
- `/check_order_validity`、`/lock_order`、`/unlock_order`、`/mark_order_used`：兑换码状态管理。
- `/order_id_query`、`/extract_order_ids`、`/extract_order`、`/submit_order`、`/uporderid_status`、`/orderid_find`、`/update_order_data`：管理员卡密/订单管理。
- `/profit_stat`：利润统计。
- `/code_upload_batch`、`/code_fetch`：兑换码池上传与领取。

### `server/app_optimized-cdp.py`

该文件负责 Selenium/CDP 自动化充值链路：

- `/submit`：用户自助充值提交，已有幂等键和原子锁定思路。
- `/admin/submit`：管理员直提，允许管理员覆盖但需要在反向代理或后续前端中补充鉴权头。
- `/sfyzm`：发送验证码并异步调用自动化逻辑。
- `/check_order_id`：兑换码可用性检查。

## 3. `order_id` / `orderID` 统一方案

- 业务统一名：`redeem_code`。
- 兼容期策略：前端请求仍兼容 `order_id`；旧库字段 `orderID` / `order_id` 保留；数据库迁移新增 `redeem_code` 列并回填旧值。
- 后续代码改造建议：
  - HTTP 层继续接收 `order_id`、`orderID`，进入后端立即归一到 `redeem_code`。
  - Repository/SQL 层短期写双字段：`redeem_code` 与旧字段同步。
  - 确认所有线上服务读取 `redeem_code` 后，再人工评估是否重命名表 `order_id` 或删除旧列。

## 4. 数据库问题清单

- `order_id` 表名与 `order_id` 字段同时存在，且其他表使用 `orderID`，命名混乱。
- `order_id.orderID`、`order_data_anj.orderID` 缺少唯一约束；如业务要求兑换码全局唯一，应先查重清洗，再添加唯一索引。
- `tel_data`、`user_data` 的手机号、兑换码、创建时间查询较多，原结构索引不足。
- `submissions.order_id` 用于幂等查询结果追踪，但缺少按兑换码/时间的辅助索引。
- SQL 文件含 `DROP TABLE IF EXISTS`，只适合作为初始化脚本，不应直接对生产库执行。
- 状态值大量使用字符串/数字混合，如 `status='1'`、`r_status='等待'`，需要补充枚举说明或状态字典表。
- `kugo_structure_events.sql` 未发现触发器/存储过程/事件定义；风险主要来自初始化脚本的 drop 语句和缺少迁移分层。

## 5. 安全与稳定风险

- 原 Python 文件硬编码了数据库账号和密码；本次已改为读取 `.env`，并提供 `.env.example`。
- 管理员接口与用户接口同源暴露，`/lock_order`、`/unlock_order`、`/mark_order_used`、`/admin/submit` 等需要通过 Nginx/宝塔访问控制或后续前端 token 机制隔离。
- `admin/list.js` 仍存在硬编码线上域名，部署到不同域名时可能跨域失败，也会暴露基础设施信息。
- 多处旧接口返回原始异常字符串；本次先收敛了关键验证码和提交接口的异常暴露，后续应统一 JSON 响应封装。
- Selenium 浏览器池原来在导入模块时立即启动 Chrome；本次改为默认懒加载，避免 gunicorn/import 检查时因 Chrome 不存在直接失败。
- `profit_stat` 中按日期拼接 SQL 条件，虽然范围值有限，但 `specific.date` 后续仍建议严格校验为 `YYYY-MM-DD` 并改为参数化查询。
- 前端重复点击风险：`/submit` 已有 `X-Idempotency-Key` 和订单锁定；其他管理接口仍建议补充幂等键或操作审计。

## 6. 文件保留/待确认/无用判断

- 必须保留：`server/`、`admin/`、`admvip/`、`usrvip/`、`kugo_structure_events.sql`、新增部署/迁移/检查文件。
- 可能无用但不能直接删除：`admin/error_log.txt`、`admin/php.log`、`admin/php_error.log`、`admin/mysql_kugo_*.tmp`、`admin/new.html`、`admin/r_status.js`、layui/layer 的 `test.html` 和乱码 `.url` 文件。这些没有被主流程明确引用，但可能是宝塔排障、历史备份或第三方包文件。
- 本次确定删除文件：无。原因是无法 100% 证明上述文件没有被部署脚本、宝塔站点或人工排障依赖。

## 7. 宝塔前端部署建议

建议三个站点分开部署，避免用户端访问管理员页面：

```bash
# 示例变量，请替换为你的真实目录；不要把真实域名或密钥写进仓库。
ADMIN_ROOT=/www/wwwroot/koko-admin
ADMVIP_ROOT=/www/wwwroot/koko-admvip
USRVIP_ROOT=/www/wwwroot/koko-usrvip

rsync -av --delete admin/ "$ADMIN_ROOT/"
rsync -av --delete admvip/ "$ADMVIP_ROOT/"
rsync -av --delete usrvip/ "$USRVIP_ROOT/"
```

推荐 Nginx/宝塔：

- `admin`：独立后台域名，开启 IP 白名单、Basic Auth 或 SSO。
- `admvip`：独立管理员免码充值域名，同样不能公开给普通用户。
- `usrvip`：公开用户自助充值域名，只反代用户必要接口。
- 后端：只监听 `127.0.0.1:${APP_PORT}`，由 Nginx 按路径反代。

## 8. 人工确认事项

- 确认当前线上到底运行一个后端端口还是两个端口；新增 `server/app.py` 支持合并为一个 gunicorn 入口，但上线前应在预生产验证所有路径。
- 确认 `order_id.orderID` 和 `order_data_anj.orderID` 是否允许重复；如不允许，应先做重复数据报表，再人工加唯一索引。
- 确认 PHP 后台 `admin/db.php`、`admin/dbclass.php` 是否也含生产凭据；本次未重写 PHP 数据层，避免破坏现有宝塔站点。
- 确认管理员接口鉴权落地方式：短期建议 Nginx IP 白名单/Basic Auth；中期再让前端发送 `ADMIN_API_TOKEN`。
