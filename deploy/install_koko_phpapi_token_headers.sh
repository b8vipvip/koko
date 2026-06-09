#!/usr/bin/env bash
set -euo pipefail

python3 <<'PY'
from pathlib import Path
import time

env_path = Path("/opt/koko/.env")
conf_path = Path("/www/server/panel/vhost/nginx/ka.k2n.cn.conf")
inc_path = Path("/www/server/panel/vhost/nginx/koko_php_admin_fastcgi.inc")

env = {}
for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

token = env.get("ADMIN_API_TOKEN", "")
if not token:
    raise SystemExit("ADMIN_API_TOKEN 为空")

inc_path.write_text(f'''# Auto generated on server. Do not commit this file.
fastcgi_param HTTP_X_ADMIN_TOKEN "{token}";
fastcgi_param HTTP_AUTHORIZATION "Bearer {token}";
fastcgi_param HTTP_X_REQUESTED_WITH "XMLHttpRequest";
''', encoding="utf-8")

s = conf_path.read_text(encoding="utf-8", errors="ignore")
bak = conf_path.with_suffix(conf_path.suffix + f".bak.phpapi_token.{int(time.time())}")
bak.write_text(s, encoding="utf-8")

block = r'''
    location = /phpapi/transfer_in.php {
        root /www/wwwroot/ka.k2n.cn;
        include /www/server/nginx/conf/fastcgi.conf;
        include /www/server/panel/vhost/nginx/koko_php_admin_fastcgi.inc;
        fastcgi_pass unix:/tmp/php-cgi-80.sock;
        fastcgi_index index.php;
    }

    location = /phpapi/transfer_out.php {
        root /www/wwwroot/ka.k2n.cn;
        include /www/server/nginx/conf/fastcgi.conf;
        include /www/server/panel/vhost/nginx/koko_php_admin_fastcgi.inc;
        fastcgi_pass unix:/tmp/php-cgi-80.sock;
        fastcgi_index index.php;
    }

'''

if "location = /phpapi/transfer_in.php" not in s:
    marker = "    location /getyzm"
    if marker in s:
        s = s.replace(marker, block + marker, 1)
    else:
        pos = s.rfind("}")
        if pos == -1:
            raise SystemExit("Nginx 配置缺少 server 结束括号")
        s = s[:pos] + block + s[pos:]
    conf_path.write_text(s, encoding="utf-8")

print("已处理 PHP API token fastcgi include")
PY

/www/server/nginx/sbin/nginx -t
/etc/init.d/nginx reload
