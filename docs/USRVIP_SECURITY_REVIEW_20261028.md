# /usrvip 安全审查与分阶段上线说明（2026-10-28）

## 现阶段结论

本站不是酷狗官方登录页。生产前端要求手机号、短信验证码和兑换码；
`server/app_optimized-cdp.py` 的 `process_user_record` 把验证码输入
`https://m3ws.kugou.com/loginReg.php` 对应的短信登录页。
因此这不是单纯的“手机号验证”。**不得通过视觉包装把该流程表现成官方或无风险的身份认证。**

本分支仅包含减少误操作和敏感信息泄露的防御性修复，**不代表此登录流程已安全**。
应优先改为酷狗正式授权/合作接口，或完全不接触酷狗登录短信验证码的兑换机制。

## 本分支已做（防御性修复）

- 取消输入框填写完整、粘贴或失焦时自动触发 /submit；仅显式点击提交。
- 弹层不再承诺“30 秒后确认”，准确提示等待真实结果。
- 动态账号昵称、用户 ID 进行 HTML 编码；第三方头像 URL 不直接注入 DOM。
- 移除无法核实的“验证码仅用于手机号验证”说明及仓库中不存在的
  `/privacy.html`、`/terms.html` 链接，改为真实的第三方验证码风险告知。
- 未认证 `/get_recharge_status` 只返回公开的最小状态字段；不再返回
  验证码、完整手机号、兑换码、用户头像/ID、内部记录 ID。
- 两条核对错误响应不再回显手机号、短信验证码；删除公开状态路由的原始记录/账号/响应日志。

**兼容性提醒：** 旧版“刷新后凭手机号/兑换码恢复账号选择”依赖无身份校验地回传验证码和账号信息。
这一不安全能力被有意关闭；刷新后的处理请从原提交会话继续，或联系人工核对。
若要安全恢复，需要实现带授权、到期和防重放的订单查询凭证，不能恢复公开的敏感信息字段。

## 剩余 P0 / P1

- P0：使用官方授权机制替代输入酷狗短信登录验证码的网页表单。
- P0：所有提交、记录查询与 worker API 做逐项鉴权与最小权限审计。
- P0：公开进度路由仍可用手机号/兑换码查询任务存在与处理状态；
  需设计不可枚举、短期、授权绑定的订单查询 token 和服务端限速。
- P1：移除其他页面和任务流中的原始验证码保存、过度日志与不必要长期保留。
- P1：把多个“虚拟充值进度条/倒计时”脚本改为仅使用服务端真实状态的单一状态组件。
- P1：编写真实、可访问的隐私政策与用户协议，明确主体、运营方、验证码用途、
  数据存储期限、第三方传输、售后和删除申请渠道；不得凭空写官方合作关系。
- P1：完成移动端无障碍、成功/失败/超时/网络故障场景的回归。

## 部署风险：用户上传的 redeploy_koko_to_opt.sh

该文件主要在**国内服务器**重建 `/opt/koko` 后端和同步 admin/admvip，
并没有独立部署 US01 的 `/usrvip` 站点。故不能只执行它就假定 cn12.vip 已更新。

尚需专门审核的行为：
1. 先停止服务，再备份/移动目录并重新 clone；失败后可能中断服务。
2. `EXIT` trap 无论成功失败都调用 `restore_runtime_state`；
   若 guard 还原了源码，会覆盖刚拉取的新版。
3. 对 `/www/wwwroot/ka.k2n.cn` 使用 `rsync --delete`，
   但仓库文档说明该目录可能映射到 `/opt/koko/admin`，
   必须先核对 inode、真实路径和 mount。
4. Composer 安装两次，可能修改依赖；systemd 服务以 root 运行；
   后置的 `/root/install_koko_*.sh` 无版本固定、需要独立审核。
5. 后端切换和 US01 Nginx/SSH 隧道属于不同部署层，不应在未验证前一起更改。

**此分支未运行生产部署脚本，也没有连接任何服务器。**

## 不改变生产状态的预检

在国内服务器执行（需有相应权限）：

```bash
hostname
git -C /opt/koko rev-parse HEAD
git -C /opt/koko status --short
readlink -f /opt/koko/admin
readlink -f /www/wwwroot/ka.k2n.cn
findmnt -T /www/wwwroot/ka.k2n.cn
systemctl status koko-backend koko-selenium koko-us01-tunnel --no-pager
```

使用已有的 SSH 连接信息（这里的 `US01` **仅为占位别名**；先检查 SSH 配置），对 US01 执行只读检查：

```bash
ssh US01 'hostname; sudo nginx -T 2>/dev/null | grep -n -A35 -B8 "server_name cn12.vip"'
ssh US01 'sudo ss -lntp | grep -E ":(18000|19999|13306)[[:space:]]" || true'
```

只有查到 CN12 的**实际静态站点根目录**且确认没有符号链接/挂载覆盖风险，
才在修复分支合并、完成正式授权改造和测试后，为静态前端使用
`rsync -a --dry-run --checksum` 演练，备份旧文件、复制新文件、
核对 sha256/HTTP 响应，再决定是否切换；US01 的静态前端更新一般不需要重启国内 Selenium。

后端更新必须另行先备份 `/opt/koko/server/kugo_mergedl.py`，
完成 Python 语法检查和配置差异检查，再由运维在维护窗口逐步重启
`koko-backend` 并验证国内端口、隧道和真实业务状态；失败时按备份回滚。

回归检测（无需连接真实平台）：
```bash
python3 -m unittest discover -s tests -p test_usrvip_security_contract.py
```
