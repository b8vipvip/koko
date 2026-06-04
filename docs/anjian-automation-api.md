# 按键精灵 / 自动化客户端接入 API

本文档说明国内按键精灵或其他自动化客户端如何通过后端 API 领取 `tel_data` 充值任务、回传状态并发送心跳。当前生产主链路仍然是 `tel_data` 队列表 + 按键精灵；不要启动或依赖 `worker/worker_client.py`。

## 安全与部署

- 旧接口和 `/api/anj/*` 新接口都支持请求头：`X-Worker-Token: <WORKER_API_TOKEN>`。
- 为兼容按键精灵，旧接口也支持 URL 参数：`?token=<WORKER_API_TOKEN>`。
- `WORKER_API_TOKEN` 从后端 `.env` 读取；如果配置了该变量，token 错误返回 HTTP `401`。如果未配置，则兼容旧环境不强制鉴权。
- 日志只记录手机号尾号、兑换码尾号，不记录完整手机号、验证码或兑换码。
- 国内 API 只监听 `127.0.0.1:8000` 或隧道本地端口，通过 107 反向 SSH 隧道/Nginx 提供入口；不要开放国内公网 `8000`。
- 107 Nginx 需要把 `/getTelData`、`/update_run_status`、`/update_re_status`、`/api`、`/api/` 反代到后端，例如隧道入口 `http://127.0.0.1:18000`。
- 按键精灵不要直连 MySQL，只能访问本 API。

## 状态流转

推荐状态流转：

```text
等待 → 准备登录 → webdl/appdl/正在充值 → 充值成功/失败/超时
```

后端领取任务时会把 `tel_data` 从：

```text
status='1', yzm_status='3', r_status IN ('等待','准备登录')
```

原子更新为：

```text
status='2', r_status='准备登录', c_status='1'
```

## 旧按键精灵接口（优先兼容现有脚本）

### 1. 旧领取任务：GET /getTelData

按键精灵原调用：

```text
uget = Url.Get("https://ka.k2n.cn/getTelData?token=xxx")
```

curl 测试：

```bash
curl -X GET 'http://127.0.0.1:8000/getTelData?token=xxx'
```

返回纯文本逗号拼接字符串，字段顺序固定：

```text
tel,yzm,zhanghu,huiyuanguize,lingqu3,shougong,qdzhb,applogin,weblog,init,id,c_status,orderID
```

示例：

```text
18589922052,134483,zh1,0,1,0,0,1,1,0,106093,1,4peqirtdcj1149
```

没有任务时返回空字符串。

### 2. 旧心跳：POST /update_run_status

按键精灵原调用：

```text
post数据 = dev
返回值 = Url.Post("https://ka.k2n.cn/update_run_status?token=xxx", post数据)
```

curl 测试：

```bash
curl -X POST 'http://127.0.0.1:8000/update_run_status?token=xxx' \
  --data-binary 'anj-cn-01'
```

成功返回纯文本：

```text
ok
```

失败返回：

```text
error: xxx
```

### 3. 旧回传结果：POST /update_re_status

按键精灵原调用：

```text
detail = CStr(details) & "," & CStr(手机号) & "," & CStr(验证码) & "," & CStr(多账户) & "," & CStr(pxtype) & "," & CStr(GetNetworkTime()) & ",设备:" & code & ",订单号:" & oid
post数据 = id & "," & r_status & "," & c_status & "," & detail
返回值 = Url.Post("https://ka.k2n.cn/update_re_status?token=xxx", post数据)
```

curl 测试：

```bash
curl -X POST 'http://127.0.0.1:8000/update_re_status?token=xxx' \
  --data-binary '106093,充值成功,2,完成,18589922052,134483,zh1,pxtype1,2026-06-04 12:00:00,设备:anj-cn-01,订单号:4peqirtdcj1149'
```

后端只按前 3 个逗号切分，`detail` 内部可以继续包含逗号。成功返回纯文本：

```text
ok
```

失败返回：

```text
error: xxx
```

## JSON 新接口（可选）

### 1. 领取任务：POST /api/anj/claim

```bash
curl -X POST http://127.0.0.1:8000/api/anj/claim \
  -H "Content-Type: application/json" \
  -H "X-Worker-Token: xxx" \
  -d '{"worker_id":"anj-cn-01"}'
```

没有任务时返回：

```json
{"success": true, "task": null, "message": "暂无任务"}
```

### 2. 回传状态：POST /api/anj/report

```bash
curl -X POST http://127.0.0.1:8000/api/anj/report \
  -H "Content-Type: application/json" \
  -H "X-Worker-Token: xxx" \
  -d '{"id":106093,"worker_id":"anj-cn-01","r_status":"充值成功","c_status":"2","details":"完成"}'
```

说明：

- 必须传 `id`，只允许按 `tel_data.id` 更新当前任务，不支持按手机号批量更新。
- 可更新字段：`r_status`、`c_status`、`details`、`pxtype`、`userid`、`status`。
- 成功类 `r_status`：`充值成功`、`成功`、`已成功`、`手动成功`，后端强制 `c_status='2'`、`status='2'`。
- 失败/结束类 `r_status`：`失败`、`无效订单`、`重复订单`、`验证码失效`、`验证错`、`超时`、`已拦截`，后端强制 `c_status='2'`、`status='2'`。
- 运行中 `r_status`：`准备登录`、`webdl`、`appdl`、`登录成功`、`正在充值`、`充值中`，后端强制 `status='2'`，`c_status` 保持传入值或默认 `1`。

### 3. 心跳：POST /api/anj/heartbeat

```bash
curl -X POST http://127.0.0.1:8000/api/anj/heartbeat \
  -H "Content-Type: application/json" \
  -H "X-Worker-Token: xxx" \
  -d '{"worker_id":"anj-cn-01","status":"online"}'
```

### 4. 查询单条任务：GET /api/anj/task/<id>

```bash
curl -X GET http://127.0.0.1:8000/api/anj/task/106093 \
  -H "X-Worker-Token: xxx"
```

## 按键精灵 URL 怎么改

如果只方便改 URL，不方便改请求体，建议只追加 `token` 参数：

```text
https://ka.k2n.cn/getTelData?token=xxx
https://ka.k2n.cn/update_run_status?token=xxx
https://ka.k2n.cn/update_re_status?token=xxx
```

请求体仍保持原来的纯文本格式即可。

## 数据库迁移

如果生产库已经包含以下字段和表，一般不需要额外迁移：

- `tel_data.redeem_code`、`tel_data.details`、`tel_data.pxtype`、`tel_data.userid`、`tel_data.dev`
- `user_data.redeem_code`
- `run_status.dev` 可保存按键精灵设备名（建议 `varchar(64)`）
- `workers`（可选，用于同步心跳）

如旧库缺字段、索引，或 `run_status.dev` 还是 `int` 无法保存 `anj-cn-01` 这类设备名，请在备份并完成测试库验证后执行安全迁移：

```bash
mysql -u <user> -p <database> < migrations/002_anj_api_compatibility.sql
```

该 migration 使用 MySQL 5.7 兼容的 `INFORMATION_SCHEMA` 检查，只新增缺失字段/表/索引、把 `run_status.dev` 改为 `varchar(64)` 并回填 `redeem_code`，不会删除、清空或覆盖生产数据。
