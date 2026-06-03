#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '[check] Python syntax check\n'
python -m py_compile server/app.py server/app_optimized-cdp.py server/kugo_mergedl.py

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



printf '[check] SQL file presence and full schema table scan\n'
python - <<'PY'
from pathlib import Path
migration = Path('migrations/001_normalize_redeem_code.sql')
full_schema = Path('sql/koko_full_schema.sql')
if not migration.exists():
    raise SystemExit('missing migrations/001_normalize_redeem_code.sql')
if not full_schema.exists():
    raise SystemExit('missing sql/koko_full_schema.sql')
sql = full_schema.read_text().lower()
core_tables = [
    'api_tokens', 'code_data', 'device_fund_details', 'img_data',
    'order_data', 'order_data_anj', 'order_id', 'recharge_tasks',
    'run_status', 'submissions', 'task_batches', 'task_logs',
    'tel_data', 'user_data', 'workers',
]
missing = [table for table in core_tables if f'create table if not exists `{table}`' not in sql and f'create table `{table}`' not in sql]
if missing:
    raise SystemExit('full schema missing core tables: ' + ', '.join(missing))
print('SQL files and core tables ok')
PY

printf '[check] Secret regression scan\n'
if rg -n 'password\s*=\s*["'"'"']HP77|user\s*=\s*["'"'"']kaaa|database\s*=\s*["'"'"']kaaa' server/*.py; then
  printf 'Hardcoded database credential regression found.\n' >&2
  exit 1
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


printf '[check] PHP sensitive config regression scan\n'
php_sensitive_files=$(find admin -path 'admin/vendor' -prune -o -type f -name '*.php' ! -path 'admin/lib/mailer.php' ! -path 'admin/lib/config.php' -print)
if [ -n "$php_sensitive_files" ] && rg -n 'HP77C?|kaaa|smtp\.qq\.com|\$mail->Password\s*=|\$mail->Username\s*=|setFrom\(["'"'"'][^"'"'"'$]|addAddress\(["'"'"'][^"'"'"'$]' $php_sensitive_files; then
  printf 'Hardcoded PHP secret or duplicate SMTP configuration found.\n' >&2
  exit 1
fi

printf '[check] PHP syntax check\n'
if command -v php >/dev/null 2>&1; then
  php_files=$(find admin -path 'admin/vendor' -prune -o -type f -name '*.php' -print)
  for file in $php_files; do
    php -l "$file" >/dev/null
  done
  printf 'PHP syntax ok\n'
else
  printf 'WARN: php command not found; skipping PHP syntax check\n'
fi

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
