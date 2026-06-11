#!/usr/bin/env bash
set -euo pipefail

python3 <<'PY'
from pathlib import Path
import re
import time

env_path = Path("/opt/koko/.env")
conf_path = Path("/www/server/panel/vhost/nginx/ka.k2n.cn.conf")
inc_path = Path("/www/server/panel/vhost/nginx/koko_backend_admin_headers.inc")

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
proxy_set_header X-Admin-Token "{token}";
proxy_set_header Authorization "Bearer {token}";
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
''', encoding="utf-8")

s = conf_path.read_text(encoding="utf-8", errors="ignore")
bak = conf_path.with_suffix(conf_path.suffix + f".bak.backend_token.{int(time.time())}")
bak.write_text(s, encoding="utf-8")

include_line = "        include /www/server/panel/vhost/nginx/koko_backend_admin_headers.inc;\n"

def ensure_location(path):
    global s

    one_line = rf'location\s+{re.escape(path)}\s*\{{\s*proxy_pass\s+http://127\.0\.0\.1:9999;\s*\}}'
    repl = (
        f'location {path} {{\n'
        f'{include_line}'
        f'        proxy_pass http://127.0.0.1:9999;\n'
        f'        proxy_set_header Host $host;\n'
        f'        proxy_set_header X-Real-IP $remote_addr;\n'
        f'    }}'
    )
    new_s, count = re.subn(one_line, repl, s)
    if count:
        s = new_s
        return

    block_re = re.compile(rf'(location\s+{re.escape(path)}\s*\{{)(.*?)(\n\s*\}})', re.S)
    m = block_re.search(s)
    if m:
        head, body, tail = m.group(1), m.group(2), m.group(3)
        if "koko_backend_admin_headers.inc" not in body:
            body = re.sub(r'(\n\s*proxy_pass\s+)', "\n" + include_line + r"\1", body, count=1)
            s = s[:m.start()] + head + body + tail + s[m.end():]
        return

    insert_block = "\n    " + repl.replace("\n", "\n    ") + "\n"
    marker = "    location /check_order_id"
    if marker in s:
        s = s.replace(marker, insert_block + "\n" + marker, 1)
    else:
        pos = s.rfind("}")
        if pos == -1:
            raise SystemExit("Nginx 配置缺少 server 结束括号")
        s = s[:pos] + insert_block + s[pos:]

for path in ["/extract_order", "/extract_order_ids", "/admin/agent/list"]:
    ensure_location(path)

conf_path.write_text(s, encoding="utf-8")
print("已处理后端接口 token header")
PY

/www/server/nginx/sbin/nginx -t
/etc/init.d/nginx reload
