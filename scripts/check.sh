#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '[check] Python syntax check\n'
python -m py_compile server/app.py server/app_optimized-cdp.py server/kugo_mergedl.py worker/worker_client.py

printf '[check] requirements metadata check\n'
python - <<'PY'
from pathlib import Path
req = Path('requirements.txt')
assert req.exists(), 'requirements.txt missing'
needed = {'Flask', 'PyMySQL', 'python-dotenv', 'gunicorn'}
text = req.read_text()
missing = [pkg for pkg in needed if pkg not in text]
assert not missing, f'missing packages: {missing}'
print('requirements ok')
PY

printf '[check] Worker API deployment files scan\n'
python - <<'PYCHECK_WORKER_FILES'
from pathlib import Path
required = [
    Path('worker/worker_client.py'),
    Path('deploy/koko-worker.service'),
]
for path in required:
    assert path.exists(), f'{path} missing'
env_text = Path('.env.example').read_text()
for key in ['PUBLIC_API_BASE_URL', 'WORKER_API_TOKEN', 'WORKER_ID', 'WORKER_POLL_INTERVAL']:
    assert f'{key}=' in env_text, f'.env.example missing {key}'
print('worker files and env example ok')
PYCHECK_WORKER_FILES

printf '[check] Worker route protection scan\n'
python - <<'PYCHECK_WORKER_ROUTES'
from pathlib import Path
text = Path('server/kugo_mergedl.py').read_text()
for route in ['/api/worker/fetch', '/api/worker/report']:
    idx = text.find(route)
    if idx == -1:
        raise SystemExit(f'{route}: route not found')
    window = text[max(0, idx - 300):idx + 2500]
    if '@worker_required' not in window:
        raise SystemExit(f'{route}: missing @worker_required')
    if 'X-Worker-Token' not in text or 'WORKER_API_TOKEN' not in text:
        raise SystemExit(f'{route}: missing X-Worker-Token / WORKER_API_TOKEN handling')
print('worker route protection ok')
PYCHECK_WORKER_ROUTES

printf '[check] Hardcoded infrastructure secret/IP scan\n'
python - <<'PYCHECK_INFRA_SECRETS'
from pathlib import Path
import re
text_paths = []
for p in Path('.').rglob('*'):
    if not p.is_file() or '.git' in p.parts or 'vendor' in p.parts:
        continue
    if p.suffix.lower() in {'.py', '.php', '.js', '.html', '.sh', '.service', '.md', '.example', '.txt'} or p.name in {'.env.example', 'README.md'}:
        text_paths.append(p)
private_ip = re.compile(r'(?<![\d.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})(?![\d.])')
credential_assignment = re.compile(r'(?i)(?:token|password|passwd|pwd|secret)\s*[:=]\s*["\'](?!change-me)[^"\']{12,}["\']')
violations = []
for path in text_paths:
    try:
        content = path.read_text(errors='ignore')
    except Exception:
        continue
    for lineno, line in enumerate(content.splitlines(), 1):
        if private_ip.search(line):
            violations.append(f'{path}:{lineno}: private/server IP literal found')
        if credential_assignment.search(line):
            violations.append(f'{path}:{lineno}: suspicious hardcoded credential assignment')
if violations:
    raise SystemExit('\n'.join(violations))
print('no hardcoded domestic IP/token/database password patterns found')
PYCHECK_INFRA_SECRETS


printf '[check] SQL migration safety lint\n'
python - <<'PY'
from pathlib import Path
for path in Path('migrations').glob('*.sql'):
    sql = path.read_text().lower()
    forbidden = ['drop table', 'truncate table', 'delete from user_data', 'delete from order_id']
    bad = [token for token in forbidden if token in sql and '--' not in token]
    # DROP INDEX / DROP COLUMN rollback notes are comments; destructive table ops are not allowed.
    assert 'drop table' not in '\n'.join(line for line in sql.splitlines() if not line.strip().startswith('--')), path
    assert 'truncate table' not in sql, path
    print(f'{path}: safety lint ok')
PY



printf '[check] SQL schema presence and core table scan\n'
python - <<'PYSQLCHECK'
from pathlib import Path
import re
schema = Path('sql/koko_full_schema.sql')
migration = Path('migrations/001_normalize_redeem_code.sql')
assert schema.exists(), 'sql/koko_full_schema.sql missing'
assert migration.exists(), 'migrations/001_normalize_redeem_code.sql missing'
text = schema.read_text()
required_tables = [
    'api_tokens', 'code_data', 'device_fund_details', 'img_data', 'order_data',
    'order_data_anj', 'order_id', 'recharge_tasks', 'run_status', 'submissions',
    'task_batches', 'task_logs', 'tel_data', 'user_data', 'workers',
]
missing = [t for t in required_tables if not re.search(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?' + re.escape(t) + r'`?', text, re.I)]
assert not missing, f'full schema missing core tables: {missing}'
required_columns = {
    'order_id': ['orderID', 'redeem_code', 'status'],
    'order_data_anj': ['orderID', 'redeem_code', 'status'],
    'tel_data': ['tel', 'orderID', 'redeem_code', 'status', 'r_status', 'c_status', 'yzm_status', 'create_date', 'userid'],
    'user_data': ['phone', 'code', 'order_id', 'redeem_code', 'status', 'submitstatus', 'admin_override'],
    'submissions': ['idempotency_key', 'order_id', 'redeem_code', 'response_json'],
    'code_data': ['code', 'fetch_status', 'fetched_at'],
    'device_fund_details': ['device_id', 'balance', 'operation_time'],
}
for table, columns in required_columns.items():
    m = re.search(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?' + re.escape(table) + r'`?\s*\((.*?)\)\s*ENGINE=', text, re.I | re.S)
    assert m, f'{table}: table definition not found'
    body = m.group(1)
    absent = [c for c in columns if not re.search(r'`' + re.escape(c) + r'`', body)]
    assert not absent, f'{table}: missing columns {absent}'
print('SQL schema files and core tables ok')
PYSQLCHECK

printf '[check] Secret regression scan\n'
if rg -n 'password\s*=\s*["'"'"']HP77|user\s*=\s*["'"'"']kaaa|database\s*=\s*["'"'"']kaaa' server/*.py; then
  printf 'Hardcoded database credential regression found.\n' >&2
  exit 1
fi


printf '[check] PHP secret regression scan\n'
php_secret_pattern='HP77|HP77C|\bkaaa\b|smtp\.qq\.com|\$mail->Password\s*=|\$mail->Username\s*=|setFrom\(["'"'"'][^"'"'"']*@|addAddress\(["'"'"'][^"'"'"']*@'
if rg -n --glob '*.php' --glob '!vendor/**' "$php_secret_pattern" admin; then
  printf 'Hardcoded PHP database or SMTP secret regression found. Use admin/lib/config.php and admin/lib/mailer.php instead.\n' >&2
  exit 1
fi

printf '[check] PHP syntax check\n'
if command -v php >/dev/null 2>&1; then
  mapfile -t php_files < <(find admin -maxdepth 1 -type f -name '*.php' -print | sort)
  mapfile -t phpapi_files < <(find admin/phpapi -maxdepth 1 -type f -name '*.php' -print | sort)
  for file in "${php_files[@]}" "${phpapi_files[@]}"; do
    php -l "$file" >/dev/null
    printf '%s: syntax ok\n' "$file"
  done
else
  printf 'WARN: php command not found; skipped PHP syntax check\n' >&2
fi

printf '[check] Admin route protection scan\n'
python - <<'PY'
from pathlib import Path
text = Path('server/kugo_mergedl.py').read_text()
protected = [
    '/lock_order',
    '/unlock_order',
    '/extract_order_ids',
    '/extract_order',
    '/mark_order_used',
    '/submit_order',
    '/uporderid_status',
    '/code_upload_batch',
    '/code_fetch',
]
missing = []
for route in protected:
    marker = f"@app.route('{route}'"
    idx = text.find(marker)
    if idx == -1:
        missing.append(f'{route}: route not found')
        continue
    func_idx = text.find('def ', idx)
    block = text[idx:func_idx]
    if '@admin_required' not in block:
        missing.append(f'{route}: missing @admin_required')
if missing:
    raise SystemExit('\n'.join(missing))
print('admin route protection ok')
PY

printf '[check] CORS admin headers scan\n'
python - <<'PY'
from pathlib import Path
for path in [Path('server/kugo_mergedl.py'), Path('server/app_optimized-cdp.py')]:
    text = path.read_text()
    if 'X-Admin-Token' not in text or 'Authorization' not in text:
        raise SystemExit(f'{path}: CORS allow_headers missing X-Admin-Token/Authorization')
    print(f'{path}: CORS headers ok')
PY

printf '[check] Optional import smoke test (skipped unless RUN_IMPORT_SMOKE=1)\n'
if [[ "${RUN_IMPORT_SMOKE:-0}" == "1" ]]; then
  python - <<'PY'
import sys
sys.path.insert(0, 'server')
import app
print(app.app.name)
PY
else
  printf 'set RUN_IMPORT_SMOKE=1 on a configured host with DB/Chrome to import Flask app\n'
fi
