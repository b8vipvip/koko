# cn12.vip / US01 部署说明

US01 不直接运行 Koko Python 后端，而是通过 SSH 反向隧道访问 134 国内服务器。

## 隧道端口约定

在 134.175.188.6 上运行 koko-us01-tunnel.service：

- US01 127.0.0.1:18000 -> 134.175.188.6 127.0.0.1:5000
- US01 127.0.0.1:19999 -> 134.175.188.6 127.0.0.1:9999
- US01 127.0.0.1:13306 -> 134.175.188.6 127.0.0.1:3306

## cn12.vip Nginx 分流

- /submit、/sfyzm 等 Selenium 相关接口 -> 127.0.0.1:18000
- /api、/check_order_validity、/check_recharge_duplicate、/check_send_interval、/get_recharge_status 等后端接口 -> 127.0.0.1:19999

## 注意

不要让旧服务器 106.53.164.35 再占用 US01 的 18000/13306。
US01 上可以保留 sshd Match Address 封禁旧 IP 的配置。
