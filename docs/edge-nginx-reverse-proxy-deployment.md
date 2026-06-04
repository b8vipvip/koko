# 107 边缘 Nginx 反向代理部署说明

本文档描述当前小流量部署适配后的浏览器访问链路：

```text
用户浏览器 → 107 边缘 Nginx / 公网域名 → 国内服务器 API
```

> 注意：仓库文档和前端代码不写入真实公网 IP、国内服务器 IP、数据库密码或 token。生产环境的真实地址只应配置在 Nginx、systemd 环境变量、`.env` 或机密管理系统中，并确保这些文件不提交到仓库。

## 架构要求

- `admin`、`admvip`、`usrvip` 前端文件部署在 107 边缘 Nginx 对外提供的站点下。
- 国内服务器 API 不直接暴露给用户浏览器；由 107 边缘 Nginx 按路径反向代理到国内服务器。
- 前端 JavaScript 必须使用当前域名下的同源相对路径发起 API 请求，不允许写死国内服务器 IP、国内服务器域名、旧域名或固定 API 域名。
- 如果管理端后续确实需要独立 API 前缀，也应集中放在文件顶部常量中，默认值保持为空字符串，生产差异通过 Nginx 路由或非仓库配置处理。

## 前端 API 路径规范

用户端请求应保持为相对路径，例如：

- `/submit`
- `/sfyzm`
- `/check_order_validity`
- `/check_send_interval`
- `/api/task/status`

`usrvip/index.html` 中的 API helper 应保持同源相对路径：

```js
const API_BASE = "";

function api(path) {
  return path;
}
```

管理端如需配置前缀，默认也应使用空字符串：

```js
const ADMIN_API_BASE = "";

function adminApi(path) {
  return ADMIN_API_BASE + path;
}
```

## Nginx 路由建议

107 边缘 Nginx 负责两类请求：

1. 静态文件 / PHP 管理页面：直接从站点目录或 PHP-FPM 提供。
2. API 路径：通过 `proxy_pass` 反向代理到国内服务器 API。

示例路径包括但不限于：

- `/submit`
- `/sfyzm`
- `/check_order_validity`
- `/check_send_interval`
- `/check_recharge_duplicate`
- `/get_recharge_status`
- `/api/`
- `/api.php`
- `/mark_order_used`

请在生产 Nginx 配置中填写真实 upstream；不要把真实 upstream 地址提交到仓库。

## 上线检查

上线前运行：

```bash
bash scripts/check.sh
```

其中的前端反代检查会阻止以下回归：

- `usrvip`、`admin`、`admvip` 中再次出现旧 API 域名 `https://s.k2n.cn`。
- 前端文件写死 IP 字面量。
- `fetch("http://...cn")`、`fetch("https://...cn")` 或 `fetch("http://IP")` 这类绝对地址请求。
- `$.ajax({ url: "http://...cn" })` 或 `$.ajax({ url: "http://IP" })` 这类绝对地址请求。
