# Koko 仓库扫描报告

生成日期：2026-06-03  
范围：`/workspace/koko` 全仓库静态扫描。  
说明：本报告仅记录扫描结论与重构建议，未修改业务代码。

## 1. 项目结构概览

```text
/workspace/koko
├── admin/                  # 管理端静态页 + PHP API + PHPMailer + 资金/设备监控脚本
│   ├── api.php             # PHP 后台查询/详情/拦截/手动成功接口
│   ├── db.php              # PHP PDO 数据库连接
│   ├── dbclass.php         # PHP mysqli 简易封装
│   ├── dev.php             # 设备状态/余额监控接口
│   ├── email.php           # 邮件通知脚本
│   ├── phpapi/             # 设备资金接口
│   ├── vendor/             # Composer 依赖，主要 PHPMailer
│   ├── layer/layui/jquery  # 前端库多份拷贝
│   └── *.html/*.js         # 管理端页面与脚本
├── admvip/                 # 另一套 VIP/后台页面
├── usrvip/                 # 用户端页面
├── server/
│   ├── kugo_mergedl.py     # 主 Flask 服务，端口 9999
│   └── app_optimized-cdp.py# Selenium/CDP 服务，端口 5000
└── kugo_structure_events.sql # MySQL 结构与事件 dump
```

技术栈判断：

- 后端 1：Python Flask，`server/kugo_mergedl.py` 定义主 app、CORS、数据库访问和多数业务接口。
- 后端 2：Python Flask + Selenium/CDP，`server/app_optimized-cdp.py` 负责验证码、提交、浏览器自动化相关接口。
- 后端 3：PHP，`admin/api.php`、`admin/phpapi/*.php`、`admin/dev.php` 等提供后台查询、设备余额、邮件等接口。
- 数据库：MySQL，结构 dump 在 `kugo_structure_events.sql`，核心表包括 `tel_data`、`user_data`、`order_id`、`order_data`、`order_data_anj`。

## 2. 接口清单

### 2.1 Python Flask：`server/kugo_mergedl.py`

| 路径 | 方法 | 主要用途 | 关键表/字段 |
|---|---:|---|---|
| `/` | GET | 健康/启动提示 | 无 |
| `/api` | POST | 统一提交入口，按 `type` 分支处理，如 `fasong` 等 | `tel_data.orderID` |
| `/getTelData` | GET | 获取待处理 tel 数据 | `tel_data` |
| `/getyzm` | GET | 获取验证码相关数据 | `tel_data` |
| `/getTel` | GET | 获取手机号 | `tel_data` |
| `/update_tel_status` | POST | 更新手机号状态，原始文本入参 | `tel_data` |
| `/getTelYzm` | GET | 获取手机号验证码 | `tel_data` |
| `/update_tel_statu3` | POST | 更新状态 3，注意路径拼写为 `statu3` | `tel_data` |
| `/update_r_status` | POST | 按 `id,r_status,pxtype,details` 更新充值结果 | `tel_data` |
| `/update_re_status` | POST | 按 `id,r_status,c_status,details` 更新结果/拦截 | `tel_data` |
| `/checkAndUpdateCStatus` | POST | 检查并更新 `c_status` | `tel_data` |
| `/update_run_status` | POST | 更新设备运行状态 | `run_status` |
| `/c_status` | POST | 查询 `c_status` | `tel_data` |
| `/img_updata` | POST | 更新图片记录，路径拼写为 `updata` | `img_data` |
| `/submituserinfo` | POST | 插入用户信息，返回 `record_id` | `user_data.order_id` |
| `/getUserStatus/<record_id>` | GET | 查询用户账号识别状态 | `user_data` |
| `/check_send_interval` | GET | 手机号发送验证码 30 秒限频 | `tel_data` |
| `/check_recharge_duplicate` | POST | 充值重复提交检查 | `user_data.order_id` / `tel_data.orderID` |
| `/get_recharge_status` | GET | 按手机号或兑换码查询进度 | `user_data.order_id` / `tel_data.orderID` |
| `/check_order_validity` | POST | 检查卡密是否可用 | `order_id.orderID,status` |
| `/lock_order` | POST | 锁定卡密为 `status=2` | `order_id.orderID` |
| `/unlock_order` | POST | 解锁卡密为 `status=1` | `order_id.orderID` |
| `/order_id_query` | GET | 按兑换码查最近 details | `tel_data.orderID` |
| `/extract_order_ids` | POST | 从库存提取多个卡密并标记 `getstatus=2` | `order_id` |
| `/extract_order` | POST | 从不同仓库提取卡密 | `order_id` |
| `/mark_order_used` | POST | 同步锁定/解锁 `order_id` 和 `order_data_anj` | `order_id` / `order_data_anj` |
| `/profit_stat` | POST | 按时间范围统计利润 | `order_data.llp,time` |
| `/submit_order` | POST | 生成卡密，写入 `order_id` 和 `order_data_anj` | `orderID` |
| `/uporderid_status` | POST | 重置卡密状态为 1 | `order_id` / `order_data_anj` |
| `/orderid_find` | GET | 按键精灵风格查询卡密状态 | `order_data_anj.orderID` |
| `/update_order_data` | POST | 按表单更新/插入订单数据 | `order_data_anj.orderID` |
| `/code_upload_batch` | POST | 批量上传券码 | `code_data` |
| `/code_fetch` | GET/POST | FIFO 获取一条未取券码 | `code_data` |

### 2.2 Python Flask：`server/app_optimized-cdp.py`

| 路径 | 方法 | 主要用途 | 关键表/字段 |
|---|---:|---|---|
| `/check_order_id` | GET | 检查 `orderID` 是否可用 | `order_id.orderID,status` |
| `/submit` | POST | 带幂等键的用户提交、锁单、写入 `user_data` | `submissions.order_id` / `user_data.order_id` / `order_id.orderID` |
| `/sfyzm` | POST | 发送验证码并插入 `tel_data` | `tel_data.orderID` |

### 2.3 PHP：`admin/api.php`

| 入口 | 方法 | 参数 | 主要用途 |
|---|---:|---|---|
| `api.php?action=search` | GET | `tel`、`page` | 查询 `tel_data`，若关键字是 11 位数字按手机号，否则按 `orderID` 查 |
| `api.php?action=getDetails` | GET | `id` | 查询详情、图片、账号信息 |
| `api.php?action=checkNewTasks` | GET | 无 | 获取最多 20 条待处理任务 |
| `api.php?action=check_and_update_c_status` | POST | JSON `{id}` | 检查并更新拦截状态 |
| `api.php?action=setManualSuccess` | POST | form `id` | 手动设置 `r_status=已成功` |

### 2.4 PHP：`admin/phpapi/*.php`

| 文件 | 方法 | 主要用途 |
|---|---:|---|
| `get_balances.php` | GET | 查询固定设备 `[157,178,188,198,208,308]` 的最新余额 |
| `transfer_in.php` | POST JSON | 给设备资金转入，写一条 `device_fund_details` |
| `transfer_out.php` | POST JSON | 给设备资金转出，写一条 `device_fund_details` |
| `fund_summary.php` | POST JSON | 按时间范围统计转入/转出汇总 |

## 3. 数据库表清单

来自 `kugo_structure_events.sql`，当前结构 dump 里共有 15 张表：

| 表 | 作用推断 | 关键字段 |
|---|---|---|
| `api_tokens` | API 访问令牌 | `token,type,status` |
| `code_data` | 券码 FIFO 队列 | `code,fetch_status,fetched_at` |
| `device_fund_details` | 设备资金流水 | `device_id,fund_in,manual_fund_out,auto_fund_out,balance` |
| `img_data` | 图片/截图记录 | `img_name,tel_id,status,cz_status,url` |
| `order_data` | 订单、利润、设备同步数据 | `orderID,status,type,xp,llp,czp,dev,processed` |
| `order_data_anj` | 另一份订单数据/按键精灵同步表 | `orderID,status,type,xp,processed` |
| `order_id` | 卡密库存/状态主表 | `orderID,status,type,xp,getstatus,91kami,adminkami` |
| `recharge_tasks` | 新版任务表雏形 | `task_no,account_identifier,plan_type,status,worker_id` |
| `run_status` | 设备运行心跳 | `dev,status,restart,create_date` |
| `submissions` | `/submit` 幂等记录 | `idempotency_key,order_id,response_json` |
| `task_batches` | 任务批次 | `batch_no,total_count,success_count` |
| `task_logs` | 任务日志 | `task_id,worker_id,action,content` |
| `tel_data` | 验证码/充值流程主流水 | `tel,yzm,orderID,status,r_status,c_status,details,userid,dev` |
| `user_data` | 用户提交与账号识别结果 | `phone,code,order_id,status,nickname1..3,userid1..3` |
| `workers` | 执行节点 | `worker_id,status,last_heartbeat_at,current_task_id` |

关键结构结论：

- `order_data` 使用 `orderID` 字段，并已有 `idx_orderID_time` 索引。
- `order_data_anj` 使用 `orderID`，但未看到 `orderID` 唯一索引。
- `order_id` 使用 `orderID`，但未看到 `orderID` 唯一索引。
- `submissions` 使用 snake_case 的 `order_id`。
- `tel_data` 使用 camelCase 的 `orderID`。
- `user_data` 使用 snake_case 的 `order_id`。

## 4. 无用文件/可清理候选清单

> 以下只是候选，不建议直接删除；需要先确认线上部署是否依赖这些路径。

### 4.1 高优先级清理候选

| 候选 | 原因 |
|---|---|
| `admin/php_error.log`、`admin/php.log`、`admin/error_log.txt` | 日志文件进入仓库，容易泄露路径、异常、敏感信息，也会造成无意义 diff |
| `admin/mysql_kugo_20260323085256.sql.90840890.upload.tmp` | 约 2MB 的临时 SQL 上传文件，文件名带 `.upload.tmp`，疑似误提交 |
| `admin/run_` | 0KB 文件，疑似临时/误生成 |
| `admin/mail_test.php` | 测试邮件脚本，若线上可访问会造成邮件滥发/凭据验证风险 |
| `admin/run_cron_auto_sync.bat`、`admin/run_php_script.bat` | Windows 批处理文件，是否仍用于生产需确认 |
| 多处 `layer-v3.5.1/test.html`、`layui-v2.11.2/test.html` | 第三方库测试页，通常不应部署到生产静态目录 |
| `usrvip/tencent5606972037306898132.txt` | 站点验证文件，若域名验证已完成可确认是否保留 |

### 4.2 重复静态库候选

仓库里存在多份 `jquery.min.js`、`layui.js`、`layer.js`、`layer.css`，分别散落在 `admin/`、`admvip/`、`usrvip/`，并且还同时保留完整 `layui-v2.11.2`、`layer-v3.5.1` 目录。建议后续统一为 `/assets/vendor/...` 或 CDN/构建产物，避免版本漂移。

## 5. Bug 风险清单

### P0 / 高风险

1. `orderID/order_id/orderid` 命名混用，已出现明确 SQL 风险。`tel_data` schema 字段是 `orderID`，但 `/check_recharge_duplicate` 在 `source == "tel"` 时查询的是 `tel_data.order_id`，这在当前 schema 中不存在。`/sfyzm` 插入 SQL 写的是小写 `orderid`，在默认 MySQL 大小写不敏感场景可能侥幸可用，但跨环境、工具、ORM 会埋雷。
2. 两套 Flask 服务存在职责重叠，接口命名相同或相近，部署路由容易混乱。
3. 锁单逻辑不完全一致，可能导致 `order_id` 与 `order_data_anj` 状态不同步。`/lock_order` 和 `/unlock_order` 只更新 `order_id`，但 `/mark_order_used` 同步更新 `order_id` 和 `order_data_anj`。
4. 库存提取接口可能并发重复提取。`/extract_order_ids` 先 `SELECT` 再 `UPDATE`，中间没有事务锁或 `FOR UPDATE`。
5. 资金转出允许余额变负。`transfer_out.php` 只校验 `amount > 0`，没有余额不足校验。

### P1 / 中风险

1. 数据库连接配置分散且密码不一致，Python 与 PHP 中多处硬编码连接参数。
2. 接口返回格式不统一，包括 JSON、纯字符串、`up_result=...` 等多种风格。
3. `profit_stat` 当前范围参数是白名单，但 SQL 使用字符串拼接，后续扩展容易引入注入。
4. 前端硬编码线上域名，`admin/list.js` 直接调用 `https://ka.k2n.cn/...`。
5. 表索引不足，`order_id.orderID`、`order_data_anj.orderID`、`tel_data.orderID`、`user_data.order_id` 均是高频查询字段，建议补索引或唯一约束。

## 6. 安全风险清单

### P0 / 高风险

1. 数据库密码、SMTP 授权码硬编码在仓库，应迁到环境变量或密钥管理。
2. 管理接口缺少认证/鉴权。例如 `/mark_order_used` 可直接改卡密状态，`/submit_order` 可生成卡密，`/code_upload_batch` 可批量写券码。
3. CORS 允许多个线上来源，但接口本身未配合 token/session 鉴权，会放大无鉴权管理接口风险。
4. 错误信息可能直接返回给客户端，容易泄露数据库、路径、SQL 或异常栈信息。

### P1 / 中风险

1. 日志和临时 SQL 文件被纳入仓库，通常包含路径、SQL、异常栈、业务数据甚至敏感信息。
2. 没有统一输入校验层，部分接口直接读取原始文本再按逗号拆分，对逗号、换行、编码、字段数量都脆弱。

## 7. 数据库 `order_id/orderID` 统一方案

### 7.1 当前混乱点

当前同时存在三类命名：

| 层级 | 当前命名 | 示例 |
|---|---|---|
| 表名 | `order_id` | 卡密库存表 |
| DB 字段 camelCase | `orderID` | `tel_data.orderID`、`order_id.orderID`、`order_data.orderID`、`order_data_anj.orderID` |
| DB/API 字段 snake_case | `order_id` | `user_data.order_id`、`submissions.order_id`、前端 `/submit` payload |

### 7.2 推荐统一原则

建议统一为：

- 数据库列名统一使用 `order_id`。
- API JSON 入参/出参统一使用 `order_id`。
- 前端 JS 变量逐步改为 `orderId`。
- 表名 `order_id` 短期保留，避免大范围迁移表名。

原因：

1. Python/PHP/JSON 生态更适合 snake_case。
2. 当前新表 `submissions`、`user_data` 已经使用 `order_id`。
3. `orderID` 在 PHP/JS 中大小写容易出错，当前已经出现 `orderid`/`orderID` 混写。

### 7.3 迁移路径建议

#### 第 0 阶段：冻结新增混写

- 新代码只允许使用 API 字段 `order_id`。
- 后端入口临时兼容读取：`data.get("order_id") or data.get("orderID") or data.get("orderid")`。
- 后端内部变量统一叫 `order_id`。
- SQL 暂时继续写旧列，避免立刻改表。

#### 第 1 阶段：增加兼容层或改列名

长期最干净的方案是直接改列名：

```sql
ALTER TABLE tel_data CHANGE orderID order_id VARCHAR(50);
ALTER TABLE order_id CHANGE orderID order_id VARCHAR(255);
ALTER TABLE order_data CHANGE orderID order_id VARCHAR(255);
ALTER TABLE order_data_anj CHANGE orderID order_id VARCHAR(255);
```

短期更安全的方案是保留旧列，但通过 DAO/Repository 屏蔽差异，例如：

- `find_order_by_order_id(order_id)`
- `lock_order(order_id)`
- `insert_tel_data(..., order_id=...)`
- `find_tel_by_order_id(order_id)`

所有 SQL 只在统一访问层里处理旧字段名。

#### 第 2 阶段：补索引/唯一约束

如果已经改列名，建议至少增加：

```sql
ALTER TABLE order_id ADD UNIQUE KEY uk_order_id_order_id (order_id);
ALTER TABLE order_data_anj ADD KEY idx_order_data_anj_order_id (order_id);
ALTER TABLE tel_data ADD KEY idx_tel_data_order_id_created (order_id, create_date);
ALTER TABLE user_data ADD KEY idx_user_data_order_id_created (order_id, create_date);
```

若暂时不改列名，则索引用 `orderID`。

#### 第 3 阶段：前端统一

- HTML input id 保持 `order_id` 可以。
- JS 变量统一 `orderId`。
- JSON payload 统一 `{ order_id: orderId }`。
- 废弃 `{ orderID: ... }`，但后端保留兼容一个版本。

## 8. 推荐重构计划

### 阶段 1：先止血，不改变业务行为

1. 建立 `.env` / 环境变量读取，移除代码内数据库密码和 SMTP 授权码。
2. 加 `.gitignore`，忽略日志、临时 SQL、缓存、上传临时文件。
3. 修复明显字段错误：`tel_data.order_id` → `tel_data.orderID` 或迁移后的 `order_id`，并统一 `orderid/orderID/order_id`。
4. 给危险管理接口加最小鉴权，例如 `Authorization: Bearer <admin token>`。
5. 给 `/extract_order_ids` 加事务和 `FOR UPDATE`，防并发重复提取。
6. 给 `transfer_out.php` 加余额不足校验。

### 阶段 2：统一数据访问

1. Python 新建 `server/db.py` 或 `server/repositories/order_repository.py`。
2. 把所有 `pymysql.connect(...)` 收敛到一个连接函数。
3. PHP 统一只用 `admin/db.php` 或统一 `DbClass`，不要 PDO/mysqli 混用。
4. 建立统一响应格式：`{ "success": true, "code": "OK", "message": "...", "data": {} }`。
5. 对所有接口做参数 schema 校验。

### 阶段 3：统一订单命名

1. 先做兼容层：API 只出 `order_id`，入参兼容 `orderID`。
2. 再做数据库迁移：`orderID` → `order_id`。
3. 增加索引/唯一约束。
4. 删除兼容分支和旧字段引用。

### 阶段 4：拆服务与前端资产整理

1. 明确两个 Flask 服务职责：`kugo_mergedl.py` 作为业务 API，`app_optimized-cdp.py` 作为浏览器自动化 worker。
2. 浏览器自动化不直接暴露公网，改成内部队列/任务消费。
3. 前端静态库统一到 `assets/vendor`。
4. 删除测试页、重复库、日志、临时 SQL。
5. 将 `admin/list.js` 中硬编码域名改成统一 `apiBase`。

### 阶段 5：测试与上线保障

1. 增加接口级 smoke tests。
2. 增加数据库迁移脚本和回滚脚本。
3. 增加并发锁单测试。
4. 增加资金余额不可负测试。
5. 增加日志脱敏与异常统一处理。

## 9. 本次扫描/检查命令

- `pwd && rg --files -g 'AGENTS.md' -g '!node_modules' -g '!vendor' -g '!dist' -g '!build'`
- `find .. -name AGENTS.md -print`
- `find . -maxdepth 2 -type f | sed 's#^./##' | sort | head -200`
- `find . -maxdepth 3 -type d -not -path './.git*' -not -path './node_modules*' | sed 's#^./##' | sort | head -200`
- `rg --files -g '!node_modules' -g '!vendor' -g '!dist' -g '!build' -g '!coverage'`
- `rg -n "@app\\.route" server/app_optimized-cdp.py server/kugo_mergedl.py`
- `rg -n "fetch\\(|\\$\\.ajax|ajax\\(|url:|api\\.php|phpapi|action=|/submit|/api|/admin/submit|order_id|orderID" ...`
- `python3 -m py_compile server/*.py`
- `php -l admin/api.php`
- `php -l admin/dev.php`
- `for f in admin/*.php admin/phpapi/*.php; do php -l "$f" >/dev/null || echo "PHP syntax fail: $f"; done`
- `git status --short`
