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
