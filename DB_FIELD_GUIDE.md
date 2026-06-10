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

## 兑换码字段统一规则

兑换码语义字段统一使用：
- user_data.order_id
- tel_data.orderID
- order_id.orderID 或 order_id.order_id，按现有表结构兼容

注意：
- redeem_code 和 order_id 不是同一个语义
- 不要把 redeem_code 当成 order_id 兼容
- 不要新增 redeem_code 字段

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
