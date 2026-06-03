# Koko 数据库兼容性与初始化说明

## 结论

当前新版 Python 后端与 PHP 后端仍然可以兼容旧数据库，但旧库必须至少补齐新版代码已经引用的字段、表和索引。推荐做法不是换库，而是在旧库上执行安全迁移：`migrations/001_normalize_redeem_code.sql`。

本次核查后同时提供两类 SQL：

1. `migrations/001_normalize_redeem_code.sql`：旧数据库安全升级使用。
2. `sql/koko_full_schema.sql`：全新服务器或全新数据库初始化使用。

## 旧数据库升级

旧数据库升级应执行：

```bash
mysql -u <user> -p <database> < migrations/001_normalize_redeem_code.sql
```

执行前必须先做 `mysqldump` 备份，例如：

```bash
mysqldump --single-transaction --routines --events --databases <database> > koko_backup_$(date +%F_%H%M%S).sql
```

建议流程：

1. 在生产库执行前，先把生产备份恢复到测试库。
2. 在测试库执行 `migrations/001_normalize_redeem_code.sql`。
3. 启动新版 Python 后端和 PHP 后端做提交、提码、充值、资金查询等主流程验证。
4. 低峰期在生产库执行同一份 SQL。

该迁移不会删除旧数据，不会删除生产表，也不会清空生产表。它会新增 `redeem_code` 规范字段，保留旧代码仍在使用的 `orderID` / `order_id` 字段，并补齐新版后端需要的新表、字段和索引。

## 全新部署

全新部署或空数据库初始化应执行：

```bash
mysql -u <user> -p <database> < sql/koko_full_schema.sql
```

`sql/koko_full_schema.sql` 是完整空 schema，不包含真实手机号、真实兑换码、真实 token、真实邮箱或真实密码。它包含新版 Python 后端与 PHP 后端会访问的表，包括：

- `api_tokens`
- `code_data`
- `device_fund_details`
- `img_data`
- `order_data`
- `order_data_anj`
- `order_id`
- `recharge_tasks`
- `run_status`
- `submissions`
- `task_batches`
- `task_logs`
- `tel_data`
- `user_data`
- `workers`

## 哪些 SQL 不可重复执行

- `sql/koko_full_schema.sql`：只建议用于空库/新库初始化。虽然表定义使用 `CREATE TABLE IF NOT EXISTS`，但它不会把已有旧表自动改造成最新版结构，因此不要把它当成旧库迁移脚本反复执行。
- `migrations/001_normalize_redeem_code.sql`：内部使用 `INFORMATION_SCHEMA` 做了字段和索引存在性检查，重复执行通常不会重复加同名字段/索引；但生产变更仍应按“一次变更窗口执行一次并记录”的方式管理，避免在业务高峰反复触发 DDL。

## 迁移失败如何回滚

MySQL 的 `ALTER TABLE`、`CREATE INDEX` 等 DDL 会隐式提交，因此不能依赖普通事务完整回滚迁移。推荐回滚方式：

1. 立即停止新版后端写入，避免旧代码和新代码继续写出不一致数据。
2. 如果迁移尚未进入生产业务写入，优先使用升级前的 `mysqldump` 备份恢复：

   ```bash
   mysql -u <user> -p <database> < koko_backup_<timestamp>.sql
   ```

3. 如果必须保留迁移期间产生的新业务数据，需要先导出新增业务数据，再在测试库演练“备份恢复 + 数据补录/重放”。
4. 不建议在生产库盲目手工删除新增字段或索引；只有确认新版后端尚未依赖 `redeem_code` 写入时，才可在测试验证后手工移除新增列/索引。

## 兼容性细节

### redeem_code 与旧字段关系

新版推荐统一使用 `redeem_code` 表示兑换码/充值码。但为兼容旧 Python/PHP 代码，数据库中继续保留：

- `order_id.orderID`
- `order_data.orderID`
- `order_data_anj.orderID`
- `tel_data.orderID`
- `user_data.order_id`
- `submissions.order_id`

字段关系如下：

- `orderID` / `order_id` 是旧接口和当前部分代码仍在读写的字段。
- `redeem_code` 是规范字段，迁移时会从旧字段回填。
- 在兼容窗口内，应保持同一行的旧字段与 `redeem_code` 值一致。

### 旧库必须补齐的点

如果旧库缺少以下内容，新版后端会出现字段不存在或表不存在错误，必须通过迁移补齐：

- `user_data.admin_override`：管理员直提接口会写入该字段。
- `user_data.submitstatus`：强一致充值提交流程会读取并更新该字段。
- `submissions`：幂等提交记录表。
- `code_data.fetch_status`、`code_data.fetched_at`：优惠券 FIFO 上传/提取接口使用。
- `tel_data.email_sent`：邮件告警脚本使用。
- `tel_data.userid`：充值提交时用于记录选中的酷狗用户 ID。
- `device_fund_details`：PHP 资金进出与余额接口使用。
- `api_tokens`、`task_batches`、`recharge_tasks`、`task_logs`、`workers`：任务化后端结构使用。

### 是否仍兼容旧数据库

结论：仍兼容，但不是“零迁移兼容”。

- 如果旧库已经包含旧版核心表，执行 `migrations/001_normalize_redeem_code.sql` 后可以继续使用旧库，不需要强制换库。
- 如果旧库缺字段或缺新表，必须新增字段/索引/表；这些变更都是非破坏性的，不删除旧数据。
- 如果长期希望完全脱离旧字段，可以后续逐步让代码只读写 `redeem_code`，但当前全量 schema 仍保留旧字段以保护 PHP 后端和历史脚本。
